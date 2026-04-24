"""Consumer contract tests for the Tennis bet_recommendations row payload."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from tests.contracts.fixtures.tennis_bet_recommendation_samples import (
    build_tennis_persisted_recommendation_row,
    build_tennis_saved_bet_payload,
    build_tennis_saved_bet_payload_synthetic_ticker,
)


SCHEMA_PATH = (
    Path(__file__).resolve().parent
    / "schemas"
    / "tennis_bet_recommendation_row_v1.json"
)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator(def_name: str) -> Draft202012Validator:
    schema = _load_schema()
    resource = Resource.from_contents(schema)
    registry = Registry().with_resource(uri=schema["$id"], resource=resource)
    return Draft202012Validator(
        {"$ref": f"{schema['$id']}#/$defs/{def_name}"}, registry=registry
    )


def test_canonical_saved_payload_satisfies_contract() -> None:
    _validator("saved_payload").validate(build_tennis_saved_bet_payload())


def test_synthetic_ticker_saved_payload_satisfies_contract() -> None:
    _validator("saved_payload").validate(
        build_tennis_saved_bet_payload_synthetic_ticker()
    )


def test_canonical_persisted_row_satisfies_contract() -> None:
    _validator("persisted_row").validate(build_tennis_persisted_recommendation_row())


@pytest.mark.parametrize(
    "missing_field",
    ["bet_id", "sport", "recommendation_date", "ticker", "edge", "confidence"],
)
def test_persisted_row_rejects_missing_required_field(missing_field: str) -> None:
    payload = build_tennis_persisted_recommendation_row()
    payload.pop(missing_field)
    with pytest.raises(ValidationError):
        _validator("persisted_row").validate(payload)


def test_persisted_row_rejects_invalid_bet_id_pattern() -> None:
    payload = build_tennis_persisted_recommendation_row(bet_id="MLB_2026-04-07_X_home")
    with pytest.raises(ValidationError):
        _validator("persisted_row").validate(payload)


def test_persisted_row_rejects_non_tennis_sport() -> None:
    payload = build_tennis_persisted_recommendation_row(sport="MLB")
    with pytest.raises(ValidationError):
        _validator("persisted_row").validate(payload)
