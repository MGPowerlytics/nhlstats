"""Deterministic Kalshi balance response payloads for contract tests.

These match the Kalshi balance response schema in
``tests/contracts/schemas/kalshi_balance_response_v1.json``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_BASE_BALANCE_RESPONSE: dict[str, Any] = {
    "balance": 10000,
    "portfolio_value": 10500,
}


def build_balance_response(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic Kalshi balance response payload.

    Args:
        **overrides: Override specific fields (e.g. balance=20000).

    Returns:
        A deep copy of the base balance payload with overrides applied.
    """
    payload = deepcopy(_BASE_BALANCE_RESPONSE)
    payload.update(overrides)
    return payload


def build_empty_balance_response() -> dict[str, Any]:
    """Build a Kalshi balance response with zero values."""
    return {"balance": 0, "portfolio_value": 0}


def build_high_value_response() -> dict[str, Any]:
    """Build a Kalshi balance response with large portfolio values."""
    return {"balance": 10000000, "portfolio_value": 10500000}
