"""Provider RED tests for tennis_games + unified_games persistence (TennisCSVProcessor)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from jsonschema import Draft202012Validator

from plugins.csv_processors import TennisCSVProcessor
from tests.contracts.fixtures.tennis_csv_samples import build_tennis_csv_row
from tests.contracts.fixtures.tennis_games_db_samples import build_tennis_games_row
from tests.contracts.helpers import find_execute_params


SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"


def _load(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / name).read_text(encoding="utf-8"))


class _FakeExecuteCall:
    def __init__(self, sql: str, params: dict[str, Any]) -> None:
        self.args = (sql, params)


class RecordingDB:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    def execute(self, sql: str, params: dict[str, Any]) -> None:
        self.calls.append(_FakeExecuteCall(sql, dict(params)))


def _csv_series() -> pd.Series:
    base = build_tennis_csv_row()
    base["Date"] = pd.Timestamp(base["Date"])
    return pd.Series(base)


def test_tennis_csv_processor_writes_contract_valid_tennis_games_row() -> None:
    db = RecordingDB()
    TennisCSVProcessor(db).process_row(_csv_series(), tour="ATP", season="2026")

    rows = find_execute_params(db.calls, "tennis_games")
    assert len(rows) == 1

    schema = _load("tennis_tennis_games_row_v1.json")
    Draft202012Validator(schema).validate(rows[0])

    assert rows[0]["game_id"] == build_tennis_games_row()["game_id"]


def test_tennis_csv_processor_writes_contract_valid_unified_games_row() -> None:
    db = RecordingDB()
    TennisCSVProcessor(db).process_row(_csv_series(), tour="ATP", season="2026")

    rows = find_execute_params(db.calls, "unified_games")
    assert len(rows) == 1
    row = rows[0]
    # Producer params use {game_id, game_date, season_year, winner, loser}
    # mapped via INSERT placeholders. Build the persisted-shape projection
    # (matching the SQL column list) for contract validation.
    persisted = {
        "game_id": row["game_id"],
        "sport": "TENNIS",
        "game_date": row["game_date"],
        "home_team_name": row["winner"],
        "away_team_name": row["loser"],
        "status": "Final",
        "season": row["season_year"],
        "home_score": 1,
        "away_score": 0,
    }
    Draft202012Validator(_load("tennis_unified_game_row_v1.json")).validate(persisted)
