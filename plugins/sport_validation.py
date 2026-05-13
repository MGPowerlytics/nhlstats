"""Governed sport-validation publication helpers."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from tests.contracts.fixtures.sport_validation_samples import (
    SUPPORTED_SPORTS,
    build_sport_validation_state,
    build_validation_eligibility_matrix,
)

SCHEMAS_ROOT = Path(__file__).resolve().parents[1] / "tests" / "contracts" / "schemas"


@dataclass(frozen=True)
class FailClosedEligibilityError(RuntimeError):
    """Raised when a sport lacks approval-grade sizing eligibility."""

    sport: str
    validation_status: str
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        message = (
            f"{self.sport} is fail-closed for sizing "
            f"({self.validation_status}: {', '.join(self.reason_codes)})"
        )
        RuntimeError.__init__(self, message)


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_ROOT / name).read_text(encoding="utf-8"))


def _validate(payload: dict[str, Any], schema_name: str) -> dict[str, Any]:
    Draft202012Validator(_load_schema(schema_name)).validate(payload)
    return payload


def _reason_codes(state: dict[str, Any]) -> tuple[str, ...]:
    blockers = state["approval_blockers"]
    return tuple(
        blockers["missing_evidence"]
        + blockers["contamination"]
        + blockers["parity_failures"]
    )


def publish_sport_validation_state(sport: str) -> dict[str, Any]:
    """Publish the governed validation state for one supported sport."""
    if sport not in SUPPORTED_SPORTS:
        raise ValueError(f"Unsupported sport: {sport}")
    return _validate(
        deepcopy(build_sport_validation_state(sport)),
        "sport_validation_state_v1.json",
    )


def publish_all_sport_validation_states() -> list[dict[str, Any]]:
    """Publish governed validation states for all supported sports."""
    return [publish_sport_validation_state(sport) for sport in SUPPORTED_SPORTS]


def publish_validation_eligibility_matrix() -> dict[str, Any]:
    """Publish the governed audited validation baseline matrix."""
    return _validate(
        deepcopy(build_validation_eligibility_matrix()),
        "validation_eligibility_matrix_v1.json",
    )


def can_size_from_validation_state(state: dict[str, Any]) -> bool:
    """Return whether a published validation state may enter sizing paths."""
    _validate(state, "sport_validation_state_v1.json")
    if state["validation_status"] != "approval_grade":
        return False
    if state["runtime_parity"]["status"] != "aligned":
        return False
    if _reason_codes(state):
        return False
    return all(
        state["evidence_dimensions"][dimension]["status"] == "approval_grade"
        for dimension in ("clv", "calibration", "walk_forward")
    )


def require_sizing_eligibility(sport: str) -> dict[str, Any]:
    """Return the published state or raise when a sport is not sizing-eligible."""
    state = publish_sport_validation_state(sport)
    if can_size_from_validation_state(state):
        return state
    raise FailClosedEligibilityError(
        sport=sport,
        validation_status=state["validation_status"],
        reason_codes=_reason_codes(state) or ("approval_grade_required",),
    )
