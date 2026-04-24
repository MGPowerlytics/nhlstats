"""Wave-3 provider-red MLB Kalshi sample fixtures.

These complement :mod:`tests.contracts.fixtures.mlb_kalshi_samples` with
shapes the consumer-side fixtures don't cover but that the provider tests
need (home-side franchise-code ticker for the known drift, and a (2, 3)
compact-split ticker for the parser symmetry test).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_HOME_SIDE_RAW_MARKET: dict[str, Any] = {
    # Same matchup as the Wave-2 fixture, but the YES side is the home team
    # (San Francisco Giants -> "SF" suffix). This is the realistic Kalshi
    # shape for the home-team side of the moneyline binary.
    "ticker": "KXMLBGAME-24APR21LADSF-SF",
    "market_id": "KXMLBGAME-24APR21LADSF-SF",
    "title": "Los Angeles Dodgers at San Francisco Giants",
    "yes_ask": 63,
    "close_time": "2024-04-21T20:10:00Z",
    "status": "active",
}


_TWO_THREE_SPLIT_RAW_MARKET: dict[str, Any] = {
    # Reverses the matchup so the compact-team string is "SFLAD" — exercises
    # the (2, 3) split branch of ``_parse_mlb_teams``.
    "ticker": "KXMLBGAME-24APR21SFLAD-LAD",
    "market_id": "KXMLBGAME-24APR21SFLAD-LAD",
    "title": "San Francisco Giants at Los Angeles Dodgers",
    "yes_ask": 55,
    "close_time": "2024-04-21T20:10:00Z",
    "status": "active",
}


def build_mlb_kalshi_home_side_market() -> dict[str, Any]:
    """Return a Kalshi-shaped market whose YES side is the home team (SF)."""
    return deepcopy(_HOME_SIDE_RAW_MARKET)


def build_mlb_kalshi_two_three_split_market() -> dict[str, Any]:
    """Return a Kalshi-shaped market whose compact teams use a (2, 3) split."""
    return deepcopy(_TWO_THREE_SPLIT_RAW_MARKET)
