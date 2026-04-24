"""Consumer contract tests for the Tennis Sackmann/tennis-data CSV ingestion boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from tests.contracts.fixtures.tennis_csv_samples import (
    build_tennis_csv_minimal_row,
    build_tennis_csv_row,
)


SCHEMA_PATH = (
    Path(__file__).resolve().parent / "schemas" / "tennis_csv_ingestion_v1.json"
)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_canonical_tennis_csv_row_satisfies_contract() -> None:
    Draft202012Validator(_load_schema()).validate(build_tennis_csv_row())


def test_minimal_tennis_csv_row_satisfies_contract() -> None:
    Draft202012Validator(_load_schema()).validate(build_tennis_csv_minimal_row())


@pytest.mark.parametrize("missing_field", ["Date", "Winner", "Loser"])
def test_tennis_csv_contract_rejects_missing_required_fields(
    missing_field: str,
) -> None:
    row = build_tennis_csv_row()
    row.pop(missing_field)
    with pytest.raises(ValidationError):
        Draft202012Validator(_load_schema()).validate(row)


def test_tennis_csv_contract_rejects_blank_winner() -> None:
    row = build_tennis_csv_row(Winner="")
    with pytest.raises(ValidationError):
        Draft202012Validator(_load_schema()).validate(row)
