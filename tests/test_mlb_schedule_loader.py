"""Tests for MLB schedule loader hygiene rules.

Covers:
* Pre-game scores must be persisted as NULL (not the API's literal 0).
* Spring-training/exhibition/All-Star game types must be skipped at write-time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from plugins.db_loader import NHLDatabaseLoader


class _StubDB:
    """In-memory stand-in for DBManager that captures executed parameters."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def execute(self, query: str, params: Dict[str, Any] | None = None) -> None:
        self.calls.append({"query": query, "params": params or {}})


def _make_payload(games: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"dates": [{"games": games}]}


def _write_payload(tmp_path: Path, games: List[Dict[str, Any]]) -> Path:
    file_path = tmp_path / "mlb_schedule.json"
    file_path.write_text(json.dumps(_make_payload(games)))
    return file_path


def _base_game(**overrides: Any) -> Dict[str, Any]:
    """Build a minimal MLB Stats API schedule game payload."""
    game = {
        "gamePk": 824448,
        "officialDate": "2026-04-21",
        "season": "2026",
        "gameType": "R",
        "gameDate": "2026-04-21T22:10:00Z",
        "venue": {"name": "Progressive Field"},
        "status": {"abstractGameState": "Preview"},
        "teams": {
            "home": {
                "team": {"id": 114, "name": "Cleveland Guardians"},
                "score": 0,
            },
            "away": {
                "team": {"id": 117, "name": "Houston Astros"},
                "score": 0,
            },
        },
    }
    game.update(overrides)
    return game


def _params_for_table(stub: _StubDB, table: str) -> List[Dict[str, Any]]:
    return [c["params"] for c in stub.calls if table in c["query"]]


class TestPreviewScoresAreNull:
    """Pre-game (status != Final) games must persist NULL scores, not literal 0."""

    def test_preview_status_zero_score_persisted_as_null(self, tmp_path: Path) -> None:
        loader = NHLDatabaseLoader(db=_StubDB())
        loader._load_mlb_schedule(_write_payload(tmp_path, [_base_game()]))

        for table in ("mlb_games", "unified_games"):
            params = _params_for_table(loader.db, table)
            assert params, f"expected at least one insert into {table}"
            assert (
                params[0]["home_score"] is None
            ), f"{table}: home_score must be NULL when status is Preview"
            assert (
                params[0]["away_score"] is None
            ), f"{table}: away_score must be NULL when status is Preview"

    def test_final_status_scores_persisted_as_is(self, tmp_path: Path) -> None:
        loader = NHLDatabaseLoader(db=_StubDB())
        final_game = _base_game(
            status={"abstractGameState": "Final"},
            teams={
                "home": {
                    "team": {"id": 114, "name": "Cleveland Guardians"},
                    "score": 4,
                },
                "away": {
                    "team": {"id": 117, "name": "Houston Astros"},
                    "score": 2,
                },
            },
        )
        loader._load_mlb_schedule(_write_payload(tmp_path, [final_game]))

        for table in ("mlb_games", "unified_games"):
            params = _params_for_table(loader.db, table)[0]
            assert params["home_score"] == 4
            assert params["away_score"] == 2


class TestNonRegularSeasonFiltered:
    """Spring training / exhibition / All-Star games must be skipped."""

    @pytest.mark.parametrize("game_type", ["S", "E", "A"])
    def test_non_regular_season_is_skipped(
        self, tmp_path: Path, game_type: str
    ) -> None:
        loader = NHLDatabaseLoader(db=_StubDB())
        loader._load_mlb_schedule(
            _write_payload(tmp_path, [_base_game(gameType=game_type)])
        )

        assert (
            loader.db.calls == []
        ), f"game_type={game_type!r} must not be persisted"

    @pytest.mark.parametrize("game_type", ["R", "D", "L", "W", "F"])
    def test_regular_and_postseason_are_persisted(
        self, tmp_path: Path, game_type: str
    ) -> None:
        loader = NHLDatabaseLoader(db=_StubDB())
        loader._load_mlb_schedule(
            _write_payload(tmp_path, [_base_game(gameType=game_type)])
        )

        assert _params_for_table(
            loader.db, "mlb_games"
        ), f"game_type={game_type!r} should be persisted"
