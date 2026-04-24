from __future__ import annotations

import json
from collections.abc import Iterable
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - dependency is optional during scaffold setup.
    Draft202012Validator = None


CONTRACTS_ROOT = Path(__file__).resolve().parent
FIXTURES_ROOT = CONTRACTS_ROOT / "fixtures"
SCHEMAS_ROOT = CONTRACTS_ROOT / "schemas"
DEFAULT_SCHEMA_VERSION = "v1"


class ContractValidationDependencyError(RuntimeError):
    """Raised when JSON Schema validation is requested without jsonschema."""


def schema_path(schema_group: str, schema_name: str, version: str = DEFAULT_SCHEMA_VERSION) -> Path:
    """Build the canonical path for a versioned EPL contract schema asset."""
    return SCHEMAS_ROOT / schema_group / version / f"{schema_name}.json"


def load_versioned_schema(
    schema_group: str,
    schema_name: str,
    version: str = DEFAULT_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Load a versioned EPL contract schema from the canonical schema tree."""
    contract_path = schema_path(schema_group=schema_group, schema_name=schema_name, version=version)
    return json.loads(contract_path.read_text(encoding="utf-8"))


def validate_contract_payload(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate a payload against a JSON Schema when jsonschema is available."""
    if Draft202012Validator is None:
        raise ContractValidationDependencyError(
            "jsonschema is not installed; validation helpers are unavailable in this scaffold."
        )

    Draft202012Validator(schema).validate(payload)


def build_contract_definition_schema(
    contract: dict[str, Any], definition: str
) -> dict[str, Any]:
    """Build a temporary schema that targets one contract definition."""
    return {
        "$schema": contract["$schema"],
        "$ref": f"#/$defs/{definition}",
        "$defs": contract["$defs"],
    }


def validate_contract_definition(
    payload: dict[str, Any], contract: dict[str, Any], definition: str
) -> None:
    """Validate a payload against a named definition in a composite contract."""
    validate_contract_payload(payload, build_contract_definition_schema(contract, definition))


def clone_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a defensive copy of a deterministic fixture payload."""
    return deepcopy(payload)


def serialize_contract_payload(payload: Any) -> Any:
    """Recursively coerce date-like values into schema-friendly JSON primitives."""
    if isinstance(payload, dict):
        return {key: serialize_contract_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [serialize_contract_payload(value) for value in payload]
    if hasattr(payload, "isoformat"):
        return payload.isoformat()
    return payload


def find_execute_params(execute_calls: Iterable[Any], table_name: str) -> list[dict[str, Any]]:
    """Collect DB execute params for INSERTs into a specific table."""
    matches: list[dict[str, Any]] = []
    for call in execute_calls:
        args = getattr(call, "args", ())
        if len(args) < 2 or not isinstance(args[0], str):
            continue
        if f"INSERT INTO {table_name}" not in args[0]:
            continue
        matches.append(dict(args[1]))
    return matches
