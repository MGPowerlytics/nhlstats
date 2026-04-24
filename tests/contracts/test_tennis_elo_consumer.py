"""Consumer contract tests for the tennis Elo prediction payload."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from tests.contracts.fixtures.tennis_elo_samples import (
    build_tennis_elo_prediction,
    build_tennis_elo_prediction_wta,
)


SCHEMA_PATH = (
    Path(__file__).resolve().parent / "schemas" / "tennis_elo_prediction_v1.json"
)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_canonical_atp_prediction_satisfies_contract() -> None:
    Draft202012Validator(_load_schema()).validate(build_tennis_elo_prediction())


def test_wta_prediction_satisfies_contract() -> None:
    Draft202012Validator(_load_schema()).validate(build_tennis_elo_prediction_wta())


@pytest.mark.parametrize(
    "missing_field",
    [
        "schema_version",
        "sport",
        "payload_kind",
        "tour",
        "raw_prob_a",
        "calibrated_prob_a",
    ],
)
def test_prediction_contract_rejects_missing_required_field(
    missing_field: str,
) -> None:
    payload = build_tennis_elo_prediction()
    payload.pop(missing_field)
    with pytest.raises(ValidationError):
        Draft202012Validator(_load_schema()).validate(payload)


def test_prediction_contract_rejects_invalid_tour() -> None:
    payload = build_tennis_elo_prediction(tour="DAVIS")
    with pytest.raises(ValidationError):
        Draft202012Validator(_load_schema()).validate(payload)


def test_prediction_contract_rejects_out_of_range_probability() -> None:
    payload = build_tennis_elo_prediction(raw_prob_a=1.2)
    with pytest.raises(ValidationError):
        Draft202012Validator(_load_schema()).validate(payload)
