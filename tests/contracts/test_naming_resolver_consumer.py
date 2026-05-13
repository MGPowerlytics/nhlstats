"""Consumer contract tests for the NamingResolver boundary.

Tests that consumers can trust resolve and add_mapping payloads
produced by the NamingResolver.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from tests.contracts.fixtures.naming_resolver_samples import (
    build_add_mapping_payload,
    build_resolve_payload,
)
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema() -> dict[str, Any]:
    return json.loads(
        (SCHEMAS_ROOT / "naming_resolver_contract_v1.json").read_text(encoding="utf-8")
    )


@pytest.fixture(scope="module")
def naming_schema() -> dict[str, Any]:
    return _load_schema()


@pytest.fixture
def resolve_payload() -> dict[str, Any]:
    return build_resolve_payload()


@pytest.fixture
def add_mapping_payload() -> dict[str, Any]:
    return build_add_mapping_payload()


class TestNamingResolverConsumerContract:
    """Consumer guarantees for NamingResolver resolve/add_mapping outputs."""

    def test_valid_resolve_payload_passes_contract(
        self,
        resolve_payload: dict[str, Any],
        naming_schema: dict[str, Any],
    ) -> None:
        validate_contract_payload(resolve_payload, naming_schema)

    def test_valid_add_mapping_payload_passes_contract(
        self,
        add_mapping_payload: dict[str, Any],
        naming_schema: dict[str, Any],
    ) -> None:
        validate_contract_payload(add_mapping_payload, naming_schema)

    def test_resolved_name_is_non_empty_string(
        self,
        resolve_payload: dict[str, Any],
    ) -> None:
        resolved = resolve_payload["resolved_name"]
        assert isinstance(resolved, str)
        assert len(resolved) >= 1

    def test_canonical_name_is_non_empty_string(
        self,
        add_mapping_payload: dict[str, Any],
    ) -> None:
        canonical = add_mapping_payload["canonical_name"]
        assert isinstance(canonical, str)
        assert len(canonical) >= 1

    def test_resolve_input_key_has_min_items_2(
        self,
        resolve_payload: dict[str, Any],
    ) -> None:
        assert len(resolve_payload["input_key"]) >= 2

    def test_add_mapping_context_key_has_min_items_2(
        self,
        add_mapping_payload: dict[str, Any],
    ) -> None:
        assert len(add_mapping_payload["context_key"]) >= 2

    def test_resolve_was_mapped_is_boolean(
        self,
        resolve_payload: dict[str, Any],
    ) -> None:
        assert isinstance(resolve_payload["was_mapped"], bool)

    def test_add_mapping_success_is_boolean(
        self,
        add_mapping_payload: dict[str, Any],
    ) -> None:
        assert isinstance(add_mapping_payload["success"], bool)

    def test_missing_resolve_field_is_rejected(
        self,
        resolve_payload: dict[str, Any],
        naming_schema: dict[str, Any],
    ) -> None:
        invalid = {k: v for k, v in resolve_payload.items() if k != "resolved_name"}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, naming_schema)

    def test_missing_add_mapping_field_is_rejected(
        self,
        add_mapping_payload: dict[str, Any],
        naming_schema: dict[str, Any],
    ) -> None:
        invalid = {k: v for k, v in add_mapping_payload.items() if k != "canonical_name"}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, naming_schema)

    def test_unknown_field_is_rejected(
        self,
        resolve_payload: dict[str, Any],
        naming_schema: dict[str, Any],
    ) -> None:
        invalid = {**resolve_payload, "mystery_field": "spy"}
        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, naming_schema)
