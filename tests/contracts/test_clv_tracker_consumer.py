"""Consumer contract tests for the CLV Tracker boundary.

Validates that CLV analysis payloads and report summaries conform to the
frozen JSON Schema contract in ``tests/contracts/schemas/clv_tracker_contract_v1.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from tests.contracts.fixtures.clv_tracker_samples import (
    build_clv_analysis_payload,
    build_clv_report_summary_payload,
    build_negative_clv_payload,
    build_positive_clv_payload,
)

SCHEMA_PATH = (
    Path(__file__).parent / "schemas" / "clv_tracker_contract_v1.json"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def clv_schema() -> dict[str, Any]:
    """Load the CLV tracker contract schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def analysis_schema(clv_schema: dict[str, Any]) -> dict[str, Any]:
    """Build a standalone schema that validates only ``clv_analysis_result``."""
    return {
        "$schema": clv_schema["$schema"],
        "$ref": "#/$defs/clv_analysis_result",
        "$defs": clv_schema["$defs"],
    }


@pytest.fixture(scope="module")
def summary_schema(clv_schema: dict[str, Any]) -> dict[str, Any]:
    """Build a standalone schema that validates only ``clv_report_summary``."""
    return {
        "$schema": clv_schema["$schema"],
        "$ref": "#/$defs/clv_report_summary",
        "$defs": clv_schema["$defs"],
    }


def _validate(schema: dict[str, Any], payload: dict[str, Any]) -> None:
    Draft202012Validator(schema).validate(payload)


# ---------------------------------------------------------------------------
# Fixture → schema conformance
# ---------------------------------------------------------------------------


class TestCLVAnalysisFixtureConformance:
    """Canonical CLV analysis fixtures must match the frozen schema."""

    def test_canonical_clv_analysis_matches_schema(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        _validate(analysis_schema, build_clv_analysis_payload())

    def test_positive_clv_payload_matches_schema(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        _validate(analysis_schema, build_positive_clv_payload())

    def test_negative_clv_payload_matches_schema(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        _validate(analysis_schema, build_negative_clv_payload())

    def test_canonical_report_summary_matches_schema(
        self, summary_schema: dict[str, Any]
    ) -> None:
        _validate(summary_schema, build_clv_report_summary_payload())


class TestCLVAnalysisValidation:
    """CLV analysis payloads must satisfy schema constraints."""

    def test_clv_can_be_positive(self, analysis_schema: dict[str, Any]) -> None:
        payload = build_positive_clv_payload()
        assert payload["clv"] > 0
        _validate(analysis_schema, payload)

    def test_clv_can_be_negative(self, analysis_schema: dict[str, Any]) -> None:
        payload = build_negative_clv_payload()
        assert payload["clv"] < 0
        _validate(analysis_schema, payload)

    def test_clv_can_be_zero(self, analysis_schema: dict[str, Any]) -> None:
        payload = build_clv_analysis_payload(placed_prob=0.50, closing_prob=0.50, clv=0.0)
        _validate(analysis_schema, payload)

    def test_placed_prob_in_range_zero(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        payload = build_clv_analysis_payload(placed_prob=0.0, closing_prob=0.50, clv=-0.50)
        _validate(analysis_schema, payload)

    def test_placed_prob_in_range_one(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        payload = build_clv_analysis_payload(placed_prob=1.0, closing_prob=0.90, clv=0.10)
        _validate(analysis_schema, payload)

    def test_closing_prob_in_range_zero(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        payload = build_clv_analysis_payload(placed_prob=0.50, closing_prob=0.0, clv=0.50)
        _validate(analysis_schema, payload)

    def test_closing_prob_in_range_one(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        payload = build_clv_analysis_payload(placed_prob=0.80, closing_prob=1.0, clv=-0.20)
        _validate(analysis_schema, payload)

    def test_market_close_time_can_be_null(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        payload = build_clv_analysis_payload(market_close_time=None)
        _validate(analysis_schema, payload)

    def test_market_close_time_must_be_datetime_string_or_null(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(analysis_schema, build_clv_analysis_payload(market_close_time=12345))

    def test_is_stale_can_be_true(self, analysis_schema: dict[str, Any]) -> None:
        payload = build_clv_analysis_payload(is_stale=True)
        _validate(analysis_schema, payload)

    def test_is_stale_can_be_false(self, analysis_schema: dict[str, Any]) -> None:
        payload = build_clv_analysis_payload(is_stale=False)
        _validate(analysis_schema, payload)


class TestCLVReportSummaryValidation:
    """CLV report summary payloads must satisfy schema constraints."""

    def test_zero_bets_accepted(self, summary_schema: dict[str, Any]) -> None:
        payload = build_clv_report_summary_payload(
            total_bets=0, total_clv=0.0, avg_clv=0.0,
            positive_clv_count=0, negative_clv_count=0, sports_analyzed=0,
        )
        _validate(summary_schema, payload)

    def test_negative_bets_rejected(self, summary_schema: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            _validate(
                summary_schema,
                build_clv_report_summary_payload(total_bets=-1),
            )

    def test_negative_positive_count_rejected(
        self, summary_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(
                summary_schema,
                build_clv_report_summary_payload(positive_clv_count=-1),
            )

    def test_negative_negative_count_rejected(
        self, summary_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(
                summary_schema,
                build_clv_report_summary_payload(negative_clv_count=-1),
            )

    def test_sports_analyzed_negative_rejected(
        self, summary_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(
                summary_schema,
                build_clv_report_summary_payload(sports_analyzed=-1),
            )


class TestCLVRejection:
    """Invalid payloads must be rejected by the schema."""

    def test_missing_bet_id_rejected(self, analysis_schema: dict[str, Any]) -> None:
        payload = build_clv_analysis_payload()
        del payload["bet_id"]
        with pytest.raises(ValidationError):
            _validate(analysis_schema, payload)

    def test_missing_placed_prob_rejected(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        payload = build_clv_analysis_payload()
        del payload["placed_prob"]
        with pytest.raises(ValidationError):
            _validate(analysis_schema, payload)

    def test_missing_closing_prob_rejected(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        payload = build_clv_analysis_payload()
        del payload["closing_prob"]
        with pytest.raises(ValidationError):
            _validate(analysis_schema, payload)

    def test_missing_clv_rejected(self, analysis_schema: dict[str, Any]) -> None:
        payload = build_clv_analysis_payload()
        del payload["clv"]
        with pytest.raises(ValidationError):
            _validate(analysis_schema, payload)

    def test_missing_schema_version_rejected(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        payload = build_clv_analysis_payload()
        del payload["schema_version"]
        with pytest.raises(ValidationError):
            _validate(analysis_schema, payload)

    def test_missing_payload_kind_rejected(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        payload = build_clv_analysis_payload()
        del payload["payload_kind"]
        with pytest.raises(ValidationError):
            _validate(analysis_schema, payload)

    def test_missing_sport_rejected(self, analysis_schema: dict[str, Any]) -> None:
        payload = build_clv_analysis_payload()
        del payload["sport"]
        with pytest.raises(ValidationError):
            _validate(analysis_schema, payload)

    def test_unknown_field_rejected(self, analysis_schema: dict[str, Any]) -> None:
        payload = {**build_clv_analysis_payload(), "extra_field": "should_not_exist"}
        with pytest.raises(ValidationError):
            _validate(analysis_schema, payload)

    def test_unknown_field_in_summary_rejected(
        self, summary_schema: dict[str, Any]
    ) -> None:
        payload = {
            **build_clv_report_summary_payload(),
            "unknown_key": "should_not_exist",
        }
        with pytest.raises(ValidationError):
            _validate(summary_schema, payload)

    def test_empty_bet_id_rejected(self, analysis_schema: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            _validate(analysis_schema, build_clv_analysis_payload(bet_id=""))

    def test_wrong_schema_version_rejected(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(
                analysis_schema,
                build_clv_analysis_payload(schema_version="v2"),
            )

    def test_wrong_payload_kind_rejected(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(
                analysis_schema,
                build_clv_analysis_payload(payload_kind="wrong_kind"),
            )

    def test_placed_prob_below_zero_rejected(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(
                analysis_schema,
                build_clv_analysis_payload(placed_prob=-0.1),
            )

    def test_placed_prob_above_one_rejected(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(
                analysis_schema,
                build_clv_analysis_payload(placed_prob=1.5),
            )

    def test_closing_prob_below_zero_rejected(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(
                analysis_schema,
                build_clv_analysis_payload(closing_prob=-0.01),
            )

    def test_closing_prob_above_one_rejected(
        self, analysis_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            _validate(
                analysis_schema,
                build_clv_analysis_payload(closing_prob=1.01),
            )
