from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest
from jsonschema import ValidationError

from plugins.csv_processors import EPLCSVProcessor
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"


def _load_schema(filename: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / filename).read_text(encoding="utf-8"))


def _build_canonical_epl_games_row() -> dict[str, Any]:
    return {
        "game_id": "EPL_20250816_MANCHESTERCITY_TOTTENHAMHOTSPUR",
        "game_date": "2025-08-16",
        "season": "2526",
        "home_team": "Man City",
        "away_team": "Tottenham",
        "home_score": 2,
        "away_score": 1,
        "result": "H",
    }


def _build_canonical_unified_games_row() -> dict[str, Any]:
    return {
        "game_id": "EPL_20250816_MANCHESTERCITY_TOTTENHAMHOTSPUR",
        "sport": "EPL",
        "game_date": "2025-08-16",
        "season": 2025,
        "status": "Final",
        "home_team_name": "Manchester City",
        "away_team_name": "Tottenham Hotspur",
        "home_score": 2,
        "away_score": 1,
    }


def _build_current_processor_rows() -> tuple[dict[str, Any], dict[str, Any]]:
    processor = EPLCSVProcessor(MagicMock())
    row = pd.Series(
        {
            "Date": "2025-08-16",
            "HomeTeam": "Manchester City",
            "AwayTeam": "Tottenham Hotspur",
            "FTHG": 2,
            "FTAG": 1,
            "FTR": "H",
        }
    )

    processor.process_row(row, season_code="2526")

    epl_params = processor.db.execute.call_args_list[0].args[1]
    unified_params = processor.db.execute.call_args_list[1].args[1]

    return (
        {
            "game_id": epl_params["game_id"],
            "game_date": epl_params["game_date"],
            "season": epl_params["season"],
            "home_team": epl_params["home_team"],
            "away_team": epl_params["away_team"],
            "home_score": epl_params["home_score"],
            "away_score": epl_params["away_score"],
            "result": epl_params["result"],
        },
        {
            "game_id": unified_params["game_id"],
            "sport": unified_params["sport_upper"],
            "game_date": unified_params["game_date"],
            "season": unified_params["season_year"],
            "status": "Final",
            "home_team_name": unified_params.get("home_team_name", unified_params["home_team"]),
            "away_team_name": unified_params.get("away_team_name", unified_params["away_team"]),
            "home_score": unified_params["home_score"],
            "away_score": unified_params["away_score"],
        },
    )


def test_epl_games_row_schema_defines_canonical_contract() -> None:
    """The EPL-owned epl_games row schema freezes the required persisted shape."""
    schema = _load_schema("epl_epl_games_row_v1.json")

    assert schema["title"] == "EPL epl_games Row Contract"
    assert schema["required"] == [
        "game_id",
        "game_date",
        "season",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "result",
    ]


def test_unified_games_row_schema_defines_canonical_contract() -> None:
    """The shared-storage subset stays explicit and EPL-bounded."""
    schema = _load_schema("epl_unified_game_row_v1.json")

    assert schema["title"] == "EPL unified_games Row Contract"
    assert schema["properties"]["sport"]["const"] == "EPL"
    assert schema["properties"]["status"]["const"] == "Final"


def test_canonical_epl_games_row_satisfies_contract() -> None:
    """A canonical EPL row validates against the frozen epl_games schema."""
    validate_contract_payload(
        _build_canonical_epl_games_row(),
        _load_schema("epl_epl_games_row_v1.json"),
    )


def test_canonical_unified_games_row_satisfies_contract() -> None:
    """A canonical shared-storage row validates against the unified_games schema."""
    validate_contract_payload(
        _build_canonical_unified_games_row(),
        _load_schema("epl_unified_game_row_v1.json"),
    )


@pytest.mark.parametrize(
    ("filename", "builder", "missing_field"),
    [
        ("epl_epl_games_row_v1.json", _build_canonical_epl_games_row, "game_id"),
        ("epl_epl_games_row_v1.json", _build_canonical_epl_games_row, "home_team"),
        ("epl_epl_games_row_v1.json", _build_canonical_epl_games_row, "result"),
        ("epl_unified_game_row_v1.json", _build_canonical_unified_games_row, "game_id"),
        ("epl_unified_game_row_v1.json", _build_canonical_unified_games_row, "home_team_name"),
        ("epl_unified_game_row_v1.json", _build_canonical_unified_games_row, "status"),
    ],
)
def test_persisted_row_contracts_reject_missing_required_fields(
    filename: str,
    builder: Any,
    missing_field: str,
) -> None:
    """Missing persisted fields fail fast as row-shape drift."""
    row = builder()
    row.pop(missing_field)

    with pytest.raises(ValidationError):
        validate_contract_payload(row, _load_schema(filename))


def test_current_epl_processor_game_id_drift_is_visible_to_consumers() -> None:
    """Consumer expectations freeze the canonical EPL game_id before provider fixes."""
    current_epl_row, _ = _build_current_processor_rows()

    assert current_epl_row["game_id"] == _build_canonical_epl_games_row()["game_id"]


def test_current_unified_row_team_normalization_drift_is_visible_to_consumers() -> None:
    """Shared-storage team naming must satisfy the governed EPL contract."""
    _, current_unified_row = _build_current_processor_rows()

    assert current_unified_row["home_team_name"] == "Manchester City"
    assert current_unified_row["away_team_name"] == "Tottenham Hotspur"
    validate_contract_payload(
        current_unified_row,
        _load_schema("epl_unified_game_row_v1.json"),
    )
