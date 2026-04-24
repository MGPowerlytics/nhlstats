from __future__ import annotations

from typing import Any

from tests.contracts.helpers import load_versioned_schema, validate_contract_payload
from tests.contracts.fixtures.epl import (
    build_epl_game_payload,
    build_epl_governed_row,
    build_epl_market_payload,
)


def test_load_versioned_schema_reads_payload_asset() -> None:
    """Payload schemas load from the canonical versioned EPL location."""
    schema = load_versioned_schema("payloads", "epl_contract_stub")

    assert schema["title"] == "EPL Contract Payload Stub"
    assert schema["properties"]["competition"]["const"] == "EPL"


def test_load_versioned_schema_reads_governed_row_asset() -> None:
    """Governed row schemas load from the canonical versioned EPL location."""
    schema = load_versioned_schema("governed_rows", "epl_contract_stub")

    assert schema["title"] == "EPL Governed Row Stub"
    assert schema["properties"]["competition"]["const"] == "EPL"


def test_epl_fixture_builders_are_deterministic() -> None:
    """EPL fixture builders return repeatable canonical sample payloads."""
    first: dict[str, Any] = {
        "game": build_epl_game_payload(),
        "market": build_epl_market_payload(),
        "row": build_epl_governed_row(),
    }
    second: dict[str, Any] = {
        "game": build_epl_game_payload(),
        "market": build_epl_market_payload(),
        "row": build_epl_governed_row(),
    }

    assert first == second
    assert first["game"]["competition"] == "EPL"
    assert first["market"]["sport"] == "EPL"
    assert first["row"]["competition"] == "EPL"


def test_epl_shared_fixtures_validate_against_stub_schemas() -> None:
    """Shared EPL scaffold fixtures validate against their canonical stub schemas."""
    payload_schema = load_versioned_schema("payloads", "epl_contract_stub")
    governed_row_schema = load_versioned_schema("governed_rows", "epl_contract_stub")

    validate_contract_payload(build_epl_game_payload(), payload_schema)
    validate_contract_payload(build_epl_market_payload(), payload_schema)
    validate_contract_payload(build_epl_governed_row(), governed_row_schema)
