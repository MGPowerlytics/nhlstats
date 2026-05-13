"""Dashboard consumer-side contract tests for bet opportunity payloads.

The dashboard (via plugins/portfolio_optimizer.py BetOpportunity) consumes
bet opportunity payloads that flow through OddsComparator.find_opportunities.
These tests validate the full opportunity contract including the home_team_raw /
away_team_raw fields that were added to support display-name differentiation.

This is a consumer-red contract test layer — the schemas under
tests/contracts/schemas/ are the source of truth.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError

from tests.contracts.helpers import validate_contract_payload

SCHEMAS_DIR = Path(__file__).parent / "schemas"


# ------------------------------------------------------------------
# Schema fixtures
# ------------------------------------------------------------------


@pytest.fixture(scope="module")
def epl_opportunity_schema() -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / "epl_bet_opportunity_v1.json").read_text())


@pytest.fixture(scope="module")
def mlb_opportunity_schema() -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / "mlb_bet_opportunity_v1.json").read_text())


@pytest.fixture(scope="module")
def tennis_opportunity_schema() -> dict[str, Any]:
    return json.loads((SCHEMAS_DIR / "tennis_bet_opportunity_v1.json").read_text())


# ------------------------------------------------------------------
# Valid opportunity payload factories
# ------------------------------------------------------------------


def _epl_opportunity(**overrides: Any) -> dict[str, Any]:
    base = {
        "schema_version": "v1",
        "sport": "EPL",
        "payload_kind": "bet_opportunity",
        "game_id": "EPL-2025-08-16-LIV-ARS-home",
        "home_team": "Liverpool",
        "away_team": "Arsenal",
        "home_team_raw": " Liverpool ",
        "away_team_raw": " Arsenal ",
        "home_rating": 1750.0,
        "away_rating": 1700.0,
        "bet_on": "Liverpool",
        "side": "home",
        "elo_prob": 0.62,
        "market_prob": 0.52,
        "market_odds": 1.92,
        "bookmaker": "Kalshi",
        "ticker": "KX-2025-08-16-LIV-ARS-Y",
        "edge": 0.10,
        "expected_value": 0.1923,
        "kelly_fraction": 0.12,
        "sharp_confirmed": True,
        "confidence": "HIGH",
        "agreement_diff": 0.10,
    }
    base.update(overrides)
    return base


def _mlb_opportunity(**overrides: Any) -> dict[str, Any]:
    base = {
        "sport": "MLB",
        "game_id": "745431",
        "home_team": "New York Yankees",
        "away_team": "Boston Red Sox",
        "home_team_raw": "NYY",
        "away_team_raw": "BOS",
        "side": "home",
        "bet_on": "New York Yankees",
        "elo_prob": 0.58,
        "market_prob": 0.47,
        "market_odds": 2.13,
        "bookmaker": "Kalshi",
        "ticker": "KXMLBGAME-25APR15NYYBOS-NYY",
        "edge": 0.11,
        "expected_value": 0.234,
        "kelly_fraction": 0.10,
        "sharp_confirmed": False,
        "confidence": "MEDIUM",
        "agreement_diff": 0.11,
        "home_rating": 1612.4,
        "away_rating": 1498.2,
    }
    base.update(overrides)
    return base


def _tennis_opportunity(**overrides: Any) -> dict[str, Any]:
    base = {
        "sport": "TENNIS",
        "game_id": "TENNIS_ATP_2026-04-07_AlexanderBlockx_FlavioCobolli",
        "home_team": "Alexander Blockx",
        "away_team": "Flavio Cobolli",
        "home_team_raw": "Blockx A.",
        "away_team_raw": "Cobolli F.",
        "side": "away",
        "bet_on": "Flavio Cobolli",
        "elo_prob": 0.72,
        "market_prob": 0.66,
        "market_odds": 1.52,
        "bookmaker": "Kalshi",
        "ticker": "KXATPMATCH-26APR07COBBLO-COB",
        "edge": 0.06,
        "expected_value": 0.091,
        "kelly_fraction": 0.12,
        "sharp_confirmed": False,
        "confidence": "LOW",
        "agreement_diff": 0.06,
        "home_rating": 1620.0,
        "away_rating": 1700.0,
        "tour": "ATP",
    }
    base.update(overrides)
    return base


# ------------------------------------------------------------------
# EPL Bet Opportunity consumer tests
# ------------------------------------------------------------------


class TestEPLBetOpportunityConsumer:
    """Consumer contract tests: dashboard reading EPL bet opportunities."""

    def test_valid_epl_opportunity_passes_contract(
        self, epl_opportunity_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(_epl_opportunity(), epl_opportunity_schema)

    def test_epl_opportunity_home_team_raw_accepted(
        self, epl_opportunity_schema: dict[str, Any]
    ) -> None:
        """home_team_raw is allowed on EPL opportunities for display-name differentiation."""
        # Should not raise
        validate_contract_payload(_epl_opportunity(home_team_raw="Liverpool FC"), epl_opportunity_schema)

    def test_epl_opportunity_away_team_raw_accepted(
        self, epl_opportunity_schema: dict[str, Any]
    ) -> None:
        """away_team_raw is allowed on EPL opportunities for display-name differentiation."""
        validate_contract_payload(_epl_opportunity(away_team_raw="Arsenal FC"), epl_opportunity_schema)

    def test_epl_opportunity_requires_all_required_fields(
        self, epl_opportunity_schema: dict[str, Any]
    ) -> None:
        required = epl_opportunity_schema["required"]
        for field in required:
            base = _epl_opportunity()
            del base[field]
            with pytest.raises(ValidationError):
                validate_contract_payload(base, epl_opportunity_schema)

    def test_epl_opportunity_side_enum(
        self, epl_opportunity_schema: dict[str, Any]
    ) -> None:
        side_schema = epl_opportunity_schema["properties"]["side"]
        assert set(side_schema["enum"]) == {"home", "draw", "away"}
        # Invalid side
        with pytest.raises(ValidationError):
            validate_contract_payload(_epl_opportunity(side="invalid"), epl_opportunity_schema)

    def test_epl_opportunity_confidence_enum(
        self, epl_opportunity_schema: dict[str, Any]
    ) -> None:
        conf_schema = epl_opportunity_schema["properties"]["confidence"]
        assert set(conf_schema["enum"]) == {"HIGH", "MEDIUM", "LOW"}
        with pytest.raises(ValidationError):
            validate_contract_payload(_epl_opportunity(confidence="medium"), epl_opportunity_schema)

    def test_epl_opportunity_elo_prob_range(
        self, epl_opportunity_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(_epl_opportunity(elo_prob=0.5), epl_opportunity_schema)
        with pytest.raises(ValidationError):
            validate_contract_payload(_epl_opportunity(elo_prob=1.5), epl_opportunity_schema)

    def test_epl_opportunity_market_prob_range(
        self, epl_opportunity_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(_epl_opportunity(market_prob=0.5), epl_opportunity_schema)
        with pytest.raises(ValidationError):
            validate_contract_payload(_epl_opportunity(market_prob=-0.1), epl_opportunity_schema)

    def test_epl_opportunity_game_id_pattern(
        self, epl_opportunity_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(_epl_opportunity(), epl_opportunity_schema)
        bad = {**_epl_opportunity(), "game_id": "NBA_2025_Lakers_Celtics"}
        with pytest.raises(ValidationError):
            validate_contract_payload(bad, epl_opportunity_schema)

    def test_epl_opportunity_sharp_confirmed_boolean(
        self, epl_opportunity_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(_epl_opportunity(sharp_confirmed=True), epl_opportunity_schema)
        validate_contract_payload(_epl_opportunity(sharp_confirmed=False), epl_opportunity_schema)
        with pytest.raises(ValidationError):
            validate_contract_payload(_epl_opportunity(sharp_confirmed="yes"), epl_opportunity_schema)

    def test_epl_opportunity_blocks_unknown_fields(
        self, epl_opportunity_schema: dict[str, Any]
    ) -> None:
        assert epl_opportunity_schema["additionalProperties"] is False
        bad = {**_epl_opportunity(), "unknown_column": 99}
        with pytest.raises(ValidationError):
            validate_contract_payload(bad, epl_opportunity_schema)


# ------------------------------------------------------------------
# MLB Bet Opportunity consumer tests
# ------------------------------------------------------------------


class TestMLBBetOpportunityConsumer:
    """Consumer contract tests: dashboard reading MLB bet opportunities."""

    def test_valid_mlb_opportunity_passes_contract(
        self, mlb_opportunity_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(_mlb_opportunity(), mlb_opportunity_schema)

    def test_mlb_opportunity_home_team_raw_optional(
        self, mlb_opportunity_schema: dict[str, Any]
    ) -> None:
        """home_team_raw is optional on MLB — null is valid."""
        row = {k: v for k, v in _mlb_opportunity().items() if k != "home_team_raw"}
        validate_contract_payload(row, mlb_opportunity_schema)

    def test_mlb_opportunity_away_team_raw_optional_null(
        self, mlb_opportunity_schema: dict[str, Any]
    ) -> None:
        """away_team_raw explicitly nullable for MLB."""
        validate_contract_payload(_mlb_opportunity(away_team_raw=None), mlb_opportunity_schema)

    def test_mlb_opportunity_side_home_away_only(
        self, mlb_opportunity_schema: dict[str, Any]
    ) -> None:
        side_schema = mlb_opportunity_schema["properties"]["side"]
        assert set(side_schema["enum"]) == {"home", "away"}
        with pytest.raises(ValidationError):
            validate_contract_payload(_mlb_opportunity(side="draw"), mlb_opportunity_schema)

    def test_mlb_opportunity_edge_band(
        self, mlb_opportunity_schema: dict[str, Any]
    ) -> None:
        edge_schema = mlb_opportunity_schema["properties"]["edge"]
        assert edge_schema["minimum"] == 0.05
        assert edge_schema["maximum"] == 0.15
        # Out of band
        with pytest.raises(ValidationError):
            validate_contract_payload(_mlb_opportunity(edge=0.50), mlb_opportunity_schema)
        with pytest.raises(ValidationError):
            validate_contract_payload(_mlb_opportunity(edge=0.01), mlb_opportunity_schema)

    def test_mlb_opportunity_requires_required_fields(
        self, mlb_opportunity_schema: dict[str, Any]
    ) -> None:
        required = mlb_opportunity_schema["required"]
        for field in required:
            base = _mlb_opportunity()
            del base[field]
            with pytest.raises(ValidationError):
                validate_contract_payload(base, mlb_opportunity_schema)

    def test_mlb_opportunity_blocks_unknown_fields(
        self, mlb_opportunity_schema: dict[str, Any]
    ) -> None:
        assert mlb_opportunity_schema["additionalProperties"] is False
        bad = {**_mlb_opportunity(), "mystery_field": True}
        with pytest.raises(ValidationError):
            validate_contract_payload(bad, mlb_opportunity_schema)


# ------------------------------------------------------------------
# Tennis Bet Opportunity consumer tests
# ------------------------------------------------------------------


class TestTennisBetOpportunityConsumer:
    """Consumer contract tests: dashboard reading Tennis bet opportunities."""

    def test_valid_tennis_opportunity_passes_contract(
        self, tennis_opportunity_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(_tennis_opportunity(), tennis_opportunity_schema)

    def test_tennis_opportunity_home_team_raw_optional(
        self, tennis_opportunity_schema: dict[str, Any]
    ) -> None:
        """home_team_raw is optional (nullable string) for tennis."""
        row = {k: v for k, v in _tennis_opportunity().items() if k != "home_team_raw"}
        validate_contract_payload(row, tennis_opportunity_schema)

    def test_tennis_opportunity_away_team_raw_accepted(
        self, tennis_opportunity_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(_tennis_opportunity(away_team_raw="Cobolli F."), tennis_opportunity_schema)

    def test_tennis_opportunity_tour_required(
        self, tennis_opportunity_schema: dict[str, Any]
    ) -> None:
        tour_schema = tennis_opportunity_schema["properties"]["tour"]
        assert set(tour_schema["enum"]) == {"ATP", "WTA"}
        with pytest.raises(ValidationError):
            validate_contract_payload(_tennis_opportunity(tour="WTT"), tennis_opportunity_schema)

    def test_tennis_opportunity_side_home_away_only(
        self, tennis_opportunity_schema: dict[str, Any]
    ) -> None:
        side_schema = tennis_opportunity_schema["properties"]["side"]
        assert set(side_schema["enum"]) == {"home", "away"}
        with pytest.raises(ValidationError):
            validate_contract_payload(_tennis_opportunity(side="draw"), tennis_opportunity_schema)

    def test_tennis_opportunity_edge_range_wider(
        self, tennis_opportunity_schema: dict[str, Any]
    ) -> None:
        """Tennis edge range is [-0.40, 0.15] vs MLB's [0.05, 0.15]."""
        edge_schema = tennis_opportunity_schema["properties"]["edge"]
        assert edge_schema["minimum"] == -0.40
        assert edge_schema["maximum"] == 0.15
        validate_contract_payload(_tennis_opportunity(edge=-0.20), tennis_opportunity_schema)
        with pytest.raises(ValidationError):
            validate_contract_payload(_tennis_opportunity(edge=-0.50), tennis_opportunity_schema)

    def test_tennis_opportunity_game_id_pattern(
        self, tennis_opportunity_schema: dict[str, Any]
    ) -> None:
        validate_contract_payload(_tennis_opportunity(), tennis_opportunity_schema)
        bad = {**_tennis_opportunity(), "game_id": "ATP_2026-04-07_Blockx_Cobolli"}
        with pytest.raises(ValidationError):
            validate_contract_payload(bad, tennis_opportunity_schema)

    def test_tennis_opportunity_blocks_unknown_fields(
        self, tennis_opportunity_schema: dict[str, Any]
    ) -> None:
        assert tennis_opportunity_schema["additionalProperties"] is False
        bad = {**_tennis_opportunity(), "extra_col": 123}
        with pytest.raises(ValidationError):
            validate_contract_payload(bad, tennis_opportunity_schema)
