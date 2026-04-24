"""Consumer contract tests for the MLB Glicko-2 boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from tests.contracts.fixtures.mlb_glicko2_samples import (
    build_glicko2_prediction_payload,
    build_glicko2_team_rating_payload,
)
from tests.contracts.helpers import validate_contract_definition


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_ROOT / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def glicko2_schema() -> dict[str, Any]:
    return _load_schema("mlb_glicko2_v1.json")


@pytest.fixture
def team_rating_payload() -> dict[str, Any]:
    return build_glicko2_team_rating_payload()


@pytest.fixture
def prediction_payload() -> dict[str, Any]:
    return build_glicko2_prediction_payload()


class TestMlbGlicko2ConsumerContract:
    """Consumer guarantees for MLBGlicko2Rating predict/get_rating outputs."""

    def test_valid_team_rating_passes_contract(
        self,
        team_rating_payload: dict[str, Any],
        glicko2_schema: dict[str, Any],
    ) -> None:
        validate_contract_definition(team_rating_payload, glicko2_schema, "team_rating")

    def test_valid_prediction_passes_contract(
        self,
        prediction_payload: dict[str, Any],
        glicko2_schema: dict[str, Any],
    ) -> None:
        validate_contract_definition(prediction_payload, glicko2_schema, "prediction")

    def test_rating_deviation_must_be_positive(
        self,
        team_rating_payload: dict[str, Any],
        glicko2_schema: dict[str, Any],
    ) -> None:
        invalid = {**team_rating_payload, "rd": 0.0}
        with pytest.raises(ValidationError):
            validate_contract_definition(invalid, glicko2_schema, "team_rating")

    def test_volatility_must_be_positive(
        self,
        team_rating_payload: dict[str, Any],
        glicko2_schema: dict[str, Any],
    ) -> None:
        invalid = {**team_rating_payload, "vol": -0.01}
        with pytest.raises(ValidationError):
            validate_contract_definition(invalid, glicko2_schema, "team_rating")

    def test_prediction_prob_out_of_range_is_rejected(
        self,
        prediction_payload: dict[str, Any],
        glicko2_schema: dict[str, Any],
    ) -> None:
        invalid = {**prediction_payload, "prob": 1.5}
        with pytest.raises(ValidationError):
            validate_contract_definition(invalid, glicko2_schema, "prediction")

    def test_missing_vol_is_rejected(
        self,
        team_rating_payload: dict[str, Any],
        glicko2_schema: dict[str, Any],
    ) -> None:
        invalid = {k: v for k, v in team_rating_payload.items() if k != "vol"}
        with pytest.raises(ValidationError):
            validate_contract_definition(invalid, glicko2_schema, "team_rating")

    def test_non_mlb_sport_is_rejected(
        self,
        team_rating_payload: dict[str, Any],
        glicko2_schema: dict[str, Any],
    ) -> None:
        invalid = {**team_rating_payload, "sport": "NBA"}
        with pytest.raises(ValidationError):
            validate_contract_definition(invalid, glicko2_schema, "team_rating")
