"""Consumer contract tests for the MLB ensemble I/O boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from tests.contracts.fixtures.mlb_ensemble_samples import (
    build_ensemble_input_payload,
    build_ensemble_output_payload,
)
from tests.contracts.helpers import validate_contract_definition


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"
WEIGHT_SUM_TOLERANCE = 0.01


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_ROOT / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ensemble_schema() -> dict[str, Any]:
    return _load_schema("mlb_ensemble_io_v1.json")


@pytest.fixture
def ensemble_input_payload() -> dict[str, Any]:
    return build_ensemble_input_payload()


@pytest.fixture
def ensemble_output_payload() -> dict[str, Any]:
    return build_ensemble_output_payload()


def _assert_weights_sum_to_one(payload: dict[str, Any]) -> None:
    total = sum(payload["weights"].values())
    assert abs(total - 1.0) <= WEIGHT_SUM_TOLERANCE


class TestMlbEnsembleConsumerContract:
    """Consumer guarantees for the ensemble input + output boundary."""

    def test_valid_input_payload_passes_contract(
        self,
        ensemble_input_payload: dict[str, Any],
        ensemble_schema: dict[str, Any],
    ) -> None:
        validate_contract_definition(
            ensemble_input_payload, ensemble_schema, "ensemble_input"
        )

    def test_valid_output_payload_passes_contract(
        self,
        ensemble_output_payload: dict[str, Any],
        ensemble_schema: dict[str, Any],
    ) -> None:
        validate_contract_definition(
            ensemble_output_payload, ensemble_schema, "ensemble_output"
        )
        _assert_weights_sum_to_one(ensemble_output_payload)

    def test_pitcher_prob_nullable(
        self,
        ensemble_input_payload: dict[str, Any],
        ensemble_schema: dict[str, Any],
    ) -> None:
        payload = {**ensemble_input_payload, "pitcher_prob": None}
        validate_contract_definition(payload, ensemble_schema, "ensemble_input")

    def test_missing_base_elo_prob_is_rejected(
        self,
        ensemble_input_payload: dict[str, Any],
        ensemble_schema: dict[str, Any],
    ) -> None:
        invalid = {
            k: v for k, v in ensemble_input_payload.items() if k != "base_elo_prob"
        }
        with pytest.raises(ValidationError):
            validate_contract_definition(invalid, ensemble_schema, "ensemble_input")

    def test_out_of_range_base_elo_prob_is_rejected(
        self,
        ensemble_input_payload: dict[str, Any],
        ensemble_schema: dict[str, Any],
    ) -> None:
        invalid = {**ensemble_input_payload, "base_elo_prob": -0.01}
        with pytest.raises(ValidationError):
            validate_contract_definition(invalid, ensemble_schema, "ensemble_input")

    def test_missing_blended_prob_is_rejected(
        self,
        ensemble_output_payload: dict[str, Any],
        ensemble_schema: dict[str, Any],
    ) -> None:
        invalid = {
            k: v for k, v in ensemble_output_payload.items() if k != "blended_prob"
        }
        with pytest.raises(ValidationError):
            validate_contract_definition(
                invalid, ensemble_schema, "ensemble_output"
            )

    def test_missing_provenance_is_rejected(
        self,
        ensemble_output_payload: dict[str, Any],
        ensemble_schema: dict[str, Any],
    ) -> None:
        invalid = {
            k: v for k, v in ensemble_output_payload.items() if k != "provenance"
        }
        with pytest.raises(ValidationError):
            validate_contract_definition(
                invalid, ensemble_schema, "ensemble_output"
            )

    def test_missing_model_id_in_provenance_is_rejected(
        self,
        ensemble_output_payload: dict[str, Any],
        ensemble_schema: dict[str, Any],
    ) -> None:
        invalid = {
            **ensemble_output_payload,
            "provenance": {"components": {}},
        }
        with pytest.raises(ValidationError):
            validate_contract_definition(
                invalid, ensemble_schema, "ensemble_output"
            )

    def test_blended_prob_out_of_range_is_rejected(
        self,
        ensemble_output_payload: dict[str, Any],
        ensemble_schema: dict[str, Any],
    ) -> None:
        invalid = {**ensemble_output_payload, "blended_prob": 1.05}
        with pytest.raises(ValidationError):
            validate_contract_definition(
                invalid, ensemble_schema, "ensemble_output"
            )
