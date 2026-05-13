"""Provider contract tests for the NamingResolver boundary.

These tests exercise the real :class:`NamingResolver` producer against
the frozen JSON Schema contract. They verify that resolve and add_mapping
outputs conform to the contract, and detect drift if the implementation
changes behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from plugins.naming_resolver import NamingContext, NamingResolver
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema() -> dict[str, Any]:
    return json.loads(
        (SCHEMAS_ROOT / "naming_resolver_contract_v1.json").read_text(encoding="utf-8")
    )


def _assemble_resolve_payload(context: NamingContext) -> dict[str, Any]:
    """Assemble a contract payload from a real NamingResolver resolve call."""
    resolved = NamingResolver.resolve(context)
    was_mapped = resolved != context.name
    return {
        "schema_version": "v1",
        "payload_kind": "resolve_result",
        "input_key": list(context.to_key()),
        "resolved_name": resolved,
        "was_mapped": was_mapped,
    }


def _assemble_add_mapping_payload(
    context: NamingContext,
    canonical_name: str,
) -> dict[str, Any]:
    """Assemble a contract payload from a real NamingResolver add_mapping call."""
    NamingResolver.add_mapping(context, canonical_name)
    return {
        "schema_version": "v1",
        "payload_kind": "add_mapping_result",
        "context_key": list(context.to_key()),
        "canonical_name": canonical_name,
        "success": True,
    }


# Sport/source combos that won't collide with existing production mappings.
_CONTRACT_SPORT = "contract_test_sport"
_CONTRACT_SOURCE = "contract_test_source"


class TestNamingResolverProviderContract:
    """Provider-side guarantees against the real ``NamingResolver``."""

    def test_resolve_known_team_returns_canonical_name(self) -> None:
        """Resolving a known NBA team returns its cannonical name."""
        context = NamingContext(sport="nba", source="kalshi", name="lal")
        payload = _assemble_resolve_payload(context)

        validate_contract_payload(payload, _load_schema())
        assert payload["resolved_name"] == "Los Angeles Lakers"
        assert payload["was_mapped"] is True

    def test_resolve_unknown_team_returns_input(self) -> None:
        """Resolving an unmapped name returns the input name unchanged."""
        context = NamingContext(
            sport=_CONTRACT_SPORT,
            source=_CONTRACT_SOURCE,
            name="unknown_team_xyz",
        )
        payload = _assemble_resolve_payload(context)

        validate_contract_payload(payload, _load_schema())
        assert payload["resolved_name"] == "unknown_team_xyz"
        assert payload["was_mapped"] is False

    def test_add_mapping_then_resolve_returns_newly_mapped_name(self) -> None:
        """Adding a mapping makes the newly mapped name resolvable."""
        ctx = NamingContext(
            sport=_CONTRACT_SPORT,
            source=_CONTRACT_SOURCE,
            name="short_name",
        )
        canonical = "Canonical Full Name"

        add_payload = _assemble_add_mapping_payload(ctx, canonical)
        validate_contract_payload(add_payload, _load_schema())
        assert add_payload["success"] is True

        resolve_payload = _assemble_resolve_payload(ctx)
        validate_contract_payload(resolve_payload, _load_schema())
        assert resolve_payload["resolved_name"] == canonical
        assert resolve_payload["was_mapped"] is True

    def test_drift_detection_invalid_resolve_payload_rejected(self) -> None:
        """A malformed resolve payload is correctly rejected by the schema."""
        context = NamingContext(sport="nba", source="kalshi", name="lal")
        payload = _assemble_resolve_payload(context)

        # Corrupt: set resolved_name to empty string (violates minLength)
        payload["resolved_name"] = ""

        with pytest.raises(ValidationError):
            validate_contract_payload(payload, _load_schema())

    def test_drift_detection_missing_resolved_name_rejected(self) -> None:
        """A resolve payload missing required field is rejected."""
        context = NamingContext(sport="nba", source="kalshi", name="lal")
        payload = _assemble_resolve_payload(context)

        invalid = {k: v for k, v in payload.items() if k != "resolved_name"}

        with pytest.raises(ValidationError):
            validate_contract_payload(invalid, _load_schema())

    def test_drift_detection_unknown_field_rejected(self) -> None:
        """A resolve payload with an unexpected field is rejected."""
        context = NamingContext(sport="nba", source="kalshi", name="lal")
        payload = _assemble_resolve_payload(context)
        payload["rogue_field"] = "should_not_be_here"

        with pytest.raises(ValidationError):
            validate_contract_payload(payload, _load_schema())
