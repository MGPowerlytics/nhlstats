"""Deterministic TheOddsAPI payload samples for contract tests.

These match the TheOddsAPI contract schema in
``tests/contracts/schemas/the_odds_api_contract_v1.json``.

Each builder returns a deep copy so callers can safely mutate the result.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_CANONICAL_SPORT = "nba"
_CANONICAL_GAME_ID = "basketball_nba_cfb8c60c1c1e1c1e1c1e1c1e"
_CANONICAL_HOME_TEAM = "Los Angeles Lakers"
_CANONICAL_AWAY_TEAM = "Golden State Warriors"
_CANONICAL_COMMENCE_TIME = "2025-01-20T19:00:00Z"

_BASE_ODDS_RESPONSE_PAYLOAD: dict[str, Any] = {
    "sport": _CANONICAL_SPORT,
    "game_id": _CANONICAL_GAME_ID,
    "home_team": _CANONICAL_HOME_TEAM,
    "away_team": _CANONICAL_AWAY_TEAM,
    "commence_time": _CANONICAL_COMMENCE_TIME,
    "bookmakers": [
        {
            "key": "draftkings",
            "title": "DraftKings",
            "markets": [
                {
                    "market_key": "h2h",
                    "outcomes": [
                        {"name": "Los Angeles Lakers", "price": 1.95, "point": None},
                        {"name": "Golden State Warriors", "price": 1.91, "point": None},
                    ],
                    "is_best": False,
                    "schema_version": "v1",
                    "payload_kind": "market_result",
                },
            ],
        },
        {
            "key": "fanduel",
            "title": "FanDuel",
            "markets": [
                {
                    "market_key": "h2h",
                    "outcomes": [
                        {"name": "Los Angeles Lakers", "price": 1.92, "point": None},
                        {"name": "Golden State Warriors", "price": 1.94, "point": None},
                    ],
                    "is_best": True,
                    "schema_version": "v1",
                    "payload_kind": "market_result",
                },
            ],
        },
    ],
    "total_bookmakers": 2,
    "schema_version": "v1",
    "payload_kind": "odds_response_result",
}

_BASE_MARKET_RESULT_PAYLOAD: dict[str, Any] = {
    "market_key": "h2h",
    "outcomes": [
        {"name": "Los Angeles Lakers", "price": 1.95, "point": None},
        {"name": "Golden State Warriors", "price": 1.91, "point": None},
    ],
    "is_best": True,
    "schema_version": "v1",
    "payload_kind": "market_result",
}

_BASE_BOOKMAKER_PAYLOAD: dict[str, Any] = {
    "key": "draftkings",
    "title": "DraftKings",
    "markets": [
        {
            "market_key": "h2h",
            "outcomes": [
                {"name": "Los Angeles Lakers", "price": 1.95, "point": None},
                {"name": "Golden State Warriors", "price": 1.91, "point": None},
            ],
            "is_best": False,
            "schema_version": "v1",
            "payload_kind": "market_result",
        },
    ],
}

_BASE_OUTCOME_PAYLOAD: dict[str, Any] = {
    "name": "Los Angeles Lakers",
    "price": 1.95,
    "point": None,
}


def build_odds_response_payload(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic odds response result payload.

    Args:
        **overrides: Override top-level fields (e.g. sport="nhl").

    Returns:
        A deep copy with overrides applied.
    """
    payload = deepcopy(_BASE_ODDS_RESPONSE_PAYLOAD)
    payload.update(overrides)
    return payload


def build_market_result_payload(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic market result payload.

    Args:
        **overrides: Override top-level fields (e.g. is_best=False).

    Returns:
        A deep copy with overrides applied.
    """
    payload = deepcopy(_BASE_MARKET_RESULT_PAYLOAD)
    payload.update(overrides)
    return payload


def build_bookmaker_payload(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic bookmaker entry payload.

    Args:
        **overrides: Override top-level fields (e.g. key="betmgm").

    Returns:
        A deep copy with overrides applied.
    """
    payload = deepcopy(_BASE_BOOKMAKER_PAYLOAD)
    payload.update(overrides)
    return payload


def build_outcome_payload(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic outcome payload.

    Args:
        **overrides: Override top-level fields (e.g. price=2.50).

    Returns:
        A deep copy with overrides applied.
    """
    payload = deepcopy(_BASE_OUTCOME_PAYLOAD)
    payload.update(overrides)
    return payload


def build_raw_api_game_response() -> dict[str, Any]:
    """Build a deterministic raw Odds API game response (pre-parsing).

    This mimics the JSON structure returned by the-odds-api.com/v4/sports/
    endpoints. Used by provider tests to simulate the external API.
    """
    return {
        "id": _CANONICAL_GAME_ID,
        "sport_key": "basketball_nba",
        "sport_title": "NBA",
        "commence_time": _CANONICAL_COMMENCE_TIME,
        "home_team": _CANONICAL_HOME_TEAM,
        "away_team": _CANONICAL_AWAY_TEAM,
        "bookmakers": [
            {
                "key": "draftkings",
                "title": "DraftKings",
                "last_update": "2025-01-20T18:30:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Los Angeles Lakers", "price": 1.95},
                            {"name": "Golden State Warriors", "price": 1.91},
                        ],
                    },
                ],
            },
            {
                "key": "fanduel",
                "title": "FanDuel",
                "last_update": "2025-01-20T18:30:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Los Angeles Lakers", "price": 1.92},
                            {"name": "Golden State Warriors", "price": 1.94},
                        ],
                    },
                ],
            },
        ],
    }


def build_raw_api_odds_response() -> dict[str, Any]:
    """Build a deterministic raw Odds API multi-game response.

    Returns a dict mirroring the JSON response from the-odds-api.com/v4/sports/
    {sport_key}/odds/ endpoint (a list of games).
    """
    return {
        "games": [build_raw_api_game_response()],
        "total_games": 1,
    }
