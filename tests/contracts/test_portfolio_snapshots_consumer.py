"""Consumer contract tests for the PortfolioSnapshots → Dashboard boundary.

Validates that the ``portfolio_snapshot_result`` and ``snapshot_summary``
dicts serialize to match the frozen portfolio snapshots schema, and that
consumer-side extraction logic correctly derives metrics from
schema-compliant payloads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from tests.contracts.fixtures.portfolio_snapshots_samples import (
    build_portfolio_snapshots_empty_positions,
    build_portfolio_snapshots_loss,
    build_portfolio_snapshots_payload,
    build_portfolio_snapshots_profitable,
)

SCHEMA_PATH = (
    Path(__file__).parent / "schemas" / "portfolio_snapshots_contract_v1.json"
)


@pytest.fixture(scope="module")
def snapshots_schema() -> dict[str, Any]:
    """Load the portfolio snapshots schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate(schema: dict[str, Any], payload: dict[str, Any]) -> None:
    Draft202012Validator(schema).validate(payload)


# ---------------------------------------------------------------------------
# Fixture → schema conformance
# ---------------------------------------------------------------------------


class TestPortfolioSnapshotResultFixtures:
    """Canonical ``portfolio_snapshot_result`` fixtures must match the schema."""

    def test_profitable_snapshot_result_matches_schema(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        """Profitable snapshot result validates against the full schema as a
        nested property of the combined payload."""
        payload = build_portfolio_snapshots_profitable()
        _validate(snapshots_schema, payload)

    def test_loss_snapshot_result_validates(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_loss()
        _validate(snapshots_schema, payload)

    def test_empty_positions_snapshot_result_validates(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_empty_positions()
        _validate(snapshots_schema, payload)

    def test_snapshot_result_rejects_extra_field(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_profitable()
        payload["portfolio_snapshot_result"]["unknown_field"] = "x"
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_snapshot_result_rejects_missing_date_str(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_profitable()
        del payload["portfolio_snapshot_result"]["date_str"]
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_snapshot_result_rejects_missing_total_value(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_profitable()
        del payload["portfolio_snapshot_result"]["total_value"]
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_snapshot_result_rejects_negative_cash_balance(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_payload(
            portfolio_snapshot_result__cash_balance=-100.0
        )
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_snapshot_result_rejects_negative_position_count(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_payload(
            portfolio_snapshot_result__position_count=-1
        )
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_snapshot_result_rejects_string_total_value(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_payload(
            portfolio_snapshot_result__total_value="not-a-number"
        )
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_snapshot_result_rejects_non_integer_position_count(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_payload(
            portfolio_snapshot_result__position_count=3.5
        )
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)


class TestSnapshotSummaryFixtures:
    """Canonical ``snapshot_summary`` fixtures must match the schema."""

    def test_profitable_summary_validates(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_profitable()
        _validate(snapshots_schema, payload)

    def test_loss_summary_validates(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_loss()
        _validate(snapshots_schema, payload)

    def test_empty_positions_summary_validates(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_empty_positions()
        _validate(snapshots_schema, payload)

    def test_summary_rejects_extra_field(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_profitable()
        payload["snapshot_summary"]["unknown_field"] = "x"
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_summary_rejects_missing_start_date(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_profitable()
        del payload["snapshot_summary"]["start_date"]
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_summary_rejects_missing_end_date(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_profitable()
        del payload["snapshot_summary"]["end_date"]
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_summary_rejects_missing_snapshot_count(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_profitable()
        del payload["snapshot_summary"]["snapshot_count"]
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_summary_rejects_zero_snapshot_count(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_payload(
            snapshot_summary__snapshot_count=0
        )
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_summary_rejects_negative_snapshot_count(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_payload(
            snapshot_summary__snapshot_count=-5
        )
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_summary_rejects_string_total_return(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_payload(
            snapshot_summary__total_return="not-a-number"
        )
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_summary_rejects_non_string_start_date(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_payload(
            snapshot_summary__start_date=12345
        )
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)


# ---------------------------------------------------------------------------
# Combined payload structural tests
# ---------------------------------------------------------------------------


class TestCombinedPayloadStructure:
    """Top-level payload structure must match the schema."""

    def test_combined_payload_has_both_required_sections(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_profitable()
        _validate(snapshots_schema, payload)
        assert "portfolio_snapshot_result" in payload
        assert "snapshot_summary" in payload

    def test_combined_payload_rejects_missing_portfolio_snapshot_result(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_profitable()
        del payload["portfolio_snapshot_result"]
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_combined_payload_rejects_missing_snapshot_summary(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_profitable()
        del payload["snapshot_summary"]
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_combined_payload_rejects_extra_top_level_field(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_profitable()
        payload["extra_field"] = "x"
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)


# ---------------------------------------------------------------------------
# Consumer: Simulated dashboard extraction logic
# ---------------------------------------------------------------------------


def _extract_snapshot_metrics(payload: dict[str, Any]) -> dict[str, float]:
    """Simulate how a dashboard consumer extracts derived metrics from a
    schema-compliant portfolio snapshots payload.

    This mirrors the kind of transformation a dashboard would perform:
    - PnL ratio = unrealized_pnl / total_value (how much is floating)
    - Cash ratio = cash_balance / total_value (how much is liquid)
    - Position exposure = positions_value / total_value

    Args:
        payload: A schema-compliant portfolio snapshots payload.

    Returns:
        Dict of derived metrics.
    """
    snapshot = payload["portfolio_snapshot_result"]
    summary = payload["snapshot_summary"]

    total = snapshot["total_value"]
    pnl_ratio = snapshot["unrealized_pnl"] / total if total != 0 else 0.0
    cash_ratio = snapshot["cash_balance"] / total if total != 0 else 0.0
    exposure = snapshot["positions_value"] / total if total != 0 else 0.0

    return {
        "pnl_ratio": pnl_ratio,
        "cash_ratio": cash_ratio,
        "exposure": exposure,
        "total_return": summary["total_return"],
        "avg_daily_return": summary["avg_daily_return"],
        "snapshot_count": float(summary["snapshot_count"]),
    }


def _calculate_return_rate(payload: dict[str, Any]) -> float:
    """Simulate a dashboard's return rate calculation.

    Returns total_return / start_value where start_value is approximated
    from the relationship: total_value - total_return.

    Args:
        payload: A schema-compliant portfolio snapshots payload.

    Returns:
        Return rate as a decimal (e.g. 0.25 for 25% return).
    """
    snapshot = payload["portfolio_snapshot_result"]
    summary = payload["snapshot_summary"]

    total_value = snapshot["total_value"]
    total_return = summary["total_return"]
    start_value = total_value - total_return

    if start_value == 0:
        return 0.0
    return total_return / start_value


class TestDashboardPortfolioSnapshotsConsumer:
    """Dashboard consumer correctly extracts metrics from schema-compliant payloads."""

    def test_extracts_pnl_ratio_from_profitable_payload(self) -> None:
        payload = build_portfolio_snapshots_profitable()
        metrics = _extract_snapshot_metrics(payload)

        # unrealized_pnl=250, total_value=12500 → 250/12500 = 0.02
        assert metrics["pnl_ratio"] == pytest.approx(0.02, abs=0.001)
        assert metrics["cash_ratio"] == pytest.approx(0.68, abs=0.001)
        assert metrics["exposure"] == pytest.approx(0.32, abs=0.001)

    def test_extracts_metrics_from_loss_payload(self) -> None:
        payload = build_portfolio_snapshots_loss()
        metrics = _extract_snapshot_metrics(payload)

        # unrealized_pnl=-200, total_value=11500 → -200/11500 = -0.01739
        assert metrics["pnl_ratio"] == pytest.approx(-0.01739, abs=0.001)
        assert metrics["total_return"] == -500.0

    def test_extracts_metrics_from_empty_positions_payload(self) -> None:
        payload = build_portfolio_snapshots_empty_positions()
        metrics = _extract_snapshot_metrics(payload)

        # total_value=10000, positions_value=0, unrealized_pnl=0
        assert metrics["pnl_ratio"] == 0.0
        assert metrics["cash_ratio"] == 1.0
        assert metrics["exposure"] == 0.0
        assert metrics["total_return"] == 0.0

    def test_calculates_return_rate_profitable(self) -> None:
        payload = build_portfolio_snapshots_profitable()
        rate = _calculate_return_rate(payload)

        # total_value=12500, total_return=2500 → start=10000, rate=2500/10000=0.25
        assert rate == pytest.approx(0.25, abs=0.001)

    def test_calculates_return_rate_loss(self) -> None:
        payload = build_portfolio_snapshots_loss()
        rate = _calculate_return_rate(payload)

        # total_value=11500, total_return=-500 → start=12000, rate=-500/12000=-0.04167
        assert rate == pytest.approx(-0.04167, abs=0.001)

    def test_calculates_return_rate_empty_positions(self) -> None:
        payload = build_portfolio_snapshots_empty_positions()
        rate = _calculate_return_rate(payload)

        # total_value=10000, total_return=0 → start=10000, rate=0/10000=0.0
        assert rate == 0.0

    def test_snapshot_count_is_positive_integer(self) -> None:
        payload = build_portfolio_snapshots_profitable()
        metrics = _extract_snapshot_metrics(payload)
        assert metrics["snapshot_count"] == 15.0

    def test_pnl_ratio_sign_reflects_profit_or_loss(self) -> None:
        profitable = _extract_snapshot_metrics(build_portfolio_snapshots_profitable())
        loss = _extract_snapshot_metrics(build_portfolio_snapshots_loss())

        assert profitable["pnl_ratio"] > 0
        assert loss["pnl_ratio"] < 0

    def test_cash_ratio_plus_exposure_approx_one(self) -> None:
        """Cash ratio + exposure should approximately equal 1 (total = cash + positions)."""
        payload = build_portfolio_snapshots_profitable()
        metrics = _extract_snapshot_metrics(payload)

        # 8500/12500 + 4000/12500 = 0.68 + 0.32 = 1.0
        assert metrics["cash_ratio"] + metrics["exposure"] == pytest.approx(1.0, abs=0.001)


class TestDashboardSnapshotsConsumerRejection:
    """Consumer must reject invalid payloads before processing."""

    def test_missing_portfolio_snapshot_result_raises_validation_error(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_profitable()
        del payload["portfolio_snapshot_result"]
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_missing_snapshot_summary_raises_validation_error(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_profitable()
        del payload["snapshot_summary"]
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_extra_top_level_field_raises_validation_error(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_profitable()
        payload["extra_field"] = "should_not_exist"
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_negative_cash_balance_raises_validation_error(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_payload(
            portfolio_snapshot_result__cash_balance=-1.0
        )
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_negative_position_count_raises_validation_error(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_payload(
            portfolio_snapshot_result__position_count=-3
        )
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_string_instead_of_number_raises_validation_error(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = build_portfolio_snapshots_payload(
            portfolio_snapshot_result__total_value="invalid"
        )
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)
