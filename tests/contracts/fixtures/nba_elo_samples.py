"""Deterministic NBA Elo fixtures for consumer contract tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from plugins.elo.nba_elo_rating import NBAEloRating


NBA_HOME_TEAM = "Los Angeles Lakers"
NBA_AWAY_TEAM = "Boston Celtics"


def build_trained_nba_elo() -> NBAEloRating:
    """Return a deterministically-seeded :class:`NBAEloRating`.

    Trains the model with 3 updates: two home wins, then one away win.
    The ``k_factor`` is 20.0 and ``home_advantage`` is 100.0 (NBA defaults).
    """
    elo = NBAEloRating(k_factor=20.0, home_advantage=100.0)
    elo.update(NBA_HOME_TEAM, NBA_AWAY_TEAM, home_won=True)
    elo.update(NBA_HOME_TEAM, NBA_AWAY_TEAM, home_won=True)
    elo.update(NBA_AWAY_TEAM, NBA_HOME_TEAM, home_won=True)
    return elo


def _build_payload() -> Dict[str, Any]:
    elo = build_trained_nba_elo()
    return {
        "schema_version": "v1",
        "sport": "NBA",
        "payload_kind": "elo_prediction",
        "home_team": NBA_HOME_TEAM,
        "away_team": NBA_AWAY_TEAM,
        "home_rating": float(elo.get_rating(NBA_HOME_TEAM)),
        "away_rating": float(elo.get_rating(NBA_AWAY_TEAM)),
        "home_prob": float(elo.predict(NBA_HOME_TEAM, NBA_AWAY_TEAM)),
        "home_advantage": 100.0,
        "k_factor": 20.0,
        "is_neutral": False,
    }


_BASE_NBA_ELO_PAYLOAD: Dict[str, Any] = _build_payload()


def build_nba_elo_prediction_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical NBA Elo prediction."""
    return deepcopy(_BASE_NBA_ELO_PAYLOAD)
