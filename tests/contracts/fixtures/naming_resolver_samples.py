"""Deterministic NamingResolver fixtures for consumer contract tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from plugins.naming_resolver import NamingContext, NamingResolver


NBA_SPORT = "nba"
NHL_SPORT = "nhl"
KALSHI_SOURCE = "kalshi"

NBA_ABBREV = "lal"
NBA_CANONICAL = "Los Angeles Lakers"

NHL_ABBREV = "tor"
NHL_CANONICAL = "Toronto Maple Leafs"

UNKNOWN_ABBREV = "xyz"
UNKNOWN_SPORT = "unknown_sport"


def build_nba_naming_context() -> NamingContext:
    """Build a NamingContext for "LAL" → "Los Angeles Lakers"."""
    return NamingContext(sport=NBA_SPORT, source=KALSHI_SOURCE, name=NBA_ABBREV)


def build_nhl_naming_context() -> NamingContext:
    """Build a NamingContext for "TOR" → "Toronto Maple Leafs"."""
    return NamingContext(sport=NHL_SPORT, source=KALSHI_SOURCE, name=NHL_ABBREV)


def build_unknown_naming_context() -> NamingContext:
    """Build a NamingContext that will NOT match any mapping."""
    return NamingContext(sport=UNKNOWN_SPORT, source=KALSHI_SOURCE, name=UNKNOWN_ABBREV)


def _build_resolve_payload() -> Dict[str, Any]:
    """Build the canonical resolve result payload."""
    context = build_nba_naming_context()
    resolved = NamingResolver.resolve(context)
    return {
        "schema_version": "v1",
        "payload_kind": "resolve_result",
        "input_key": list(context.to_key()),
        "resolved_name": resolved,
        "was_mapped": True,
    }


_BASE_RESOLVE_PAYLOAD: Dict[str, Any] = _build_resolve_payload()


def build_resolve_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical resolve result payload."""
    return deepcopy(_BASE_RESOLVE_PAYLOAD)


def _build_add_mapping_payload() -> Dict[str, Any]:
    """Build the canonical add_mapping result payload."""
    context = NamingContext(sport="test_sport", source="test_source", name="test_name")
    canonical = "Test Canonical Name"
    NamingResolver.add_mapping(context, canonical)
    return {
        "schema_version": "v1",
        "payload_kind": "add_mapping_result",
        "context_key": list(context.to_key()),
        "canonical_name": canonical,
        "success": True,
    }


_BASE_ADD_MAPPING_PAYLOAD: Dict[str, Any] = _build_add_mapping_payload()


def build_add_mapping_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical add_mapping result payload."""
    return deepcopy(_BASE_ADD_MAPPING_PAYLOAD)
