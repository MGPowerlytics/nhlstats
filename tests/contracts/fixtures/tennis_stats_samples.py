"""Deterministic tennis_player_match_stats row builders."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_BASE_WINNER_ROW: dict[str, Any] = {
    "game_id": "atp_2023-560_0001",
    "player_name": "Novak Djokovic",
    "aces": 12,
    "double_faults": 2,
    "first_serve_pct": 0.6450,
    "first_serve_won_pct": 0.7800,
    "second_serve_won_pct": 0.5500,
    "break_points_saved": 4,
    "break_points_faced": 5,
    "winners": None,
    "unforced_errors": None,
    "sets_won": 3,
    "games_won": 18,
    "won": True,
}


_BASE_LOSER_ROW: dict[str, Any] = {
    "game_id": "atp_2023-560_0001",
    "player_name": "Carlos Alcaraz",
    "aces": 6,
    "double_faults": 4,
    "first_serve_pct": 0.5800,
    "first_serve_won_pct": 0.6700,
    "second_serve_won_pct": 0.4300,
    "break_points_saved": 2,
    "break_points_faced": 6,
    "winners": None,
    "unforced_errors": None,
    "sets_won": 1,
    "games_won": 14,
    "won": False,
}


def build_tennis_winner_stats_row(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic winner row for tennis_player_match_stats."""
    row = deepcopy(_BASE_WINNER_ROW)
    row.update(overrides)
    return row


def build_tennis_loser_stats_row(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic loser row for tennis_player_match_stats."""
    row = deepcopy(_BASE_LOSER_ROW)
    row.update(overrides)
    return row
