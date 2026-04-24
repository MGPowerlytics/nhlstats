from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError

from tests.contracts.fixtures.mlb_schedule_samples import (
    build_mlb_games_row,
    build_mlb_unified_games_row,
)
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"


def _load_schema(filename: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / filename).read_text(encoding="utf-8"))


def test_mlb_games_row_schema_defines_canonical_contract() -> None:
    """The MLB-owned mlb_games row schema freezes the persisted shape."""
    schema = _load_schema("mlb_mlb_games_row_v1.json")

    assert schema["title"] == "MLB mlb_games Row Contract"
    assert schema["required"] == [
        "game_id",
        "game_date",
        "season",
        "game_type",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "status",
    ]


def test_unified_mlb_row_schema_defines_canonical_contract() -> None:
    """The shared-storage MLB subset stays explicit and MLB-bounded."""
    schema = _load_schema("mlb_unified_game_row_v1.json")

    assert schema["title"] == "MLB unified_games Row Contract"
    assert schema["properties"]["sport"]["const"] == "MLB"


def test_canonical_mlb_games_row_satisfies_contract() -> None:
    """A canonical MLB row validates against the frozen mlb_games schema."""
    validate_contract_payload(
        build_mlb_games_row(),
        _load_schema("mlb_mlb_games_row_v1.json"),
    )


def test_canonical_unified_mlb_row_satisfies_contract() -> None:
    """A canonical shared-storage MLB row validates against the unified_games schema."""
    validate_contract_payload(
        build_mlb_unified_games_row(),
        _load_schema("mlb_unified_game_row_v1.json"),
    )


def test_unified_mlb_row_rejects_non_mlb_sport_label() -> None:
    """unified_games sport label must remain locked to MLB."""
    row = build_mlb_unified_games_row()
    row["sport"] = "NHL"

    with pytest.raises(ValidationError):
        validate_contract_payload(row, _load_schema("mlb_unified_game_row_v1.json"))


def test_canonical_mlb_games_row_allows_null_scores_for_pregame() -> None:
    """Pre-game persisted rows must carry NULL scores per loader hygiene rules."""
    row = build_mlb_games_row(home_score=None, away_score=None, status="Preview")

    validate_contract_payload(row, _load_schema("mlb_mlb_games_row_v1.json"))


@pytest.mark.parametrize(
    ("filename", "builder", "missing_field"),
    [
        ("mlb_mlb_games_row_v1.json", build_mlb_games_row, "game_id"),
        ("mlb_mlb_games_row_v1.json", build_mlb_games_row, "home_team"),
        ("mlb_mlb_games_row_v1.json", build_mlb_games_row, "game_type"),
        ("mlb_mlb_games_row_v1.json", build_mlb_games_row, "status"),
        ("mlb_unified_game_row_v1.json", build_mlb_unified_games_row, "game_id"),
        ("mlb_unified_game_row_v1.json", build_mlb_unified_games_row, "home_team_name"),
        ("mlb_unified_game_row_v1.json", build_mlb_unified_games_row, "sport"),
    ],
)
def test_persisted_mlb_row_contracts_reject_missing_required_fields(
    filename: str,
    builder: Any,
    missing_field: str,
) -> None:
    """Missing persisted MLB fields fail fast as row-shape drift."""
    row = builder()
    row.pop(missing_field)

    with pytest.raises(ValidationError):
        validate_contract_payload(row, _load_schema(filename))


def test_unified_mlb_game_id_pattern_locks_to_native_gamepk() -> None:
    """unified_games.game_id for MLB stays the native gamePk integer string."""
    row = build_mlb_unified_games_row(game_id="not-a-gamepk")

    with pytest.raises(ValidationError):
        validate_contract_payload(row, _load_schema("mlb_unified_game_row_v1.json"))


@pytest.mark.parametrize("invalid_game_type", ["S", "E", "A", "X", ""])
def test_mlb_games_row_rejects_excluded_or_unknown_game_types(invalid_game_type: str) -> None:
    """mlb_games row must reject any gameType filtered at the loader."""
    row = build_mlb_games_row(game_type=invalid_game_type)

    with pytest.raises(ValidationError):
        validate_contract_payload(row, _load_schema("mlb_mlb_games_row_v1.json"))
