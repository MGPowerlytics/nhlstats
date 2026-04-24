"""Deterministic MLB base-Elo fixtures for consumer contract tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from plugins.elo.mlb_elo_rating import MLBEloRating


MLB_HOME_TEAM = "New York Yankees"
MLB_AWAY_TEAM = "Boston Red Sox"


def build_trained_mlb_elo() -> MLBEloRating:
    """Return a deterministically-seeded :class:`MLBEloRating`."""
    elo = MLBEloRating(k_factor=4.0, home_advantage=20.0)
    elo.update(MLB_HOME_TEAM, MLB_AWAY_TEAM, True)
    elo.update(MLB_HOME_TEAM, MLB_AWAY_TEAM, True)
    elo.update(MLB_AWAY_TEAM, MLB_HOME_TEAM, False)
    return elo


def _build_payload() -> Dict[str, Any]:
    elo = build_trained_mlb_elo()
    return {
        "schema_version": "v1",
        "sport": "MLB",
        "payload_kind": "elo_prediction",
        "home_team": MLB_HOME_TEAM,
        "away_team": MLB_AWAY_TEAM,
        "home_rating": float(elo.get_rating(MLB_HOME_TEAM)),
        "away_rating": float(elo.get_rating(MLB_AWAY_TEAM)),
        "home_prob": float(elo.predict(MLB_HOME_TEAM, MLB_AWAY_TEAM)),
        "home_advantage": 20.0,
        "k_factor": 4.0,
        "is_neutral": False,
    }


_BASE_MLB_ELO_PAYLOAD: Dict[str, Any] = _build_payload()


def build_mlb_elo_prediction_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical MLB Elo prediction."""
    return deepcopy(_BASE_MLB_ELO_PAYLOAD)
