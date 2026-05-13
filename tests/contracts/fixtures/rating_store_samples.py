"""Deterministic RatingStore contract fixtures for consumer contract tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


def build_save_rating_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical save_rating result payload.

    Represents a persisted Elo rating for a team in a given sport,
    as consumed by downstream components that depend on RatingStore.
    """
    return deepcopy(_BASE_SAVE_RATING_PAYLOAD)


def build_load_rating_payload_found() -> Dict[str, Any]:
    """Return a payload for a successful rating lookup (team exists)."""
    return deepcopy(_BASE_LOAD_RATING_FOUND_PAYLOAD)


def build_load_rating_payload_not_found() -> Dict[str, Any]:
    """Return a payload for a rating lookup where the team has no rating."""
    return deepcopy(_BASE_LOAD_RATING_NOT_FOUND_PAYLOAD)


def build_load_all_ratings_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical load_all_ratings result payload.

    Represents the full rating map for a sport, as consumed by
    components that need all current Elo ratings (e.g. sport-specific
    Elo classes).
    """
    return deepcopy(_BASE_LOAD_ALL_RATINGS_PAYLOAD)


_BASE_SAVE_RATING_PAYLOAD: Dict[str, Any] = {
    "team": "NYY",
    "rating": 1520.0,
    "sport": "MLB",
    "timestamp": "2025-01-15T14:30:00",
    "schema_version": "v1",
    "payload_kind": "save_rating_result",
}

_BASE_LOAD_RATING_FOUND_PAYLOAD: Dict[str, Any] = {
    "team": "NYY",
    "rating": 1520.0,
    "sport": "MLB",
    "found": True,
    "schema_version": "v1",
    "payload_kind": "load_rating_result",
}

_BASE_LOAD_RATING_NOT_FOUND_PAYLOAD: Dict[str, Any] = {
    "team": "UNKN",
    "rating": None,
    "sport": "MLB",
    "found": False,
    "schema_version": "v1",
    "payload_kind": "load_rating_result",
}

_BASE_LOAD_ALL_RATINGS_PAYLOAD: Dict[str, Any] = {
    "sport": "MLB",
    "ratings": {
        "NYY": 1520.0,
        "BOS": 1485.0,
        "LAD": 1510.0,
        "SFG": 1475.0,
    },
    "count": 4,
    "schema_version": "v1",
    "payload_kind": "load_all_ratings_result",
}
