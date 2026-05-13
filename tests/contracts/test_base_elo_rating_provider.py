"""Provider RED tests for the BaseEloRating interface boundary.

These tests exercise the real :class:`StandardEloRating` producer and
verify that its outputs conform to the frozen contract schema.  Tests
that detect genuine drift (probability out of [0,1], non-positive
ratings, etc.) are marked ``xfail(strict=True)`` with the associated
fix task id where applicable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from plugins.elo.base_elo_rating import StandardEloRating
from tests.contracts.fixtures.base_elo_rating_samples import (
    AWAY_TEAM,
    HOME_TEAM,
    build_trained_elo_state,
)
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"


def _load_contract() -> dict[str, Any]:
    return json.loads(
        (SCHEMAS_ROOT / "base_elo_rating_contract_v1.json").read_text(encoding="utf-8")
    )


def _assemble_predict_payload(elo: StandardEloRating) -> dict[str, Any]:
    """Wrap real predict() output into the contract shape."""
    return {
        "schema_version": "v1",
        "payload_kind": "predict_result",
        "home_team": HOME_TEAM,
        "away_team": AWAY_TEAM,
        "home_prob": float(elo.predict(HOME_TEAM, AWAY_TEAM)),
        "is_neutral": False,
    }


def _assemble_update_payload(
    elo: StandardEloRating,
    home_won: bool = True,
) -> dict[str, Any]:
    """Wrap real update() output into the contract shape."""
    change = elo.update(HOME_TEAM, AWAY_TEAM, home_won=home_won)
    return {
        "schema_version": "v1",
        "payload_kind": "update_result",
        "home_team": HOME_TEAM,
        "away_team": AWAY_TEAM,
        "home_won": home_won,
        "rating_change": float(change) if change is not None else 0.0,
        "home_rating_after": float(elo.get_rating(HOME_TEAM)),
        "away_rating_after": float(elo.get_rating(AWAY_TEAM)),
    }


def _assemble_get_rating_payload(elo: StandardEloRating) -> dict[str, Any]:
    """Wrap real get_rating() output into the contract shape."""
    return {
        "schema_version": "v1",
        "payload_kind": "get_rating_result",
        "team": HOME_TEAM,
        "rating": float(elo.get_rating(HOME_TEAM)),
    }


class TestBaseEloRatingProviderContract:
    """Provider-side guarantees against real ``StandardEloRating`` outputs."""

    # ── predict_result ──────────────────────────────────────────────

    def test_real_predict_payload_matches_frozen_contract(self) -> None:
        elo = build_trained_elo_state()
        payload = _assemble_predict_payload(elo)
        validate_contract_payload(payload, _load_contract())

    def test_real_predict_returns_probability_in_unit_interval(self) -> None:
        elo = build_trained_elo_state()
        prob = elo.predict(HOME_TEAM, AWAY_TEAM)
        assert 0.0 <= float(prob) <= 1.0

    # ── update_result ───────────────────────────────────────────────

    def test_real_update_payload_matches_frozen_contract(self) -> None:
        elo = StandardEloRating(k_factor=32.0, home_advantage=50.0)
        payload = _assemble_update_payload(elo, home_won=True)
        validate_contract_payload(payload, _load_contract())

    def test_real_update_payload_matches_frozen_contract_for_away_win(
        self,
    ) -> None:
        elo = StandardEloRating(k_factor=32.0, home_advantage=50.0)
        payload = _assemble_update_payload(elo, home_won=False)
        validate_contract_payload(payload, _load_contract())

    def test_after_home_win_home_rating_increases(self) -> None:
        elo = StandardEloRating(k_factor=32.0, home_advantage=50.0)
        before_home = float(elo.get_rating(HOME_TEAM))
        before_away = float(elo.get_rating(AWAY_TEAM))

        elo.update(HOME_TEAM, AWAY_TEAM, home_won=True)

        after_home = float(elo.get_rating(HOME_TEAM))
        after_away = float(elo.get_rating(AWAY_TEAM))
        assert after_home > before_home
        assert after_away < before_away

    def test_after_away_win_home_rating_decreases(self) -> None:
        elo = StandardEloRating(k_factor=32.0, home_advantage=50.0)
        before_home = float(elo.get_rating(HOME_TEAM))
        before_away = float(elo.get_rating(AWAY_TEAM))

        elo.update(HOME_TEAM, AWAY_TEAM, home_won=False)

        after_home = float(elo.get_rating(HOME_TEAM))
        after_away = float(elo.get_rating(AWAY_TEAM))
        assert after_home < before_home
        assert after_away > before_away

    def test_update_ratings_are_strictly_positive(self) -> None:
        elo = StandardEloRating(k_factor=32.0, home_advantage=50.0)
        elo.update(HOME_TEAM, AWAY_TEAM, home_won=True)
        assert float(elo.get_rating(HOME_TEAM)) > 0
        assert float(elo.get_rating(AWAY_TEAM)) > 0

    # ── get_rating_result ───────────────────────────────────────────

    def test_real_get_rating_payload_matches_frozen_contract(self) -> None:
        elo = build_trained_elo_state()
        payload = _assemble_get_rating_payload(elo)
        validate_contract_payload(payload, _load_contract())

    def test_real_get_rating_returns_positive_number(self) -> None:
        elo = build_trained_elo_state()
        assert float(elo.get_rating(HOME_TEAM)) > 0
        assert float(elo.get_rating(AWAY_TEAM)) > 0

    # ── Drift detection ─────────────────────────────────────────────

    def test_invalid_predict_payload_is_rejected_by_schema(self) -> None:
        elo = build_trained_elo_state()
        payload = _assemble_predict_payload(elo)
        payload["home_prob"] = 1.5  # forced drift

        with pytest.raises(ValidationError):
            validate_contract_payload(payload, _load_contract())

    def test_invalid_update_payload_is_rejected_by_schema(self) -> None:
        elo = StandardEloRating(k_factor=32.0, home_advantage=50.0)
        payload = _assemble_update_payload(elo, home_won=True)
        payload["home_rating_after"] = -10  # forced drift

        with pytest.raises(ValidationError):
            validate_contract_payload(payload, _load_contract())

    def test_invalid_get_rating_payload_is_rejected_by_schema(self) -> None:
        elo = build_trained_elo_state()
        payload = _assemble_get_rating_payload(elo)
        payload["rating"] = 0  # forced drift — must be > 0

        with pytest.raises(ValidationError):
            validate_contract_payload(payload, _load_contract())
