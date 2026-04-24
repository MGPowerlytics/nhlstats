"""Consumer contract tests for the Tennis bet opportunity payload."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from tests.contracts.fixtures.tennis_bet_opportunity_samples import (
    build_tennis_bet_opportunity,
    build_tennis_bet_opportunity_clamped_edge,
    build_tennis_bet_opportunity_high_edge,
)


SCHEMA_PATH = (
    Path(__file__).resolve().parent / "schemas" / "tennis_bet_opportunity_v1.json"
)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_canonical_opportunity_satisfies_contract() -> None:
    Draft202012Validator(_load_schema()).validate(build_tennis_bet_opportunity())


def test_high_edge_opportunity_satisfies_contract() -> None:
    Draft202012Validator(_load_schema()).validate(
        build_tennis_bet_opportunity_high_edge()
    )


def test_clamped_edge_opportunity_satisfies_contract() -> None:
    Draft202012Validator(_load_schema()).validate(
        build_tennis_bet_opportunity_clamped_edge()
    )


@pytest.mark.parametrize(
    "missing_field",
    ["sport", "game_id", "side", "elo_prob", "market_prob", "edge", "tour"],
)
def test_opportunity_contract_rejects_missing_required_field(
    missing_field: str,
) -> None:
    payload = build_tennis_bet_opportunity()
    payload.pop(missing_field)
    with pytest.raises(ValidationError):
        Draft202012Validator(_load_schema()).validate(payload)


def test_opportunity_contract_rejects_invalid_tour() -> None:
    payload = build_tennis_bet_opportunity(tour="DAVIS")
    with pytest.raises(ValidationError):
        Draft202012Validator(_load_schema()).validate(payload)


def test_opportunity_contract_rejects_edge_above_max() -> None:
    payload = build_tennis_bet_opportunity(edge=0.50)
    with pytest.raises(ValidationError):
        Draft202012Validator(_load_schema()).validate(payload)
