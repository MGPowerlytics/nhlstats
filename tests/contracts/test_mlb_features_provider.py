"""Provider RED tests for MLB feature engineering boundary.

``plugins/elo/mlb_features.py`` is a collection of helper functions plus
the :class:`MLBPredictionContext` dataclass. The locked
``mlb_features_v1`` contract describes the per-matchup feature bundle the
ensemble consumes (mirrors ``MLBPredictionContext`` shape with the
contract envelope keys). This test exercises the real helpers, builds a
real ``MLBPredictionContext``, and validates the dataclass shape against
the schema.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from plugins.elo.mlb_ensemble import MLBPredictionContext
from plugins.elo.mlb_features import (
    bullpen_elo_adjustment,
    pythagorean_elo_adjustment,
    pythagorean_win_pct,
    rest_elo_adjustment,
)
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema() -> dict[str, Any]:
    return json.loads(
        (SCHEMAS_ROOT / "mlb_features_v1.json").read_text(encoding="utf-8")
    )


def _build_context() -> MLBPredictionContext:
    return MLBPredictionContext(
        home_team="New York Yankees",
        away_team="Boston Red Sox",
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
        market_prob=0.56,
        market_blend_weight=0.25,
    )


def _wrap_context_payload(ctx: MLBPredictionContext) -> dict[str, Any]:
    """Wrap a real ``MLBPredictionContext`` into the locked contract shape."""
    payload: dict[str, Any] = {
        "schema_version": "v1",
        "sport": "MLB",
        "payload_kind": "feature_vector",
    }
    payload.update(asdict(ctx))
    return payload


class TestMLBFeaturesProviderContract:
    """Provider-side guarantees against real feature helpers and context."""

    def test_real_pythagorean_win_pct_is_in_unit_interval(self) -> None:
        result = pythagorean_win_pct(412.0, 388.0)

        assert 0.0 <= float(result) <= 1.0

    def test_real_pythagorean_adjustment_is_finite_number(self) -> None:
        adj = pythagorean_elo_adjustment(412.0, 388.0, 401.0, 405.0)

        assert isinstance(adj, float)
        # Helper clips to MAX_FEATURE_ELO; assert reasonable finite range.
        assert -200.0 < adj < 200.0

    def test_real_bullpen_adjustment_favors_home_when_better(self) -> None:
        # Lower bullpen ERA = better. Home is better → positive adj.
        adj = bullpen_elo_adjustment(3.00, 4.50)

        assert adj > 0.0

    def test_real_rest_adjustment_favors_more_rested_team(self) -> None:
        adj = rest_elo_adjustment(2, 0)

        assert adj > 0.0

    def test_real_prediction_context_payload_matches_contract(self) -> None:
        ctx = _build_context()

        payload = _wrap_context_payload(ctx)

        validate_contract_payload(payload, _load_schema())

    def test_invalid_context_payload_is_rejected_by_schema(self) -> None:
        ctx = _build_context()
        payload = _wrap_context_payload(ctx)
        # Forced drift: rest days must be 0..7
        payload["home_rest_days"] = 99

        with pytest.raises(ValidationError):
            validate_contract_payload(payload, _load_schema())

    def test_missing_required_field_is_rejected_by_schema(self) -> None:
        ctx = _build_context()
        payload = _wrap_context_payload(ctx)
        del payload["home_bullpen_era"]

        with pytest.raises(ValidationError):
            validate_contract_payload(payload, _load_schema())

    def test_producer_emits_native_feature_vector_payload(self) -> None:
        ctx = _build_context()

        payload = ctx.to_payload()
        validate_contract_payload(payload, _load_schema())
