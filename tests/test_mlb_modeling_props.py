"""Tests for MLB PA and prop modeling helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plugins.mlb_modeling.props import (
    PAOutcomeProbabilities,
    PropPredictionBuilder,
    build_pa_outcome_probabilities,
    empirical_bayes_rate,
    log5_probability,
)
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "contracts" / "schemas"


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_ROOT / filename).read_text(encoding="utf-8"))


def test_empirical_bayes_rate_shrinks_to_prior() -> None:
    rate = empirical_bayes_rate(
        observed_successes=5,
        observed_trials=10,
        prior_rate=0.25,
        prior_strength=30,
    )

    assert rate == pytest.approx((5 + 0.25 * 30) / 40)


def test_log5_probability_combines_rates_relative_to_league() -> None:
    probability = log5_probability(
        batter_rate=0.30,
        pitcher_rate_allowed=0.32,
        league_rate=0.22,
    )

    assert probability > 0.30
    assert 0.0 < probability < 1.0


def test_build_pa_outcome_probabilities_matches_contract() -> None:
    pa_probs = build_pa_outcome_probabilities(
        batter_rates={
            "strikeout": 0.22,
            "walk_hbp": 0.09,
            "single": 0.15,
            "double_triple": 0.05,
            "home_run": 0.04,
        },
        pitcher_rates_allowed={
            "strikeout": 0.28,
            "walk_hbp": 0.08,
            "single": 0.14,
            "double_triple": 0.04,
            "home_run": 0.03,
        },
        league_rates={
            "strikeout": 0.22,
            "walk_hbp": 0.085,
            "single": 0.145,
            "double_triple": 0.048,
            "home_run": 0.032,
        },
    )
    payload = {
        "schema_version": "v1",
        "sport": "MLB",
        "payload_kind": "pa_simulation",
        "game_id": "745431",
        "batter_id": "592450",
        "pitcher_id": "543037",
        "method": "log5_empirical_bayes",
        "outcome_probs": pa_probs.to_payload(),
        "source_features_hash": "abc123def4567890",
        "model_version": "mlb_pa_public_test_v1",
    }

    assert sum(pa_probs.to_payload().values()) == pytest.approx(1.0)
    validate_contract_payload(payload, _load_schema("mlb_pa_simulation_v1.json"))


def test_prop_prediction_builder_outputs_contract_payload() -> None:
    pa_probs = PAOutcomeProbabilities(
        strikeout=0.28,
        walk_hbp=0.09,
        single=0.14,
        double_triple=0.05,
        home_run=0.03,
        ball_in_play_out=0.41,
    )
    over_prob = PropPredictionBuilder.strikeout_over_probability(
        pa_probs,
        expected_batters_faced=25,
        line=6.5,
    )
    payload = PropPredictionBuilder.build_payload(
        prediction_id="mlb_prop_public_test_745431_543037_strikeouts",
        model_version="mlb_prop_public_test_v1",
        game_id="745431",
        player_id="543037",
        player_name="Gerrit Cole",
        team="New York Yankees",
        prop_type="strikeouts",
        line=6.5,
        over_prob=over_prob,
        market_prob=0.52,
        simulation_summary={"mean": 7.0},
    )

    validate_contract_payload(payload, _load_schema("mlb_prop_prediction_v1.json"))
    assert payload["over_prob"] > 0.5
    assert payload["under_prob"] == pytest.approx(1.0 - payload["over_prob"])
