"""Tests for MLB Monte Carlo simulation engine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plugins.mlb_modeling.simulation import MLBMonteCarloSimulator
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "contracts" / "schemas"


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_ROOT / filename).read_text(encoding="utf-8"))


def test_simulator_rejects_counts_outside_contract_bounds() -> None:
    with pytest.raises(ValueError):
        MLBMonteCarloSimulator(simulation_count=4999)

    with pytest.raises(ValueError):
        MLBMonteCarloSimulator(simulation_count=10001)


def test_simulation_is_seed_deterministic_and_contract_valid() -> None:
    simulator = MLBMonteCarloSimulator(simulation_count=5000)

    first = simulator.simulate_game(
        game_id="745431",
        home_run_mean=4.8,
        away_run_mean=4.1,
        seed=745431,
    )
    second = simulator.simulate_game(
        game_id="745431",
        home_run_mean=4.8,
        away_run_mean=4.1,
        seed=745431,
    )

    assert first == second
    payload = first.to_payload()
    validate_contract_payload(payload, _load_schema("mlb_game_simulation_v1.json"))
    assert payload["home_win_prob"] > payload["away_win_prob"]
