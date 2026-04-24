"""Deterministic MLB ensemble I/O fixtures for consumer contract tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


HOME_TEAM = "New York Yankees"
AWAY_TEAM = "Boston Red Sox"


_BASE_ENSEMBLE_INPUT_PAYLOAD: Dict[str, Any] = {
    "schema_version": "v1",
    "sport": "MLB",
    "payload_kind": "ensemble_input",
    "home_team": HOME_TEAM,
    "away_team": AWAY_TEAM,
    "base_elo_prob": 0.541,
    "pitcher_prob": 0.523,
    "features": {
        "pythag_diff": 0.024,
        "rest_diff": 1,
        "bullpen_diff": -0.67,
        "park_factor": 1.03,
        "form_diff": 0.10,
    },
    "market_prob": 0.555,
}


_BASE_ENSEMBLE_OUTPUT_PAYLOAD: Dict[str, Any] = {
    "schema_version": "v1",
    "sport": "MLB",
    "payload_kind": "ensemble_output",
    "home_team": HOME_TEAM,
    "away_team": AWAY_TEAM,
    "blended_prob": 0.548,
    "weights": {
        "team_elo": 0.55,
        "pitcher_elo": 0.20,
        "features": 0.10,
        "market": 0.15,
    },
    "provenance": {
        "model_id": "mlb_ensemble_v1",
        "components": {
            "team_elo_logit": 0.165,
            "pitcher_logit_adj": -0.072,
            "pythag_logit_adj": 0.041,
            "rest_logit_adj": 0.012,
            "bullpen_logit_adj": -0.031,
        },
    },
}


def build_ensemble_input_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical ensemble input bundle."""
    return deepcopy(_BASE_ENSEMBLE_INPUT_PAYLOAD)


def build_ensemble_output_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical ensemble output bundle."""
    return deepcopy(_BASE_ENSEMBLE_OUTPUT_PAYLOAD)
