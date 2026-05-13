"""Deterministic Tennis feature-vector payload builders."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_BASE_FEATURE_VECTOR: dict[str, Any] = {
    "schema_version": "v1",
    "sport": "TENNIS",
    "payload_kind": "feature_vector",
    "tour": "ATP",
    "player_a": "Player A",
    "player_b": "Player B",
    "target_surface": "Hard",
    "match_count_a": 18,
    "match_count_b": 21,
    "weighted_match_count_a": 12.4,
    "weighted_match_count_b": 14.7,
    "win_rate_a": 0.61,
    "win_rate_b": 0.57,
    "common_opponent_count": 4,
    "common_opponent_win_rate_diff": 0.12,
    "direct_match_count": 2,
    "direct_win_rate_a": 0.5,
    "intransitivity_complexity": 0.34,
    "serve_win_pct_a": 0.64,
    "serve_win_pct_b": 0.62,
    "return_win_pct_a": 0.39,
    "return_win_pct_b": 0.36,
    "serveadv_a": 0.28,
    "serveadv_b": 0.23,
    "complete_a": 0.2496,
    "complete_b": 0.2232,
    "fatigue_a": 31.2,
    "fatigue_b": 18.4,
    "fatigue_diff": 12.8,
    "retired_a": 0,
    "retired_b": 1,
    "age_30_a": 2.4,
    "age_30_b": 5.1,
    "rank_a": 12.0,
    "rank_b": 21.0,
    "rank_diff": -9.0,
    "data_certainty": 0.83,
}


def build_tennis_feature_vector(**overrides: Any) -> dict[str, Any]:
    """Build the canonical Tennis feature-vector payload."""
    payload = deepcopy(_BASE_FEATURE_VECTOR)
    payload.update(overrides)
    return payload


def build_low_certainty_tennis_feature_vector() -> dict[str, Any]:
    """Build a valid low-certainty Tennis feature-vector payload."""
    return build_tennis_feature_vector(
        match_count_a=1,
        match_count_b=1,
        weighted_match_count_a=0.8,
        weighted_match_count_b=0.7,
        common_opponent_count=0,
        data_certainty=0.12,
        rank_a=None,
        rank_b=None,
        rank_diff=None,
    )
