"""Deterministic MLB Glicko-2 fixtures for consumer contract tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from plugins.glicko2_rating import MLBGlicko2Rating


HOME_TEAM = "New York Yankees"
AWAY_TEAM = "Boston Red Sox"


def build_trained_mlb_glicko2() -> MLBGlicko2Rating:
    """Return a deterministically-seeded :class:`MLBGlicko2Rating`."""
    glicko = MLBGlicko2Rating()
    glicko.update(HOME_TEAM, AWAY_TEAM, True)
    glicko.update(HOME_TEAM, AWAY_TEAM, True)
    glicko.update(AWAY_TEAM, HOME_TEAM, False)
    return glicko


def _build_team_rating_payload() -> Dict[str, Any]:
    glicko = build_trained_mlb_glicko2()
    rating = glicko.get_rating(HOME_TEAM)
    return {
        "schema_version": "v1",
        "sport": "MLB",
        "payload_kind": "glicko2_rating",
        "team": HOME_TEAM,
        "rating": float(rating["rating"]),
        "rd": float(rating["rd"]),
        "vol": float(rating["vol"]),
    }


def _build_prediction_payload() -> Dict[str, Any]:
    glicko = build_trained_mlb_glicko2()
    home = glicko.get_rating(HOME_TEAM)
    away = glicko.get_rating(AWAY_TEAM)
    return {
        "schema_version": "v1",
        "sport": "MLB",
        "payload_kind": "glicko2_prediction",
        "home_team": HOME_TEAM,
        "away_team": AWAY_TEAM,
        "home_rating": {
            "rating": float(home["rating"]),
            "rd": float(home["rd"]),
            "vol": float(home["vol"]),
        },
        "away_rating": {
            "rating": float(away["rating"]),
            "rd": float(away["rd"]),
            "vol": float(away["vol"]),
        },
        "prob": float(glicko.predict(HOME_TEAM, AWAY_TEAM)),
        "home_advantage": float(glicko.home_advantage),
    }


_BASE_TEAM_RATING_PAYLOAD: Dict[str, Any] = _build_team_rating_payload()
_BASE_PREDICTION_PAYLOAD: Dict[str, Any] = _build_prediction_payload()


def build_glicko2_team_rating_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical Glicko-2 team rating payload."""
    return deepcopy(_BASE_TEAM_RATING_PAYLOAD)


def build_glicko2_prediction_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical Glicko-2 prediction payload."""
    return deepcopy(_BASE_PREDICTION_PAYLOAD)
