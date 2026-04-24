"""Deterministic unified_games row builders for the tennis pipeline."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_BASE_KALSHI_UNIFIED_ROW: dict[str, Any] = {
    "game_id": "TENNIS_ATP_2026-04-07_AlexanderBlockx_FlavioCobolli",
    "sport": "TENNIS",
    "game_date": "2026-04-07",
    "home_team_name": "Alexander Blockx",
    "away_team_name": "Flavio Cobolli",
    "home_team_id": "Alexander Blockx",
    "away_team_id": "Flavio Cobolli",
    "commence_time": "2026-04-21T09:00:00Z",
    "status": "Scheduled",
}


_BASE_CSV_UNIFIED_ROW: dict[str, Any] = {
    "game_id": "TENNIS_ATP_2026-04-07_CobolliF_BlockxA",
    "sport": "TENNIS",
    "game_date": "2026-04-07",
    "home_team_name": "Cobolli F.",
    "away_team_name": "Blockx A.",
    "status": "Final",
    "season": 2026,
    "home_score": 1,
    "away_score": 0,
}


def build_tennis_unified_row_from_kalshi(**overrides: Any) -> dict[str, Any]:
    """Return a Kalshi-side unified_games row sample (status Scheduled)."""
    row = deepcopy(_BASE_KALSHI_UNIFIED_ROW)
    row.update(overrides)
    return row


def build_tennis_unified_row_from_csv(**overrides: Any) -> dict[str, Any]:
    """Return a CSV-side unified_games row sample (status Final)."""
    row = deepcopy(_BASE_CSV_UNIFIED_ROW)
    row.update(overrides)
    return row
