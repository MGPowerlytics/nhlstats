"""Provider RED tests for the MLB Glicko-2 boundary.

The producer (:class:`MLBGlicko2Rating`) exposes:
    * ``get_rating(team)`` → ``{rating, rd, vol}`` ✓
    * ``predict(home, away)`` → ``float`` ✓ (no structured payload)

This file calls real producer methods, wraps the float prediction into
the locked ``glicko2_prediction`` shape, and validates against the frozen
schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from plugins.glicko2_rating import MLBGlicko2Rating
from tests.contracts.fixtures.mlb_glicko2_samples import (
    AWAY_TEAM,
    HOME_TEAM,
    build_trained_mlb_glicko2,
)
from tests.contracts.helpers import validate_contract_definition


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema() -> dict[str, Any]:
    return json.loads(
        (SCHEMAS_ROOT / "mlb_glicko2_v1.json").read_text(encoding="utf-8")
    )


def _assemble_team_rating(glicko: MLBGlicko2Rating, team: str) -> dict[str, Any]:
    rating = glicko.get_rating(team)
    return {
        "schema_version": "v1",
        "sport": "MLB",
        "payload_kind": "glicko2_rating",
        "team": team,
        "rating": float(rating["rating"]),
        "rd": float(rating["rd"]),
        "vol": float(rating["vol"]),
    }


def _assemble_prediction(glicko: MLBGlicko2Rating) -> dict[str, Any]:
    home = glicko.get_rating(HOME_TEAM)
    away = glicko.get_rating(AWAY_TEAM)
    return {
        "schema_version": "v1",
        "sport": "MLB",
        "payload_kind": "glicko2_prediction",
        "home_team": HOME_TEAM,
        "away_team": AWAY_TEAM,
        "home_rating": {
            "rating": float(home["rating"]),
            "rd": float(home["rd"]),
            "vol": float(home["vol"]),
        },
        "away_rating": {
            "rating": float(away["rating"]),
            "rd": float(away["rd"]),
            "vol": float(away["vol"]),
        },
        "prob": float(glicko.predict(HOME_TEAM, AWAY_TEAM)),
        "home_advantage": float(glicko.home_advantage),
    }


class TestMLBGlicko2ProviderContract:
    """Provider-side guarantees against real ``MLBGlicko2Rating`` outputs."""

    def test_real_team_rating_payload_matches_contract(self) -> None:
        glicko = build_trained_mlb_glicko2()

        payload = _assemble_team_rating(glicko, HOME_TEAM)

        validate_contract_definition(payload, _load_schema(), "team_rating")

    def test_real_prediction_payload_matches_contract(self) -> None:
        glicko = build_trained_mlb_glicko2()

        payload = _assemble_prediction(glicko)

        validate_contract_definition(payload, _load_schema(), "prediction")

    def test_real_predict_returns_probability_in_unit_interval(self) -> None:
        glicko = build_trained_mlb_glicko2()

        prob = glicko.predict(HOME_TEAM, AWAY_TEAM)

        assert isinstance(prob, float)
        assert 0.0 <= prob <= 1.0

    def test_real_get_rating_returns_positive_rating_rd_vol(self) -> None:
        glicko = build_trained_mlb_glicko2()

        rating = glicko.get_rating(HOME_TEAM)

        assert float(rating["rating"]) > 0.0
        assert float(rating["rd"]) > 0.0
        assert float(rating["vol"]) > 0.0

    def test_real_update_changes_home_rating(self) -> None:
        glicko = MLBGlicko2Rating()
        before = float(glicko.get_rating(HOME_TEAM)["rating"])

        glicko.update(HOME_TEAM, AWAY_TEAM, True)

        assert float(glicko.get_rating(HOME_TEAM)["rating"]) != before

    def test_invalid_team_rating_payload_is_rejected_by_schema(self) -> None:
        glicko = build_trained_mlb_glicko2()
        payload = _assemble_team_rating(glicko, HOME_TEAM)
        payload["rating"] = -10.0  # exclusiveMinimum: 0

        with pytest.raises(ValidationError):
            validate_contract_definition(payload, _load_schema(), "team_rating")

    def test_invalid_prediction_payload_is_rejected_by_schema(self) -> None:
        glicko = build_trained_mlb_glicko2()
        payload = _assemble_prediction(glicko)
        payload["prob"] = 1.25  # out of range

        with pytest.raises(ValidationError):
            validate_contract_definition(payload, _load_schema(), "prediction")

    def test_producer_emits_native_prediction_payload(self) -> None:
        glicko = build_trained_mlb_glicko2()

        payload = glicko.predict_payload(HOME_TEAM, AWAY_TEAM)
        validate_contract_definition(payload, _load_schema(), "prediction")
