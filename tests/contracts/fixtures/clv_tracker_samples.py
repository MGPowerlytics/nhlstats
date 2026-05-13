"""Deterministic CLV Tracker payloads for contract tests.

These match the CLV tracker schema in
``tests/contracts/schemas/clv_tracker_contract_v1.json``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_BASE_CLV_ANALYSIS: dict[str, Any] = {
    "bet_id": "bet_clv_001",
    "sport": "NBA",
    "placed_prob": 0.65,
    "closing_prob": 0.55,
    "clv": 0.10,
    "market_close_time": "2025-06-15T23:00:00Z",
    "is_stale": False,
    "schema_version": "v1",
    "payload_kind": "clv_analysis_result",
}

_BASE_CLV_REPORT_SUMMARY: dict[str, Any] = {
    "total_bets": 100,
    "total_clv": 2.50,
    "avg_clv": 0.025,
    "positive_clv_count": 60,
    "negative_clv_count": 40,
    "sports_analyzed": 5,
    "schema_version": "v1",
    "payload_kind": "clv_report_summary",
}


def build_clv_analysis_payload(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic CLV analysis payload.

    Args:
        **overrides: Override specific fields (e.g. clv=-0.05).

    Returns:
        A deep copy of the base CLV analysis payload with overrides applied.
    """
    payload = deepcopy(_BASE_CLV_ANALYSIS)
    payload.update(overrides)
    return payload


def build_clv_report_summary_payload(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic CLV report summary payload.

    Args:
        **overrides: Override specific fields (e.g. total_bets=50).

    Returns:
        A deep copy of the base CLV report summary payload with overrides applied.
    """
    payload = deepcopy(_BASE_CLV_REPORT_SUMMARY)
    payload.update(overrides)
    return payload


def build_positive_clv_payload(**overrides: Any) -> dict[str, Any]:
    """Build a CLV analysis payload with a positive edge (good CLV).

    Positive CLV means the bet was placed at better odds than the closing market.

    Args:
        **overrides: Override specific fields.

    Returns:
        A CLV analysis payload with positive CLV.
    """
    return build_clv_analysis_payload(
        bet_id="bet_clv_pos_001",
        sport="NHL",
        placed_prob=0.70,
        closing_prob=0.50,
        clv=0.20,
        is_stale=False,
        **overrides,
    )


def build_negative_clv_payload(**overrides: Any) -> dict[str, Any]:
    """Build a CLV analysis payload with a negative edge (bad CLV).

    Negative CLV means the market moved against the placed bet.

    Args:
        **overrides: Override specific fields.

    Returns:
        A CLV analysis payload with negative CLV.
    """
    return build_clv_analysis_payload(
        bet_id="bet_clv_neg_001",
        sport="MLB",
        placed_prob=0.40,
        closing_prob=0.65,
        clv=-0.25,
        is_stale=False,
        **overrides,
    )
