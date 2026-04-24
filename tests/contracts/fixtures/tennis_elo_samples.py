"""Deterministic Tennis Elo prediction payload builders."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_BASE_ELO_PREDICTION: dict[str, Any] = {
    "schema_version": "v1",
    "sport": "TENNIS",
    "payload_kind": "elo_prediction",
    "tour": "ATP",
    "player_a": "Djokovic N.",
    "player_b": "Alcaraz C.",
    "rating_a": 1700.0,
    "rating_b": 1620.0,
    "raw_prob_a": 0.6131923060087273,
    "calibrated_prob_a": 0.5973100780499928,
    "k_factor": 32.0,
    "home_advantage": 0.0,
    "is_neutral": True,
}


def build_tennis_elo_prediction(**overrides: Any) -> dict[str, Any]:
    """Build the canonical Tennis Elo prediction payload."""
    payload = deepcopy(_BASE_ELO_PREDICTION)
    payload.update(overrides)
    return payload


def build_tennis_elo_prediction_wta() -> dict[str, Any]:
    """Build a WTA Tennis Elo prediction payload sample."""
    return build_tennis_elo_prediction(
        tour="WTA",
        player_a="Swiatek I.",
        player_b="Gauff C.",
        rating_a=1850.0,
        rating_b=1730.0,
        raw_prob_a=0.6645617212733915,
        calibrated_prob_a=0.6438940420905286,
    )
