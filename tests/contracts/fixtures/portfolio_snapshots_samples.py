"""Deterministic portfolio snapshot fixtures for contract tests.

These match the ``portfolio_snapshot_result`` and ``snapshot_summary`` shapes
defined in ``portfolio_snapshots_contract_v1.json``, produced by
``plugins/portfolio_snapshots``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# ---------------------------------------------------------------------------
# Base portfolio_snapshot_result dicts
# ---------------------------------------------------------------------------

_BASE_SNAPSHOT_RESULT: dict[str, Any] = {
    "date_str": "2026-01-15",
    "total_value": 12500.00,
    "cash_balance": 8500.00,
    "positions_value": 4000.00,
    "unrealized_pnl": 250.00,
    "realized_pnl": 120.00,
    "position_count": 3,
}

_BASE_SNAPSHOT_RESULT_LOSS: dict[str, Any] = {
    "date_str": "2026-01-15",
    "total_value": 11500.00,
    "cash_balance": 8500.00,
    "positions_value": 3000.00,
    "unrealized_pnl": -200.00,
    "realized_pnl": -50.00,
    "position_count": 3,
}

_BASE_SNAPSHOT_RESULT_ZERO_POSITIONS: dict[str, Any] = {
    "date_str": "2026-01-10",
    "total_value": 10000.00,
    "cash_balance": 10000.00,
    "positions_value": 0.00,
    "unrealized_pnl": 0.00,
    "realized_pnl": 0.00,
    "position_count": 0,
}

# ---------------------------------------------------------------------------
# Base snapshot_summary dicts
# ---------------------------------------------------------------------------

_BASE_SNAPSHOT_SUMMARY: dict[str, Any] = {
    "start_date": "2026-01-01",
    "end_date": "2026-01-15",
    "snapshot_count": 15,
    "total_return": 2500.00,
    "avg_daily_return": 166.67,
}

_BASE_SNAPSHOT_SUMMARY_LOSS: dict[str, Any] = {
    "start_date": "2026-01-01",
    "end_date": "2026-01-15",
    "snapshot_count": 15,
    "total_return": -500.00,
    "avg_daily_return": -33.33,
}

# ---------------------------------------------------------------------------
# Combined payload dict
# ---------------------------------------------------------------------------

_BASE_PORTFOLIO_SNAPSHOTS_PAYLOAD: dict[str, Any] = {
    "portfolio_snapshot_result": _BASE_SNAPSHOT_RESULT,
    "snapshot_summary": _BASE_SNAPSHOT_SUMMARY,
}

_BASE_PORTFOLIO_SNAPSHOTS_LOSS_PAYLOAD: dict[str, Any] = {
    "portfolio_snapshot_result": _BASE_SNAPSHOT_RESULT_LOSS,
    "snapshot_summary": _BASE_SNAPSHOT_SUMMARY_LOSS,
}

_BASE_PORTFOLIO_SNAPSHOTS_EMPTY_POSITIONS_PAYLOAD: dict[str, Any] = {
    "portfolio_snapshot_result": _BASE_SNAPSHOT_RESULT_ZERO_POSITIONS,
    "snapshot_summary": {
        "start_date": "2026-01-01",
        "end_date": "2026-01-10",
        "snapshot_count": 10,
        "total_return": 0.00,
        "avg_daily_return": 0.00,
    },
}


# ---------------------------------------------------------------------------
# Public builders: portfolio_snapshot_result
# ---------------------------------------------------------------------------


def build_snapshot_result(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic, contract-valid ``portfolio_snapshot_result`` dict.

    Args:
        **overrides: Override specific fields (e.g. total_value=15000.0,
            date_str=\"2026-02-01\").

    Returns:
        A deep copy of the base snapshot result with overrides applied.
    """
    payload = deepcopy(_BASE_SNAPSHOT_RESULT)
    payload.update(overrides)
    return payload


def build_snapshot_result_profitable() -> dict[str, Any]:
    """Build a snapshot result with positive PnL."""
    return deepcopy(_BASE_SNAPSHOT_RESULT)


def build_snapshot_result_loss() -> dict[str, Any]:
    """Build a snapshot result with negative PnL."""
    return deepcopy(_BASE_SNAPSHOT_RESULT_LOSS)


def build_snapshot_result_zero_positions() -> dict[str, Any]:
    """Build a snapshot result with no open positions."""
    return deepcopy(_BASE_SNAPSHOT_RESULT_ZERO_POSITIONS)


# ---------------------------------------------------------------------------
# Public builders: snapshot_summary
# ---------------------------------------------------------------------------


def build_snapshot_summary(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic, contract-valid ``snapshot_summary`` dict.

    Args:
        **overrides: Override specific fields (e.g. total_return=3000.0).

    Returns:
        A deep copy of the base snapshot summary with overrides applied.
    """
    payload = deepcopy(_BASE_SNAPSHOT_SUMMARY)
    payload.update(overrides)
    return payload


def build_snapshot_summary_profitable() -> dict[str, Any]:
    """Build a snapshot summary with positive returns."""
    return deepcopy(_BASE_SNAPSHOT_SUMMARY)


def build_snapshot_summary_loss() -> dict[str, Any]:
    """Build a snapshot summary with negative returns."""
    return deepcopy(_BASE_SNAPSHOT_SUMMARY_LOSS)


# ---------------------------------------------------------------------------
# Public builders: combined payload
# ---------------------------------------------------------------------------


def build_portfolio_snapshots_payload(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic, contract-valid combined portfolio snapshots payload.

    Supports double-underscore traversal for nested overrides
    (e.g. ``portfolio_snapshot_result__total_value=15000``).

    Args:
        **overrides: Override fields at top level or nested via
            ``field__subfield`` convention.

    Returns:
        A deep copy of the base combined payload with overrides applied.
    """
    payload = deepcopy(_BASE_PORTFOLIO_SNAPSHOTS_PAYLOAD)

    snapshot_overrides: dict[str, Any] = {}
    summary_overrides: dict[str, Any] = {}
    top_overrides: dict[str, Any] = {}

    for key, value in overrides.items():
        if key.startswith("portfolio_snapshot_result__"):
            snapshot_overrides[key.replace("portfolio_snapshot_result__", "")] = value
        elif key.startswith("snapshot_summary__"):
            summary_overrides[key.replace("snapshot_summary__", "")] = value
        else:
            top_overrides[key] = value

    payload.update(top_overrides)
    if snapshot_overrides:
        payload["portfolio_snapshot_result"] = {
            **payload["portfolio_snapshot_result"],
            **snapshot_overrides,
        }
    if summary_overrides:
        payload["snapshot_summary"] = {
            **payload["snapshot_summary"],
            **summary_overrides,
        }
    return payload


def build_portfolio_snapshots_profitable() -> dict[str, Any]:
    """Build a combined payload with profitable PnL."""
    return deepcopy(_BASE_PORTFOLIO_SNAPSHOTS_PAYLOAD)


def build_portfolio_snapshots_loss() -> dict[str, Any]:
    """Build a combined payload with negative PnL."""
    return deepcopy(_BASE_PORTFOLIO_SNAPSHOTS_LOSS_PAYLOAD)


def build_portfolio_snapshots_empty_positions() -> dict[str, Any]:
    """Build a combined payload with zero positions across the board."""
    return deepcopy(_BASE_PORTFOLIO_SNAPSHOTS_EMPTY_POSITIONS_PAYLOAD)
