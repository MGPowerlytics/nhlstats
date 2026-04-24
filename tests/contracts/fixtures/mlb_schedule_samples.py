from __future__ import annotations

from copy import deepcopy
from typing import Any


_BASE_HOME_TEAM: dict[str, Any] = {
    "team": {"id": 137, "name": "San Francisco Giants"},
    "score": 5,
    "probablePitcher": {"id": 592332, "fullName": "Logan Webb"},
}

_BASE_AWAY_TEAM: dict[str, Any] = {
    "team": {"id": 119, "name": "Los Angeles Dodgers"},
    "score": 3,
    "probablePitcher": {"id": 477132, "fullName": "Clayton Kershaw"},
}

_BASE_SCHEDULE_GAME: dict[str, Any] = {
    "gamePk": 745804,
    "gameDate": "2024-04-21T20:10:00Z",
    "officialDate": "2024-04-21",
    "season": 2024,
    "gameType": "R",
    "seriesDescription": "Regular Season",
    "status": {
        "abstractGameState": "Final",
        "detailedState": "Final",
    },
    "teams": {
        "home": deepcopy(_BASE_HOME_TEAM),
        "away": deepcopy(_BASE_AWAY_TEAM),
    },
    "venue": {"id": 2395, "name": "Oracle Park"},
}


_BASE_MLB_GAMES_ROW: dict[str, Any] = {
    "game_id": 745804,
    "game_date": "2024-04-21",
    "season": 2024,
    "game_type": "R",
    "home_team": "San Francisco Giants",
    "away_team": "Los Angeles Dodgers",
    "home_score": 5,
    "away_score": 3,
    "status": "Final",
    "home_pitcher_id": "592332",
    "away_pitcher_id": "477132",
    "home_pitcher_name": "Logan Webb",
    "away_pitcher_name": "Clayton Kershaw",
}


_BASE_UNIFIED_GAMES_ROW: dict[str, Any] = {
    "game_id": "745804",
    "sport": "MLB",
    "game_date": "2024-04-21",
    "season": 2024,
    "status": "Final",
    "home_team_id": "137",
    "home_team_name": "San Francisco Giants",
    "away_team_id": "119",
    "away_team_name": "Los Angeles Dodgers",
    "home_score": 5,
    "away_score": 3,
    "commence_time": "2024-04-21T20:10:00Z",
    "venue": "Oracle Park",
    "home_pitcher_id": "592332",
    "away_pitcher_id": "477132",
    "home_pitcher_name": "Logan Webb",
    "away_pitcher_name": "Clayton Kershaw",
}


def build_mlb_schedule_game(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic MLB Stats API schedule game record."""
    game = deepcopy(_BASE_SCHEDULE_GAME)
    game.update(overrides)
    return game


def build_mlb_games_row(**overrides: Any) -> dict[str, Any]:
    """Build a canonical mlb_games persisted row."""
    row = deepcopy(_BASE_MLB_GAMES_ROW)
    row.update(overrides)
    return row


def build_mlb_unified_games_row(**overrides: Any) -> dict[str, Any]:
    """Build a canonical unified_games persisted row for MLB."""
    row = deepcopy(_BASE_UNIFIED_GAMES_ROW)
    row.update(overrides)
    return row


def build_mlb_excluded_game_types() -> tuple[str, ...]:
    """Return MLB Stats API gameType codes excluded from the warehouse."""
    return ("S", "E", "A")
