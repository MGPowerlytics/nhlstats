from __future__ import annotations

from copy import deepcopy
from typing import Any


_BASE_RAW_MARKET: dict[str, Any] = {
    "ticker": "KXMLBGAME-24APR21LADSF-LAD",
    "market_id": "KXMLBGAME-24APR21LADSF-LAD",
    "title": "Los Angeles Dodgers at San Francisco Giants",
    "yes_ask": 37,
    "close_time": "2024-04-21T20:10:00Z",
    "status": "active",
}


_BASE_NORMALIZED_MARKET: dict[str, Any] = {
    "schema_version": "v1",
    "sport": "MLB",
    "payload_kind": "kalshi_market",
    "market_id": "KXMLBGAME-24APR21LADSF-LAD",
    "ticker": "KXMLBGAME-24APR21LADSF-LAD",
    "game_id": "MLB_20240421_SANFRANCISCOGIANTS_LOSANGELESDODGERS",
    "game_date": "2024-04-21",
    "home_team": "San Francisco Giants",
    "away_team": "Los Angeles Dodgers",
    "outcome_name": "away",
    "bookmaker": "Kalshi",
    "market_name": "moneyline",
    "external_id": "KXMLBGAME-24APR21LADSF-LAD",
    "price": 2.7027027027,
    "is_pregame": True,
}


_BASE_GAME_ODDS_ROW: dict[str, Any] = {
    "odds_id": "MLB_20240421_SANFRANCISCOGIANTS_LOSANGELESDODGERS_kalshi_away",
    "game_id": "MLB_20240421_SANFRANCISCOGIANTS_LOSANGELESDODGERS",
    "bookmaker": "Kalshi",
    "market_name": "moneyline",
    "outcome_name": "away",
    "price": 2.7027027027,
    "is_pregame": True,
    "external_id": "KXMLBGAME-24APR21LADSF-LAD",
}


def build_mlb_kalshi_raw_market(outcome_suffix: str = "LAD") -> dict[str, Any]:
    """Build a deterministic raw MLB Kalshi market sample."""
    market = deepcopy(_BASE_RAW_MARKET)
    ticker = f"KXMLBGAME-24APR21LADSF-{outcome_suffix}"
    market["ticker"] = ticker
    market["market_id"] = ticker
    return market


def build_mlb_kalshi_normalized_market(outcome_name: str = "away") -> dict[str, Any]:
    """Build the canonical normalized MLB Kalshi market payload."""
    payload = deepcopy(_BASE_NORMALIZED_MARKET)
    payload["outcome_name"] = outcome_name
    suffix = "LAD" if outcome_name == "away" else "SF"
    ticker = f"KXMLBGAME-24APR21LADSF-{suffix}"
    payload["ticker"] = ticker
    payload["market_id"] = ticker
    payload["external_id"] = ticker
    return payload


def build_mlb_kalshi_game_odds_row(outcome_name: str = "away") -> dict[str, Any]:
    """Build the canonical game_odds payload for an MLB Kalshi market."""
    row = deepcopy(_BASE_GAME_ODDS_ROW)
    suffix = "LAD" if outcome_name == "away" else "SF"
    ticker = f"KXMLBGAME-24APR21LADSF-{suffix}"
    row["odds_id"] = (
        f"MLB_20240421_SANFRANCISCOGIANTS_LOSANGELESDODGERS_kalshi_{outcome_name}"
    )
    row["outcome_name"] = outcome_name
    row["external_id"] = ticker
    return row
