"""Canonical governed approval read-model contract tests."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError


SCHEMAS_DIR = Path(__file__).parent / "schemas"

GOVERNED_SCHEMA_NAMES = (
    "governed_evidence_record_v1",
    "governed_recommendation_execution_link_v1",
    "governed_clv_evidence_envelope_v1",
    "sport_validation_state_v1",
    "governed_portfolio_risk_state_v1",
)

BASE_REQUIRED_FIELDS = (
    "sport",
    "market_type",
    "cohort_type",
    "evidence_dimension",
    "canonical_game_id",
    "market_ticker",
    "selection_key",
    "source_relation",
    "source_record_id",
    "evidence_state_scope",
    "evidence_state",
    "evidence_state_reason",
    "evidence_state_as_of",
    "evidence_state_source_artifact",
    "governance_status",
    "descriptive_only_flag",
    "contamination_flag",
    "contamination_reason",
    "excluded_from_approval_flag",
    "observed_at",
    "loaded_at",
    "last_updated_at",
)

QUOTE_LINEAGE_FIELDS = (
    "quote_source_system",
    "quote_bookmaker",
    "quote_observed_at",
    "quote_loaded_at",
    "quote_payload_ref",
    "quote_lineage_status",
    "quote_price_cents",
    "quote_price_role",
    "quote_freshness_result",
    "quote_fallback_status",
)

LINKAGE_FIELDS = (
    "linkage_status",
    "linkage_basis",
    "linked_canonical_game_id",
    "linked_market_ticker",
    "linked_selection_key",
    "entry_quote_source_system",
    "entry_quote_bookmaker",
    "entry_quote_observed_at",
    "entry_quote_loaded_at",
    "entry_quote_payload_ref",
    "entry_quote_lineage_status",
    "entry_price_cents",
    "entry_quote_freshness_result",
    "entry_quote_fallback_status",
)

CLV_GOVERNANCE_FIELDS = (
    "recommendation_id",
    "linked_canonical_game_id",
    "linked_market_ticker",
    "linked_selection_key",
    "entry_price_role",
    "entry_price_cents",
    "entry_price_source",
    "entry_quote_source_system",
    "entry_quote_bookmaker",
    "entry_quote_observed_at",
    "entry_quote_loaded_at",
    "entry_quote_payload_ref",
    "entry_freshness_result",
    "entry_fallback_status",
    "close_price_role",
    "close_freshness_result",
    "closing_quote_loaded_at",
    "closing_quote_payload_ref",
    "close_fallback_status",
    "selected_close_rule",
    "selected_close_provenance",
    "clv_evidence_tier",
)

EXPOSURE_BREAKDOWN_FIELDS = (
    "resting_order_exposure_amount",
    "resting_order_count",
    "executed_unsettled_exposure_amount",
    "executed_unsettled_count",
    "exposure_state",
)


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def _validate(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    Draft202012Validator(schema).validate(payload)


@pytest.fixture(scope="module")
def governed_schemas() -> dict[str, dict[str, Any]]:
    return {name: _load_schema(name) for name in GOVERNED_SCHEMA_NAMES}


@pytest.fixture
def valid_payloads() -> dict[str, dict[str, Any]]:
    base = {
        "sport": "NHL",
        "market_type": "moneyline",
        "cohort_type": "approval_review",
        "evidence_dimension": "read_model",
        "canonical_game_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS",
        "market_ticker": "KXNHL-26MAY03NYRBOS-NYR",
        "selection_key": "New York Rangers",
        "source_relation": "bet_recommendations",
        "source_record_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME",
        "evidence_state_scope": "sport",
        "evidence_state": "blocked",
        "evidence_state_reason": "NHL remains blocked until governed approval evidence exists.",
        "evidence_state_as_of": "2026-05-12T00:00:00Z",
        "evidence_state_source_artifact": "docs/plan/2026-05-12-betting-pipeline-audit/evidence-readmodel-spec.md",
        "governance_status": "descriptive_only",
        "descriptive_only_flag": True,
        "contamination_flag": False,
        "contamination_reason": None,
        "excluded_from_approval_flag": True,
        "observed_at": "2026-05-03T14:00:00Z",
        "loaded_at": "2026-05-03T13:56:00Z",
        "last_updated_at": "2026-05-03T14:00:00Z",
    }
    return {
        "governed_evidence_record_v1": {
            **base,
            "recommendation_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME",
            "recommendation_created_at": "2026-05-03T14:00:00Z",
            "recommendation_source_surface": "bet_recommendations",
            "probability_source": "elo_prob",
            "calibrated_probability": 0.62,
            "market_probability": 0.54,
            "edge": 0.08,
            "expected_value": 0.14,
            "kelly_fraction": 0.11,
            "confidence_label": "HIGH",
            "quote_source_system": "bet_recommendation_payload",
            "quote_bookmaker": "Kalshi",
            "quote_observed_at": "2026-05-03T13:55:00Z",
            "quote_loaded_at": "2026-05-03T13:56:00Z",
            "quote_payload_ref": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-KALSHI-HOME",
            "quote_lineage_status": "linked_market_quote",
            "quote_price_cents": 54,
            "quote_price_role": "executable",
            "quote_freshness_result": "fresh",
            "quote_fallback_status": "direct_quote",
        },
        "governed_recommendation_execution_link_v1": {
            **base,
            "placed_bet_id": "DASHBOARD-SEED-NHL-ORDER-20260503-NYR-BOS-HOME",
            "recommendation_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME",
            "execution_source_surface": "placed_bets",
            "execution_status": "open",
            "submitted_at": "2026-05-03T14:15:00Z",
            "filled_at": None,
            "contracts": 10,
            "execution_cost_dollars": 10.0,
            "notional_exposure": 10.0,
            "entry_probability": 0.54,
            "entry_quote_role": "executable",
            "entry_price_source": "dashboard_seed",
            "linkage_status": "linked",
            "linkage_basis": "market_ticker_selection_key_canonical_game_id",
            "linked_canonical_game_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS",
            "linked_market_ticker": "KXNHL-26MAY03NYRBOS-NYR",
            "linked_selection_key": "New York Rangers",
            "entry_quote_source_system": "kalshi_market_details",
            "entry_quote_bookmaker": "Kalshi",
            "entry_quote_observed_at": "2026-05-03T13:55:00Z",
            "entry_quote_loaded_at": "2026-05-03T13:56:00Z",
            "entry_quote_payload_ref": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-KALSHI-HOME",
            "entry_quote_lineage_status": "linked_market_quote",
            "entry_price_cents": 54,
            "entry_quote_freshness_result": "fresh",
            "entry_quote_fallback_status": "direct_market_quote",
        },
        "governed_clv_evidence_envelope_v1": {
            **{
                **base,
                "evidence_dimension": "pricing_clv",
                "source_relation": "placed_bets",
            },
            "placed_bet_id": "DASHBOARD-SEED-NHL-20260501-CAR-NJD-HOME",
            "recommendation_id": "DASHBOARD-SEED-NHL-20260501-CAR-NJD-HOME",
            "linked_canonical_game_id": "DASHBOARD-SEED-NHL-20260501-CAR-NJD",
            "linked_market_ticker": "KXNHL-26MAY01CARNJD-CAR",
            "linked_selection_key": "Carolina Hurricanes",
            "clv_source_type": "market_close",
            "clv_computed_at": "2026-05-02T03:15:00Z",
            "entry_probability": 0.54,
            "entry_price_role": "executable",
            "entry_price_cents": 54,
            "entry_price_source": "dashboard_seed",
            "entry_quote_source_system": "kalshi_market_details",
            "entry_quote_bookmaker": "Kalshi",
            "entry_quote_observed_at": "2026-05-01T14:15:00Z",
            "entry_quote_loaded_at": "2026-05-01T14:15:00Z",
            "entry_quote_payload_ref": "DASHBOARD-SEED-NHL-20260501-CAR-NJD-HOME",
            "entry_freshness_result": "fresh",
            "entry_fallback_status": "direct_market_quote",
            "closing_probability": 0.58,
            "clv_delta": 0.04,
            "clv_direction": "positive",
            "closing_quote_source": "SBR",
            "closing_quote_at": "2026-05-01T22:55:00Z",
            "close_price_role": "close",
            "close_freshness_result": "fresh",
            "closing_quote_loaded_at": "2026-05-01T22:56:00Z",
            "closing_quote_payload_ref": "DASHBOARD-SEED-NHL-20260501-CAR-NJD-SBR-HOME",
            "close_fallback_status": "latest_admissible_pregame_quote",
            "selected_close_rule": "latest_admissible_pregame_quote",
            "selected_close_provenance": "SBR|Carolina Hurricanes|2026-05-01T22:55:00",
            "clv_evidence_tier": "partially_evidenced",
            "binary_result_placeholder_flag": False,
            "stale_close_flag": False,
            "proxy_close_flag": False,
            "clv_contaminated_flag": False,
        },
        "sport_validation_state_v1": {
            **{
                **base,
                "evidence_dimension": "validation",
                "canonical_game_id": None,
                "market_ticker": None,
                "selection_key": None,
                "source_relation": "audit_specification",
                "source_record_id": "NHL",
                "observed_at": "2026-05-12T00:00:00Z",
                "loaded_at": None,
                "last_updated_at": "2026-05-12T00:00:00Z",
            },
            "review_timestamp": "2026-05-12T00:00:00Z",
            "runtime_consumer": None,
            "artifact_id": None,
            "artifact_version": "v1",
            "artifact_family": "approval_evidence_read_model",
            "artifact_available_flag": False,
            "placed_bet_only_flag": False,
            "synthetic_identity_flag": False,
            "backfill_flag": False,
        },
        "governed_portfolio_risk_state_v1": {
            **{
                **base,
                "evidence_dimension": "portfolio_risk",
                "canonical_game_id": None,
                "market_ticker": None,
                "selection_key": None,
                "source_relation": "placed_bets",
                "source_record_id": "NHL",
            },
            "snapshot_hour_utc": "2026-05-03T14:00:00Z",
            "open_exposure_flag": True,
            "open_exposure_amount": 22.0,
            "position_status": "open",
            "exposure_inclusion_state": "included_open_risk",
            "sport_exposure_amount": 22.0,
            "same_event_exposure_amount": None,
            "same_side_exposure_amount": None,
            "existing_position_flag": True,
            "resting_order_exposure_amount": 10.0,
            "resting_order_count": 1,
            "executed_unsettled_exposure_amount": 12.0,
            "executed_unsettled_count": 1,
            "exposure_state": "mixed_open_exposure",
            "daily_risk_cap_dollars": 368.94,
            "remaining_daily_risk_budget_dollars": 346.94,
            "peak_portfolio_value_dollars": 1600.0,
            "current_portfolio_value_dollars": 1475.75,
            "drawdown_amount_dollars": 124.25,
            "drawdown_ratio": 0.07765625,
            "drawdown_state": "drawdown_active",
            "risk_of_ruin_state": "capital_available",
            "portfolio_guardrail_state": "eligible",
            "portfolio_guardrail_reason_code": None,
            "portfolio_guardrail_reason_detail": None,
            "concentration_bucket": "same_side",
            "concentration_state": "descriptive_only_no_governed_limit",
            "existing_position_state": "mixed_open_exposure",
            "same_match_conflict": True,
            "rejection_reason_code": "missing_evidence",
            "rejection_reason_detail": "NHL remains blocked until governed approval evidence exists.",
            "operator_semantics_version": "portfolio_risk_state_v1",
            "bankroll_source": "portfolio_value_snapshots",
            "bankroll_amount": 1475.75,
            "bankroll_observed_at": "2026-05-03T14:00:00Z",
            "bankroll_snapshot_id": "2026-05-03T14:00:00",
        },
    }


class TestGovernedReadModelSchemaInventory:
    @pytest.mark.parametrize("name", GOVERNED_SCHEMA_NAMES)
    def test_schema_file_exists(self, name: str) -> None:
        assert (SCHEMAS_DIR / f"{name}.schema.json").exists()

    @pytest.mark.parametrize("name", GOVERNED_SCHEMA_NAMES)
    def test_schema_is_strict(
        self, name: str, governed_schemas: dict[str, dict[str, Any]]
    ) -> None:
        schema = governed_schemas[name]
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["additionalProperties"] is False

    @pytest.mark.parametrize("name", GOVERNED_SCHEMA_NAMES)
    def test_base_approval_fields_are_required(
        self, name: str, governed_schemas: dict[str, dict[str, Any]]
    ) -> None:
        required = governed_schemas[name]["required"]
        for field in BASE_REQUIRED_FIELDS:
            assert field in required

    def test_evidence_record_requires_quote_lineage_fields(
        self, governed_schemas: dict[str, dict[str, Any]]
    ) -> None:
        required = governed_schemas["governed_evidence_record_v1"]["required"]
        for field in QUOTE_LINEAGE_FIELDS:
            assert field in required

    def test_execution_link_requires_linkage_and_quote_lineage_fields(
        self, governed_schemas: dict[str, dict[str, Any]]
    ) -> None:
        required = governed_schemas["governed_recommendation_execution_link_v1"][
            "required"
        ]
        for field in LINKAGE_FIELDS:
            assert field in required

    def test_clv_schema_requires_governance_fields(
        self, governed_schemas: dict[str, dict[str, Any]]
    ) -> None:
        required = governed_schemas["governed_clv_evidence_envelope_v1"]["required"]
        for field in CLV_GOVERNANCE_FIELDS:
            assert field in required

    def test_portfolio_risk_requires_exposure_breakdown_fields(
        self, governed_schemas: dict[str, dict[str, Any]]
    ) -> None:
        required = governed_schemas["governed_portfolio_risk_state_v1"]["required"]
        for field in EXPOSURE_BREAKDOWN_FIELDS:
            assert field in required


class TestGovernedReadModelContracts:
    @pytest.mark.parametrize("name", GOVERNED_SCHEMA_NAMES)
    def test_valid_payload_passes(
        self,
        name: str,
        governed_schemas: dict[str, dict[str, Any]],
        valid_payloads: dict[str, dict[str, Any]],
    ) -> None:
        _validate(valid_payloads[name], governed_schemas[name])

    @pytest.mark.parametrize("name", GOVERNED_SCHEMA_NAMES)
    def test_missing_required_field_fails(
        self,
        name: str,
        governed_schemas: dict[str, dict[str, Any]],
        valid_payloads: dict[str, dict[str, Any]],
    ) -> None:
        schema = governed_schemas[name]
        for field in schema["required"]:
            payload = deepcopy(valid_payloads[name])
            del payload[field]
            with pytest.raises(ValidationError):
                _validate(payload, schema)

    @pytest.mark.parametrize("name", GOVERNED_SCHEMA_NAMES)
    def test_extra_field_fails(
        self,
        name: str,
        governed_schemas: dict[str, dict[str, Any]],
        valid_payloads: dict[str, dict[str, Any]],
    ) -> None:
        payload = {**valid_payloads[name], "unexpected_column": "drift"}
        with pytest.raises(ValidationError):
            _validate(payload, governed_schemas[name])

    @pytest.mark.parametrize(
        ("name", "field", "bad_value"),
        (
            ("governed_evidence_record_v1", "calibrated_probability", 1.2),
            ("governed_recommendation_execution_link_v1", "entry_probability", -0.1),
            ("governed_clv_evidence_envelope_v1", "clv_direction", "up"),
            ("sport_validation_state_v1", "evidence_state", "approval_grade"),
            ("governed_portfolio_risk_state_v1", "position_status", "active"),
        ),
    )
    def test_invalid_enum_or_range_fails(
        self,
        name: str,
        field: str,
        bad_value: Any,
        governed_schemas: dict[str, dict[str, Any]],
        valid_payloads: dict[str, dict[str, Any]],
    ) -> None:
        payload = {**valid_payloads[name], field: bad_value}
        with pytest.raises(ValidationError):
            _validate(payload, governed_schemas[name])

    def test_sport_validation_state_rejects_soccer_moneyline_semantics(
        self,
        governed_schemas: dict[str, dict[str, Any]],
        valid_payloads: dict[str, dict[str, Any]],
    ) -> None:
        payload = {
            **valid_payloads["sport_validation_state_v1"],
            "sport": "EPL",
            "market_type": "moneyline",
            "source_record_id": "EPL",
        }
        with pytest.raises(ValidationError):
            _validate(payload, governed_schemas["sport_validation_state_v1"])

    def test_execution_link_allows_non_parity_ids_when_linkage_fields_exist(
        self,
        governed_schemas: dict[str, dict[str, Any]],
        valid_payloads: dict[str, dict[str, Any]],
    ) -> None:
        payload = {
            **valid_payloads["governed_recommendation_execution_link_v1"],
            "placed_bet_id": "KALSHI-ORDER-123",
            "recommendation_id": "RECOMMENDATION-789",
        }
        _validate(payload, governed_schemas["governed_recommendation_execution_link_v1"])

    def test_portfolio_risk_rejects_unknown_exposure_state(
        self,
        governed_schemas: dict[str, dict[str, Any]],
        valid_payloads: dict[str, dict[str, Any]],
    ) -> None:
        payload = {
            **valid_payloads["governed_portfolio_risk_state_v1"],
            "exposure_state": "understated_open_exposure",
        }
        with pytest.raises(ValidationError):
            _validate(payload, governed_schemas["governed_portfolio_risk_state_v1"])
