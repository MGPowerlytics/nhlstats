"""Deterministic tennis_games row builders matching TennisCSVProcessor output."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_BASE_TENNIS_GAMES_ROW: dict[str, Any] = {
    "game_id": "TENNIS_ATP_2026-04-07_CobolliF_BlockxA",
    "game_date": "2026-04-07",
    "season": "2026",
    "tour": "ATP",
    "tournament": "Monte Carlo Masters",
    "surface": "Clay",
    "winner": "Cobolli F.",
    "loser": "Blockx A.",
    "score": "6-4 7-5",
}


def build_tennis_games_row(**overrides: Any) -> dict[str, Any]:
    """Return the canonical tennis_games persisted-row payload."""
    row = deepcopy(_BASE_TENNIS_GAMES_ROW)
    row.update(overrides)
    return row


def build_tennis_games_row_wta() -> dict[str, Any]:
    """Return a WTA-tour tennis_games persisted-row sample."""
    return build_tennis_games_row(
        game_id="TENNIS_WTA_2026-04-07_SwiatekI_GauffC",
        tour="WTA",
        winner="Swiatek I.",
        loser="Gauff C.",
    )
