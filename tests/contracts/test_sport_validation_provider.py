"""Provider contract tests for governed sport-validation publication."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.contracts.fixtures.sport_validation_samples import (
    BLOCKED_SPORTS,
    SHADOW_ONLY_SPORTS,
    SUPPORTED_SPORTS,
    build_approval_grade_validation_state,
    build_candidate_validation_state,
    build_contaminated_validation_state,
)
from tests.contracts.helpers import validate_contract_payload

from plugins.sport_validation import (
    FailClosedEligibilityError,
    can_size_from_validation_state,
    publish_all_sport_validation_states,
    publish_sport_validation_state,
    publish_validation_eligibility_matrix,
    require_sizing_eligibility,
)

SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_ROOT / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validation_state_schema() -> dict[str, Any]:
    return _load_schema("sport_validation_state_v1.json")


@pytest.fixture(scope="module")
def eligibility_matrix_schema() -> dict[str, Any]:
    return _load_schema("validation_eligibility_matrix_v1.json")


@pytest.mark.parametrize("sport", SUPPORTED_SPORTS)
def test_publish_sport_validation_state_matches_contract(
    sport: str, validation_state_schema: dict[str, Any]
) -> None:
    validate_contract_payload(
        publish_sport_validation_state(sport),
        validation_state_schema,
    )


def test_publish_all_states_covers_every_supported_sport() -> None:
    published = publish_all_sport_validation_states()
    assert [state["sport"] for state in published] == list(SUPPORTED_SPORTS)


def test_publish_validation_eligibility_matrix_matches_contract(
    eligibility_matrix_schema: dict[str, Any],
) -> None:
    validate_contract_payload(
        publish_validation_eligibility_matrix(),
        eligibility_matrix_schema,
    )


def test_matrix_matches_published_states() -> None:
    matrix = publish_validation_eligibility_matrix()
    published = {
        state["sport"]: state for state in publish_all_sport_validation_states()
    }

    assert matrix["states_by_sport"] == published
    assert matrix["status_index"]["shadow_only"] == list(SHADOW_ONLY_SPORTS)
    assert matrix["status_index"]["blocked"] == list(BLOCKED_SPORTS)
    assert matrix["status_index"]["candidate"] == []
    assert matrix["status_index"]["approval_grade"] == []
    assert matrix["status_index"]["sizing_eligible"] == []


@pytest.mark.parametrize("sport", SUPPORTED_SPORTS)
def test_baseline_publication_is_fail_closed_for_sizing(sport: str) -> None:
    assert can_size_from_validation_state(publish_sport_validation_state(sport)) is False


def test_candidate_state_stays_fail_closed_without_approval_grade() -> None:
    assert can_size_from_validation_state(build_candidate_validation_state()) is False


def test_contaminated_state_stays_fail_closed() -> None:
    assert can_size_from_validation_state(build_contaminated_validation_state()) is False


def test_approval_grade_state_is_sizing_eligible() -> None:
    assert can_size_from_validation_state(build_approval_grade_validation_state()) is True


@pytest.mark.parametrize("sport", ("MLB", "NHL"))
def test_require_sizing_eligibility_raises_with_explicit_blockers(sport: str) -> None:
    with pytest.raises(FailClosedEligibilityError) as exc_info:
        require_sizing_eligibility(sport)

    assert exc_info.value.sport == sport
    assert exc_info.value.validation_status in {"blocked", "shadow_only"}
    assert exc_info.value.reason_codes


def test_unknown_sport_rejected_fail_closed() -> None:
    with pytest.raises(ValueError, match="Unsupported sport"):
        publish_sport_validation_state("MLS")
