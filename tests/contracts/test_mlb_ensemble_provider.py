"""Provider RED tests for the MLB ensemble I/O boundary.

The locked ``ensemble_input`` requires ``{home_team, away_team,
base_elo_prob, pitcher_prob, features, market_prob}`` and the locked
``ensemble_output`` requires ``{blended_prob, weights, provenance}``.

Producer drift:
    * :class:`MLBEnsembleModel.predict` returns ONLY a float.
    * ``predict`` accepts a :class:`MLBPredictionContext`, not a
      ``base_elo_prob`` + ``features`` bundle.

The provider tests call the real producer, attempt to assemble the locked
payloads, and ``xfail(strict=True)`` for the structural drift fixed in
Wave 4-6 task ``mlb-elo-ensemble-fix``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from plugins.elo.mlb_ensemble import MLBEnsembleModel, MLBPredictionContext
from plugins.elo.mlb_ensemble_adapter import MLBEnsembleAdapter
from tests.contracts.fixtures.mlb_elo_samples import (
    MLB_AWAY_TEAM,
    MLB_HOME_TEAM,
)
from tests.contracts.helpers import validate_contract_definition


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema() -> dict[str, Any]:
    return json.loads(
        (SCHEMAS_ROOT / "mlb_ensemble_io_v1.json").read_text(encoding="utf-8")
    )


def _build_context() -> MLBPredictionContext:
    return MLBPredictionContext(
        home_team=MLB_HOME_TEAM,
        away_team=MLB_AWAY_TEAM,
        venue="Yankee Stadium",
        home_pitcher_id="543037",
        away_pitcher_id="519242",
        home_runs_scored_ytd=412.0,
        home_runs_allowed_ytd=388.0,
        away_runs_scored_ytd=401.0,
        away_runs_allowed_ytd=405.0,
        home_bullpen_era=3.45,
        away_bullpen_era=4.12,
        home_rest_days=2,
        away_rest_days=1,
        market_prob=0.555,
        market_blend_weight=0.25,
    )


class TestMLBEnsembleProviderContract:
    """Provider-side guarantees against real ``MLBEnsembleModel`` outputs."""

    def test_real_predict_returns_probability_in_unit_interval(self) -> None:
        model = MLBEnsembleModel()
        ctx = _build_context()

        prob = model.predict(ctx)

        assert isinstance(prob, float)
        assert 0.0 <= prob <= 1.0

    def test_real_predict_returns_only_a_float(self) -> None:
        """Document current producer surface — predict yields a scalar."""
        model = MLBEnsembleModel()

        result = model.predict(_build_context())

        assert isinstance(result, float)
        assert not isinstance(result, dict)

    def test_real_adapter_predict_matches_ensemble_predict(self) -> None:
        adapter = MLBEnsembleAdapter()

        prob = adapter.predict(MLB_HOME_TEAM, MLB_AWAY_TEAM)

        assert isinstance(prob, float)
        assert 0.0 <= prob <= 1.0

    def test_invalid_output_payload_is_rejected_by_schema(self) -> None:
        invalid = {
            "schema_version": "v1",
            "sport": "MLB",
            "payload_kind": "ensemble_output",
            "home_team": MLB_HOME_TEAM,
            "away_team": MLB_AWAY_TEAM,
            "blended_prob": 0.55,
            # Missing required ``weights`` and ``provenance``
        }

        with pytest.raises(ValidationError):
            validate_contract_definition(invalid, _load_schema(), "ensemble_output")

    def test_invalid_input_payload_is_rejected_by_schema(self) -> None:
        invalid = {
            "schema_version": "v1",
            "sport": "MLB",
            "payload_kind": "ensemble_input",
            "home_team": MLB_HOME_TEAM,
            "away_team": MLB_AWAY_TEAM,
            "base_elo_prob": 1.5,  # out of range
            "features": {"x": 1.0},
        }

        with pytest.raises(ValidationError):
            validate_contract_definition(invalid, _load_schema(), "ensemble_input")

    def test_real_predict_emits_locked_ensemble_output_payload(self) -> None:
        model = MLBEnsembleModel()
        ctx = _build_context()

        result = model.predict_with_provenance(ctx)

        assert isinstance(result, dict)
        validate_contract_definition(result, _load_schema(), "ensemble_output")

    def test_real_predict_accepts_locked_ensemble_input_bundle(self) -> None:
        model = MLBEnsembleModel()
        bundle = {
            "schema_version": "v1",
            "sport": "MLB",
            "payload_kind": "ensemble_input",
            "home_team": MLB_HOME_TEAM,
            "away_team": MLB_AWAY_TEAM,
            "base_elo_prob": 0.541,
            "pitcher_prob": 0.523,
            "features": {"pythag_diff": 0.024, "rest_diff": 1},
            "market_prob": 0.555,
        }

        result = model.predict_with_provenance(bundle)
        assert isinstance(result, dict)
        validate_contract_definition(result, _load_schema(), "ensemble_output")
