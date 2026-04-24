from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from plugins.kalshi_markets import (
    GameParseData,
    _determine_outcome_name,
    _extract_outcome_side_from_ticker,
    _generate_game_id,
    _parse_market,
    _upsert_odds,
)
from tests.contracts.fixtures.epl_kalshi_samples import (
    build_epl_kalshi_game_odds_row,
    build_epl_kalshi_normalized_market,
    build_epl_kalshi_raw_market,
)

CONTRACT_PATH = Path(__file__).parent / "schemas" / "epl_kalshi_market_v1.json"


class RecordingDBManager:
    """Capture DB execute payloads without touching a real database."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def execute(self, _query: str, params: dict[str, Any]) -> None:
        self.calls.append(dict(params))


@pytest.fixture(scope="module")
def kalshi_contract() -> dict[str, Any]:
    """Load the canonical EPL Kalshi consumer contract."""
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _validate_definition(
    contract: dict[str, Any], definition: str, payload: dict[str, Any]
) -> None:
    schema = {
        "$schema": contract["$schema"],
        "$ref": f"#/$defs/{definition}",
        "$defs": contract["$defs"],
    }
    Draft202012Validator(schema).validate(payload)


def _assert_draw_suffix_contract(ticker: str, outcome_name: str, odds_id: str | None = None) -> None:
    suffix = ticker.rsplit("-", 1)[-1].upper()
    if suffix in {"DRAW", "TIE"}:
        assert outcome_name == "draw"
        if odds_id is not None:
            assert odds_id.endswith("_draw")


def test_canonical_normalized_market_fixture_matches_contract(
    kalshi_contract: dict[str, Any],
) -> None:
    _validate_definition(
        kalshi_contract,
        "normalized_market",
        build_epl_kalshi_normalized_market(),
    )


def test_canonical_game_odds_fixture_matches_contract(
    kalshi_contract: dict[str, Any],
) -> None:
    _validate_definition(
        kalshi_contract,
        "game_odds_row",
        build_epl_kalshi_game_odds_row(),
    )


@pytest.mark.parametrize("suffix", ["DRAW", "TIE"])
def test_current_outcome_mapping_must_treat_draw_and_tie_suffixes_as_draw(
    suffix: str,
) -> None:
    market = build_epl_kalshi_raw_market(outcome_suffix=suffix)

    assert (
        _determine_outcome_name(
            _extract_outcome_side_from_ticker(market["ticker"]) or "",
            "Liverpool",
            "Bournemouth",
        )
        == "draw"
    )


def test_current_ticker_parser_must_stably_map_market_to_canonical_game() -> None:
    market = build_epl_kalshi_raw_market()
    parsed = _parse_market(market["ticker"], market["title"], "epl")

    assert parsed is not None
    assert parsed.home_team == "Liverpool"
    assert parsed.away_team == "Bournemouth"
    assert parsed.game_date == "2025-08-16"


def test_current_game_id_generation_must_match_contract_safe_mapping() -> None:
    assert (
        _generate_game_id("epl", "2025-08-16", "Liverpool", "Bournemouth")
        == build_epl_kalshi_normalized_market()["game_id"]
    )


def test_current_draw_market_persistence_payload_must_match_contract(
    kalshi_contract: dict[str, Any],
) -> None:
    market = build_epl_kalshi_raw_market()
    db_manager = RecordingDBManager()
    game_id = build_epl_kalshi_normalized_market()["game_id"]

    inserted = _upsert_odds(
        db_manager=db_manager,
        game_id=game_id,
        market=market,
        game_data=GameParseData(
            sport="epl",
            home_team="Liverpool",
            away_team="Bournemouth",
            game_date="2025-08-16",
            ticker=market["ticker"],
            title=market["title"],
        ),
    )

    assert inserted is True
    assert db_manager.calls

    persisted_row = {
        "odds_id": db_manager.calls[-1]["odds_id"],
        "game_id": db_manager.calls[-1]["game_id"],
        "bookmaker": "Kalshi",
        "market_name": "moneyline",
        "outcome_name": db_manager.calls[-1]["outcome_name"],
        "price": db_manager.calls[-1]["price"],
        "is_pregame": True,
        "external_id": db_manager.calls[-1]["ticker"],
    }

    _assert_draw_suffix_contract(
        persisted_row["external_id"],
        persisted_row["outcome_name"],
        persisted_row["odds_id"],
    )
    _validate_definition(kalshi_contract, "game_odds_row", persisted_row)


def test_contract_is_limited_to_epl_kalshi_boundary(
    kalshi_contract: dict[str, Any],
) -> None:
    invalid_payload = {
        **build_epl_kalshi_normalized_market(),
        "sport": "NHL",
    }

    with pytest.raises(Exception):
        _validate_definition(kalshi_contract, "normalized_market", invalid_payload)
