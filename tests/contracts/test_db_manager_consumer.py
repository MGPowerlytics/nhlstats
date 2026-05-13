"""Consumer contract tests for the DBManager boundary.

Consumers trust the DBManager to return structured results for three
payload kinds:
  - fetch_df_result: columns (list[str]) + rows (list[list])
  - fetch_scalar_result: value (number | string | null)
  - execution_result: rowcount (int) + success (bool)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from tests.contracts.fixtures.db_manager_samples import (
    build_db_execution_payload,
    build_db_fetch_df_payload,
    build_db_fetch_scalar_payload,
)
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema() -> dict[str, Any]:
    return json.loads(
        (SCHEMAS_ROOT / "db_manager_contract_v1.json").read_text(encoding="utf-8")
    )


def _validate_definition(payload: dict[str, Any], definition: str) -> None:
    """Validate a payload against a single $defs entry in the contract schema."""
    schema = _load_schema()
    v_schema: dict[str, Any] = {
        "$schema": schema["$schema"],
        "$ref": f"#/$defs/{definition}",
        "$defs": schema["$defs"],
    }
    validate_contract_payload(payload, v_schema)


class TestDbManagerFetchDfConsumerContract:
    """Consumer guarantees for DBManager.fetch_df() outputs."""

    def test_canonical_fetch_df_payload_passes_contract(self) -> None:
        payload = build_db_fetch_df_payload()
        _validate_definition(payload, "fetch_df_result")

    def test_fetch_df_has_non_empty_columns(self) -> None:
        payload = build_db_fetch_df_payload()
        assert len(payload["columns"]) > 0

    def test_fetch_df_columns_and_rows_align(self) -> None:
        payload = build_db_fetch_df_payload()
        expected_width = len(payload["columns"])
        for row in payload["rows"]:
            assert len(row) == expected_width, (
                f"Row length {len(row)} != column count {expected_width}"
            )

    def test_fetch_df_empty_rows_is_valid(self) -> None:
        payload = build_db_fetch_df_payload()
        payload["rows"] = []
        _validate_definition(payload, "fetch_df_result")

    def test_fetch_df_empty_columns_and_rows_is_valid(self) -> None:
        payload: dict[str, Any] = {"columns": [], "rows": []}
        _validate_definition(payload, "fetch_df_result")

    def test_fetch_df_missing_columns_is_rejected(self) -> None:
        payload = build_db_fetch_df_payload()
        invalid = {k: v for k, v in payload.items() if k != "columns"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "fetch_df_result")

    def test_fetch_df_missing_rows_is_rejected(self) -> None:
        payload = build_db_fetch_df_payload()
        invalid = {k: v for k, v in payload.items() if k != "rows"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "fetch_df_result")

    def test_fetch_df_non_string_column_is_rejected(self) -> None:
        payload = build_db_fetch_df_payload()
        invalid = {**payload, "columns": [1, 2, 3]}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "fetch_df_result")

    def test_fetch_df_unknown_field_is_rejected(self) -> None:
        payload = build_db_fetch_df_payload()
        invalid = {**payload, "extra_metadata": "stowaway"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "fetch_df_result")


class TestDbManagerFetchScalarConsumerContract:
    """Consumer guarantees for DBManager.fetch_scalar() outputs."""

    def test_canonical_fetch_scalar_payload_passes_contract(self) -> None:
        payload = build_db_fetch_scalar_payload()
        _validate_definition(payload, "fetch_scalar_result")

    def test_scalar_value_is_integer(self) -> None:
        payload = build_db_fetch_scalar_payload()
        assert isinstance(payload["value"], int)

    def test_scalar_value_is_string(self) -> None:
        payload = {"value": "hello"}
        _validate_definition(payload, "fetch_scalar_result")

    def test_scalar_value_is_null(self) -> None:
        payload = {"value": None}
        _validate_definition(payload, "fetch_scalar_result")

    def test_scalar_value_is_float(self) -> None:
        payload = {"value": 3.14}
        _validate_definition(payload, "fetch_scalar_result")

    def test_scalar_missing_value_is_rejected(self) -> None:
        invalid: dict[str, Any] = {}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "fetch_scalar_result")

    def test_scalar_boolean_is_rejected(self) -> None:
        payload = {"value": True}
        with pytest.raises(ValidationError):
            _validate_definition(payload, "fetch_scalar_result")

    def test_scalar_unknown_field_is_rejected(self) -> None:
        payload = {"value": 42, "extra": "spy"}
        with pytest.raises(ValidationError):
            _validate_definition(payload, "fetch_scalar_result")


class TestDbManagerExecutionConsumerContract:
    """Consumer guarantees for DBManager.execute() outputs."""

    def test_canonical_execution_payload_passes_contract(self) -> None:
        payload = build_db_execution_payload()
        _validate_definition(payload, "execution_result")

    def test_execution_success_is_true(self) -> None:
        payload = build_db_execution_payload()
        assert payload["success"] is True

    def test_execution_rowcount_is_non_negative(self) -> None:
        payload = build_db_execution_payload()
        assert payload["rowcount"] >= 0

    def test_execution_missing_rowcount_is_rejected(self) -> None:
        payload = build_db_execution_payload()
        invalid = {k: v for k, v in payload.items() if k != "rowcount"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "execution_result")

    def test_execution_missing_success_is_rejected(self) -> None:
        payload = build_db_execution_payload()
        invalid = {k: v for k, v in payload.items() if k != "success"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "execution_result")

    def test_execution_non_integer_rowcount_is_rejected(self) -> None:
        payload = build_db_execution_payload()
        invalid = {**payload, "rowcount": "one"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "execution_result")

    def test_execution_negative_rowcount_is_allowed(self) -> None:
        payload = {"rowcount": -1, "success": True}
        _validate_definition(payload, "execution_result")

    def test_execution_non_boolean_success_is_rejected(self) -> None:
        payload = build_db_execution_payload()
        invalid = {**payload, "success": "yes"}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "execution_result")

    def test_execution_unknown_field_is_rejected(self) -> None:
        payload = build_db_execution_payload()
        invalid = {**payload, "mystery_rows": 999}
        with pytest.raises(ValidationError):
            _validate_definition(invalid, "execution_result")

    def test_execution_failure_payload_is_valid(self) -> None:
        payload = {"rowcount": 0, "success": False}
        _validate_definition(payload, "execution_result")
