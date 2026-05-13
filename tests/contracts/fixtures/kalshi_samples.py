"""Deterministic Kalshi sample payloads for contract tests.

These match the Kalshi fill, order, and market_details schemas in
``tests/contracts/schemas/``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_BASE_FILL: dict[str, Any] = {
    "ticker": "KXNBAGAME-26JAN20LAL-LAL",
    "trade_id": "abc123",
    "side": "yes",
    "count": 10,
    "count_fp": 10.0,
    "yes_price": 60,
    "yes_price_dollars": "0.60",
    "no_price": 40,
    "no_price_dollars": "0.40",
    "fee_cost": 5,
    "created_time": "2026-01-20T18:00:00Z",
}

_BASE_ORDER: dict[str, Any] = {
    "order_id": "ord_abc123",
    "client_order_id": "550e8400-e29b-41d4-a716-446655440000",
    "ticker": "KXNBAGAME-26JAN20LAL-LAL",
    "side": "yes",
    "status": "executed",
    "fill_count_fp": 10.0,
    "initial_count_fp": 10.0,
    "yes_price": 60,
    "yes_price_dollars": "0.60",
    "no_price": 40,
    "no_price_dollars": "0.40",
    "taker_fill_cost_dollars": "6.00",
    "taker_fees_dollars": "0.30",
    "created_time": "2026-01-20T18:00:00Z",
}

_BASE_MARKET_DETAILS: dict[str, Any] = {
    "status": "active",
    "result": "",
    "close_time": "2026-01-20T19:00:00Z",
    "title": "Lakers vs Celtics - Winner",
}

_BASE_FILL_NO_SIDE: dict[str, Any] = {
    "ticker": "KXNBAGAME-26JAN20LAL-LAL",
    "trade_id": "no_side_fill_001",
    "side": "no",
    "count": 5,
    "count_fp": 5.0,
    "yes_price": 55,
    "yes_price_dollars": "0.55",
    "no_price": 45,
    "no_price_dollars": "0.45",
    "fee_cost": 3,
    "created_time": "2026-01-20T18:05:00Z",
}


def build_kalshi_fill_payload(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic Kalshi fill payload matching the fill schema.

    Args:
        **overrides: Override specific fields (e.g. side=\"no\", count=20).

    Returns:
        A deep copy of the base fill payload with overrides applied.
    """
    payload = deepcopy(_BASE_FILL)
    payload.update(overrides)
    return payload


def build_kalshi_order_payload(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic Kalshi order payload matching the order schema.

    Args:
        **overrides: Override specific fields.

    Returns:
        A deep copy of the base order payload with overrides applied.
    """
    payload = deepcopy(_BASE_ORDER)
    payload.update(overrides)
    return payload


def build_kalshi_market_details_payload(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic Kalshi market details payload.

    Args:
        **overrides: Override specific fields.

    Returns:
        A deep copy of the base market details payload with overrides applied.
    """
    payload = deepcopy(_BASE_MARKET_DETAILS)
    payload.update(overrides)
    return payload


def build_kalshi_fill_no_side_payload(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic Kalshi fill payload with side=\"no\".

    Args:
        **overrides: Override specific fields.

    Returns:
        A deep copy of the base no-side fill payload with overrides applied.
    """
    payload = deepcopy(_BASE_FILL_NO_SIDE)
    payload.update(overrides)
    return payload
