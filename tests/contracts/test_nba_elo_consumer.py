"""Consumer contract tests for the NBA Elo boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from tests.contracts.fixtures.nba_elo_samples import (
    build_nba_elo_prediction_payload,
)
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_ROOT / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def nba_elo_schema() -> dict[str, Any]:
    return _load_schema("nba_elo_prediction_v1.json")


@pytest.fixture
def nba_elo_payload() -> dict[str, Any]:
    return build_nba_elo_prediction_payload()


class TestNbaEloConsumerContract:
    """Consumer guarantees for NBAEloRating predict/update/get_rating outputs."""

    def test_valid_payload_passes_contract(
        self, nba_elo_payload: dict[str, Any], nba_elo_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(nba_elo_payload, nba_elo_schema)

    def test_home_prob_is_within_unit_interval(
        self, nba_elo_payload: dict[str, Any]
    ) -> None:
        assert 0.0 <= nba_elo_payload["home_prob"] <= 1.0

    def test_ratings_are_strictly_positive(
        self, nba_elo_payload: dict[str, Any]
    ) -> None:
        assert nba_elo_payload["home_rating"] > 0
        assert nba_elo_payload["away_rating"] > 0

    def test_missing_home_prob_is_rejected(
        self, nba_elo_payload: dict[str, Any], nba_elo_schema: dict[str, Any]
    ) -> None:
        invalid = {k: v for k, v in nba_elo_payload.items() if k != "home_prob"}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, nba_elo_schema)

    def test_out_of_range_probability_is_rejected(
        self, nba_elo_payload: dict[str, Any], nba_elo_schema: dict[str, Any]
    ) -> None:
        invalid = {**nba_elo_payload, "home_prob": 1.01}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, nba_elo_schema)

    def test_non_nba_sport_is_rejected(
        self, nba_elo_payload: dict[str, Any], nba_elo_schema: dict[str, Any]
    ) -> None:
        invalid = {**nba_elo_payload, "sport": "NHL"}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, nba_elo_schema)

    def test_unknown_field_is_rejected(
        self, nba_elo_payload: dict[str, Any], nba_elo_schema: dict[str, Any]
    ) -> None:
        invalid = {**nba_elo_payload, "mystery_field": 1}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, nba_elo_schema)
