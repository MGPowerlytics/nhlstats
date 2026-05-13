"""Deterministic BetReconciliation payloads for contract tests.

These match the schemas in
``tests/contracts/schemas/bet_reconciliation_contract_v1.json``:
- ``reconciliation_result`` — per-bet diff outcome
- ``reconciliation_report`` — aggregate summary
- ``kalshi_state_entry`` — remote fill snapshot
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# ---------------------------------------------------------------------------
# Base discrepancy entries
# ---------------------------------------------------------------------------

_BASE_DISCREPANCIES_MATCHED: list[dict[str, Any]] = []

_BASE_DISCREPANCIES_STATUS_CHANGE: list[dict[str, Any]] = [
    {"field": "status", "old": "open", "new": "settled"},
]

_BASE_DISCREPANCIES_MULTI: list[dict[str, Any]] = [
    {"field": "status", "old": "open", "new": "settled"},
    {"field": "settled_date", "old": None, "new": "2026-04-07"},
    {"field": "payout_dollars", "old": None, "new": 150.0},
    {"field": "profit_dollars", "old": None, "new": 45.0},
]

# ---------------------------------------------------------------------------
# Base reconciliation_result dicts
# ---------------------------------------------------------------------------

_BASE_RECONCILIATION_RESULT_MATCHED: dict[str, Any] = {
    "bet_id": "KXNBAGAME-26JAN20LAL-LAL_home",
    "status": "matched",
    "matched": True,
    "unmatched": False,
    "discrepancies": _BASE_DISCREPANCIES_MATCHED,
}

_BASE_RECONCILIATION_RESULT_CORRECTED: dict[str, Any] = {
    "bet_id": "KXMLBGAME-25APR15NYYBOS-NYY_home",
    "status": "corrected",
    "matched": False,
    "unmatched": True,
    "discrepancies": _BASE_DISCREPANCIES_STATUS_CHANGE,
}

_BASE_RECONCILIATION_RESULT_MULTI: dict[str, Any] = {
    "bet_id": "KXATPMATCH-26JAN20ALCARAZ-ZVEREV-ALCARAZ_home",
    "status": "corrected",
    "matched": False,
    "unmatched": True,
    "discrepancies": _BASE_DISCREPANCIES_MULTI,
}

# ---------------------------------------------------------------------------
# Base reconciliation_report dicts
# ---------------------------------------------------------------------------

_BASE_RECONCILIATION_REPORT: dict[str, Any] = {
    "total_reviewed": 10,
    "matched": 6,
    "unmatched": 4,
    "discrepancies": 3,
    "corrected": 3,
    "missing_locally_inserted": 1,
    "missing_on_kalshi": 0,
    "audit_rows_written": 7,
    "excluded_by_cutoff": 2,
    "sport": "NBA",
}

_BASE_RECONCILIATION_REPORT_MLB: dict[str, Any] = {
    "total_reviewed": 25,
    "matched": 20,
    "unmatched": 5,
    "discrepancies": 4,
    "corrected": 4,
    "missing_locally_inserted": 2,
    "missing_on_kalshi": 1,
    "audit_rows_written": 9,
    "excluded_by_cutoff": 0,
    "sport": "MLB",
}

_BASE_RECONCILIATION_REPORT_EMPTY: dict[str, Any] = {
    "total_reviewed": 0,
    "matched": 0,
    "unmatched": 0,
    "discrepancies": 0,
    "corrected": 0,
    "missing_locally_inserted": 0,
    "missing_on_kalshi": 0,
    "audit_rows_written": 0,
    "excluded_by_cutoff": 0,
    "sport": "TENNIS",
}

# ---------------------------------------------------------------------------
# Base kalshi_state_entry dicts
# ---------------------------------------------------------------------------

_BASE_KALSHI_STATE_ENTRY: dict[str, Any] = {
    "bet_id": "KXNBAGAME-26JAN20LAL-LAL_home",
    "ticker": "KXNBAGAME-26JAN20LAL-LAL",
    "contracts": 10,
    "price_cents": 55,
    "cost_dollars": 5.50,
    "fees_dollars": 0.25,
    "status": "settled",
    "settled_date": "2026-01-21",
    "payout_dollars": 10.00,
    "profit_dollars": 4.25,
    "market_title": "Lakers vs Celtics - Winner",
}

_BASE_KALSHI_STATE_ENTRY_OPEN: dict[str, Any] = {
    "bet_id": "KXMLBGAME-25APR15NYYBOS-NYY_home",
    "ticker": "KXMLBGAME-25APR15NYYBOS-NYY",
    "contracts": 5,
    "price_cents": 60,
    "cost_dollars": 3.00,
    "fees_dollars": 0.15,
    "status": "open",
    "settled_date": None,
    "payout_dollars": None,
    "profit_dollars": None,
    "market_title": "Yankees vs Red Sox - Winner",
}


# ---------------------------------------------------------------------------
# Public builders
# ---------------------------------------------------------------------------


def build_reconciliation_result(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic, contract-valid ``reconciliation_result`` dict.

    Args:
        **overrides: Override specific fields.

    Returns:
        A deep copy of the base reconciled payload with overrides applied.
    """
    payload = deepcopy(_BASE_RECONCILIATION_RESULT_CORRECTED)
    payload.update(overrides)
    return payload


def build_reconciliation_result_matched() -> dict[str, Any]:
    """Build a reconciliation_result for a fully matched bet."""
    return deepcopy(_BASE_RECONCILIATION_RESULT_MATCHED)


def build_reconciliation_result_corrected() -> dict[str, Any]:
    """Build a reconciliation_result for a bet that was corrected."""
    return deepcopy(_BASE_RECONCILIATION_RESULT_CORRECTED)


def build_reconciliation_result_multi() -> dict[str, Any]:
    """Build a reconciliation_result with multiple field discrepancies."""
    return deepcopy(_BASE_RECONCILIATION_RESULT_MULTI)


def build_reconciliation_report(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic, contract-valid ``reconciliation_report`` dict.

    Args:
        **overrides: Override specific fields.

    Returns:
        A deep copy of the base report with overrides applied.
    """
    payload = deepcopy(_BASE_RECONCILIATION_REPORT)
    payload.update(overrides)
    return payload


def build_reconciliation_report_mlb() -> dict[str, Any]:
    """Build a reconciliation report for MLB."""
    return deepcopy(_BASE_RECONCILIATION_REPORT_MLB)


def build_reconciliation_report_empty() -> dict[str, Any]:
    """Build a reconciliation report with zero values (empty run)."""
    return deepcopy(_BASE_RECONCILIATION_REPORT_EMPTY)


def build_kalshi_state_entry(**overrides: Any) -> dict[str, Any]:
    """Build a deterministic, contract-valid ``kalshi_state_entry`` dict.

    Args:
        **overrides: Override specific fields.

    Returns:
        A deep copy of the base state entry with overrides applied.
    """
    payload = deepcopy(_BASE_KALSHI_STATE_ENTRY)
    payload.update(overrides)
    return payload


def build_kalshi_state_entry_open() -> dict[str, Any]:
    """Build a kalshi_state_entry for an open (unsettled) position."""
    return deepcopy(_BASE_KALSHI_STATE_ENTRY_OPEN)
