from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError, validate

from plugins.odds_comparator import OddsComparator


SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"
SUM_TOLERANCE = 0.01


def load_schema(name: str) -> dict[str, Any]:
    """Load a flat EPL contract schema asset for this wave."""
    return json.loads((SCHEMAS_ROOT / name).read_text(encoding="utf-8"))


def assert_probability_triplet(payload: dict[str, Any]) -> None:
    """Require explicit three-way probabilities that approximately sum to one."""
    total = (
        payload["home_win_probability"]
        + payload["draw_probability"]
        + payload["away_win_probability"]
    )
    assert abs(total - 1.0) <= SUM_TOLERANCE


@pytest.fixture(scope="module")
def elo_prediction_schema() -> dict[str, Any]:
    """Load the canonical EPL Elo prediction contract."""
    return load_schema("epl_elo_prediction_v1.json")


@pytest.fixture(scope="module")
def bet_opportunity_schema() -> dict[str, Any]:
    """Load the canonical EPL bet opportunity contract."""
    return load_schema("epl_bet_opportunity_v1.json")


@pytest.fixture
def valid_elo_prediction() -> dict[str, Any]:
    """Return a schema-compliant EPL Elo prediction sample."""
    return {
        "schema_version": "v1",
        "sport": "EPL",
        "payload_kind": "elo_prediction",
        "game_id": "EPL-2025-08-16-LIV-BOU",
        "home_team": "Liverpool",
        "away_team": "Bournemouth",
        "home_rating": 1612.4,
        "away_rating": 1498.8,
        "home_win_probability": 0.59,
        "draw_probability": 0.24,
        "away_win_probability": 0.17,
    }


@pytest.fixture
def valid_bet_opportunity() -> dict[str, Any]:
    """Return a schema-compliant EPL draw opportunity sample."""
    return {
        "schema_version": "v1",
        "sport": "EPL",
        "payload_kind": "bet_opportunity",
        "game_id": "EPL-2025-08-16-LIV-BOU",
        "home_team": "Liverpool",
        "away_team": "Bournemouth",
        "home_rating": 1612.4,
        "away_rating": 1498.8,
        "bet_on": "Draw",
        "side": "draw",
        "elo_prob": 0.24,
        "market_prob": 0.19,
        "market_odds": 5.25,
        "bookmaker": "Kalshi",
        "ticker": "KXHEPL-LIVBOU-20250816-DRAW",
        "edge": 0.05,
        "expected_value": 0.2631578947,
        "kelly_fraction": 0.0595238095,
        "sharp_confirmed": False,
        "confidence": "LOW",
        "agreement_diff": 0.05,
    }


class FakeDBManager:
    """Minimal stub DB manager for consumer-side OddsComparator tests."""


class FakeEloSystem:
    """Track rating checks while simulating an unknown away-side rating."""

    def __init__(self) -> None:
        self.checked_teams: list[str] = []

    def has_real_rating(self, team: str) -> bool:
        self.checked_teams.append(team)
        return team != "Bournemouth"


class TestEplEloConsumerContract:
    """Consumer contract tests for the EPL Elo and opportunity boundary."""

    def test_valid_elo_prediction_passes_contract(
        self,
        valid_elo_prediction: dict[str, Any],
        elo_prediction_schema: dict[str, Any],
    ) -> None:
        """Consumer accepts an explicit three-way EPL Elo prediction payload."""
        validate(valid_elo_prediction, elo_prediction_schema)
        assert_probability_triplet(valid_elo_prediction)

    def test_valid_bet_opportunity_passes_contract(
        self,
        valid_bet_opportunity: dict[str, Any],
        bet_opportunity_schema: dict[str, Any],
    ) -> None:
        """Consumer accepts a draw-capable EPL opportunity payload."""
        validate(valid_bet_opportunity, bet_opportunity_schema)

    def test_missing_draw_probability_is_rejected(
        self,
        valid_elo_prediction: dict[str, Any],
        elo_prediction_schema: dict[str, Any],
    ) -> None:
        """Consumer rejects Elo payloads that hide draw probability."""
        invalid_payload = {
            key: value
            for key, value in valid_elo_prediction.items()
            if key != "draw_probability"
        }

        with pytest.raises(ValidationError):
            validate(invalid_payload, elo_prediction_schema)

    @pytest.mark.parametrize(
        ("schema_name", "fixture_name", "field_name", "invalid_value"),
        [
            (
                "elo_prediction_schema",
                "valid_elo_prediction",
                "home_win_probability",
                1.01,
            ),
            (
                "bet_opportunity_schema",
                "valid_bet_opportunity",
                "market_prob",
                -0.01,
            ),
        ],
    )
    def test_probability_bounds_are_rejected(
        self,
        request: pytest.FixtureRequest,
        schema_name: str,
        fixture_name: str,
        field_name: str,
        invalid_value: float,
    ) -> None:
        """Consumer rejects probability values outside inclusive [0, 1] bounds."""
        schema = request.getfixturevalue(schema_name)
        payload = dict(request.getfixturevalue(fixture_name))
        payload[field_name] = invalid_value

        with pytest.raises(ValidationError):
            validate(payload, schema)

    def test_probabilities_must_approximately_sum_to_one(
        self,
        valid_elo_prediction: dict[str, Any],
        elo_prediction_schema: dict[str, Any],
    ) -> None:
        """Consumer rejects explicit three-way predictions that drift from 1.0."""
        invalid_payload = {
            **valid_elo_prediction,
            "away_win_probability": 0.30,
        }

        validate(invalid_payload, elo_prediction_schema)

        with pytest.raises(AssertionError):
            assert_probability_triplet(invalid_payload)

    def test_contract_is_limited_to_epl_betting_boundary(
        self,
        valid_elo_prediction: dict[str, Any],
        elo_prediction_schema: dict[str, Any],
    ) -> None:
        """Consumer rejects non-EPL payloads at this boundary."""
        invalid_payload = {**valid_elo_prediction, "sport": "LIGUE1"}

        with pytest.raises(ValidationError):
            validate(invalid_payload, elo_prediction_schema)

    def test_odds_comparator_rejects_default_elo_fallback_matchups(self) -> None:
        """Consumer must skip matches when a team lacks a real Elo rating."""
        comparator = OddsComparator(db_manager=FakeDBManager())
        elo_system = FakeEloSystem()
        row = {
            "game_id": "EPL-2025-08-16-LIV-BOU",
            "home_team_name": "Liverpool",
            "away_team_name": "Bournemouth",
        }

        comparator._get_source = lambda game_id: "kalshi"  # type: ignore[method-assign]
        comparator._resolve_name = lambda context: context.name  # type: ignore[method-assign]
        comparator._organize_odds = lambda match: (  # type: ignore[method-assign]
            {
                "Kalshi": {
                    "home": 2.0,
                    "draw": 3.2,
                    "away": 3.6,
                }
            },
            {
                "Kalshi": {
                    "home": "KXHEPL-LIVBOU-20250816-HOME",
                    "draw": "KXHEPL-LIVBOU-20250816-DRAW",
                    "away": "KXHEPL-LIVBOU-20250816-AWAY",
                }
            },
        )

        context = comparator._resolve_game_context("epl", row, elo_system)

        assert context is None
        assert elo_system.checked_teams == ["Liverpool", "Bournemouth"]
