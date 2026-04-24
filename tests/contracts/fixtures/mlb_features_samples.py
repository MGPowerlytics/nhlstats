"""Deterministic MLB feature-vector fixtures for consumer contract tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


_BASE_MLB_FEATURES_PAYLOAD: Dict[str, Any] = {
    "schema_version": "v1",
    "sport": "MLB",
    "payload_kind": "feature_vector",
    "home_team": "New York Yankees",
    "away_team": "Boston Red Sox",
    "venue": "Yankee Stadium",
    "home_pitcher_id": "543037",
    "away_pitcher_id": "519242",
    "home_runs_scored_ytd": 412.0,
    "home_runs_allowed_ytd": 388.0,
    "away_runs_scored_ytd": 401.0,
    "away_runs_allowed_ytd": 405.0,
    "home_bullpen_era": 3.45,
    "away_bullpen_era": 4.12,
    "home_rest_days": 2,
    "away_rest_days": 1,
    "market_prob": 0.56,
    "market_blend_weight": 0.25,
}


def build_mlb_features_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical MLB feature-vector payload."""
    return deepcopy(_BASE_MLB_FEATURES_PAYLOAD)
