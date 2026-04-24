from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from plugins.csv_processors import EPLCSVProcessor, Ligue1CSVProcessor
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_DIR / filename).read_text(encoding="utf-8"))


def _build_actual_provider_rows() -> tuple[dict, dict]:
    processor = EPLCSVProcessor(MagicMock())
    row = pd.Series(
        {
            "Date": pd.Timestamp("2025-08-16"),
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


def test_epl_csv_processor_uses_canonical_game_id_for_epl_rows() -> None:
    """EPL provider game_id generation should match the frozen canonical identifier."""
    epl_row, _ = _build_actual_provider_rows()

    assert epl_row["game_id"] == "EPL_20250816_MANCHESTERCITY_TOTTENHAMHOTSPUR"


def test_epl_csv_processor_emits_contract_valid_unified_games_params() -> None:
    """Unified-games persistence params should satisfy the canonical EPL storage subset."""
    _, unified_row = _build_actual_provider_rows()

    validate_contract_payload(unified_row, _load_schema("epl_unified_game_row_v1.json"))


def test_ligue1_csv_processor_keeps_non_epl_persistence_behavior_unchanged() -> None:
    """The EPL contract fix must not rewire Ligue 1 into EPL-owned persistence paths."""
    processor = Ligue1CSVProcessor(MagicMock())
    row = pd.Series(
        {
            "Date": pd.Timestamp("2025-08-16"),
            "HomeTeam": "Paris SG",
            "AwayTeam": "St Etienne",
            "FTHG": 2,
            "FTAG": 1,
            "FTR": "H",
        }
    )

    processor.process_row(row, season_code="2526")

    assert processor.db.execute.call_count == 1

    sql, params = processor.db.execute.call_args_list[0].args
    assert "INSERT INTO ligue1_games" in sql
    assert params == {
        "game_id": "LIGUE1_2025-08-16_ParisSG_StEtienne",
        "game_date": "2025-08-16",
        "season": "2526",
        "home_team": "Paris SG",
        "away_team": "St Etienne",
        "home_score": 2,
        "away_score": 1,
        "result": "H",
    }
