"""Deterministic Tennis bet recommendation row builders."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_BASE_TENNIS_RECOMMENDATION: dict[str, Any] = {
    "bet_id": "TENNIS_2026-04-07_KXATPMATCH-26APR07COBBLO-COB_away",
    "sport": "TENNIS",
    "recommendation_date": "2026-04-07",
    "home_team": "Alexander Blockx",
    "away_team": "Flavio Cobolli",
    "bet_on": "Flavio Cobolli",
    "ticker": "KXATPMATCH-26APR07COBBLO-COB",
    "elo_prob": 0.72,
    "market_prob": 0.66,
    "edge": 0.06,
    "expected_value": 0.0909090909,
    "kelly_fraction": 0.1166,
    "confidence": "LOW",
    "home_rating": 1620.0,
    "away_rating": 1700.0,
    "yes_ask": 66,
    "no_ask": 34,
}


def build_tennis_saved_bet_payload(**overrides: Any) -> dict[str, Any]:
    """Build the in-process saved-bet payload (includes 'side')."""
    payload = deepcopy(_BASE_TENNIS_RECOMMENDATION)
    payload["side"] = "away"
    payload.update(overrides)
    return payload


def build_tennis_persisted_recommendation_row(**overrides: Any) -> dict[str, Any]:
    """Build the persisted bet_recommendations row payload."""
    payload = deepcopy(_BASE_TENNIS_RECOMMENDATION)
    payload.update(overrides)
    return payload


def build_tennis_saved_bet_payload_synthetic_ticker() -> dict[str, Any]:
    """Build a tennis saved-bet payload with a synthesized ticker fallback."""
    return build_tennis_saved_bet_payload(
        ticker="KXATPMATCH-SYNTH-2026-04-07-ALEXANDERBLOCKX-FLAVIOCOBOLLI-AWAY",
        bet_id="TENNIS_2026-04-07_KXATPMATCH-SYNTH-2026-04-07-ALEXANDERBLOCKX-FLAVIOCOBOLLI-AWAY_away",
    )
