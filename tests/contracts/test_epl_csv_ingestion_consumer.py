from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError
from naming_resolver import NamingContext, NamingResolver

from tests.contracts.fixtures.epl_csv_samples import (
    build_epl_canonical_team_name_cases,
    build_epl_csv_row,
)
from tests.contracts.helpers import validate_contract_payload


SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "epl_csv_ingestion_v1.json"


def _load_epl_csv_ingestion_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_epl_csv_ingestion_schema_defines_canonical_contract() -> None:
    """The canonical EPL ingestion schema freezes required fields and enum values."""
    schema = _load_epl_csv_ingestion_schema()

    assert schema["title"] == "EPL CSV Ingestion Contract"
    assert schema["required"] == [
        "Date",
        "HomeTeam",
        "AwayTeam",
        "FTHG",
        "FTAG",
        "FTR",
    ]
    assert schema["properties"]["FTR"]["enum"] == ["H", "D", "A"]


def test_valid_epl_csv_row_satisfies_contract() -> None:
    """A canonical EPL CSV row sample validates against the frozen schema."""
    validate_contract_payload(build_epl_csv_row(), _load_epl_csv_ingestion_schema())


@pytest.mark.parametrize(
    "missing_field",
    ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"],
)
def test_epl_csv_contract_rejects_missing_required_fields(missing_field: str) -> None:
    """Missing ingestion fields fail fast before the loader is exercised."""
    row = build_epl_csv_row()
    row.pop(missing_field)

    with pytest.raises(ValidationError):
        validate_contract_payload(row, _load_epl_csv_ingestion_schema())


@pytest.mark.parametrize("invalid_result", ["", "X", "HOME", "DRAW"])
def test_epl_csv_contract_rejects_invalid_full_time_results(invalid_result: str) -> None:
    """Only H, D, and A are valid EPL full-time result values."""
    row = build_epl_csv_row(FTR=invalid_result)

    with pytest.raises(ValidationError):
        validate_contract_payload(row, _load_epl_csv_ingestion_schema())


@pytest.mark.parametrize(
    ("raw_name", "expected_canonical"),
    build_epl_canonical_team_name_cases(),
)
def test_epl_csv_team_aliases_resolve_to_deterministic_canonical_names(
    raw_name: str, expected_canonical: str
) -> None:
    """EPL CSV team names resolve to the canonical Elo-facing names used downstream."""
    resolved = NamingResolver.resolve(
        NamingContext(sport="epl", source="elo", name=raw_name)
    )

    assert resolved == expected_canonical
