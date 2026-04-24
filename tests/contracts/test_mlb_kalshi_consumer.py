from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from plugins.kalshi_markets import (
    GameParseData,
    _determine_outcome_name,
    _extract_outcome_side_from_ticker,
    _generate_game_id,
    _parse_market,
    _upsert_odds,
)
from tests.contracts.fixtures.mlb_kalshi_samples import (
    build_mlb_kalshi_game_odds_row,
    build_mlb_kalshi_normalized_market,
    build_mlb_kalshi_raw_market,
)


CONTRACT_PATH = Path(__file__).parent / "schemas" / "mlb_kalshi_market_v1.json"


class RecordingDBManager:
    """Capture DB execute payloads without touching a real database."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def execute(self, _query: str, params: dict[str, Any]) -> None:
        self.calls.append(dict(params))


@pytest.fixture(scope="module")
def kalshi_contract() -> dict[str, Any]:
    """Load the canonical MLB Kalshi consumer contract."""
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


def test_canonical_normalized_market_fixture_matches_contract(
    kalshi_contract: dict[str, Any],
) -> None:
    _validate_definition(
        kalshi_contract,
        "normalized_market",
        build_mlb_kalshi_normalized_market(),
    )


def test_canonical_game_odds_fixture_matches_contract(
    kalshi_contract: dict[str, Any],
) -> None:
    _validate_definition(
        kalshi_contract,
        "game_odds_row",
        build_mlb_kalshi_game_odds_row(),
    )


def test_current_ticker_parser_must_stably_map_market_to_canonical_game() -> None:
    market = build_mlb_kalshi_raw_market()
    parsed = _parse_market(market["ticker"], market["title"], "mlb")

    assert parsed is not None
    assert parsed.home_team == "San Francisco Giants"
    assert parsed.away_team == "Los Angeles Dodgers"
    assert parsed.game_date == "2024-04-21"


def test_current_game_id_generation_must_match_contract_safe_mapping() -> None:
    assert (
        _generate_game_id(
            "mlb", "2024-04-21", "San Francisco Giants", "Los Angeles Dodgers"
        )
        == build_mlb_kalshi_normalized_market()["game_id"]
    )


def test_current_outcome_extraction_must_recover_team_code_suffix() -> None:
    market = build_mlb_kalshi_raw_market()
    outcome_side = _extract_outcome_side_from_ticker(market["ticker"])

    assert outcome_side == "LAD"
    assert (
        _determine_outcome_name(outcome_side, "San Francisco Giants", "Los Angeles Dodgers")
        == "away"
    )


def test_current_away_market_persistence_payload_must_match_contract(
    kalshi_contract: dict[str, Any],
) -> None:
    market = build_mlb_kalshi_raw_market()
    db_manager = RecordingDBManager()
    game_id = build_mlb_kalshi_normalized_market()["game_id"]

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

    _validate_definition(kalshi_contract, "game_odds_row", persisted_row)
    assert persisted_row["outcome_name"] == "away"
    assert persisted_row["odds_id"].endswith("_kalshi_away")


def test_contract_is_limited_to_mlb_kalshi_boundary(
    kalshi_contract: dict[str, Any],
) -> None:
    invalid_payload = {
        **build_mlb_kalshi_normalized_market(),
        "sport": "EPL",
    }

    with pytest.raises(Exception):
        _validate_definition(kalshi_contract, "normalized_market", invalid_payload)


def test_contract_rejects_draw_outcome_for_mlb_two_way_market(
    kalshi_contract: dict[str, Any],
) -> None:
    invalid_payload = build_mlb_kalshi_normalized_market(outcome_name="away")
    invalid_payload["outcome_name"] = "draw"

    with pytest.raises(ValidationError):
        _validate_definition(kalshi_contract, "normalized_market", invalid_payload)
