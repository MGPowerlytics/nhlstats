"""Consumer contract tests for the BetReconciliation boundary.

Validates that consumers of ``reconcile_all()`` output can trust the shape
and constraints defined in ``bet_reconciliation_contract_v1.json``:
- ``reconciliation_result`` — per-bet diff outcome
- ``reconciliation_report`` — aggregate summary
- ``kalshi_state_entry`` — remote fill snapshot
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from tests.contracts.fixtures.bet_reconciliation_samples import (
    build_kalshi_state_entry,
    build_kalshi_state_entry_open,
    build_reconciliation_report,
    build_reconciliation_report_empty,
    build_reconciliation_report_mlb,
    build_reconciliation_result,
    build_reconciliation_result_corrected,
    build_reconciliation_result_matched,
    build_reconciliation_result_multi,
)

SCHEMA_PATH = (
    Path(__file__).resolve().parent / "schemas" / "bet_reconciliation_contract_v1.json"
)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator(def_name: str) -> Draft202012Validator:
    schema = _load_schema()
    resource = Resource.from_contents(schema)
    registry = Registry().with_resource(uri=schema["$id"], resource=resource)
    return Draft202012Validator(
        {"$ref": f"{schema['$id']}#/$defs/{def_name}"}, registry=registry
    )


# ---------------------------------------------------------------------------
# reconciliation_result
# ---------------------------------------------------------------------------


class TestReconciliationResult:
    """Contract tests for the reconciliation_result definition."""

    def test_canonical_corrected_payload_satisfies_contract(self) -> None:
        """Baseline: the canonical corrected fixture must validate."""
        _validator("reconciliation_result").validate(
            build_reconciliation_result_corrected()
        )

    def test_matched_payload_satisfies_contract(self) -> None:
        """A fully matched bet (no discrepancies) must validate."""
        _validator("reconciliation_result").validate(
            build_reconciliation_result_matched()
        )

    def test_multi_discrepancy_payload_satisfies_contract(self) -> None:
        """A bet with multiple field-level discrepancies must validate."""
        _validator("reconciliation_result").validate(
            build_reconciliation_result_multi()
        )

    def test_rejects_missing_bet_id(self) -> None:
        payload = build_reconciliation_result()
        del payload["bet_id"]
        with pytest.raises(ValidationError):
            _validator("reconciliation_result").validate(payload)

    def test_rejects_missing_status(self) -> None:
        payload = build_reconciliation_result()
        del payload["status"]
        with pytest.raises(ValidationError):
            _validator("reconciliation_result").validate(payload)

    def test_rejects_missing_matched(self) -> None:
        payload = build_reconciliation_result()
        del payload["matched"]
        with pytest.raises(ValidationError):
            _validator("reconciliation_result").validate(payload)

    def test_rejects_missing_unmatched(self) -> None:
        payload = build_reconciliation_result()
        del payload["unmatched"]
        with pytest.raises(ValidationError):
            _validator("reconciliation_result").validate(payload)

    def test_rejects_missing_discrepancies(self) -> None:
        payload = build_reconciliation_result()
        del payload["discrepancies"]
        with pytest.raises(ValidationError):
            _validator("reconciliation_result").validate(payload)

    def test_unknown_field_is_rejected(self) -> None:
        """additionalProperties: false — unknown keys should fail."""
        payload = build_reconciliation_result()
        payload["unknown_field"] = "anything"
        with pytest.raises(ValidationError):
            _validator("reconciliation_result").validate(payload)

    @pytest.mark.parametrize("bad_status", ["", "unknown", "partial", "done"])
    def test_rejects_invalid_status(self, bad_status: str) -> None:
        with pytest.raises(ValidationError):
            _validator("reconciliation_result").validate(
                build_reconciliation_result(status=bad_status)
            )

    @pytest.mark.parametrize("bad_bool", ["true", 1, 0, "false", None])
    def test_rejects_non_boolean_matched(self, bad_bool: Any) -> None:
        with pytest.raises(ValidationError):
            _validator("reconciliation_result").validate(
                build_reconciliation_result(matched=bad_bool)
            )


# ---------------------------------------------------------------------------
# reconciliation_report
# ---------------------------------------------------------------------------


class TestReconciliationReport:
    """Contract tests for the reconciliation_report definition."""

    def test_canonical_report_satisfies_contract(self) -> None:
        """Baseline: the canonical NBA report must validate."""
        _validator("reconciliation_report").validate(
            build_reconciliation_report()
        )

    def test_mlb_report_satisfies_contract(self) -> None:
        """MLB variant must validate."""
        _validator("reconciliation_report").validate(
            build_reconciliation_report_mlb()
        )

    def test_empty_report_satisfies_contract(self) -> None:
        """Empty run (all zeros) must validate."""
        _validator("reconciliation_report").validate(
            build_reconciliation_report_empty()
        )

    def test_rejects_missing_total_reviewed(self) -> None:
        payload = build_reconciliation_report()
        del payload["total_reviewed"]
        with pytest.raises(ValidationError):
            _validator("reconciliation_report").validate(payload)

    def test_rejects_missing_matched(self) -> None:
        payload = build_reconciliation_report()
        del payload["matched"]
        with pytest.raises(ValidationError):
            _validator("reconciliation_report").validate(payload)

    def test_rejects_missing_unmatched(self) -> None:
        payload = build_reconciliation_report()
        del payload["unmatched"]
        with pytest.raises(ValidationError):
            _validator("reconciliation_report").validate(payload)

    def test_rejects_missing_discrepancies(self) -> None:
        payload = build_reconciliation_report()
        del payload["discrepancies"]
        with pytest.raises(ValidationError):
            _validator("reconciliation_report").validate(payload)

    def test_rejects_missing_sport(self) -> None:
        payload = build_reconciliation_report()
        del payload["sport"]
        with pytest.raises(ValidationError):
            _validator("reconciliation_report").validate(payload)

    def test_unknown_field_is_rejected(self) -> None:
        payload = build_reconciliation_report()
        payload["extra_field"] = "nope"
        with pytest.raises(ValidationError):
            _validator("reconciliation_report").validate(payload)

    @pytest.mark.parametrize("bad_count", [-1, -5, -100])
    def test_rejects_negative_total_reviewed(self, bad_count: int) -> None:
        with pytest.raises(ValidationError):
            _validator("reconciliation_report").validate(
                build_reconciliation_report(total_reviewed=bad_count)
            )

    @pytest.mark.parametrize("bad_count", [-1, -5])
    def test_rejects_negative_matched(self, bad_count: int) -> None:
        with pytest.raises(ValidationError):
            _validator("reconciliation_report").validate(
                build_reconciliation_report(matched=bad_count)
            )

    @pytest.mark.parametrize("bad_count", [-1, -5])
    def test_rejects_negative_unmatched(self, bad_count: int) -> None:
        with pytest.raises(ValidationError):
            _validator("reconciliation_report").validate(
                build_reconciliation_report(unmatched=bad_count)
            )

    @pytest.mark.parametrize("bad_count", [-1, -5])
    def test_rejects_negative_discrepancies(self, bad_count: int) -> None:
        with pytest.raises(ValidationError):
            _validator("reconciliation_report").validate(
                build_reconciliation_report(discrepancies=bad_count)
            )

    def test_rejects_non_string_sport(self) -> None:
        with pytest.raises(ValidationError):
            _validator("reconciliation_report").validate(
                build_reconciliation_report(sport=123)
            )

    def test_rejects_empty_sport(self) -> None:
        with pytest.raises(ValidationError):
            _validator("reconciliation_report").validate(
                build_reconciliation_report(sport="")
            )


# ---------------------------------------------------------------------------
# kalshi_state_entry
# ---------------------------------------------------------------------------


class TestKalshiStateEntry:
    """Contract tests for the kalshi_state_entry definition."""

    def test_canonical_entry_satisfies_contract(self) -> None:
        """Baseline: the canonical settled state entry must validate."""
        _validator("kalshi_state_entry").validate(build_kalshi_state_entry())

    def test_open_entry_satisfies_contract(self) -> None:
        """Open (unsettled) entry with null fields must validate."""
        _validator("kalshi_state_entry").validate(build_kalshi_state_entry_open())

    def test_rejects_missing_bet_id(self) -> None:
        payload = build_kalshi_state_entry()
        del payload["bet_id"]
        with pytest.raises(ValidationError):
            _validator("kalshi_state_entry").validate(payload)

    def test_rejects_missing_ticker(self) -> None:
        payload = build_kalshi_state_entry()
        del payload["ticker"]
        with pytest.raises(ValidationError):
            _validator("kalshi_state_entry").validate(payload)

    def test_rejects_missing_contracts(self) -> None:
        payload = build_kalshi_state_entry()
        del payload["contracts"]
        with pytest.raises(ValidationError):
            _validator("kalshi_state_entry").validate(payload)

    def test_rejects_missing_price_cents(self) -> None:
        payload = build_kalshi_state_entry()
        del payload["price_cents"]
        with pytest.raises(ValidationError):
            _validator("kalshi_state_entry").validate(payload)

    def test_rejects_missing_cost_dollars(self) -> None:
        payload = build_kalshi_state_entry()
        del payload["cost_dollars"]
        with pytest.raises(ValidationError):
            _validator("kalshi_state_entry").validate(payload)

    def test_rejects_missing_fees_dollars(self) -> None:
        payload = build_kalshi_state_entry()
        del payload["fees_dollars"]
        with pytest.raises(ValidationError):
            _validator("kalshi_state_entry").validate(payload)

    def test_rejects_missing_status(self) -> None:
        payload = build_kalshi_state_entry()
        del payload["status"]
        with pytest.raises(ValidationError):
            _validator("kalshi_state_entry").validate(payload)

    def test_unknown_field_is_rejected(self) -> None:
        payload = build_kalshi_state_entry()
        payload["unknown_field"] = "anything"
        with pytest.raises(ValidationError):
            _validator("kalshi_state_entry").validate(payload)

    @pytest.mark.parametrize("bad_contracts", [-1, -5, -100])
    def test_rejects_negative_contracts(self, bad_contracts: int) -> None:
        with pytest.raises(ValidationError):
            _validator("kalshi_state_entry").validate(
                build_kalshi_state_entry(contracts=bad_contracts)
            )

    @pytest.mark.parametrize("bad_price", [-1, -5])
    def test_rejects_negative_price_cents(self, bad_price: int) -> None:
        with pytest.raises(ValidationError):
            _validator("kalshi_state_entry").validate(
                build_kalshi_state_entry(price_cents=bad_price)
            )

    @pytest.mark.parametrize("bad_cost", [-1.0, -0.01])
    def test_rejects_negative_cost_dollars(self, bad_cost: float) -> None:
        with pytest.raises(ValidationError):
            _validator("kalshi_state_entry").validate(
                build_kalshi_state_entry(cost_dollars=bad_cost)
            )

    @pytest.mark.parametrize("bad_fees", [-1.0, -0.01])
    def test_rejects_negative_fees_dollars(self, bad_fees: float) -> None:
        with pytest.raises(ValidationError):
            _validator("kalshi_state_entry").validate(
                build_kalshi_state_entry(fees_dollars=bad_fees)
            )

    @pytest.mark.parametrize("bad_contracts", [1.5, "10", None])
    def test_rejects_non_integer_contracts(self, bad_contracts: Any) -> None:
        with pytest.raises(ValidationError):
            _validator("kalshi_state_entry").validate(
                build_kalshi_state_entry(contracts=bad_contracts)
            )

    def test_settled_date_is_nullable(self) -> None:
        """settled_date may be null for open bets."""
        _validator("kalshi_state_entry").validate(
            build_kalshi_state_entry(settled_date=None)
        )

    def test_payout_dollars_is_nullable(self) -> None:
        _validator("kalshi_state_entry").validate(
            build_kalshi_state_entry(payout_dollars=None)
        )

    def test_profit_dollars_is_nullable(self) -> None:
        _validator("kalshi_state_entry").validate(
            build_kalshi_state_entry(profit_dollars=None)
        )

    def test_market_title_is_nullable(self) -> None:
        _validator("kalshi_state_entry").validate(
            build_kalshi_state_entry(market_title=None)
        )
