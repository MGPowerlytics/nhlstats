"""Deterministic MLB historical-stats fixtures for Wave-2 consumer-red contract tests."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any

# Canonical MLB ``team_game_stats`` core rows for one finalised game.
# Mirrors the shape returned by ``MLBBoxScoreFetcher._build_row`` in
# ``plugins/stats/mlb_box_score.py`` (sans the nested ``"ext"`` sub-dict).
_BASE_MLB_TEAM_ROWS: list[dict[str, Any]] = [
    {
        "game_id": "745431",
        "sport": "MLB",
        "team": "NYY",
        "opponent": "BOS",
        "is_home": True,
        "game_date": "2025-04-15",
        "season": "2025",
        "points_for": 6,
        "points_against": 3,
        "won": True,
        "margin": 3,
    },
    {
        "game_id": "745431",
        "sport": "MLB",
        "team": "BOS",
        "opponent": "NYY",
        "is_home": False,
        "game_date": "2025-04-15",
        "season": "2025",
        "points_for": 3,
        "points_against": 6,
        "won": False,
        "margin": -3,
    },
]

# Canonical MLB extension rows for the same finalised game.
_BASE_MLB_EXT_ROWS: list[dict[str, Any]] = [
    {
        "game_id": "745431",
        "team": "NYY",
        "hits": 11,
        "errors": 0,
        "lob": 7,
        "doubles": 2,
        "triples": 0,
        "home_runs": 2,
        "rbi": 6,
        "stolen_bases": 1,
        "strikeouts": 8,
        "walks": 4,
        "at_bats": 34,
        "obp": 0.395,
        "slg": 0.588,
        "ops": 0.983,
        "woba": 0.412,
        "era": 3.00,
    },
    {
        "game_id": "745431",
        "team": "BOS",
        "hits": 7,
        "errors": 1,
        "lob": 6,
        "doubles": 1,
        "triples": 0,
        "home_runs": 1,
        "rbi": 3,
        "stolen_bases": 0,
        "strikeouts": 10,
        "walks": 2,
        "at_bats": 33,
        "obp": 0.270,
        "slg": 0.333,
        "ops": 0.603,
        "woba": 0.291,
        "era": 6.00,
    },
]

# Sample raw MLB Stats API ``boxscore`` ``teamStats`` payload — useful for
# provider-side wiring tests later. Numbers match _BASE_MLB_EXT_ROWS[0].
_BASE_MLB_BOXSCORE_BATTING: dict[str, Any] = {
    "hits": 11,
    "doubles": 2,
    "triples": 0,
    "homeRuns": 2,
    "baseOnBalls": 4,
    "hitByPitch": 0,
    "sacFlies": 0,
    "atBats": 34,
    "strikeOuts": 8,
    "leftOnBase": 7,
    "rbi": 6,
    "stolenBases": 1,
    "obp": "0.395",
    "slg": "0.588",
}


def build_mlb_team_game_stats_rows() -> list[dict[str, Any]]:
    """Return the canonical MLB ``team_game_stats`` contract rows."""
    return deepcopy(_BASE_MLB_TEAM_ROWS)


def build_mlb_team_game_stats_ext_rows() -> list[dict[str, Any]]:
    """Return the canonical ``mlb_team_game_stats_ext`` contract rows."""
    return deepcopy(_BASE_MLB_EXT_ROWS)


def build_mlb_box_score_fetcher_rows() -> list[dict[str, Any]]:
    """Return rows shaped like ``MLBBoxScoreFetcher._build_row`` output.

    The core fields use a real :class:`datetime.date` for ``game_date`` and
    nest extension stats under ``"ext"`` (matching the production contract
    boundary between ``team_game_stats`` and ``mlb_team_game_stats_ext``).
    """
    rows: list[dict[str, Any]] = []
    for core, ext in zip(
        deepcopy(_BASE_MLB_TEAM_ROWS), deepcopy(_BASE_MLB_EXT_ROWS), strict=True
    ):
        merged = dict(core)
        merged["game_date"] = date.fromisoformat(core["game_date"])
        merged["ext"] = {k: v for k, v in ext.items() if k not in {"game_id", "team"}}
        rows.append(merged)
    return rows


def build_mlb_boxscore_batting_payload(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic MLB Stats API batting payload sample."""
    payload = deepcopy(_BASE_MLB_BOXSCORE_BATTING)
    payload.update(overrides)
    return payload
