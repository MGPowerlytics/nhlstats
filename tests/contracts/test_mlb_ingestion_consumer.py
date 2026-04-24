from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from tests.contracts.fixtures.mlb_schedule_samples import (
    build_mlb_excluded_game_types,
    build_mlb_schedule_game,
)
from tests.contracts.helpers import validate_contract_payload


SCHEMA_PATH = (
    Path(__file__).resolve().parent / "schemas" / "mlb_schedule_ingestion_v1.json"
)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_mlb_schedule_ingestion_schema_defines_canonical_contract() -> None:
    """MLB schedule ingestion schema freezes the required producer fields."""
    schema = _load_schema()

    assert schema["title"] == "MLB Schedule Ingestion Contract v1"
    schedule_game = schema["$defs"]["schedule_game"]
    assert schedule_game["required"] == [
        "gamePk",
        "gameDate",
        "gameType",
        "season",
        "officialDate",
        "status",
        "teams",
    ]
    assert set(schema["$defs"]["game_type"]["enum"]) == {"R", "F", "D", "L", "W"}


def test_canonical_mlb_schedule_game_satisfies_contract() -> None:
    """A canonical MLB Stats API schedule record validates against the schema."""
    validate_contract_payload(build_mlb_schedule_game(), _load_schema())


@pytest.mark.parametrize(
    "missing_field",
    ["gamePk", "gameDate", "gameType", "season", "officialDate", "status", "teams"],
)
def test_mlb_schedule_contract_rejects_missing_required_fields(missing_field: str) -> None:
    """Missing producer-side fields fail fast as ingestion drift."""
    game = build_mlb_schedule_game()
    game.pop(missing_field)

    with pytest.raises(ValidationError):
        validate_contract_payload(game, _load_schema())


@pytest.mark.parametrize("excluded_game_type", build_mlb_excluded_game_types())
def test_mlb_schedule_contract_rejects_spring_training_and_exhibition_game_types(
    excluded_game_type: str,
) -> None:
    """Spring training (S), exhibition (E) and All-Star (A) games are not ingested."""
    game = build_mlb_schedule_game(gameType=excluded_game_type)

    with pytest.raises(ValidationError):
        validate_contract_payload(game, _load_schema())


def test_mlb_schedule_contract_requires_team_id_and_name_for_both_sides() -> None:
    """Both home and away team blocks must carry the producer-supplied id and name."""
    game = build_mlb_schedule_game()
    game["teams"]["home"]["team"].pop("id")

    with pytest.raises(ValidationError):
        validate_contract_payload(game, _load_schema())


def test_mlb_schedule_contract_allows_null_score_for_unplayed_games() -> None:
    """Pre-game schedule entries with null scores remain contract-valid."""
    game = build_mlb_schedule_game()
    game["status"]["abstractGameState"] = "Preview"
    game["status"]["detailedState"] = "Scheduled"
    game["teams"]["home"]["score"] = None
    game["teams"]["away"]["score"] = None

    validate_contract_payload(game, _load_schema())


def test_mlb_schedule_contract_pinned_to_known_abstract_game_states() -> None:
    """abstractGameState is constrained to MLB Stats API canonical values."""
    schema = _load_schema()

    assert set(schema["$defs"]["abstract_game_state"]["enum"]) == {
        "Preview",
        "Live",
        "Final",
    }
