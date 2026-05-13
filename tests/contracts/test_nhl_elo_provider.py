"""Provider RED tests for the NHL Elo boundary.

These tests exercise the real :class:`NHLEloRating` producer. The locked
contract requires a structured payload with ``home_prob``/``home_rating``/
``away_rating``, but the producer only exposes ``predict()`` and
``get_rating()`` separately. The provider test assembles the payload from
the real outputs and validates it against the frozen schema. Tests that
detect genuine drift (probability out of [0, 1], etc.) are marked
``xfail(strict=True)`` with the Wave 4-6 fix task id.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from plugins.elo.nhl_elo_rating import NHLEloRating
from tests.contracts.fixtures.nhl_elo_samples import (
    NHL_AWAY_TEAM,
    NHL_HOME_TEAM,
    build_trained_nhl_elo,
)
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema() -> dict[str, Any]:
    return json.loads(
        (SCHEMAS_ROOT / "nhl_elo_prediction_v1.json").read_text(encoding="utf-8")
    )


def _assemble_payload(elo: NHLEloRating) -> dict[str, Any]:
    """Wrap the real producer outputs into the locked contract shape."""
    return {
        "schema_version": "v1",
        "sport": "NHL",
        "payload_kind": "elo_prediction",
        "home_team": NHL_HOME_TEAM,
        "away_team": NHL_AWAY_TEAM,
        "home_rating": float(elo.get_rating(NHL_HOME_TEAM)),
        "away_rating": float(elo.get_rating(NHL_AWAY_TEAM)),
        "home_prob": float(elo.predict(NHL_HOME_TEAM, NHL_AWAY_TEAM)),
        "home_advantage": float(elo.config.home_advantage),
        "k_factor": float(elo.config.k_factor),
        "is_neutral": False,
    }


class TestNhlEloProviderContract:
    """Provider-side guarantees against the real ``NHLEloRating`` outputs."""

    def test_real_predict_payload_matches_frozen_contract(self) -> None:
        elo = build_trained_nhl_elo()
        payload = _assemble_payload(elo)

        validate_contract_payload(payload, _load_schema())

    def test_real_predict_returns_probability_in_unit_interval(self) -> None:
        elo = build_trained_nhl_elo()

        prob = elo.predict(NHL_HOME_TEAM, NHL_AWAY_TEAM)

        assert 0.0 <= float(prob) <= 1.0

    def test_real_get_rating_returns_strictly_positive_rating(self) -> None:
        elo = build_trained_nhl_elo()

        assert float(elo.get_rating(NHL_HOME_TEAM)) > 0.0
        assert float(elo.get_rating(NHL_AWAY_TEAM)) > 0.0

    def test_real_update_persists_rating_change(self) -> None:
        elo = NHLEloRating(k_factor=20.0, home_advantage=65.0)
        before_home = float(elo.get_rating(NHL_HOME_TEAM))
        before_away = float(elo.get_rating(NHL_AWAY_TEAM))

        elo.update(NHL_HOME_TEAM, NHL_AWAY_TEAM, home_win=1.0, is_neutral=False)

        after_home = float(elo.get_rating(NHL_HOME_TEAM))
        after_away = float(elo.get_rating(NHL_AWAY_TEAM))
        assert after_home > before_home
        assert after_away < before_away

    def test_invalid_assembled_payload_is_rejected_by_schema(self) -> None:
        elo = build_trained_nhl_elo()
        payload = _assemble_payload(elo)
        payload["home_prob"] = 1.5  # forced drift

        with pytest.raises(ValidationError):
            validate_contract_payload(payload, _load_schema())
