"""Consumer contract tests for the NHL Elo boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from tests.contracts.fixtures.nhl_elo_samples import (
    build_nhl_elo_prediction_payload,
)
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_ROOT / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def nhl_elo_schema() -> dict[str, Any]:
    return _load_schema("nhl_elo_prediction_v1.json")


@pytest.fixture
def nhl_elo_payload() -> dict[str, Any]:
    return build_nhl_elo_prediction_payload()


class TestNhlEloConsumerContract:
    """Consumer guarantees for NHLEloRating predict/update/get_rating outputs."""

    def test_valid_payload_passes_contract(
        self, nhl_elo_payload: dict[str, Any], nhl_elo_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(nhl_elo_payload, nhl_elo_schema)

    def test_home_prob_is_within_unit_interval(
        self, nhl_elo_payload: dict[str, Any]
    ) -> None:
        assert 0.0 <= nhl_elo_payload["home_prob"] <= 1.0

    def test_ratings_are_strictly_positive(
        self, nhl_elo_payload: dict[str, Any]
    ) -> None:
        assert nhl_elo_payload["home_rating"] > 0
        assert nhl_elo_payload["away_rating"] > 0

    def test_missing_home_prob_is_rejected(
        self, nhl_elo_payload: dict[str, Any], nhl_elo_schema: dict[str, Any]
    ) -> None:
        invalid = {k: v for k, v in nhl_elo_payload.items() if k != "home_prob"}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, nhl_elo_schema)

    def test_out_of_range_probability_is_rejected(
        self, nhl_elo_payload: dict[str, Any], nhl_elo_schema: dict[str, Any]
    ) -> None:
        invalid = {**nhl_elo_payload, "home_prob": 1.01}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, nhl_elo_schema)

    def test_non_nhl_sport_is_rejected(
        self, nhl_elo_payload: dict[str, Any], nhl_elo_schema: dict[str, Any]
    ) -> None:
        invalid = {**nhl_elo_payload, "sport": "MLB"}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, nhl_elo_schema)

    def test_unknown_field_is_rejected(
        self, nhl_elo_payload: dict[str, Any], nhl_elo_schema: dict[str, Any]
    ) -> None:
        invalid = {**nhl_elo_payload, "mystery_field": 1}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, nhl_elo_schema)
