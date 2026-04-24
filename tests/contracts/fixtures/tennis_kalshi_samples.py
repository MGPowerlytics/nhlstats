"""Deterministic Kalshi tennis market + game_odds row builders."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_BASE_RAW_MARKET: dict[str, Any] = {
    "ticker": "KXATPMATCH-26APR07COBBLO-COB",
    "event_ticker": "KXATPMATCH-26APR07COBBLO",
    "yes_sub_title": "Flavio Cobolli",
    "no_sub_title": "Flavio Cobolli",
    "yes_ask": 66,
    "no_ask": 34,
    "title": "Will Flavio Cobolli win the Cobolli vs Blockx : Round Of 32 match?",
    "close_time": "2026-04-07T09:00:00Z",
    "status": "active",
}


_BASE_GAME_ODDS_ROW: dict[str, Any] = {
    "odds_id": "TENNIS_ATP_2026-04-07_AlexanderBlockx_FlavioCobolli_kalshi_away",
    "game_id": "TENNIS_ATP_2026-04-07_AlexanderBlockx_FlavioCobolli",
    "bookmaker": "Kalshi",
    "market_name": "moneyline",
    "outcome_name": "away",
    "price": 1.5151515151515151,
    "is_pregame": True,
    "external_id": "KXATPMATCH-26APR07COBBLO-COB",
}


def build_tennis_kalshi_raw_market(side_code: str = "COB") -> dict[str, Any]:
    """Build a deterministic raw Kalshi tennis market sample."""
    market = deepcopy(_BASE_RAW_MARKET)
    market["ticker"] = f"KXATPMATCH-26APR07COBBLO-{side_code}"
    if side_code == "BLO":
        market["yes_sub_title"] = "Alexander Blockx"
        market["no_sub_title"] = "Alexander Blockx"
        market["title"] = (
            "Will Alexander Blockx win the Cobolli vs Blockx : Round Of 32 match?"
        )
        market["yes_ask"] = 38
        market["no_ask"] = 62
    return market


def build_tennis_kalshi_game_odds_row(outcome_name: str = "away") -> dict[str, Any]:
    """Build the canonical persisted game_odds row for a tennis Kalshi market."""
    row = deepcopy(_BASE_GAME_ODDS_ROW)
    if outcome_name == "home":
        row["outcome_name"] = "home"
        row["odds_id"] = (
            "TENNIS_ATP_2026-04-07_AlexanderBlockx_FlavioCobolli_kalshi_home"
        )
        row["external_id"] = "KXATPMATCH-26APR07COBBLO-BLO"
        row["price"] = 100.0 / 38.0
    return row


def build_tennis_kalshi_wta_raw_market() -> dict[str, Any]:
    """Build a deterministic WTA-tour raw Kalshi market."""
    return {
        "ticker": "KXWTAMATCH-26APR07SWIGAU-SWI",
        "event_ticker": "KXWTAMATCH-26APR07SWIGAU",
        "yes_sub_title": "Iga Swiatek",
        "no_sub_title": "Iga Swiatek",
        "yes_ask": 72,
        "no_ask": 28,
        "title": "Will Iga Swiatek win the Swiatek vs Gauff : Round Of 16 match?",
        "close_time": "2026-04-07T15:00:00Z",
        "status": "active",
    }
