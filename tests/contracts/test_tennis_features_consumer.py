"""Consumer contract tests for Tennis feature-vector payloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from tests.contracts.fixtures.tennis_features_samples import (
    build_low_certainty_tennis_feature_vector,
    build_tennis_feature_vector,
)


SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "tennis_features_v1.json"


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def validator() -> Draft202012Validator:
    """Return a JSON Schema validator for Tennis feature payloads."""
    return Draft202012Validator(_load_schema())


def test_valid_tennis_feature_vector_fixture_passes(
    validator: Draft202012Validator,
) -> None:
    """Canonical feature-vector sample should satisfy the consumer contract."""
    validator.validate(build_tennis_feature_vector())


def test_low_certainty_feature_vector_fixture_passes(
    validator: Draft202012Validator,
) -> None:
    """Low-certainty samples remain valid so betting can reject them downstream."""
    validator.validate(build_low_certainty_tennis_feature_vector())


def test_feature_vector_rejects_extra_fields(
    validator: Draft202012Validator,
) -> None:
    """Feature payloads must not grow undeclared fields at contract boundaries."""
    payload = build_tennis_feature_vector(unexpected_model_signal=0.1)

    with pytest.raises(ValidationError):
        validator.validate(payload)


def test_feature_vector_requires_probability_bounds(
    validator: Draft202012Validator,
) -> None:
    """Serve/return/complexity fields must stay in calibrated probability ranges."""
    payload = build_tennis_feature_vector(intransitivity_complexity=1.2)

    with pytest.raises(ValidationError):
        validator.validate(payload)
