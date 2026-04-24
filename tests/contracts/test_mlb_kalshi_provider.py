"""Wave-3 provider-red contract tests for the MLB Kalshi pipeline.

Exercises the real producer code paths in :mod:`plugins.kalshi_markets`:

* ``fetch_mlb_markets`` — verifies the live HTTP fetcher returns market dicts
  whose downstream parse/normalize output matches ``mlb_kalshi_market_v1``.
* ``_parse_mlb_teams`` — covers both compact-team splits ``(2, 3)`` and
  ``(3, 2)`` against realistic Kalshi titles.
* ``_determine_outcome_name`` — exposes the known 3-char-last-name vs
  franchise-code drift on home-side tickers (xfail, fixed in Wave 4-6).
* ``save_to_db`` — captures persisted ``game_odds`` rows and validates them
  against the frozen ``game_odds_row`` definition.
"""

from __future__ import annotations

from typing import Any

import pytest

import plugins.database_schema_manager as database_schema_manager
import plugins.kalshi_markets as kalshi_markets
from plugins.kalshi_markets import (
    GameParseData,
    StandardTickerParser,
    _calculate_decimal_odds,
    _determine_outcome_name,
    _extract_outcome_side_from_ticker,
    _generate_game_id,
    _parse_market,
    _resolve_names,
    _upsert_odds,
    fetch_mlb_markets,
)
from tests.contracts.fixtures.mlb_kalshi_provider_samples import (
    build_mlb_kalshi_home_side_market,
    build_mlb_kalshi_two_three_split_market,
)
from tests.contracts.fixtures.mlb_kalshi_samples import (
    build_mlb_kalshi_game_odds_row,
    build_mlb_kalshi_normalized_market,
    build_mlb_kalshi_raw_market,
)
from tests.contracts.helpers import (
    find_execute_params,
    load_versioned_schema,  # noqa: F401  (re-exported for any future xfail use)
    validate_contract_payload,
)


# ---------------------------------------------------------------------------
# Recording / schema-skip fakes (mirrors the EPL provider test pattern)
# ---------------------------------------------------------------------------


class RecordingDBManager:
    """Capture DB writes without touching PostgreSQL."""

    def __init__(self) -> None:
        self.calls: list[Any] = []

    def execute(self, query: str, params: dict[str, Any]) -> None:
        # Mirror the (sql, params) call shape used by the EPL helper so
        # ``find_execute_params`` works against ``self.calls``.
        self.calls.append(_FakeExecuteCall(query, dict(params)))

    def fetch_scalar(self, query: str, params: dict[str, Any]) -> Any:
        # No prior MLB schedule row exists in this provider test, so the
        # native gamePk reconciliation path returns None and the synthetic
        # game_id flows through to ``_upsert_odds``.
        return None


class _FakeExecuteCall:
    """Mimic ``unittest.mock.call`` so helpers.find_execute_params works."""

    def __init__(self, sql: str, params: dict[str, Any]) -> None:
        self.args = (sql, params)


class NoOpSchemaManager:
    """Skip schema initialisation during provider contract tests."""

    def __init__(self, _db_manager: RecordingDBManager) -> None:
        pass

    def initialize_schema(self) -> None:
        return None


def _kalshi_contract() -> dict[str, Any]:
    import json
    from pathlib import Path

    schema_path = (
        Path(__file__).resolve().parent / "schemas" / "mlb_kalshi_market_v1.json"
    )
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _validate_def(payload: dict[str, Any], definition: str) -> None:
    contract = _kalshi_contract()
    schema = {
        "$schema": contract["$schema"],
        "$ref": f"#/$defs/{definition}",
        "$defs": contract["$defs"],
    }
    validate_contract_payload(payload, schema)


def _build_provider_normalized_market(market: dict[str, Any]) -> dict[str, Any]:
    parsed = _parse_market(market["ticker"], market["title"], "mlb")
    assert parsed is not None, f"parser must handle {market['ticker']}"
    if not parsed.game_date:
        parsed.game_date = market["close_time"].split("T")[0]

    canon_home, canon_away = _resolve_names(parsed)
    outcome_side = _extract_outcome_side_from_ticker(market["ticker"]) or ""

    return {
        "schema_version": "v1",
        "sport": "MLB",
        "payload_kind": "kalshi_market",
        "market_id": market["ticker"],
        "ticker": market["ticker"],
        "game_id": _generate_game_id("mlb", parsed.game_date, canon_home, canon_away),
        "game_date": parsed.game_date,
        "home_team": canon_home,
        "away_team": canon_away,
        "outcome_name": _determine_outcome_name(outcome_side, canon_home, canon_away),
        "bookmaker": "Kalshi",
        "market_name": "moneyline",
        "external_id": market["ticker"],
        "price": _calculate_decimal_odds(market["yes_ask"]),
        "is_pregame": True,
    }


# ---------------------------------------------------------------------------
# fetch_mlb_markets — real producer path with HTTP/auth stubbed at the seam
# ---------------------------------------------------------------------------


def test_fetch_mlb_markets_provider_output_matches_frozen_normalized_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real fetcher emits markets whose normalized form satisfies the contract."""
    market = build_mlb_kalshi_raw_market()  # away-side LAD ticker

    class FakeKalshiAPI:
        def get_markets(self, *, series_ticker: str, limit: int) -> dict[str, Any]:
            assert series_ticker == "KXMLBGAME"
            return {"markets": [market]}

        def get_market(self, ticker: str) -> dict[str, Any]:
            assert ticker == market["ticker"]
            return {
                "ticker": ticker,
                "market_id": ticker,
                "title": market["title"],
                "yes_ask": market["yes_ask"],
                "close_time": market["close_time"],
            }

    monkeypatch.setattr(kalshi_markets, "KALSHI_AVAILABLE", True)
    monkeypatch.setattr(kalshi_markets, "load_kalshi_credentials", lambda: ("k", "p"))
    monkeypatch.setattr(kalshi_markets, "KalshiAPI", lambda *_: FakeKalshiAPI())
    monkeypatch.setattr(kalshi_markets, "save_to_db", lambda sport, mks: len(mks))

    fetched = fetch_mlb_markets()
    assert fetched == [market]

    normalized = _build_provider_normalized_market(fetched[0])
    _validate_def(normalized, "normalized_market")
    assert normalized == build_mlb_kalshi_normalized_market(outcome_name="away")


# ---------------------------------------------------------------------------
# _parse_mlb_teams — both compact-team splits with non-trivial titles
# ---------------------------------------------------------------------------


def test_parse_mlb_teams_three_two_split_resolves_franchise_codes() -> None:
    """LADSF / 'Dodgers at Giants' must resolve via the (3, 2) split."""
    parser = StandardTickerParser("mlb")
    result = parser._parse_mlb_teams(
        "LADSF", "Los Angeles Dodgers at San Francisco Giants"
    )
    assert result == ("San Francisco Giants", "Los Angeles Dodgers")


def test_parse_mlb_teams_two_three_split_resolves_franchise_codes() -> None:
    """SFLAD / 'Giants at Dodgers' must resolve via the (2, 3) split."""
    parser = StandardTickerParser("mlb")
    result = parser._parse_mlb_teams(
        "SFLAD", "San Francisco Giants at Los Angeles Dodgers"
    )
    assert result == ("Los Angeles Dodgers", "San Francisco Giants")


def test_parse_mlb_teams_six_char_split_uses_three_three_legacy_path() -> None:
    """Six-char compact teams fall through to the legacy 3+3 split."""
    parser = StandardTickerParser("mlb")
    # Non-MLB six-char tickers use the standard path; verify via _parse_teams.
    result = parser._parse_teams("NYYBOS", "New York Yankees at Boston Red Sox")
    # In the six-char path the parser does NOT resolve via NamingResolver,
    # it returns the raw 3-char codes — keep the assertion strict to catch
    # any future regression that quietly rewires the path.
    assert result == ("BOS", "NYY")


# ---------------------------------------------------------------------------
# _determine_outcome_name — known drift on franchise-code home tickers
# ---------------------------------------------------------------------------


def test_determine_outcome_name_correctly_classifies_away_franchise_code() -> None:
    """Away-side LAD ticker must classify as 'away' (already green)."""
    assert (
        _determine_outcome_name("LAD", "San Francisco Giants", "Los Angeles Dodgers")
        == "away"
    )


def test_determine_outcome_name_classifies_home_side_franchise_code() -> None:
    """Home-side SF ticker should classify as 'home' but the producer returns 'away'."""
    assert (
        _determine_outcome_name("SF", "San Francisco Giants", "Los Angeles Dodgers")
        == "home"
    )


# ---------------------------------------------------------------------------
# save_to_db — real persistence path against frozen game_odds_row contract
# ---------------------------------------------------------------------------


def test_save_to_db_emits_contract_valid_game_odds_row_for_away_market(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Away-side persistence params must satisfy the frozen game_odds_row contract."""
    monkeypatch.setattr(
        database_schema_manager, "DatabaseSchemaManager", NoOpSchemaManager
    )

    db_manager = RecordingDBManager()
    market = build_mlb_kalshi_raw_market()  # LAD (away)

    saved = kalshi_markets.save_to_db("mlb", [market], db_manager=db_manager)
    assert saved == 1

    odds_rows = find_execute_params(db_manager.calls, "game_odds")
    assert len(odds_rows) == 1

    row = odds_rows[0]
    expected = build_mlb_kalshi_game_odds_row(outcome_name="away")

    payload = {
        "odds_id": row["odds_id"],
        "game_id": row["game_id"],
        "bookmaker": "Kalshi",
        "market_name": "moneyline",
        "outcome_name": row["outcome_name"],
        "price": row["price"],
        "is_pregame": True,
        "external_id": row["ticker"],
    }
    _validate_def(payload, "game_odds_row")
    assert payload["odds_id"] == expected["odds_id"]
    assert payload["external_id"] == expected["external_id"]


def test_save_to_db_persists_home_side_market_as_kalshi_home_odds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Home-side SF ticker must persist with outcome_name='home' and matching odds_id."""
    monkeypatch.setattr(
        database_schema_manager, "DatabaseSchemaManager", NoOpSchemaManager
    )

    db_manager = RecordingDBManager()
    market = build_mlb_kalshi_home_side_market()

    saved = kalshi_markets.save_to_db("mlb", [market], db_manager=db_manager)
    assert saved == 1

    odds_rows = find_execute_params(db_manager.calls, "game_odds")
    assert len(odds_rows) == 1

    row = odds_rows[0]
    assert row["outcome_name"] == "home"
    assert row["odds_id"].endswith("_kalshi_home")


def test_save_to_db_persists_two_three_split_market_with_resolved_teams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A (2, 3) compact split (e.g., SFLAD) must persist using resolved franchise names."""
    monkeypatch.setattr(
        database_schema_manager, "DatabaseSchemaManager", NoOpSchemaManager
    )

    db_manager = RecordingDBManager()
    market = build_mlb_kalshi_two_three_split_market()

    saved = kalshi_markets.save_to_db("mlb", [market], db_manager=db_manager)
    assert saved == 1

    unified_rows = find_execute_params(db_manager.calls, "unified_games")
    assert unified_rows, "Expected a unified_games write"
    unified = unified_rows[0]
    assert unified["home_name"] == "Los Angeles Dodgers"
    assert unified["away_name"] == "San Francisco Giants"


# ---------------------------------------------------------------------------
# _upsert_odds — direct producer call ensures odds_id pattern stays stable
# ---------------------------------------------------------------------------


def test_upsert_odds_for_canonical_away_market_persists_contract_valid_row() -> None:
    """Direct ``_upsert_odds`` invocation must emit a contract-valid game_odds row."""
    db_manager = RecordingDBManager()
    market = build_mlb_kalshi_raw_market()
    game_id = build_mlb_kalshi_normalized_market(outcome_name="away")["game_id"]

    inserted = _upsert_odds(
        db_manager=db_manager,
        game_id=game_id,
        market=market,
        game_data=GameParseData(
            sport="mlb",
            home_team="San Francisco Giants",
            away_team="Los Angeles Dodgers",
            game_date="2024-04-21",
            ticker=market["ticker"],
            title=market["title"],
        ),
    )

    assert inserted is True
    odds_rows = find_execute_params(db_manager.calls, "game_odds")
    assert len(odds_rows) == 1

    row = odds_rows[0]
    payload = {
        "odds_id": row["odds_id"],
        "game_id": row["game_id"],
        "bookmaker": "Kalshi",
        "market_name": "moneyline",
        "outcome_name": row["outcome_name"],
        "price": row["price"],
        "is_pregame": True,
        "external_id": row["ticker"],
    }
    _validate_def(payload, "game_odds_row")
    assert row["odds_id"].endswith("_kalshi_away")
