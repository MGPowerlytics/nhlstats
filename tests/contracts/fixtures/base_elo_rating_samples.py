"""Deterministic BaseEloRating contract fixtures.

These builders produce canonical payloads for the three contract payload
kinds (predict_result, update_result, get_rating_result) using the concrete
:class:`StandardEloRating` implementation.  All values are deterministic.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from plugins.elo.base_elo_rating import StandardEloRating


HOME_TEAM = "Home Team"
AWAY_TEAM = "Away Team"


def build_trained_elo_state() -> StandardEloRating:
    """Return a deterministically-seeded :class:`StandardEloRating`.

    Trains the model with 3 updates:
      1. Home beats Away
      2. Home beats Away
      3. Away beats Home
    Uses ``k_factor=32.0`` and ``home_advantage=50.0`` to keep ratings
    predictable but distinct.
    """
    elo = StandardEloRating(k_factor=32.0, home_advantage=50.0)
    elo.update(HOME_TEAM, AWAY_TEAM, home_won=True)
    elo.update(HOME_TEAM, AWAY_TEAM, home_won=True)
    elo.update(AWAY_TEAM, HOME_TEAM, home_won=True)
    return elo


def _inner_predict_payload() -> Dict[str, Any]:
    elo = build_trained_elo_state()
    return {
        "schema_version": "v1",
        "payload_kind": "predict_result",
        "home_team": HOME_TEAM,
        "away_team": AWAY_TEAM,
        "home_prob": float(elo.predict(HOME_TEAM, AWAY_TEAM)),
        "is_neutral": False,
    }


def _inner_update_payload() -> Dict[str, Any]:
    elo = build_trained_elo_state()
    change = elo.update(HOME_TEAM, AWAY_TEAM, home_won=True)
    return {
        "schema_version": "v1",
        "payload_kind": "update_result",
        "home_team": HOME_TEAM,
        "away_team": AWAY_TEAM,
        "home_won": True,
        "rating_change": float(change) if change is not None else 0.0,
        "home_rating_after": float(elo.get_rating(HOME_TEAM)),
        "away_rating_after": float(elo.get_rating(AWAY_TEAM)),
    }


def _inner_get_rating_payload() -> Dict[str, Any]:
    elo = build_trained_elo_state()
    return {
        "schema_version": "v1",
        "payload_kind": "get_rating_result",
        "team": HOME_TEAM,
        "rating": float(elo.get_rating(HOME_TEAM)),
    }


_BASE_PREDICT_PAYLOAD: Dict[str, Any] = _inner_predict_payload()
_BASE_UPDATE_PAYLOAD: Dict[str, Any] = _inner_update_payload()
_BASE_GET_RATING_PAYLOAD: Dict[str, Any] = _inner_get_rating_payload()


def build_predict_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical predict_result payload."""
    return deepcopy(_BASE_PREDICT_PAYLOAD)


def build_update_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical update_result payload."""
    return deepcopy(_BASE_UPDATE_PAYLOAD)


def build_get_rating_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical get_rating_result payload."""
    return deepcopy(_BASE_GET_RATING_PAYLOAD)
