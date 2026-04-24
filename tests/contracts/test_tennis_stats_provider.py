"""Provider RED tests for tennis_player_match_stats persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from jsonschema import Draft202012Validator
from unittest.mock import MagicMock

from plugins.stats.tennis_box_score import TennisBoxScoreFetcher
from tests.contracts.helpers import find_execute_params


SCHEMA_PATH = (
    Path(__file__).resolve().parent
    / "schemas"
    / "tennis_player_match_stats_row_v1.json"
)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


class _FakeExecuteCall:
    def __init__(self, sql: str, params: dict[str, Any]) -> None:
        self.args = (sql, params)


class RecordingDB:
    def __init__(self, valid_game_ids: set[str]) -> None:
        self.calls: list[Any] = []
        self._valid = valid_game_ids

    def execute(self, sql: str, params: dict[str, Any]) -> Any:
        self.calls.append(_FakeExecuteCall(sql, dict(params)))
        if "SELECT game_id FROM unified_games" in sql:
            result = MagicMock()
            result.fetchall.return_value = [(gid,) for gid in self._valid]
            return result
        return MagicMock()


def _real_parse_rows(game_id: str) -> list[dict[str, Any]]:
    fetcher = TennisBoxScoreFetcher.__new__(TennisBoxScoreFetcher)
    series = pd.Series(
        {
            "winner_name": "Novak Djokovic",
            "loser_name": "Carlos Alcaraz",
            "score": "6-4 6-3 7-6",
            "w_ace": 12,
            "w_df": 2,
            "w_svpt": 80,
            "w_1stIn": 52,
            "w_1stWon": 41,
            "w_2ndWon": 16,
            "w_bpSaved": 4,
            "w_bpFaced": 5,
            "l_ace": 6,
            "l_df": 4,
            "l_svpt": 75,
            "l_1stIn": 44,
            "l_1stWon": 30,
            "l_2ndWon": 14,
            "l_bpSaved": 2,
            "l_bpFaced": 6,
        }
    )
    return fetcher._parse_match_row(series, game_id)


def test_real_parse_match_row_emits_contract_valid_winner_and_loser_dicts() -> None:
    rows = _real_parse_rows("atp_2023-560_0001")
    schema = _load_schema()

    assert len(rows) == 2
    for row in rows:
        Draft202012Validator(schema).validate(row)

    assert rows[0]["won"] is True
    assert rows[1]["won"] is False


def test_real_upsert_rows_persists_contract_valid_params() -> None:
    rows = _real_parse_rows("atp_2023-560_0001")

    fetcher = TennisBoxScoreFetcher.__new__(TennisBoxScoreFetcher)
    fetcher.db = RecordingDB({"atp_2023-560_0001"})

    upserted = fetcher.upsert_rows(rows)
    assert upserted == 2

    persisted = find_execute_params(fetcher.db.calls, "tennis_player_match_stats")
    assert len(persisted) == 2

    schema = _load_schema()
    for row in persisted:
        Draft202012Validator(schema).validate(row)


def test_build_game_id_format_matches_contract_pattern() -> None:
    game_id = TennisBoxScoreFetcher._build_game_id("atp", "2023-560", "0001")
    assert game_id == "atp_2023-560_0001"
