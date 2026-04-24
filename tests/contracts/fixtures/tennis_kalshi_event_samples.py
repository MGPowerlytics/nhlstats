"""Deterministic paired-event fixture builders for tennis Kalshi event contract."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .tennis_kalshi_samples import build_tennis_kalshi_game_odds_row
from .tennis_unified_samples import build_tennis_unified_row_from_kalshi


def build_tennis_kalshi_paired_event(**overrides: Any) -> dict[str, Any]:
    """Build the canonical paired-event payload for tennis Kalshi aggregation."""
    event: dict[str, Any] = {
        "event_ticker": "KXATPMATCH-26APR07COBBLO",
        "tour": "ATP",
        "game_date": "2026-04-07",
        "home_side_code": "BLO",
        "away_side_code": "COB",
        "home_player_full_name": "Alexander Blockx",
        "away_player_full_name": "Flavio Cobolli",
        "game_id": "TENNIS_ATP_2026-04-07_AlexanderBlockx_FlavioCobolli",
        "unified_game": build_tennis_unified_row_from_kalshi(),
        "game_odds": [
            build_tennis_kalshi_game_odds_row("home"),
            build_tennis_kalshi_game_odds_row("away"),
        ],
    }
    event.update(overrides)
    return event


def build_tennis_kalshi_paired_event_single_sided() -> dict[str, Any]:
    """Build a paired-event payload with only one game_odds row present."""
    base = build_tennis_kalshi_paired_event()
    base["game_odds"] = [build_tennis_kalshi_game_odds_row("away")]
    return base
