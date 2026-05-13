"""Consumer contract tests for the BaseEloRating interface boundary.

These tests verify that consumers of the contract can trust the shapes
produced by *any* sport-specific Elo implementation.  Every payload kind
(predict_result, update_result, get_rating_result) is validated against
the frozen JSON Schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from tests.contracts.fixtures.base_elo_rating_samples import (
    build_get_rating_payload,
    build_predict_payload,
    build_update_payload,
)
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_ROOT / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def base_elo_contract() -> dict[str, Any]:
    return _load_schema("base_elo_rating_contract_v1.json")


@pytest.fixture
def predict_payload() -> dict[str, Any]:
    return build_predict_payload()


@pytest.fixture
def update_payload() -> dict[str, Any]:
    return build_update_payload()


@pytest.fixture
def get_rating_payload() -> dict[str, Any]:
    return build_get_rating_payload()


class TestBaseEloRatingConsumerContract:
    """Consumer guarantees for the BaseEloRating boundary.

    Every sport-specific Elo class promises to produce outputs that conform
    to at least one of the three payload shapes defined in the contract.
    """

    # ── predict_result ──────────────────────────────────────────────

    def test_predict_payload_passes_contract(
        self, predict_payload: dict[str, Any], base_elo_contract: dict[str, Any]
    ) -> None:
        validate_contract_payload(predict_payload, base_elo_contract)

    def test_predict_returns_probability_in_unit_interval(
        self, predict_payload: dict[str, Any]
    ) -> None:
        assert 0.0 <= predict_payload["home_prob"] <= 1.0

    def test_predict_missing_home_prob_is_rejected(
        self, predict_payload: dict[str, Any], base_elo_contract: dict[str, Any]
    ) -> None:
        invalid = {k: v for k, v in predict_payload.items() if k != "home_prob"}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, base_elo_contract)

    def test_predict_out_of_range_probability_is_rejected(
        self, predict_payload: dict[str, Any], base_elo_contract: dict[str, Any]
    ) -> None:
        invalid = {**predict_payload, "home_prob": 1.01}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, base_elo_contract)

    def test_predict_unknown_field_is_rejected(
        self, predict_payload: dict[str, Any], base_elo_contract: dict[str, Any]
    ) -> None:
        invalid = {**predict_payload, "mystery_field": 42}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, base_elo_contract)

    def test_predict_missing_schema_version_is_rejected(
        self, predict_payload: dict[str, Any], base_elo_contract: dict[str, Any]
    ) -> None:
        invalid = {k: v for k, v in predict_payload.items() if k != "schema_version"}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, base_elo_contract)

    # ── update_result ───────────────────────────────────────────────

    def test_update_payload_passes_contract(
        self, update_payload: dict[str, Any], base_elo_contract: dict[str, Any]
    ) -> None:
        validate_contract_payload(update_payload, base_elo_contract)

    def test_update_returns_valid_rating_change(
        self, update_payload: dict[str, Any]
    ) -> None:
        assert isinstance(update_payload["rating_change"], (int, float))

    def test_update_ratings_are_strictly_positive(
        self, update_payload: dict[str, Any]
    ) -> None:
        assert update_payload["home_rating_after"] > 0
        assert update_payload["away_rating_after"] > 0

    def test_update_missing_rating_change_is_rejected(
        self, update_payload: dict[str, Any], base_elo_contract: dict[str, Any]
    ) -> None:
        invalid = {k: v for k, v in update_payload.items() if k != "rating_change"}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, base_elo_contract)

    def test_update_unknown_field_is_rejected(
        self, update_payload: dict[str, Any], base_elo_contract: dict[str, Any]
    ) -> None:
        invalid = {**update_payload, "bogus": True}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, base_elo_contract)

    # ── get_rating_result ───────────────────────────────────────────

    def test_get_rating_payload_passes_contract(
        self, get_rating_payload: dict[str, Any], base_elo_contract: dict[str, Any]
    ) -> None:
        validate_contract_payload(get_rating_payload, base_elo_contract)

    def test_get_rating_returns_positive_number(
        self, get_rating_payload: dict[str, Any]
    ) -> None:
        assert get_rating_payload["rating"] > 0

    def test_get_rating_missing_rating_is_rejected(
        self, get_rating_payload: dict[str, Any], base_elo_contract: dict[str, Any]
    ) -> None:
        invalid = {k: v for k, v in get_rating_payload.items() if k != "rating"}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, base_elo_contract)

    def test_get_rating_unknown_field_is_rejected(
        self, get_rating_payload: dict[str, Any], base_elo_contract: dict[str, Any]
    ) -> None:
        invalid = {**get_rating_payload, "extra": "nope"}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, base_elo_contract)
