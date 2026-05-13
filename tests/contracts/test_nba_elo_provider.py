"""Provider RED tests for the NBA Elo boundary.

These tests exercise the real :class:`NBAEloRating` producer. The locked
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

from plugins.elo.nba_elo_rating import NBAEloRating
from tests.contracts.fixtures.nba_elo_samples import (
    NBA_AWAY_TEAM,
    NBA_HOME_TEAM,
    build_trained_nba_elo,
)
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_schema() -> dict[str, Any]:
    return json.loads(
        (SCHEMAS_ROOT / "nba_elo_prediction_v1.json").read_text(encoding="utf-8")
    )


def _assemble_payload(elo: NBAEloRating) -> dict[str, Any]:
    """Wrap the real producer outputs into the locked contract shape."""
    return {
        "schema_version": "v1",
        "sport": "NBA",
        "payload_kind": "elo_prediction",
        "home_team": NBA_HOME_TEAM,
        "away_team": NBA_AWAY_TEAM,
        "home_rating": float(elo.get_rating(NBA_HOME_TEAM)),
        "away_rating": float(elo.get_rating(NBA_AWAY_TEAM)),
        "home_prob": float(elo.predict(NBA_HOME_TEAM, NBA_AWAY_TEAM)),
        "home_advantage": float(elo.config.home_advantage),
        "k_factor": float(elo.config.k_factor),
        "is_neutral": False,
    }


class TestNbaEloProviderContract:
    """Provider-side guarantees against the real ``NBAEloRating`` outputs."""

    def test_real_predict_payload_matches_frozen_contract(self) -> None:
        elo = build_trained_nba_elo()
        payload = _assemble_payload(elo)

        validate_contract_payload(payload, _load_schema())

    def test_real_predict_returns_probability_in_unit_interval(self) -> None:
        elo = build_trained_nba_elo()

        prob = elo.predict(NBA_HOME_TEAM, NBA_AWAY_TEAM)

        assert 0.0 <= float(prob) <= 1.0

    def test_real_get_rating_returns_strictly_positive_rating(self) -> None:
        elo = build_trained_nba_elo()

        assert float(elo.get_rating(NBA_HOME_TEAM)) > 0.0
        assert float(elo.get_rating(NBA_AWAY_TEAM)) > 0.0

    def test_real_update_persists_rating_change(self) -> None:
        elo = NBAEloRating(k_factor=20.0, home_advantage=100.0)
        before_home = float(elo.get_rating(NBA_HOME_TEAM))
        before_away = float(elo.get_rating(NBA_AWAY_TEAM))

        elo.update(NBA_HOME_TEAM, NBA_AWAY_TEAM, home_won=True)

        after_home = float(elo.get_rating(NBA_HOME_TEAM))
        after_away = float(elo.get_rating(NBA_AWAY_TEAM))
        assert after_home > before_home
        assert after_away < before_away

    def test_invalid_assembled_payload_is_rejected_by_schema(self) -> None:
        elo = build_trained_nba_elo()
        payload = _assemble_payload(elo)
        payload["home_prob"] = 1.5  # forced drift

        with pytest.raises(ValidationError):
            validate_contract_payload(payload, _load_schema())
