"""Consumer contract tests for the MLB pitcher Elo boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from tests.contracts.fixtures.mlb_pitcher_samples import (
    build_pitcher_matchup_payload,
    build_pitcher_rating_payload,
)
from tests.contracts.helpers import (
    validate_contract_definition,
    validate_contract_payload,
)


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_ROOT / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pitcher_schema() -> dict[str, Any]:
    return _load_schema("mlb_pitcher_elo_v1.json")


@pytest.fixture
def rating_payload() -> dict[str, Any]:
    return build_pitcher_rating_payload()


@pytest.fixture
def matchup_payload() -> dict[str, Any]:
    return build_pitcher_matchup_payload()


class TestMlbPitcherEloConsumerContract:
    """Consumer guarantees for the pitcher Elo ladder boundary."""

    def test_valid_rating_payload_passes_contract(
        self, rating_payload: dict[str, Any], pitcher_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(rating_payload, pitcher_schema)
        validate_contract_definition(
            rating_payload, pitcher_schema, "pitcher_rating"
        )

    def test_valid_matchup_payload_passes_contract(
        self, matchup_payload: dict[str, Any], pitcher_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(matchup_payload, pitcher_schema)
        validate_contract_definition(
            matchup_payload, pitcher_schema, "pitcher_matchup"
        )

    def test_missing_rating_is_rejected(
        self, rating_payload: dict[str, Any], pitcher_schema: dict[str, Any]
    ) -> None:
        invalid = {k: v for k, v in rating_payload.items() if k != "rating"}
        with pytest.raises(ValidationError):
            validate_contract_definition(invalid, pitcher_schema, "pitcher_rating")

    def test_negative_rating_is_rejected(
        self, rating_payload: dict[str, Any], pitcher_schema: dict[str, Any]
    ) -> None:
        invalid = {**rating_payload, "rating": -10.0}
        with pytest.raises(ValidationError):
            validate_contract_definition(invalid, pitcher_schema, "pitcher_rating")

    def test_unknown_field_is_rejected(
        self, matchup_payload: dict[str, Any], pitcher_schema: dict[str, Any]
    ) -> None:
        invalid = {**matchup_payload, "extra": 0}
        with pytest.raises(ValidationError):
            validate_contract_definition(invalid, pitcher_schema, "pitcher_matchup")

    def test_pitcher_weight_must_be_in_unit_interval(
        self, rating_payload: dict[str, Any], pitcher_schema: dict[str, Any]
    ) -> None:
        invalid = {**rating_payload, "pitcher_weight": 1.5}
        with pytest.raises(ValidationError):
            validate_contract_definition(invalid, pitcher_schema, "pitcher_rating")
