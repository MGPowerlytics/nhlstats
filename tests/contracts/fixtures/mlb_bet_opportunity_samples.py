"""Deterministic MLB bet opportunity fixtures for Wave-2 consumer-red contract tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# Canonical MLB opportunity payload mirroring the dict produced by
# ``BettingOutcome.to_opportunity`` in ``plugins/odds_comparator.py`` for the
# MLB code path. ``sport`` is locked to uppercase ``"MLB"`` per the consumer
# contract; the production code currently propagates the configured sport
# casing verbatim so this fixture is the canonical desired shape.
_BASE_MLB_OPPORTUNITY: dict[str, Any] = {
    "sport": "MLB",
    "game_id": "745431",
    "home_team": "New York Yankees",
    "away_team": "Boston Red Sox",
    "home_rating": 1612.4,
    "away_rating": 1498.2,
    "bet_on": "New York Yankees",
    "side": "home",
    "elo_prob": 0.58,
    "market_prob": 0.47,
    "market_odds": 2.13,
    "bookmaker": "Kalshi",
    "ticker": "KXMLBGAME-25APR15NYYBOS-NYY",
    "edge": 0.11,
    "expected_value": 0.2340425532,
    "kelly_fraction": 0.1037735849,
    "sharp_confirmed": False,
    "confidence": "MEDIUM",
    "agreement_diff": 0.11,
}


def build_mlb_bet_opportunity(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic, contract-valid MLB opportunity payload."""
    payload = deepcopy(_BASE_MLB_OPPORTUNITY)
    payload.update(overrides)
    return payload


def build_mlb_bet_opportunity_missing_field(field: str) -> dict[str, Any]:
    """Build an opportunity payload with one required field removed."""
    payload = build_mlb_bet_opportunity()
    payload.pop(field, None)
    return payload


def build_mlb_bet_opportunity_lowercase_sport() -> dict[str, Any]:
    """Build an opportunity payload using the legacy lowercase ``"mlb"`` sport casing."""
    return build_mlb_bet_opportunity(sport="mlb")


def build_mlb_bet_opportunity_out_of_range_edge(edge: float) -> dict[str, Any]:
    """Build an opportunity payload whose edge falls outside [0.05, 0.15]."""
    return build_mlb_bet_opportunity(edge=edge)
