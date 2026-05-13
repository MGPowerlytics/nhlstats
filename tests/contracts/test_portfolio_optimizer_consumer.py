"""Consumer contract tests for the PortfolioOptimizer boundary.

Validates that ``portfolio_allocation_result`` and ``optimization_summary``
payloads conform to the ``portfolio_optimizer_contract_v1.json`` schema.

Uses the ``$defs/portfolio_allocation_result`` and
``$defs/optimization_summary`` definitions from the contract schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError, validate

from tests.contracts.fixtures.portfolio_optimizer_samples import (
    build_optimization_summary_payload,
    build_portfolio_allocation_payload,
)

SCHEMA_PATH = Path(__file__).parent / "schemas" / "portfolio_optimizer_contract_v1.json"


@pytest.fixture(scope="module")
def contract_schema() -> dict[str, Any]:
    """Load the portfolio optimizer contract schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Helpers: validate against a named $def
# ---------------------------------------------------------------------------

ALLOCATION_VALIDATOR_CACHE: dict[str, Any] = {}


def _allocation_schema(contract_schema: dict[str, Any]) -> dict[str, Any]:
    """Build a standalone schema for the ``portfolio_allocation_result`` def."""
    key = "allocation"
    if key not in ALLOCATION_VALIDATOR_CACHE:
        ALLOCATION_VALIDATOR_CACHE[key] = {
            "$schema": contract_schema["$schema"],
            "$ref": "#/$defs/portfolio_allocation_result",
            "$defs": contract_schema["$defs"],
        }
    return ALLOCATION_VALIDATOR_CACHE[key]


SUMMARY_VALIDATOR_CACHE: dict[str, Any] = {}


def _summary_schema(contract_schema: dict[str, Any]) -> dict[str, Any]:
    """Build a standalone schema for the ``optimization_summary`` def."""
    key = "summary"
    if key not in SUMMARY_VALIDATOR_CACHE:
        SUMMARY_VALIDATOR_CACHE[key] = {
            "$schema": contract_schema["$schema"],
            "$ref": "#/$defs/optimization_summary",
            "$defs": contract_schema["$defs"],
        }
    return SUMMARY_VALIDATOR_CACHE[key]


# ---------------------------------------------------------------------------
# Portfolio Allocation Result tests
# ---------------------------------------------------------------------------


class TestPortfolioAllocationResultSchema:
    """``portfolio_allocation_result`` payload must conform to the contract schema."""

    def test_valid_allocation_passes_schema(
        self, contract_schema: dict[str, Any]
    ) -> None:
        """A canonical allocation payload must validate against the schema."""
        payload = build_portfolio_allocation_payload()
        validate(payload, _allocation_schema(contract_schema))

    def test_bet_size_non_negative(self, contract_schema: dict[str, Any]) -> None:
        """bet_size must be >= 0."""
        schema = _allocation_schema(contract_schema)
        validate(build_portfolio_allocation_payload(bet_size=0.0), schema)
        validate(build_portfolio_allocation_payload(bet_size=100.0), schema)
        with pytest.raises(ValidationError):
            validate(build_portfolio_allocation_payload(bet_size=-1.0), schema)

    def test_kelly_fraction_non_negative(
        self, contract_schema: dict[str, Any]
    ) -> None:
        """kelly_fraction must be >= 0."""
        schema = _allocation_schema(contract_schema)
        validate(build_portfolio_allocation_payload(kelly_fraction=0.0), schema)
        validate(build_portfolio_allocation_payload(kelly_fraction=0.5), schema)
        with pytest.raises(ValidationError):
            validate(build_portfolio_allocation_payload(kelly_fraction=-0.1), schema)

    def test_allocation_pct_in_zero_one_range(
        self, contract_schema: dict[str, Any]
    ) -> None:
        """allocation_pct must be in [0, 1]."""
        schema = _allocation_schema(contract_schema)
        validate(build_portfolio_allocation_payload(allocation_pct=0.0), schema)
        validate(build_portfolio_allocation_payload(allocation_pct=0.5), schema)
        validate(build_portfolio_allocation_payload(allocation_pct=1.0), schema)
        with pytest.raises(ValidationError):
            validate(build_portfolio_allocation_payload(allocation_pct=-0.01), schema)
        with pytest.raises(ValidationError):
            validate(build_portfolio_allocation_payload(allocation_pct=1.01), schema)

    def test_missing_field_rejected(self, contract_schema: dict[str, Any]) -> None:
        """Missing required fields must be rejected."""
        schema = _allocation_schema(contract_schema)
        for field in ("bet_size", "kelly_fraction", "allocation_pct", "opportunity", "schema_version", "payload_kind"):  # noqa: E501
            payload = build_portfolio_allocation_payload()
            del payload[field]
            with pytest.raises(ValidationError):
                validate(payload, schema)

    def test_unknown_field_rejected(self, contract_schema: dict[str, Any]) -> None:
        """Unknown top-level fields must be rejected (additionalProperties: false)."""
        schema = _allocation_schema(contract_schema)
        payload = build_portfolio_allocation_payload()
        payload["unknown_field"] = "x"
        with pytest.raises(ValidationError):
            validate(payload, schema)

    def test_unknown_opportunity_field_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        """Unknown opportunity sub-fields must be rejected."""
        schema = _allocation_schema(contract_schema)
        payload = build_portfolio_allocation_payload()
        payload["opportunity"]["unknown_opp_field"] = "y"
        with pytest.raises(ValidationError):
            validate(payload, schema)

    def test_schema_version_constrained(self, contract_schema: dict[str, Any]) -> None:
        """schema_version must be \"v1\"."""
        schema = _allocation_schema(contract_schema)
        validate(build_portfolio_allocation_payload(), schema)
        with pytest.raises(ValidationError):
            validate(build_portfolio_allocation_payload(schema_version="v2"), schema)

    def test_payload_kind_constrained(self, contract_schema: dict[str, Any]) -> None:
        """payload_kind must be \"portfolio_allocation\"."""
        schema = _allocation_schema(contract_schema)
        validate(build_portfolio_allocation_payload(), schema)
        with pytest.raises(ValidationError):
            validate(build_portfolio_allocation_payload(payload_kind="other"), schema)

    def test_confidence_enum_constrained(
        self, contract_schema: dict[str, Any]
    ) -> None:
        """confidence must be one of HIGH, MEDIUM, LOW."""
        schema = _allocation_schema(contract_schema)
        payload = build_portfolio_allocation_payload()
        payload["opportunity"]["confidence"] = "HIGH"
        validate(payload, schema)
        payload["opportunity"]["confidence"] = "MEDIUM"
        validate(payload, schema)
        payload["opportunity"]["confidence"] = "LOW"
        validate(payload, schema)
        payload["opportunity"]["confidence"] = "Unknown"
        with pytest.raises(ValidationError):
            validate(payload, schema)

    def test_opp_missing_required_field_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        """Missing required fields in opportunity must be rejected."""
        schema = _allocation_schema(contract_schema)
        for field in ("sport", "ticker", "team", "opponent", "elo_prob", "market_prob", "edge", "confidence"):  # noqa: E501
            payload = build_portfolio_allocation_payload()
            del payload["opportunity"][field]
            with pytest.raises(ValidationError):
                validate(payload, schema)

    def test_probabilities_in_range(self, contract_schema: dict[str, Any]) -> None:
        """elo_prob and market_prob must be in [0, 1]."""
        schema = _allocation_schema(contract_schema)
        payload = build_portfolio_allocation_payload()
        payload["opportunity"]["elo_prob"] = 0.5
        payload["opportunity"]["market_prob"] = 0.5
        validate(payload, schema)
        payload["opportunity"]["elo_prob"] = -0.1
        with pytest.raises(ValidationError):
            validate(payload, schema)
        payload["opportunity"]["elo_prob"] = 1.5
        with pytest.raises(ValidationError):
            validate(payload, schema)

    def test_ask_prices_non_negative(self, contract_schema: dict[str, Any]) -> None:
        """yes_ask and no_ask must be >= 0."""
        schema = _allocation_schema(contract_schema)
        payload = build_portfolio_allocation_payload()
        payload["opportunity"]["yes_ask"] = 0
        payload["opportunity"]["no_ask"] = 0
        validate(payload, schema)
        payload["opportunity"]["yes_ask"] = -1
        with pytest.raises(ValidationError):
            validate(payload, schema)
        payload["opportunity"]["yes_ask"] = 0
        payload["opportunity"]["no_ask"] = -1
        with pytest.raises(ValidationError):
            validate(payload, schema)


# ---------------------------------------------------------------------------
# Optimization Summary tests
# ---------------------------------------------------------------------------


class TestOptimizationSummarySchema:
    """``optimization_summary`` payload must conform to the contract schema."""

    def test_valid_summary_passes_schema(
        self, contract_schema: dict[str, Any]
    ) -> None:
        """A canonical summary payload must validate against the schema."""
        payload = build_optimization_summary_payload()
        validate(payload, _summary_schema(contract_schema))

    def test_total_opportunities_non_negative(
        self, contract_schema: dict[str, Any]
    ) -> None:
        """total_opportunities must be >= 0."""
        schema = _summary_schema(contract_schema)
        validate(build_optimization_summary_payload(total_opportunities=0), schema)
        validate(build_optimization_summary_payload(total_opportunities=10), schema)
        with pytest.raises(ValidationError):
            validate(build_optimization_summary_payload(total_opportunities=-1), schema)

    def test_filtered_count_non_negative(
        self, contract_schema: dict[str, Any]
    ) -> None:
        """filtered_count must be >= 0."""
        schema = _summary_schema(contract_schema)
        validate(build_optimization_summary_payload(filtered_count=0), schema)
        with pytest.raises(ValidationError):
            validate(build_optimization_summary_payload(filtered_count=-1), schema)

    def test_allocations_count_non_negative(
        self, contract_schema: dict[str, Any]
    ) -> None:
        """allocations_count must be >= 0."""
        schema = _summary_schema(contract_schema)
        validate(build_optimization_summary_payload(allocations_count=0), schema)
        with pytest.raises(ValidationError):
            validate(build_optimization_summary_payload(allocations_count=-1), schema)

    def test_total_bet_size_non_negative(
        self, contract_schema: dict[str, Any]
    ) -> None:
        """total_bet_size must be >= 0."""
        schema = _summary_schema(contract_schema)
        validate(build_optimization_summary_payload(total_bet_size=0.0), schema)
        validate(build_optimization_summary_payload(total_bet_size=100.0), schema)
        with pytest.raises(ValidationError):
            validate(build_optimization_summary_payload(total_bet_size=-1.0), schema)

    def test_summary_missing_field_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        """Missing required fields in summary must be rejected."""
        schema = _summary_schema(contract_schema)
        for field in ("date_str", "total_opportunities", "filtered_count", "allocations_count", "total_bet_size", "schema_version", "payload_kind"):  # noqa: E501
            payload = build_optimization_summary_payload()
            del payload[field]
            with pytest.raises(ValidationError):
                validate(payload, schema)

    def test_summary_unknown_field_rejected(
        self, contract_schema: dict[str, Any]
    ) -> None:
        """Unknown fields in summary must be rejected (additionalProperties: false)."""
        schema = _summary_schema(contract_schema)
        payload = build_optimization_summary_payload()
        payload["unknown_summary_field"] = "z"
        with pytest.raises(ValidationError):
            validate(payload, schema)

    def test_summary_schema_version_constrained(
        self, contract_schema: dict[str, Any]
    ) -> None:
        """schema_version must be \"v1\"."""
        schema = _summary_schema(contract_schema)
        validate(build_optimization_summary_payload(), schema)
        with pytest.raises(ValidationError):
            validate(build_optimization_summary_payload(schema_version="v2"), schema)

    def test_summary_payload_kind_constrained(
        self, contract_schema: dict[str, Any]
    ) -> None:
        """payload_kind must be \"optimization_summary\"."""
        schema = _summary_schema(contract_schema)
        validate(build_optimization_summary_payload(), schema)
        with pytest.raises(ValidationError):
            validate(
                build_optimization_summary_payload(payload_kind="other"), schema
            )
