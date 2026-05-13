"""Dashboard consumer-side contract tests for placed_bets / bet_recommendations rows.

The dashboard reads placed_bets rows via _load_betting_results_from_db() for
betting performance tracking. These rows are sourced from bet_recommendations
produced by OddsComparator.find_opportunities and persisted by BetLoader.

These tests validate the persisted-row contract for each sport's bet_recommendations,
ensuring the dashboard receives schema-compliant rows.

Note: ``home_team_raw`` / ``away_team_raw`` are NOT part of the bet_recommendation_row
schemas — they live in the bet_opportunity schemas (OddsComparator output) and are
handled by DatabaseRowParser when constructing BetOpportunity. They are therefore
omitted from these persisted-row tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError

from tests.contracts.helpers import validate_contract_definition, validate_contract_payload

SCHEMAS_DIR = Path(__file__).parent / "schemas"


# ------------------------------------------------------------------
# Schema fixtures
# ------------------------------------------------------------------


@pytest.fixture(scope="module")
def epl_bet_rec_schema() -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / "epl_bet_recommendation_row_v1.json").read_text())


@pytest.fixture(scope="module")
def mlb_bet_rec_schema() -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / "mlb_bet_recommendation_row_v1.json").read_text())


@pytest.fixture(scope="module")
def tennis_bet_rec_schema() -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / "tennis_bet_recommendation_row_v1.json").read_text())


# ------------------------------------------------------------------
# Valid persisted-row factories (schema fields only — no raw variants)
# ------------------------------------------------------------------


def _epl_row(**overrides: Any) -> dict[str, Any]:
    """Canonical EPL bet_recommendations persisted row (schema fields only)."""
    base = {
        "bet_id": "EPL-2025-08-16-KXHEPL-LIVBOU-20250816-home",
        "sport": "EPL",
        "recommendation_date": "2025-08-16",
        "home_team": "Liverpool",
        "away_team": "Bournemouth",
        "bet_on": "home",
        "ticker": "KXHEPL-LIVBOU-20250816",
        "elo_prob": 0.58,
        "market_prob": 0.47,
        "edge": 0.11,
        "expected_value": 0.234,
        "kelly_fraction": 0.104,
        "confidence": "MEDIUM",
        "home_rating": 1750.0,
        "away_rating": 1680.0,
        "yes_ask": 47,
        "no_ask": 53,
    }
    base.update(overrides)
    return base


def _mlb_row(**overrides: Any) -> dict[str, Any]:
    """Canonical MLB bet_recommendations persisted row (schema fields only)."""
    base = {
        "bet_id": "MLB_2025-04-15_KXMLBGAME-25APR15NYYBOS-NYY_home",
        "sport": "MLB",
        "recommendation_date": "2025-04-15",
        "home_team": "New York Yankees",
        "away_team": "Boston Red Sox",
        "bet_on": "New York Yankees",
        "ticker": "KXMLBGAME-25APR15NYYBOS-NYY",
        "elo_prob": 0.58,
        "market_prob": 0.47,
        "edge": 0.11,
        "expected_value": 0.234,
        "kelly_fraction": 0.104,
        "confidence": "MEDIUM",
        "home_rating": 1612.4,
        "away_rating": 1498.2,
        "yes_ask": 47,
        "no_ask": 53,
    }
    base.update(overrides)
    return base


def _tennis_row(**overrides: Any) -> dict[str, Any]:
    """Canonical TENNIS bet_recommendations persisted row (schema fields only)."""
    base = {
        "bet_id": "TENNIS_2026-04-07_KXATPMATCH-26APR07COBBLO-COB_away",
        "sport": "TENNIS",
        "recommendation_date": "2026-04-07",
        "home_team": "Alexander Blockx",
        "away_team": "Flavio Cobolli",
        "bet_on": "Flavio Cobolli",
        "ticker": "KXATPMATCH-26APR07COBBLO-COB",
        "elo_prob": 0.72,
        "market_prob": 0.66,
        "edge": 0.06,
        "expected_value": 0.091,
        "kelly_fraction": 0.117,
        "confidence": "LOW",
        "home_rating": 1620.0,
        "away_rating": 1700.0,
        "yes_ask": 66,
        "no_ask": 34,
    }
    base.update(overrides)
    return base


# ------------------------------------------------------------------
# EPL bet_recommendations persisted-row consumer tests
# ------------------------------------------------------------------


class TestEPLBetRecommendationsConsumer:
    """Consumer contract tests: dashboard reading EPL bet_recommendations rows."""

    def test_valid_epl_row_passes_contract(
        self, epl_bet_rec_schema: dict[str, Any]
    ) -> None:
        validate_contract_definition(_epl_row(), epl_bet_rec_schema, "persisted_row")

    def test_epl_row_requires_required_fields(
        self, epl_bet_rec_schema: dict[str, Any]
    ) -> None:
        base_def = epl_bet_rec_schema["$defs"]["base_recommendation"]
        for field in base_def["required"]:
            row = _epl_row()
            del row[field]
            with pytest.raises(ValidationError):
                validate_contract_definition(row, epl_bet_rec_schema, "persisted_row")

    def test_epl_row_elo_prob_range(
        self, epl_bet_rec_schema: dict[str, Any]
    ) -> None:
        validate_contract_definition(_epl_row(elo_prob=0.5), epl_bet_rec_schema, "persisted_row")
        with pytest.raises(ValidationError):
            validate_contract_definition(_epl_row(elo_prob=1.5), epl_bet_rec_schema, "persisted_row")

    def test_epl_row_confidence_enum(
        self, epl_bet_rec_schema: dict[str, Any]
    ) -> None:
        conf_def = epl_bet_rec_schema["$defs"]["base_recommendation"]["properties"]["confidence"]
        assert set(conf_def["enum"]) == {"HIGH", "MEDIUM", "LOW"}
        with pytest.raises(ValidationError):
            validate_contract_definition(_epl_row(confidence="medium"), epl_bet_rec_schema, "persisted_row")

    def test_epl_row_kelly_fraction_non_negative(
        self, epl_bet_rec_schema: dict[str, Any]
    ) -> None:
        validate_contract_definition(_epl_row(kelly_fraction=0.0), epl_bet_rec_schema, "persisted_row")
        validate_contract_definition(_epl_row(kelly_fraction=0.25), epl_bet_rec_schema, "persisted_row")
        with pytest.raises(ValidationError):
            validate_contract_definition(_epl_row(kelly_fraction=-0.1), epl_bet_rec_schema, "persisted_row")

    def test_epl_row_bet_on_enum(
        self, epl_bet_rec_schema: dict[str, Any]
    ) -> None:
        bet_on_def = epl_bet_rec_schema["$defs"]["base_recommendation"]["properties"]["bet_on"]
        assert set(bet_on_def["enum"]) == {"home", "away", "draw"}
        with pytest.raises(ValidationError):
            validate_contract_definition(_epl_row(bet_on="home_team"), epl_bet_rec_schema, "persisted_row")

    def test_epl_row_ticker_nullable(
        self, epl_bet_rec_schema: dict[str, Any]
    ) -> None:
        row = _epl_row()
        row["ticker"] = None
        validate_contract_definition(row, epl_bet_rec_schema, "persisted_row")

    def test_epl_row_bet_id_pattern(
        self, epl_bet_rec_schema: dict[str, Any]
    ) -> None:
        validate_contract_definition(_epl_row(), epl_bet_rec_schema, "persisted_row")
        bad = {**_epl_row(), "bet_id": "NBA-2025-08-16-LAL-BOS-home"}
        with pytest.raises(ValidationError):
            validate_contract_definition(bad, epl_bet_rec_schema, "persisted_row")


# ------------------------------------------------------------------
# MLB bet_recommendations persisted-row consumer tests
# ------------------------------------------------------------------


class TestMLBBetRecommendationsConsumer:
    """Consumer contract tests: dashboard reading MLB bet_recommendations rows."""

    def test_valid_mlb_row_passes_contract(
        self, mlb_bet_rec_schema: dict[str, Any]
    ) -> None:
        validate_contract_definition(_mlb_row(), mlb_bet_rec_schema, "persisted_row")

    def test_mlb_row_requires_required_fields(
        self, mlb_bet_rec_schema: dict[str, Any]
    ) -> None:
        base_def = mlb_bet_rec_schema["$defs"]["base_recommendation"]
        for field in base_def["required"]:
            row = _mlb_row()
            del row[field]
            with pytest.raises(ValidationError):
                validate_contract_definition(row, mlb_bet_rec_schema, "persisted_row")

    def test_mlb_row_edge_band(
        self, mlb_bet_rec_schema: dict[str, Any]
    ) -> None:
        edge_props = mlb_bet_rec_schema["$defs"]["base_recommendation"]["properties"]["edge"]
        assert edge_props["minimum"] == 0.05
        assert edge_props["maximum"] == 0.15
        with pytest.raises(ValidationError):
            validate_contract_definition(_mlb_row(edge=0.50), mlb_bet_rec_schema, "persisted_row")

    def test_mlb_row_sport_const(
        self, mlb_bet_rec_schema: dict[str, Any]
    ) -> None:
        sport_props = mlb_bet_rec_schema["$defs"]["base_recommendation"]["properties"]["sport"]
        assert sport_props["const"] == "MLB"

    def test_mlb_row_side_enum_via_saved_payload(
        self, mlb_bet_rec_schema: dict[str, Any]
    ) -> None:
        """MLB saved_payload requires side ∈ {home, away} (no draw)."""
        saved_def = mlb_bet_rec_schema["$defs"]["saved_payload"]
        side_props = saved_def["allOf"][1]["properties"]["side"]
        assert set(side_props["enum"]) == {"home", "away"}
        with pytest.raises(ValidationError):
            validate_contract_definition(_mlb_row(side="draw"), mlb_bet_rec_schema, "saved_payload")

    def test_mlb_row_confidence_enum(
        self, mlb_bet_rec_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            validate_contract_definition(_mlb_row(confidence="high"), mlb_bet_rec_schema, "persisted_row")


# ------------------------------------------------------------------
# Tennis bet_recommendations persisted-row consumer tests
# ------------------------------------------------------------------


class TestTennisBetRecommendationsConsumer:
    """Consumer contract tests: dashboard reading Tennis bet_recommendations rows."""

    def test_valid_tennis_row_passes_contract(
        self, tennis_bet_rec_schema: dict[str, Any]
    ) -> None:
        validate_contract_definition(_tennis_row(), tennis_bet_rec_schema, "persisted_row")

    def test_tennis_row_requires_required_fields(
        self, tennis_bet_rec_schema: dict[str, Any]
    ) -> None:
        base_def = tennis_bet_rec_schema["$defs"]["base_recommendation"]
        for field in base_def["required"]:
            row = _tennis_row()
            del row[field]
            with pytest.raises(ValidationError):
                validate_contract_definition(row, tennis_bet_rec_schema, "persisted_row")

    def test_tennis_row_bet_id_pattern(
        self, tennis_bet_rec_schema: dict[str, Any]
    ) -> None:
        validate_contract_definition(_tennis_row(), tennis_bet_rec_schema, "persisted_row")
        bad = {**_tennis_row(), "bet_id": "ATP_2026-04-07_BLOCKX_COBOLLI_away"}
        with pytest.raises(ValidationError):
            validate_contract_definition(bad, tennis_bet_rec_schema, "persisted_row")

    def test_tennis_row_edge_wider_range(
        self, tennis_bet_rec_schema: dict[str, Any]
    ) -> None:
        """Tennis edge range is [-0.40, 0.15] vs MLB's [0.05, 0.15]."""
        edge_props = tennis_bet_rec_schema["$defs"]["base_recommendation"]["properties"]["edge"]
        assert edge_props["minimum"] == -0.40
        assert edge_props["maximum"] == 0.15
        validate_contract_definition(_tennis_row(edge=-0.10), tennis_bet_rec_schema, "persisted_row")
        with pytest.raises(ValidationError):
            validate_contract_definition(_tennis_row(edge=-0.50), tennis_bet_rec_schema, "persisted_row")

    def test_tennis_row_confidence_enum_rejects_lowercase(
        self, tennis_bet_rec_schema: dict[str, Any]
    ) -> None:
        with pytest.raises(ValidationError):
            validate_contract_definition(_tennis_row(confidence="medium"), tennis_bet_rec_schema, "persisted_row")

    def test_tennis_row_ticker_pattern(
        self, tennis_bet_rec_schema: dict[str, Any]
    ) -> None:
        validate_contract_definition(_tennis_row(), tennis_bet_rec_schema, "persisted_row")
        bad = {**_tennis_row(), "ticker": "INVALID-TICKER-123"}
        with pytest.raises(ValidationError):
            validate_contract_definition(bad, tennis_bet_rec_schema, "persisted_row")
