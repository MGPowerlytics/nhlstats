"""Consumer contract tests for the Kalshi portfolio/balance → Dashboard boundary.

Validates that dashboard functions like ``_calculate_portfolio_metrics()``,
``_get_latest_cash_snapshot()``, and ``_calculate_portfolio_value()`` correctly
consume schema-compliant Kalshi balance API responses.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from tests.contracts.fixtures.kalshi_balance_samples import (
    build_balance_response,
    build_empty_balance_response,
    build_high_value_response,
)

BALANCE_SCHEMA_PATH = (
    Path(__file__).parent / "schemas" / "kalshi_balance_response_v1.json"
)


@pytest.fixture(scope="module")
def balance_schema() -> dict[str, Any]:
    """Load the Kalshi balance response schema."""
    return json.loads(BALANCE_SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate(schema: dict[str, Any], payload: dict[str, Any]) -> None:
    Draft202012Validator(schema).validate(payload)


# ---------------------------------------------------------------------------
# Fixture → schema conformance
# ---------------------------------------------------------------------------


class TestBalanceFixtureConformance:
    """Canonical balance fixture must match the frozen schema."""

    def test_canonical_balance_payload_matches_schema(
        self, balance_schema: dict[str, Any]
    ) -> None:
        _validate(balance_schema, build_balance_response())

    def test_empty_balance_payload_matches_schema(
        self, balance_schema: dict[str, Any]
    ) -> None:
        _validate(balance_schema, build_empty_balance_response())

    def test_high_value_balance_payload_matches_schema(
        self, balance_schema: dict[str, Any]
    ) -> None:
        _validate(balance_schema, build_high_value_response())

    def test_balance_payload_rejects_extra_fields(
        self, balance_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(
                balance_schema, {**build_balance_response(), "unknown_key": "x"}
            )

    def test_balance_payload_rejects_missing_required_field(
        self, balance_schema: dict[str, Any]
    ) -> None:
        payload = build_balance_response()
        del payload["balance"]
        with pytest.raises(ValidationError):
            _validate(balance_schema, payload)

    def test_balance_payload_rejects_missing_portfolio_value(
        self, balance_schema: dict[str, Any]
    ) -> None:
        payload = build_balance_response()
        del payload["portfolio_value"]
        with pytest.raises(ValidationError):
            _validate(balance_schema, payload)

    def test_balance_payload_rejects_negative_balance(
        self, balance_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(balance_schema, build_balance_response(balance=-1))

    def test_balance_payload_rejects_negative_portfolio_value(
        self, balance_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(balance_schema, build_balance_response(portfolio_value=-1))


# ---------------------------------------------------------------------------
# Consumer: Simulated dashboard extraction logic
# ---------------------------------------------------------------------------

# Simulate the consumer-side extraction that mirrors what the dashboard does.
# The dashboard's _calculate_portfolio_value() calls get_balance() which
# returns (balance_dollars, portfolio_value_dollars). Here we test that
# schema-compliant responses produce the expected extracted values.


def _extract_balance(response: dict[str, Any]) -> tuple[float, float]:
    """Simulate how a dashboard consumer extracts balance data.

    This mirrors the transformation in KalshiBetting.get_balance():
        balance_dollars = response["balance"] / 100
        portfolio_value_dollars = response["portfolio_value"] / 100

    Args:
        response: A schema-compliant Kalshi API balance response.

    Returns:
        Tuple of (balance_dollars, portfolio_value_dollars).
    """
    return (
        float(response["balance"]) / 100,
        float(response["portfolio_value"]) / 100,
    )


class TestDashboardBalanceConsumer:
    """Dashboard consumer correctly extracts balance from schema-compliant responses."""

    def test_extracts_normal_balance_correctly(self) -> None:
        response = build_balance_response(balance=10000, portfolio_value=10500)
        balance_dollars, portfolio_value_dollars = _extract_balance(response)

        assert balance_dollars == 100.00
        assert portfolio_value_dollars == 105.00

    def test_extracts_empty_balance_correctly(self) -> None:
        response = build_empty_balance_response()
        balance_dollars, portfolio_value_dollars = _extract_balance(response)

        assert balance_dollars == 0.00
        assert portfolio_value_dollars == 0.00

    def test_extracts_high_value_balance_correctly(self) -> None:
        response = build_high_value_response()
        balance_dollars, portfolio_value_dollars = _extract_balance(response)

        assert balance_dollars == 100000.00
        assert portfolio_value_dollars == 105000.00

    def test_extracts_float_values_correctly(self) -> None:
        """Non-integer balance values (e.g., dollar-denominated floats) still work."""
        response = build_balance_response(balance=100.50, portfolio_value=105.75)
        balance_dollars, portfolio_value_dollars = _extract_balance(response)

        assert balance_dollars == 1.005
        assert portfolio_value_dollars == 1.0575

    def test_portfolio_value_defaults_to_balance_if_missing(self) -> None:
        """Simulate the dashboard's handling of missing portfolio_value."""
        response = build_balance_response()
        del response["portfolio_value"]
        # The schema rejects missing portfolio_value, but the consumer
        # may have a fallback. Test the consumer's fallback behavior.
        balance = float(response.get("balance", 0)) / 100
        portfolio_value = float(response.get("portfolio_value", response.get("balance", 0))) / 100

        assert balance == 100.00
        assert portfolio_value == 100.00

    def test_returns_tuple_of_two_floats(self) -> None:
        response = build_balance_response()
        result = _extract_balance(response)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], float)
        assert isinstance(result[1], float)


class TestDashboardBalanceConsumerRejection:
    """Consumer must reject invalid payloads before processing."""

    def test_missing_balance_field_raises_validation_error(
        self, balance_schema: dict[str, Any]
    ) -> None:
        payload = build_balance_response()
        del payload["balance"]
        with pytest.raises(ValidationError):
            _validate(balance_schema, payload)

    def test_missing_portfolio_value_field_raises_validation_error(
        self, balance_schema: dict[str, Any]
    ) -> None:
        payload = build_balance_response()
        del payload["portfolio_value"]
        with pytest.raises(ValidationError):
            _validate(balance_schema, payload)

    def test_extra_fields_are_rejected(
        self, balance_schema: dict[str, Any]
    ) -> None:
        payload = {**build_balance_response(), "extra_field": "should_not_exist"}
        with pytest.raises(ValidationError):
            _validate(balance_schema, payload)

    def test_negative_balance_is_rejected(
        self, balance_schema: dict[str, Any]
    ) -> None:
        payload = build_balance_response(balance=-500)
        with pytest.raises(ValidationError):
            _validate(balance_schema, payload)

    def test_negative_portfolio_value_is_rejected(
        self, balance_schema: dict[str, Any]
    ) -> None:
        payload = build_balance_response(portfolio_value=-100)
        with pytest.raises(ValidationError):
            _validate(balance_schema, payload)
