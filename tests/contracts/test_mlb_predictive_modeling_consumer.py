"""Consumer contracts for MLB predictive-modeling boundaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest
from jsonschema.exceptions import ValidationError

from tests.contracts.fixtures.mlb_predictive_modeling_samples import (
    build_mlb_advanced_features_payload,
    build_mlb_environment_features_payload,
    build_mlb_game_simulation_payload,
    build_mlb_market_signals_payload,
    build_mlb_model_prediction_payload,
    build_mlb_pa_simulation_payload,
    build_mlb_prop_prediction_payload,
    build_mlb_travel_fatigue_payload,
)
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema(filename: str) -> dict[str, Any]:
    return json.loads((SCHEMAS_ROOT / filename).read_text(encoding="utf-8"))


CONTRACT_CASES: tuple[tuple[str, Callable[[], dict[str, Any]]], ...] = (
    ("mlb_advanced_features_v1.json", build_mlb_advanced_features_payload),
    ("mlb_environment_features_v1.json", build_mlb_environment_features_payload),
    ("mlb_travel_fatigue_v1.json", build_mlb_travel_fatigue_payload),
    ("mlb_market_signals_v1.json", build_mlb_market_signals_payload),
    ("mlb_pa_simulation_v1.json", build_mlb_pa_simulation_payload),
    ("mlb_game_simulation_v1.json", build_mlb_game_simulation_payload),
    ("mlb_model_prediction_v1.json", build_mlb_model_prediction_payload),
    ("mlb_prop_prediction_v1.json", build_mlb_prop_prediction_payload),
)


@pytest.mark.parametrize(("schema_file", "payload_builder"), CONTRACT_CASES)
def test_valid_predictive_modeling_payloads_pass_contract(
    schema_file: str,
    payload_builder: Callable[[], dict[str, Any]],
) -> None:
    """Each deterministic MLB predictive payload satisfies its canonical schema."""
    validate_contract_payload(payload_builder(), _load_schema(schema_file))


def test_advanced_features_reject_unknown_top_level_fields() -> None:
    """The advanced feature boundary is strict to surface schema drift."""
    payload = build_mlb_advanced_features_payload()
    payload["untracked_signal"] = 1.23

    with pytest.raises(ValidationError):
        validate_contract_payload(
            payload, _load_schema("mlb_advanced_features_v1.json")
        )


def test_environment_requires_hit_distance_adjustment_field() -> None:
    """Temperature-to-distance adjustment must be explicitly present or null."""
    payload = build_mlb_environment_features_payload()
    del payload["hit_distance_adjustment_ft"]

    with pytest.raises(ValidationError):
        validate_contract_payload(
            payload, _load_schema("mlb_environment_features_v1.json")
        )


def test_travel_rejects_positive_west_to_east_penalty() -> None:
    """Travel penalties are encoded as non-positive probability/rating adjustments."""
    payload = build_mlb_travel_fatigue_payload()
    payload["west_to_east_penalty"] = 0.2

    with pytest.raises(ValidationError):
        validate_contract_payload(payload, _load_schema("mlb_travel_fatigue_v1.json"))


def test_market_signals_allow_public_source_unavailable_ticket_money() -> None:
    """Public-source-first market signals may explicitly mark proprietary data unavailable."""
    payload = build_mlb_market_signals_payload()
    payload["ticket_pct"] = None
    payload["money_pct"] = None
    payload["availability"] = "unavailable"

    validate_contract_payload(payload, _load_schema("mlb_market_signals_v1.json"))


def test_game_simulation_requires_at_least_5000_runs() -> None:
    """The game-simulation contract enforces the requested simulation floor."""
    payload = build_mlb_game_simulation_payload()
    payload["simulation_count"] = 4999

    with pytest.raises(ValidationError):
        validate_contract_payload(payload, _load_schema("mlb_game_simulation_v1.json"))


def test_prop_prediction_rejects_unknown_prop_type() -> None:
    """Initial prop scope is intentionally limited to strikeouts, hits, and total bases."""
    payload = build_mlb_prop_prediction_payload()
    payload["prop_type"] = "runs"

    with pytest.raises(ValidationError):
        validate_contract_payload(payload, _load_schema("mlb_prop_prediction_v1.json"))
