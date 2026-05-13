"""Deterministic portfolio allocation fixtures for contract tests.

These match the ``PortfolioAllocation`` and ``BetOpportunity`` dataclass shapes
produced by ``PortfolioOptimizer.calculate_portfolio_allocation()``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# ---------------------------------------------------------------------------
# Base BetOpportunity dicts (sport-specific variants)
# ---------------------------------------------------------------------------

_BASE_NBA_OPPORTUNITY: dict[str, Any] = {
    "sport": "nba",
    "ticker": "KXNBAGAME-26JAN20LAL-LAL",
    "bet_on": "home",
    "team": "Los Angeles Lakers",
    "opponent": "Boston Celtics",
    "home_team": "Los Angeles Lakers",
    "away_team": "Boston Celtics",
    "home_team_raw": "Lakers",
    "away_team_raw": "Celtics",
    "elo_prob": 0.62,
    "market_prob": 0.55,
    "edge": 0.07,
    "confidence": "HIGH",
    "yes_ask": 62,
    "no_ask": 38,
    "home_rating": 1612.4,
    "away_rating": 1545.1,
    "game_time": "2026-01-20T19:30:00Z",
    "game_id": "NBA_20260120_LAL_BOS",
    "betmgm_prob": 0.60,
}

_BASE_MLB_OPPORTUNITY: dict[str, Any] = {
    "sport": "mlb",
    "ticker": "KXMLBGAME-25APR15NYYBOS-NYY",
    "bet_on": "home",
    "team": "New York Yankees",
    "opponent": "Boston Red Sox",
    "home_team": "New York Yankees",
    "away_team": "Boston Red Sox",
    "home_team_raw": "Yankees",
    "away_team_raw": "Red Sox",
    "elo_prob": 0.58,
    "market_prob": 0.47,
    "edge": 0.11,
    "confidence": "MEDIUM",
    "yes_ask": 58,
    "no_ask": 42,
    "home_rating": 1612.4,
    "away_rating": 1498.2,
    "game_time": "2025-04-15T18:00:00Z",
    "game_id": "745431",
    "betmgm_prob": 0.55,
}

_BASE_TENNIS_OPPORTUNITY: dict[str, Any] = {
    "sport": "tennis",
    "ticker": "KXATPMATCH-26JAN20ALCARAZ-ZVEREV-ALCARAZ",
    "bet_on": "home",
    "team": "Carlos Alcaraz",
    "opponent": "Alexander Zverev",
    "home_team": "Carlos Alcaraz",
    "away_team": "Alexander Zverev",
    "home_team_raw": "Alcaraz",
    "away_team_raw": "Zverev",
    "elo_prob": 0.65,
    "market_prob": 0.60,
    "edge": 0.05,
    "confidence": "MEDIUM",
    "yes_ask": 65,
    "no_ask": 35,
    "home_rating": 1850.0,
    "away_rating": 1720.0,
    "game_time": "2026-01-20T10:00:00Z",
    "game_id": "TENNIS_20260120_ALCARAZ_ZVEREV",
    "betmgm_prob": 0.62,
}

# ---------------------------------------------------------------------------
# Base PortfolioAllocation dict
# ---------------------------------------------------------------------------

_BASE_PORTFOLIO_ALLOCATION: dict[str, Any] = {
    "bet_size": 25.0,
    "kelly_fraction": 0.1139,
    "allocation_pct": 0.025,
    "opportunity": _BASE_NBA_OPPORTUNITY,
}

_BASE_PORTFOLIO_ALLOCATION_MLB: dict[str, Any] = {
    "bet_size": 20.0,
    "kelly_fraction": 0.1038,
    "allocation_pct": 0.02,
    "opportunity": _BASE_MLB_OPPORTUNITY,
}

_BASE_PORTFOLIO_ALLOCATION_TENNIS: dict[str, Any] = {
    "bet_size": 15.0,
    "kelly_fraction": 0.0417,
    "allocation_pct": 0.015,
    "opportunity": _BASE_TENNIS_OPPORTUNITY,
}


# ---------------------------------------------------------------------------
# Public builders
# ---------------------------------------------------------------------------


def build_bet_opportunity(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic, contract-shape NBA ``BetOpportunity`` dict.

    Args:
        **overrides: Override specific fields (e.g. sport=\"mlb\", elo_prob=0.7).

    Returns:
        A deep copy of the base opportunity with overrides applied.
    """
    payload = deepcopy(_BASE_NBA_OPPORTUNITY)
    payload.update(overrides)
    return payload


def build_bet_opportunity_nba() -> dict[str, Any]:
    """Build a deterministic NBA ``BetOpportunity`` dict."""
    return deepcopy(_BASE_NBA_OPPORTUNITY)


def build_bet_opportunity_mlb() -> dict[str, Any]:
    """Build a deterministic MLB ``BetOpportunity`` dict."""
    return deepcopy(_BASE_MLB_OPPORTUNITY)


def build_bet_opportunity_tennis() -> dict[str, Any]:
    """Build a deterministic Tennis ``BetOpportunity`` dict."""
    return deepcopy(_BASE_TENNIS_OPPORTUNITY)


def build_portfolio_allocation(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic, contract-valid ``PortfolioAllocation`` dict.

    Args:
        **overrides: Override specific fields at the top level or nested
            ``opportunity`` sub-dict (e.g. bet_size=50.0,
            opportunity__sport=\"mlb\").

    Returns:
        A deep copy of the base allocation with overrides applied.
    """
    payload = deepcopy(_BASE_PORTFOLIO_ALLOCATION)
    # Handle nested opportunity overrides using double-underscore convention
    opportunity_overrides: dict[str, Any] = {}
    top_overrides: dict[str, Any] = {}
    for key, value in overrides.items():
        if key.startswith("opportunity__"):
            opportunity_overrides[key.replace("opportunity__", "")] = value
        else:
            top_overrides[key] = value

    payload.update(top_overrides)
    if opportunity_overrides:
        payload["opportunity"] = {**payload["opportunity"], **opportunity_overrides}
    return payload


def build_portfolio_allocation_nba() -> dict[str, Any]:
    """Build a deterministic NBA ``PortfolioAllocation`` dict."""
    return deepcopy(_BASE_PORTFOLIO_ALLOCATION)


def build_portfolio_allocation_mlb() -> dict[str, Any]:
    """Build a deterministic MLB ``PortfolioAllocation`` dict."""
    return deepcopy(_BASE_PORTFOLIO_ALLOCATION_MLB)


def build_portfolio_allocation_tennis() -> dict[str, Any]:
    """Build a deterministic Tennis ``PortfolioAllocation`` dict."""
    return deepcopy(_BASE_PORTFOLIO_ALLOCATION_TENNIS)
