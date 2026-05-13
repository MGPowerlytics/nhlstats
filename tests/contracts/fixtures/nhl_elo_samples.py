"""Deterministic NHL Elo fixtures for consumer contract tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from plugins.elo.nhl_elo_rating import NHLEloRating


NHL_HOME_TEAM = "Toronto Maple Leafs"
NHL_AWAY_TEAM = "Boston Bruins"


def build_trained_nhl_elo() -> NHLEloRating:
    """Return a deterministically-seeded :class:`NHLEloRating`.

    Trains the model with 3 updates: two home wins, then one away win.
    """
    elo = NHLEloRating(k_factor=20.0, home_advantage=65.0)
    elo.update(NHL_HOME_TEAM, NHL_AWAY_TEAM, home_win=1.0, is_neutral=False)
    elo.update(NHL_HOME_TEAM, NHL_AWAY_TEAM, home_win=1.0, is_neutral=False)
    elo.update(NHL_AWAY_TEAM, NHL_HOME_TEAM, home_win=1.0, is_neutral=False)
    return elo


def _build_payload() -> Dict[str, Any]:
    elo = build_trained_nhl_elo()
    return {
        "schema_version": "v1",
        "sport": "NHL",
        "payload_kind": "elo_prediction",
        "home_team": NHL_HOME_TEAM,
        "away_team": NHL_AWAY_TEAM,
        "home_rating": float(elo.get_rating(NHL_HOME_TEAM)),
        "away_rating": float(elo.get_rating(NHL_AWAY_TEAM)),
        "home_prob": float(elo.predict(NHL_HOME_TEAM, NHL_AWAY_TEAM)),
        "home_advantage": 65.0,
        "k_factor": 20.0,
        "is_neutral": False,
    }


_BASE_NHL_ELO_PAYLOAD: Dict[str, Any] = _build_payload()


def build_nhl_elo_prediction_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical NHL Elo prediction."""
    return deepcopy(_BASE_NHL_ELO_PAYLOAD)
