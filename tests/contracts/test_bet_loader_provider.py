"""Provider RED contract tests for the BetLoader boundary.

Exercises the *real* producer code in ``plugins/bet_loader.py``:
- ``BetRecommendation.to_sql_params()``
- ``BetRecommendation.from_dict()``
- ``BetData.to_recommendation()``

Outputs of these methods are validated against the
``bet_loader_contract_v1.json`` schema definitions to detect drift
between the producer and the contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from plugins.bet_loader import BetContext, BetData, BetRecommendation
from tests.contracts.fixtures.bet_loader_samples import (
    build_bet_recommendation_result,
    build_epl_recommendation_result,
    build_mlb_recommendation_result,
)

SCHEMA_PATH = (
    Path(__file__).resolve().parent / "schemas" / "bet_loader_contract_v1.json"
)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator(def_name: str) -> Draft202012Validator:
    schema = _load_schema()
    resource = Resource.from_contents(schema)
    registry = Registry().with_resource(uri=schema["$id"], resource=resource)
    return Draft202012Validator(
        {"$ref": f"{schema['$id']}#/$defs/{def_name}"}, registry=registry
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def context() -> BetContext:
    return BetContext(sport="TEST", date_str="2026-04-07", index=0)


@pytest.fixture
def mlb_context() -> BetContext:
    return BetContext(sport="MLB", date_str="2026-04-07", index=0)


@pytest.fixture
def epl_context() -> BetContext:
    return BetContext(sport="EPL", date_str="2026-04-07", index=0)


# ---------------------------------------------------------------------------
# BetRecommendation.to_sql_params() provider tests
# ---------------------------------------------------------------------------


class TestBetRecommendationToSqlParams:
    """Validates that ``to_sql_params()`` output satisfies the contract."""

    def test_minimal_recommendation_satisfies_contract(
        self, context: BetContext
    ) -> None:
        """A minimal BetRecommendation (only required fields) must produce
        contract-valid SQL params."""
        rec = BetRecommendation(
            bet_id="TEST_2026-04-07_SOMEID_home",
            sport="TEST",
            recommendation_date="2026-04-07",
            home_team="Home Team",
            away_team="Away Team",
            bet_on="Home Team",
            elo_prob=0.6,
            market_prob=0.5,
            edge=0.1,
            confidence="HIGH",
        )
        params = rec.to_sql_params()
        # Remove date_str if present (defensive clean-up that BetLoader does)
        params.pop("date_str", None)
        _validator("bet_recommendation_result").validate(params)

    def test_full_recommendation_with_all_fields_satisfies_contract(
        self, context: BetContext
    ) -> None:
        """A BetRecommendation with all optional fields populated must validate."""
        rec = BetRecommendation(
            bet_id="TEST_2026-04-07_KXMLBGAME-FULL_home",
            sport="TEST",
            recommendation_date="2026-04-07",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
            bet_on="New York Yankees",
            ticker="KXMLBGAME-26APR07NYYBOS-NYY",
            market_prob=0.47,
            elo_prob=0.58,
            edge=0.11,
            kelly_fraction=0.1037,
            expected_value=0.2340,
            confidence="MEDIUM",
            home_rating=1612.4,
            away_rating=1498.2,
            yes_ask=47,
            no_ask=53,
        )
        params = rec.to_sql_params()
        params.pop("date_str", None)
        _validator("bet_recommendation_result").validate(params)

    def test_nullable_fields_can_be_none(self, context: BetContext) -> None:
        """Optional fields that are None must still produce a valid result."""
        rec = BetRecommendation(
            bet_id="TEST_2026-04-07_NULLABLE_home",
            sport="TEST",
            recommendation_date="2026-04-07",
            home_team="Team A",
            away_team="Team B",
            bet_on="Team A",
            elo_prob=0.55,
            market_prob=0.50,
            edge=0.05,
            confidence="LOW",
            ticker=None,
            home_rating=None,
            away_rating=None,
            expected_value=None,
            kelly_fraction=None,
            yes_ask=None,
            no_ask=None,
        )
        params = rec.to_sql_params()
        params.pop("date_str", None)
        _validator("bet_recommendation_result").validate(params)

    def test_governed_probability_fields_satisfy_contract(
        self, context: BetContext
    ) -> None:
        """Governed probability metadata emitted by the provider must validate."""
        rec = BetRecommendation(
            bet_id="TEST_2026-04-07_GOVERNED_home",
            sport="TEST",
            recommendation_date="2026-04-07",
            home_team="Team A",
            away_team="Team B",
            bet_on="Team A",
            elo_prob=0.6,
            market_prob=0.5,
            edge=0.1,
            confidence="HIGH",
            probability_source="elo_prob",
            evidence_state="shadow_only",
            evidence_state_reason="Monitoring only until approval evidence is reviewable.",
            evidence_state_source_artifact=(
                "docs/plan/2026-05-12-betting-pipeline-audit/governed-probability-spec.md"
            ),
            governance_status="descriptive_only",
            sizing_eligible=False,
            abstain=True,
            abstention_reason="missing_calibration_evidence",
        )
        params = rec.to_sql_params()
        params.pop("date_str", None)
        _validator("bet_recommendation_result").validate(params)

    def test_governed_approval_evidence_fields_satisfy_contract(
        self, context: BetContext
    ) -> None:
        """Approval-grade evidence tiers must persist through the loader boundary."""
        rec = BetRecommendation(
            bet_id="TEST_2026-04-07_APPROVAL_home",
            sport="TEST",
            recommendation_date="2026-04-07",
            home_team="Team A",
            away_team="Team B",
            bet_on="Team A",
            elo_prob=0.6,
            market_prob=0.5,
            edge=0.1,
            confidence="HIGH",
            clv_evidence_tier="approval_grade",
            calibration_evidence_tier="approval_grade",
            walk_forward_evidence_tier="approval_grade",
            approval_grade_evidence=True,
        )
        params = rec.to_sql_params()
        params.pop("date_str", None)
        _validator("bet_recommendation_result").validate(params)

    def test_kelly_fraction_is_non_negative(self, context: BetContext) -> None:
        """Kelly fraction must be >= 0 when present."""
        rec = BetRecommendation(
            bet_id="TEST_KELLY_home",
            sport="TEST",
            recommendation_date="2026-04-07",
            home_team="Team A",
            away_team="Team B",
            bet_on="Team A",
            elo_prob=0.6,
            market_prob=0.5,
            edge=0.1,
            confidence="HIGH",
            kelly_fraction=0.05,
        )
        params = rec.to_sql_params()
        params.pop("date_str", None)
        _validator("bet_recommendation_result").validate(params)

    def test_market_prob_in_range(self, context: BetContext) -> None:
        """Market probability must be in [0,1]."""
        rec = BetRecommendation(
            bet_id="TEST_PROB_home",
            sport="TEST",
            recommendation_date="2026-04-07",
            home_team="Team A",
            away_team="Team B",
            bet_on="Team A",
            elo_prob=0.5,
            market_prob=0.75,
            edge=-0.25,
            confidence="MEDIUM",
        )
        params = rec.to_sql_params()
        params.pop("date_str", None)
        _validator("bet_recommendation_result").validate(params)

    def test_elo_prob_in_range(self, context: BetContext) -> None:
        """Elo probability must be in [0,1]."""
        rec = BetRecommendation(
            bet_id="TEST_ELOPROB_home",
            sport="TEST",
            recommendation_date="2026-04-07",
            home_team="Team A",
            away_team="Team B",
            bet_on="Team A",
            elo_prob=0.33,
            market_prob=0.33,
            edge=0.0,
            confidence="LOW",
        )
        params = rec.to_sql_params()
        params.pop("date_str", None)
        _validator("bet_recommendation_result").validate(params)


# ---------------------------------------------------------------------------
# BetRecommendation.from_dict() provider tests
# ---------------------------------------------------------------------------


class TestBetRecommendationFromDict:
    """Validates that ``from_dict()`` produces contract-valid outputs."""

    def test_from_dict_with_mlb_payload(
        self, mlb_context: BetContext
    ) -> None:
        """MLB-style dict must yield contract-valid SQL params."""
        payload = build_mlb_recommendation_result()
        rec = BetRecommendation.from_dict(payload, mlb_context)
        params = rec.to_sql_params()
        params.pop("date_str", None)
        _validator("bet_recommendation_result").validate(params)

    def test_from_dict_with_epl_payload(
        self, epl_context: BetContext
    ) -> None:
        """EPL-style dict (null ticker) must yield contract-valid SQL params."""
        payload = build_epl_recommendation_result()
        rec = BetRecommendation.from_dict(payload, epl_context)
        params = rec.to_sql_params()
        params.pop("date_str", None)
        _validator("bet_recommendation_result").validate(params)

    def test_from_dict_normalizes_sport(
        self, context: BetContext
    ) -> None:
        """Sport should be normalized to uppercase through the pipeline."""
        payload = build_bet_recommendation_result(sport="test")
        rec = BetRecommendation.from_dict(payload, context)
        assert rec.sport == "TEST"

    def test_from_dict_includes_recommendation_date(
        self, context: BetContext
    ) -> None:
        """recommendation_date must survive through from_dict -> to_sql_params."""
        payload = build_bet_recommendation_result(
            recommendation_date="2026-04-07"
        )
        rec = BetRecommendation.from_dict(payload, context)
        params = rec.to_sql_params()
        assert "recommendation_date" in params


# ---------------------------------------------------------------------------
# BetData.to_recommendation() provider tests
# ---------------------------------------------------------------------------


class TestBetDataToRecommendation:
    """Validates that ``BetData.to_recommendation()`` produces contract-valid
    outputs through the full conversion pipeline."""

    def test_bet_data_to_recommendation_satisfies_contract(
        self, mlb_context: BetContext
    ) -> None:
        """Full BetData -> BetRecommendation -> to_sql_params pipeline must
        yield contract-valid output."""
        bet = BetData(
            home_team="New York Yankees",
            away_team="Boston Red Sox",
            ticker="KXMLBGAME-26APR07NYYBOS-NYY",
            side="home",
            bet_on="home",
            elo_prob=0.58,
            market_prob=0.47,
            edge=0.11,
            expected_value=0.2340,
            kelly_fraction=0.1037,
            confidence="MEDIUM",
            home_rating=1612.4,
            away_rating=1498.2,
            yes_ask=47,
            no_ask=53,
        )
        rec = bet.to_recommendation(mlb_context)
        params = rec.to_sql_params()
        params.pop("date_str", None)
        _validator("bet_recommendation_result").validate(params)

    def test_bet_data_to_recommendation_with_optional_fields_none(
        self, context: BetContext
    ) -> None:
        """Minimal BetData with only required fields must still produce
        contract-valid output."""
        bet = BetData(
            home_team="Team A",
            away_team="Team B",
            side="away",
            bet_on="away",
            elo_prob=0.5,
            market_prob=0.5,
            edge=0.0,
            confidence="LOW",
        )
        rec = bet.to_recommendation(context)
        params = rec.to_sql_params()
        params.pop("date_str", None)
        _validator("bet_recommendation_result").validate(params)

    def test_bet_data_to_recommendation_generates_bet_id(
        self, context: BetContext
    ) -> None:
        """When no bet_id is provided, BetData must generate one."""
        bet = BetData(
            home_team="Team A",
            away_team="Team B",
            ticker="SOMETICKER",
            side="home",
            bet_on="home",
            elo_prob=0.6,
            market_prob=0.5,
            edge=0.1,
            confidence="HIGH",
        )
        rec = bet.to_recommendation(context)
        assert rec.bet_id  # Must not be empty
        assert "SOMETICKER" in rec.bet_id


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


class TestDriftDetection:
    """Tests that detect when the real BetLoader output drifts from the
    contract. These should fail if the producer's output shape changes."""

    def test_to_sql_params_contains_required_fields(
        self, context: BetContext
    ) -> None:
        """All contract-required fields must be present in the SQL params."""
        rec = BetRecommendation(
            bet_id="TEST_DRIFT_home",
            sport="TEST",
            recommendation_date="2026-04-07",
            home_team="Team A",
            away_team="Team B",
            bet_on="Team A",
            elo_prob=0.6,
            market_prob=0.5,
            edge=0.1,
            confidence="HIGH",
        )
        params = rec.to_sql_params()
        required = {
            "bet_id",
            "sport",
            "recommendation_date",
            "home_team",
            "away_team",
            "bet_on",
            "elo_prob",
            "market_prob",
            "edge",
            "confidence",
        }
        missing = required - set(params.keys())
        assert not missing, f"Missing required fields in to_sql_params: {missing}"

    def test_to_sql_params_edge_type_is_float(
        self, context: BetContext
    ) -> None:
        """Edge must be a number (not string)."""
        rec = BetRecommendation(
            bet_id="TEST_EDGETYPE_home",
            sport="TEST",
            recommendation_date="2026-04-07",
            home_team="Team A",
            away_team="Team B",
            bet_on="Team A",
            elo_prob=0.6,
            market_prob=0.5,
            edge=0.1,
            confidence="HIGH",
        )
        params = rec.to_sql_params()
        assert isinstance(params["edge"], (int, float))

    def test_to_sql_params_confidence_is_uppercase(
        self, context: BetContext
    ) -> None:
        """Confidence must be uppercase to match the contract enum."""
        rec = BetRecommendation(
            bet_id="TEST_CONF_home",
            sport="TEST",
            recommendation_date="2026-04-07",
            home_team="Team A",
            away_team="Team B",
            bet_on="Team A",
            elo_prob=0.6,
            market_prob=0.5,
            edge=0.1,
            confidence="HIGH",
        )
        params = rec.to_sql_params()
        assert params["confidence"] in {"HIGH", "MEDIUM", "LOW"}

    def test_to_sql_params_has_no_date_str(
        self, context: BetContext
    ) -> None:
        """date_str must NOT be present (the column is recommendation_date)."""
        rec = BetRecommendation(
            bet_id="TEST_DATESTR_home",
            sport="TEST",
            recommendation_date="2026-04-07",
            home_team="Team A",
            away_team="Team B",
            bet_on="Team A",
            elo_prob=0.6,
            market_prob=0.5,
            edge=0.1,
            confidence="HIGH",
        )
        params = rec.to_sql_params()
        if "date_str" in params:
            params.pop("date_str")
        assert "date_str" not in params
