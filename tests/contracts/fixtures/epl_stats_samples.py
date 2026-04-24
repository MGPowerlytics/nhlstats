from __future__ import annotations

from copy import deepcopy
from typing import Any

import pandas as pd

_BASE_STATS_SOURCE_ROW: dict[str, Any] = {
    "Date": pd.Timestamp("2025-08-16"),
    "HomeTeam": "Manchester City",
    "AwayTeam": "Tottenham Hotspur",
    "FTHG": 2,
    "FTAG": 1,
    "FTR": "H",
    "HS": 15,
    "AS": 10,
    "HST": 6,
    "AST": 4,
    "HF": 8,
    "AF": 11,
    "HY": 1,
    "AY": 2,
    "HR": 0,
    "AR": 0,
    "HC": 7,
    "AC": 3,
}

_BASE_TEAM_ROWS: list[dict[str, Any]] = [
    {
        "game_id": "EPL_20250816_MANCHESTERCITY_TOTTENHAMHOTSPUR",
        "sport": "EPL",
        "team": "Manchester City",
        "opponent": "Tottenham Hotspur",
        "is_home": True,
        "game_date": "2025-08-16",
        "season": "2526",
        "points_for": 2,
        "points_against": 1,
        "won": True,
        "margin": 1,
    },
    {
        "game_id": "EPL_20250816_MANCHESTERCITY_TOTTENHAMHOTSPUR",
        "sport": "EPL",
        "team": "Tottenham Hotspur",
        "opponent": "Manchester City",
        "is_home": False,
        "game_date": "2025-08-16",
        "season": "2526",
        "points_for": 1,
        "points_against": 2,
        "won": False,
        "margin": -1,
    },
]

_BASE_EXTENSION_ROWS: list[dict[str, Any]] = [
    {
        "game_id": "EPL_20250816_MANCHESTERCITY_TOTTENHAMHOTSPUR",
        "team": "Manchester City",
        "shots": 15,
        "shots_on_target": 6,
        "possession_pct": None,
        "passes": None,
        "pass_accuracy": None,
        "xg": None,
        "xga": None,
        "fouls": 8,
        "yellow_cards": 1,
        "red_cards": 0,
        "corners": 7,
        "offsides": None,
        "saves": None,
    },
    {
        "game_id": "EPL_20250816_MANCHESTERCITY_TOTTENHAMHOTSPUR",
        "team": "Tottenham Hotspur",
        "shots": 10,
        "shots_on_target": 4,
        "possession_pct": None,
        "passes": None,
        "pass_accuracy": None,
        "xg": None,
        "xga": None,
        "fouls": 11,
        "yellow_cards": 2,
        "red_cards": 0,
        "corners": 3,
        "offsides": None,
        "saves": None,
    },
]


def build_epl_stats_csv_row(**overrides: Any) -> pd.Series:
    """Build a deterministic football-data.co.uk EPL stats row."""
    row = deepcopy(_BASE_STATS_SOURCE_ROW)
    row.update(overrides)
    return pd.Series(row)


def build_epl_team_game_stats_rows() -> list[dict[str, Any]]:
    """Build the canonical EPL team_game_stats contract rows."""
    return deepcopy(_BASE_TEAM_ROWS)


def build_epl_soccer_stats_ext_rows() -> list[dict[str, Any]]:
    """Build the canonical EPL soccer extension contract rows."""
    return deepcopy(_BASE_EXTENSION_ROWS)
