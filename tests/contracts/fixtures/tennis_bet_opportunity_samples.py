"""Deterministic Tennis bet opportunity builders."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_BASE_TENNIS_OPPORTUNITY: dict[str, Any] = {
    "sport": "TENNIS",
    "game_id": "TENNIS_ATP_2026-04-07_AlexanderBlockx_FlavioCobolli",
    "home_team": "Alexander Blockx",
    "away_team": "Flavio Cobolli",
    "side": "away",
    "bet_on": "Flavio Cobolli",
    "elo_prob": 0.72,
    "market_prob": 0.66,
    "market_odds": 1.5151515151515151,
    "bookmaker": "Kalshi",
    "ticker": "KXATPMATCH-26APR07COBBLO-COB",
    "edge": 0.06,
    "expected_value": 0.0909090909,
    "kelly_fraction": 0.1166,
    "sharp_confirmed": False,
    "confidence": "LOW",
    "agreement_diff": 0.06,
    "home_rating": 1620.0,
    "away_rating": 1700.0,
    "tour": "ATP",
}


def build_tennis_bet_opportunity(**overrides: Any) -> dict[str, Any]:
    """Build the canonical Tennis bet opportunity payload."""
    payload = deepcopy(_BASE_TENNIS_OPPORTUNITY)
    payload.update(overrides)
    return payload


def build_tennis_bet_opportunity_high_edge() -> dict[str, Any]:
    """Build a high-confidence Tennis bet opportunity (edge close to max of 0.15)."""
    return build_tennis_bet_opportunity(
        edge=0.14,
        elo_prob=0.80,
        market_prob=0.66,
        confidence="HIGH",
        agreement_diff=0.14,
    )


def build_tennis_bet_opportunity_clamped_edge() -> dict[str, Any]:
    """Build a Tennis bet opportunity with edge at the MAX_EDGE_THRESHOLD (0.15)."""
    return build_tennis_bet_opportunity(edge=0.15, elo_prob=0.99, market_prob=0.84)
