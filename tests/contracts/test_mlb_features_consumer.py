"""Consumer contract tests for the MLB feature-vector boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from tests.contracts.fixtures.mlb_features_samples import build_mlb_features_payload
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_ROOT / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def features_schema() -> dict[str, Any]:
    return _load_schema("mlb_features_v1.json")


@pytest.fixture
def features_payload() -> dict[str, Any]:
    return build_mlb_features_payload()


class TestMlbFeaturesConsumerContract:
    """Consumer guarantees for the MLB feature-vector boundary."""

    def test_valid_features_payload_passes_contract(
        self, features_payload: dict[str, Any], features_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(features_payload, features_schema)

    def test_rest_days_must_be_integer(
        self, features_payload: dict[str, Any], features_schema: dict[str, Any]
    ) -> None:
        invalid = {**features_payload, "home_rest_days": 2.5}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, features_schema)

    def test_rest_days_capped_at_seven(
        self, features_payload: dict[str, Any], features_schema: dict[str, Any]
    ) -> None:
        invalid = {**features_payload, "away_rest_days": 8}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, features_schema)

    def test_market_prob_out_of_range_is_rejected(
        self, features_payload: dict[str, Any], features_schema: dict[str, Any]
    ) -> None:
        invalid = {**features_payload, "market_prob": 1.2}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, features_schema)

    def test_negative_runs_are_rejected(
        self, features_payload: dict[str, Any], features_schema: dict[str, Any]
    ) -> None:
        invalid = {**features_payload, "home_runs_scored_ytd": -1.0}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, features_schema)

    def test_unknown_feature_field_is_rejected(
        self, features_payload: dict[str, Any], features_schema: dict[str, Any]
    ) -> None:
        invalid = {**features_payload, "secret_signal": 42.0}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, features_schema)

    def test_missing_required_feature_is_rejected(
        self, features_payload: dict[str, Any], features_schema: dict[str, Any]
    ) -> None:
        invalid = {
            k: v for k, v in features_payload.items() if k != "home_bullpen_era"
        }
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, features_schema)

    def test_market_prob_nullable(
        self, features_payload: dict[str, Any], features_schema: dict[str, Any]
    ) -> None:
        payload = {**features_payload, "market_prob": None}
        validate_contract_payload(payload, features_schema)
