from __future__ import annotations

from copy import deepcopy
from typing import Any


_BASE_RAW_MARKET: dict[str, Any] = {
    "ticker": "KXHEPL-LIVBOU-20250816-DRAW",
    "market_id": "KXHEPL-LIVBOU-20250816-DRAW",
    "title": "Liverpool vs Bournemouth",
    "yes_ask": 37,
    "close_time": "2025-08-16T14:00:00Z",
    "status": "active",
}


_BASE_NORMALIZED_MARKET: dict[str, Any] = {
    "schema_version": "v1",
    "sport": "EPL",
    "payload_kind": "kalshi_market",
    "market_id": "KXHEPL-LIVBOU-20250816-DRAW",
    "ticker": "KXHEPL-LIVBOU-20250816-DRAW",
    "game_id": "EPL-2025-08-16-LIV-BOU",
    "game_date": "2025-08-16",
    "home_team": "Liverpool",
    "away_team": "Bournemouth",
    "outcome_name": "draw",
    "bookmaker": "Kalshi",
    "market_name": "moneyline",
    "external_id": "KXHEPL-LIVBOU-20250816-DRAW",
    "price": 2.7027027027,
    "is_pregame": True,
}


_BASE_GAME_ODDS_ROW: dict[str, Any] = {
    "odds_id": "EPL-2025-08-16-LIV-BOU_kalshi_draw",
    "game_id": "EPL-2025-08-16-LIV-BOU",
    "bookmaker": "Kalshi",
    "market_name": "moneyline",
    "outcome_name": "draw",
    "price": 2.7027027027,
    "is_pregame": True,
    "external_id": "KXHEPL-LIVBOU-20250816-DRAW",
}


def build_epl_kalshi_raw_market(outcome_suffix: str = "DRAW") -> dict[str, Any]:
    """Build a deterministic raw EPL Kalshi market sample."""
    market = deepcopy(_BASE_RAW_MARKET)
    ticker = f"KXHEPL-LIVBOU-20250816-{outcome_suffix}"
    market["ticker"] = ticker
    market["market_id"] = ticker
    return market


def build_epl_kalshi_provider_market(outcome_suffix: str = "DRAW") -> dict[str, Any]:
    """Build a parseable EPL Kalshi provider market using the current ticker shape."""
    market = deepcopy(_BASE_RAW_MARKET)
    ticker = f"KXEPLGAME-250816-LIVBOU-{outcome_suffix}"
    market["ticker"] = ticker
    market["market_id"] = ticker
    return market


def build_epl_kalshi_normalized_market(outcome_name: str = "draw") -> dict[str, Any]:
    """Build the canonical normalized EPL Kalshi market payload."""
    payload = deepcopy(_BASE_NORMALIZED_MARKET)
    payload["outcome_name"] = outcome_name
    ticker_suffix = "DRAW" if outcome_name == "draw" else outcome_name.upper()
    ticker = f"KXHEPL-LIVBOU-20250816-{ticker_suffix}"
    payload["ticker"] = ticker
    payload["market_id"] = ticker
    payload["external_id"] = ticker
    return payload


def build_epl_kalshi_game_odds_row(outcome_name: str = "draw") -> dict[str, Any]:
    """Build the canonical game_odds payload for an EPL Kalshi market."""
    row = deepcopy(_BASE_GAME_ODDS_ROW)
    ticker_suffix = "DRAW" if outcome_name == "draw" else outcome_name.upper()
    ticker = f"KXHEPL-LIVBOU-20250816-{ticker_suffix}"
    row["odds_id"] = f"EPL-2025-08-16-LIV-BOU_kalshi_{outcome_name}"
    row["outcome_name"] = outcome_name
    row["external_id"] = ticker
    return row
