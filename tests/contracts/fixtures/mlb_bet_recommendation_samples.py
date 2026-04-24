"""Deterministic MLB bet recommendation fixtures for Wave-2 consumer-red contract tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# Canonical MLB ``bet_recommendations`` saved-payload (in-memory dict written
# by ``identify_good_bets`` and read back by ``BetLoader.load_bets_for_date``).
# ``bet_id`` follows the BetData fallback format for non-EPL sports with a
# ticker present: ``{sport}_{date_str}_{ticker}_{side}``. ``BetLoader`` then
# uppercases the sport, yielding ``MLB_...`` per repo memory.
_BASE_MLB_RECOMMENDATION_PAYLOAD: dict[str, Any] = {
    "bet_id": "MLB_2025-04-15_KXMLBGAME-25APR15NYYBOS-NYY_home",
    "sport": "MLB",
    "recommendation_date": "2025-04-15",
    "home_team": "New York Yankees",
    "away_team": "Boston Red Sox",
    "bet_on": "New York Yankees",
    "side": "home",
    "ticker": "KXMLBGAME-25APR15NYYBOS-NYY",
    "elo_prob": 0.58,
    "market_prob": 0.47,
    "edge": 0.11,
    "expected_value": 0.2340425532,
    "kelly_fraction": 0.1037735849,
    "confidence": "MEDIUM",
    "home_rating": 1612.4,
    "away_rating": 1498.2,
    "yes_ask": 47,
    "no_ask": 53,
}

# Persisted-row variant: ``side`` is dropped (the table column is ``bet_on``).
_BASE_MLB_RECOMMENDATION_ROW: dict[str, Any] = {
    key: value
    for key, value in _BASE_MLB_RECOMMENDATION_PAYLOAD.items()
    if key != "side"
}

_BASE_MLB_RECOMMENDATION_EXPECTATIONS: dict[str, Any] = {
    "bet_id": "MLB_2025-04-15_KXMLBGAME-25APR15NYYBOS-NYY_home",
    "sport": "MLB",
    "recommendation_date": "2025-04-15",
    "allowed_side": {"home", "away"},
}


def build_mlb_recommendation_payload(**overrides: Any) -> dict[str, Any]:
    """Build a canonical MLB recommendation saved-payload fixture."""
    payload = deepcopy(_BASE_MLB_RECOMMENDATION_PAYLOAD)
    payload.update(overrides)
    return payload


def build_mlb_recommendation_row(**overrides: Any) -> dict[str, Any]:
    """Build a canonical bet_recommendations persisted-row fixture for MLB."""
    row = deepcopy(_BASE_MLB_RECOMMENDATION_ROW)
    row.update(overrides)
    return row


def build_legacy_mlb_recommendation_payload(**overrides: Any) -> dict[str, Any]:
    """Build a legacy MLB recommendation that should violate the v1 contract.

    Mirrors known drift modes: lowercase sport, missing ticker, and a
    ``date_str`` field instead of ``recommendation_date``.
    """
    payload = build_mlb_recommendation_payload(sport="mlb", ticker=None)
    payload.pop("recommendation_date", None)
    payload["date_str"] = "2025-04-15"
    payload.pop("bet_id", None)
    payload.update(overrides)
    return payload


def build_mlb_recommendation_contract_expectations() -> dict[str, Any]:
    """Build the shared canonical recommendation invariant expectations."""
    return deepcopy(_BASE_MLB_RECOMMENDATION_EXPECTATIONS)
