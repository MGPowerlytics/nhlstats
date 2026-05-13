"""Deterministic BoxScoreFetcher payload samples for contract tests.

These match the ``BoxScoreFetcher`` contract schema in
``tests/contracts/schemas/box_score_fetcher_contract_v1.json``.

Each builder returns a deep copy so callers can safely mutate the result.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_CANONICAL_GAME_ID = "NBA_20250115_LAL_GSW"
_CANONICAL_SPORT = "NBA"

_BASE_SINGLE_ROW: dict[str, Any] = {
    "team": "Los Angeles Lakers",
    "opponent": "Golden State Warriors",
    "home": True,
    "points": 112,
}

_BASE_FETCH_GAME_STATS_PAYLOAD: dict[str, Any] = {
    "game_id": _CANONICAL_GAME_ID,
    "sport": _CANONICAL_SPORT,
    "rows": [
        {
            "team": "Los Angeles Lakers",
            "opponent": "Golden State Warriors",
            "home": True,
            "points": 112,
        },
        {
            "team": "Golden State Warriors",
            "opponent": "Los Angeles Lakers",
            "home": False,
            "points": 98,
        },
    ],
    "row_count": 2,
    "schema_version": "v1",
    "payload_kind": "fetch_game_stats_result",
}

_BASE_FETCH_DATE_RANGE_PAYLOAD: dict[str, Any] = {
    "start_date": "2025-01-15",
    "end_date": "2025-01-15",
    "total_games": 1,
    "total_rows": 2,
    "games": [
        {
            "game_id": _CANONICAL_GAME_ID,
            "rows": [
                {
                    "team": "Los Angeles Lakers",
                    "opponent": "Golden State Warriors",
                    "home": True,
                    "points": 112,
                },
                {
                    "team": "Golden State Warriors",
                    "opponent": "Los Angeles Lakers",
                    "home": False,
                    "points": 98,
                },
            ],
        },
    ],
    "schema_version": "v1",
    "payload_kind": "fetch_date_range_result",
}

_BASE_UPSERT_ROWS_PAYLOAD: dict[str, Any] = {
    "rows_inserted": 2,
    "sport": _CANONICAL_SPORT,
    "schema_version": "v1",
    "payload_kind": "upsert_rows_result",
}


def build_single_box_score_row(**overrides: Any) -> dict[str, Any]:
    """Build a single canonical box-score row dict.

    Args:
        **overrides: Override specific fields (e.g. team="Celtics").

    Returns:
        A deep copy with overrides applied.
    """
    payload = deepcopy(_BASE_SINGLE_ROW)
    payload.update(overrides)
    return payload


def build_fetch_game_stats_payload(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic ``fetch_game_stats`` result payload.

    Args:
        **overrides: Override top-level fields (e.g. game_id="...").  The
            ``rows`` key can be overridden to test empty or malformed data.

    Returns:
        A deep copy with overrides applied.
    """
    payload = deepcopy(_BASE_FETCH_GAME_STATS_PAYLOAD)
    payload.update(overrides)
    return payload


def build_fetch_date_range_payload(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic ``fetch_date_range`` result payload.

    Args:
        **overrides: Override top-level fields (e.g. total_games=0).

    Returns:
        A deep copy with overrides applied.
    """
    payload = deepcopy(_BASE_FETCH_DATE_RANGE_PAYLOAD)
    payload.update(overrides)
    return payload


def build_upsert_rows_payload(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic ``upsert_rows`` result payload.

    Args:
        **overrides: Override top-level fields (e.g. rows_inserted=0).

    Returns:
        A deep copy with overrides applied.
    """
    payload = deepcopy(_BASE_UPSERT_ROWS_PAYLOAD)
    payload.update(overrides)
    return payload


def build_empty_fetch_game_stats_payload() -> dict[str, Any]:
    """Build a ``fetch_game_stats`` result with zero rows."""
    return {
        "game_id": "NBA_20250115_LAL_GSW",
        "sport": "NBA",
        "rows": [],
        "row_count": 0,
        "schema_version": "v1",
        "payload_kind": "fetch_game_stats_result",
    }


def build_empty_fetch_date_range_payload() -> dict[str, Any]:
    """Build a ``fetch_date_range`` result with zero games."""
    return {
        "start_date": "2025-01-16",
        "end_date": "2025-01-16",
        "total_games": 0,
        "total_rows": 0,
        "games": [],
        "schema_version": "v1",
        "payload_kind": "fetch_date_range_result",
    }


def build_empty_upsert_rows_payload() -> dict[str, Any]:
    """Build an ``upsert_rows`` result with zero rows inserted."""
    return {
        "rows_inserted": 0,
        "sport": "NBA",
        "schema_version": "v1",
        "payload_kind": "upsert_rows_result",
    }
