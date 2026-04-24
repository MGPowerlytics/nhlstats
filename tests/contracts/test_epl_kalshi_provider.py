from __future__ import annotations

from typing import Any

import pytest

import plugins.database_schema_manager as database_schema_manager
import plugins.kalshi_markets as kalshi_markets
from plugins.kalshi_markets import (
    _calculate_decimal_odds,
    _determine_outcome_name,
    _extract_outcome_side_from_ticker,
    _generate_game_id,
    _parse_market,
    _resolve_names,
    fetch_epl_markets,
    save_to_db,
)
from tests.contracts.fixtures.epl_kalshi_samples import (
    build_epl_kalshi_game_odds_row,
    build_epl_kalshi_normalized_market,
    build_epl_kalshi_provider_market,
    build_epl_kalshi_raw_market,
)


class RecordingDBManager:
    """Capture DB writes without touching PostgreSQL."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def execute(self, query: str, params: dict[str, Any]) -> None:
        self.calls.append({"query": query, "params": dict(params)})


class NoOpSchemaManager:
    """Skip schema initialization during provider contract tests."""

    def __init__(self, _db_manager: RecordingDBManager) -> None:
        pass

    def initialize_schema(self) -> None:
        return None


def _find_call(db_manager: RecordingDBManager, table_name: str) -> dict[str, Any]:
    for call in db_manager.calls:
        if f"INSERT INTO {table_name}" in call["query"]:
            return call
    raise AssertionError(f"Expected a write into {table_name}.")


def _build_provider_normalized_market(market: dict[str, Any]) -> dict[str, Any]:
    parsed = _parse_market(market["ticker"], market["title"], "epl")

    assert parsed is not None
    if not parsed.game_date:
        parsed.game_date = market["close_time"].split("T")[0]

    canon_home, canon_away = _resolve_names(parsed)
    outcome_side = _extract_outcome_side_from_ticker(market["ticker"]) or ""

    return {
        "schema_version": "v1",
        "sport": "EPL",
        "payload_kind": "kalshi_market",
        "market_id": market["ticker"],
        "ticker": market["ticker"],
        "game_id": _generate_game_id("epl", parsed.game_date, canon_home, canon_away),
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


def test_fetch_epl_markets_provider_output_matches_frozen_normalized_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    market = build_epl_kalshi_provider_market(outcome_suffix="DRAW")

    class FakeKalshiAPI:
        def get_markets(self, *, series_ticker: str, limit: int) -> dict[str, Any]:
            assert series_ticker == "KXEPLGAME"
            assert limit == 200
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
    monkeypatch.setattr(kalshi_markets, "load_kalshi_credentials", lambda: ("key", "pem"))
    monkeypatch.setattr(kalshi_markets, "KalshiAPI", lambda *_: FakeKalshiAPI())
    monkeypatch.setattr(kalshi_markets, "save_to_db", lambda sport, markets: len(markets))

    fetched_markets = fetch_epl_markets()

    assert fetched_markets == [market]
    assert _build_provider_normalized_market(
        fetched_markets[0]
    ) == build_epl_kalshi_normalized_market()


def test_fetch_epl_markets_exposes_contract_invalid_tie_suffix_before_save(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    market = build_epl_kalshi_raw_market(outcome_suffix="TIE")

    class FakeKalshiAPI:
        def get_markets(self, *, series_ticker: str, limit: int) -> dict[str, Any]:
            assert series_ticker == "KXEPLGAME"
            assert limit == 200
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
    monkeypatch.setattr(kalshi_markets, "load_kalshi_credentials", lambda: ("key", "pem"))
    monkeypatch.setattr(kalshi_markets, "KalshiAPI", lambda *_: FakeKalshiAPI())
    monkeypatch.setattr(kalshi_markets, "save_to_db", lambda sport, markets: len(markets))

    fetched_markets = fetch_epl_markets()

    assert fetched_markets == [market]
    assert _parse_market(fetched_markets[0]["ticker"], fetched_markets[0]["title"], "epl") is not None


def test_save_to_db_surfaces_tie_persistence_drift_in_game_odds_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_manager = RecordingDBManager()
    market = build_epl_kalshi_provider_market(outcome_suffix="TIE")

    monkeypatch.setattr(
        database_schema_manager, "DatabaseSchemaManager", NoOpSchemaManager
    )

    saved = save_to_db("epl", [market], db_manager=db_manager)

    assert saved == 1
    odds_params = _find_call(db_manager, "game_odds")["params"]
    assert odds_params["outcome_name"] == build_epl_kalshi_game_odds_row()["outcome_name"]
    assert odds_params["odds_id"].endswith("_draw")


def test_save_to_db_surfaces_unstable_epl_game_mapping_before_green_fix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_manager = RecordingDBManager()
    market = build_epl_kalshi_provider_market(outcome_suffix="DRAW")

    monkeypatch.setattr(
        database_schema_manager, "DatabaseSchemaManager", NoOpSchemaManager
    )

    saved = save_to_db("epl", [market], db_manager=db_manager)

    assert saved == 1
    unified_params = _find_call(db_manager, "unified_games")["params"]

    assert unified_params["game_id"] == build_epl_kalshi_normalized_market()["game_id"]
