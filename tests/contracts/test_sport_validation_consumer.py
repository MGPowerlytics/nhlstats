"""Contract tests for governed sport-validation schemas and fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError

from tests.contracts.fixtures.sport_validation_samples import (
    BLOCKED_SPORTS,
    SHADOW_ONLY_SPORTS,
    SUPPORTED_SPORTS,
    build_approval_grade_validation_state,
    build_candidate_validation_state,
    build_contaminated_validation_state,
    build_sport_validation_state,
    build_validation_eligibility_matrix,
)
from tests.contracts.helpers import validate_contract_payload

SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_ROOT / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validation_state_schema() -> dict[str, Any]:
    return _load_schema("sport_validation_state_v1.json")


@pytest.fixture(scope="module")
def eligibility_matrix_schema() -> dict[str, Any]:
    return _load_schema("validation_eligibility_matrix_v1.json")


def test_validation_state_schema_freezes_supported_sports(
    validation_state_schema: dict[str, Any],
) -> None:
    assert validation_state_schema["properties"]["sport"]["enum"] == list(SUPPORTED_SPORTS)


def test_validation_state_schema_freezes_fail_closed_statuses(
    validation_state_schema: dict[str, Any],
) -> None:
    assert validation_state_schema["properties"]["validation_status"]["enum"] == [
        "blocked",
        "shadow_only",
        "candidate",
        "approval_grade",
    ]


def test_validation_state_schema_separates_reason_code_dimensions(
    validation_state_schema: dict[str, Any],
) -> None:
    defs = validation_state_schema["$defs"]
    assert defs["missing_reason_code"]["enum"] == [
        "missing_market_clv_evidence",
        "missing_calibration_evidence",
        "missing_walk_forward_evidence",
        "missing_governed_holdout_evidence",
        "missing_governed_artifact_lineage",
    ]
    assert defs["contamination_reason_code"]["enum"] == [
        "binary_result_clv_contamination",
        "mixed_cohort_contamination",
        "recommendation_backfill_contamination",
        "synthetic_ticker_contamination",
    ]
    assert defs["parity_reason_code"]["enum"] == [
        "runtime_consumer_mismatch",
        "governed_artifact_not_consumed",
        "reporting_runtime_divergence",
    ]


def test_eligibility_matrix_schema_requires_every_supported_sport(
    eligibility_matrix_schema: dict[str, Any],
) -> None:
    assert eligibility_matrix_schema["properties"]["states_by_sport"]["required"] == list(
        SUPPORTED_SPORTS
    )


@pytest.mark.parametrize("sport", SUPPORTED_SPORTS)
def test_audited_baseline_state_fixture_matches_contract(
    sport: str, validation_state_schema: dict[str, Any]
) -> None:
    validate_contract_payload(build_sport_validation_state(sport), validation_state_schema)


def test_audited_baseline_matrix_fixture_matches_contract(
    eligibility_matrix_schema: dict[str, Any],
) -> None:
    validate_contract_payload(build_validation_eligibility_matrix(), eligibility_matrix_schema)


def test_audited_baseline_matrix_matches_completed_audit() -> None:
    matrix = build_validation_eligibility_matrix()
    assert matrix["status_index"]["shadow_only"] == list(SHADOW_ONLY_SPORTS)
    assert matrix["status_index"]["blocked"] == list(BLOCKED_SPORTS)
    assert matrix["status_index"]["candidate"] == []
    assert matrix["status_index"]["approval_grade"] == []
    assert matrix["status_index"]["sizing_eligible"] == []


@pytest.mark.parametrize("sport", ("EPL", "LIGUE1"))
def test_soccer_baseline_fixtures_publish_match_winner_market_type(sport: str) -> None:
    state = build_sport_validation_state(sport)
    assert state["market_type"] == "match_winner"


@pytest.mark.parametrize("sport", ("EPL", "LIGUE1"))
def test_soccer_market_type_drift_is_rejected_by_schema(
    sport: str, validation_state_schema: dict[str, Any]
) -> None:
    state = build_sport_validation_state(sport)
    state["market_type"] = "moneyline"

    with pytest.raises(ValidationError):
        validate_contract_payload(state, validation_state_schema)


def test_candidate_fixture_matches_contract(
    validation_state_schema: dict[str, Any],
) -> None:
    validate_contract_payload(build_candidate_validation_state(), validation_state_schema)


def test_approval_grade_fixture_matches_contract(
    validation_state_schema: dict[str, Any],
) -> None:
    validate_contract_payload(build_approval_grade_validation_state(), validation_state_schema)


def test_contaminated_fixture_matches_contract(
    validation_state_schema: dict[str, Any],
) -> None:
    validate_contract_payload(build_contaminated_validation_state(), validation_state_schema)


def test_contaminated_fixture_surfaces_contamination_without_missing_or_parity() -> None:
    state = build_contaminated_validation_state()
    assert state["approval_blockers"]["contamination"] == [
        "binary_result_clv_contamination",
        "mixed_cohort_contamination",
        "synthetic_ticker_contamination",
    ]
    assert state["approval_blockers"]["missing_evidence"] == []
    assert state["approval_blockers"]["parity_failures"] == []


def test_shadow_only_fixture_cannot_be_promoted_without_approval_dimensions(
    validation_state_schema: dict[str, Any],
) -> None:
    state = build_sport_validation_state("MLB")
    state["validation_status"] = "approval_grade"
    state["sizing_eligible"] = True

    with pytest.raises(ValidationError):
        validate_contract_payload(state, validation_state_schema)


def test_candidate_fixture_rejects_missing_walk_forward_evidence(
    validation_state_schema: dict[str, Any],
) -> None:
    state = build_candidate_validation_state()
    state["evidence_dimensions"]["walk_forward"]["status"] = "missing"
    state["evidence_dimensions"]["walk_forward"]["missing_reason_codes"] = [
        "missing_walk_forward_evidence"
    ]
    state["approval_blockers"]["missing_evidence"] = ["missing_walk_forward_evidence"]

    with pytest.raises(ValidationError):
        validate_contract_payload(state, validation_state_schema)


def test_approval_grade_fixture_rejects_contaminated_clv(
    validation_state_schema: dict[str, Any],
) -> None:
    state = build_approval_grade_validation_state()
    state["evidence_dimensions"]["clv"]["status"] = "contaminated"
    state["evidence_dimensions"]["clv"]["contamination_reason_codes"] = [
        "binary_result_clv_contamination"
    ]
    state["approval_blockers"]["contamination"] = ["binary_result_clv_contamination"]

    with pytest.raises(ValidationError):
        validate_contract_payload(state, validation_state_schema)


def test_approval_grade_fixture_rejects_runtime_parity_failure(
    validation_state_schema: dict[str, Any],
) -> None:
    state = build_approval_grade_validation_state()
    state["runtime_parity"]["status"] = "divergent"
    state["runtime_parity"]["reason_codes"] = ["runtime_consumer_mismatch"]
    state["approval_blockers"]["parity_failures"] = ["runtime_consumer_mismatch"]

    with pytest.raises(ValidationError):
        validate_contract_payload(state, validation_state_schema)


def test_reason_code_dimension_rejects_missing_code_in_contamination_array(
    validation_state_schema: dict[str, Any],
) -> None:
    state = build_contaminated_validation_state()
    state["approval_blockers"]["contamination"] = ["missing_walk_forward_evidence"]

    with pytest.raises(ValidationError):
        validate_contract_payload(state, validation_state_schema)


def test_matrix_rejects_missing_supported_sport(
    eligibility_matrix_schema: dict[str, Any],
) -> None:
    matrix = build_validation_eligibility_matrix()
    matrix["states_by_sport"].pop("NHL")

    with pytest.raises(ValidationError):
        validate_contract_payload(matrix, eligibility_matrix_schema)
