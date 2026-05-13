"""Deterministic NFL Elo fixtures for consumer contract tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from plugins.elo.nfl_elo_rating import NFLEloRating


NFL_HOME_TEAM = "Kansas City Chiefs"
NFL_AWAY_TEAM = "San Francisco 49ers"


def build_trained_nfl_elo() -> NFLEloRating:
    """Return a deterministically-seeded :class:`NFLEloRating`.

    Trains the model with 3 updates: two home wins, then one away win.
    The ``k_factor`` is 20.0 and ``home_advantage`` is 65.0 (NFL defaults).
    """
    elo = NFLEloRating(k_factor=20.0, home_advantage=65.0)
    elo.update(NFL_HOME_TEAM, NFL_AWAY_TEAM, home_won=True, is_neutral=False)
    elo.update(NFL_HOME_TEAM, NFL_AWAY_TEAM, home_won=True, is_neutral=False)
    elo.update(NFL_AWAY_TEAM, NFL_HOME_TEAM, home_won=True, is_neutral=False)
    return elo


def _build_payload() -> Dict[str, Any]:
    elo = build_trained_nfl_elo()
    return {
        "schema_version": "v1",
        "sport": "NFL",
        "payload_kind": "elo_prediction",
        "home_team": NFL_HOME_TEAM,
        "away_team": NFL_AWAY_TEAM,
        "home_rating": float(elo.get_rating(NFL_HOME_TEAM)),
        "away_rating": float(elo.get_rating(NFL_AWAY_TEAM)),
        "home_prob": float(elo.predict(NFL_HOME_TEAM, NFL_AWAY_TEAM)),
        "home_advantage": 65.0,
        "k_factor": 20.0,
        "is_neutral": False,
    }


_BASE_NFL_ELO_PAYLOAD: Dict[str, Any] = _build_payload()


def build_nfl_elo_prediction_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical NFL Elo prediction."""
    return deepcopy(_BASE_NFL_ELO_PAYLOAD)
