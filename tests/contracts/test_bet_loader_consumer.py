"""Consumer contract tests for the BetLoader boundary.

Validates that consumers of bet_recommendation results and load_bets
summaries can trust the shape and constraints defined by
``bet_loader_contract_v1.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from tests.contracts.fixtures.bet_loader_samples import (
    build_bet_recommendation_result,
    build_epl_recommendation_result,
    build_load_bets_summary_payload,
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
# bet_recommendation_result
# ---------------------------------------------------------------------------


class TestBetRecommendationResult:
    """Contract tests for the bet_recommendation_result definition."""

    def test_canonical_payload_satisfies_contract(self) -> None:
        """Baseline: the canonical fixture must validate."""
        _validator("bet_recommendation_result").validate(
            build_bet_recommendation_result()
        )

    def test_epl_variant_satisfies_contract(self) -> None:
        """EPL variant with null ticker must validate."""
        _validator("bet_recommendation_result").validate(
            build_epl_recommendation_result()
        )

    def test_mlb_variant_satisfies_contract(self) -> None:
        """MLB variant with Kalshi ticker must validate."""
        _validator("bet_recommendation_result").validate(
            build_mlb_recommendation_result()
        )

    def test_rejects_missing_bet_id(self) -> None:
        payload = build_bet_recommendation_result()
        del payload["bet_id"]
        with pytest.raises(ValidationError):
            _validator("bet_recommendation_result").validate(payload)

    def test_rejects_missing_sport(self) -> None:
        payload = build_bet_recommendation_result()
        del payload["sport"]
        with pytest.raises(ValidationError):
            _validator("bet_recommendation_result").validate(payload)

    def test_rejects_missing_recommendation_date(self) -> None:
        payload = build_bet_recommendation_result()
        del payload["recommendation_date"]
        with pytest.raises(ValidationError):
            _validator("bet_recommendation_result").validate(payload)

    def test_rejects_missing_home_team(self) -> None:
        payload = build_bet_recommendation_result()
        del payload["home_team"]
        with pytest.raises(ValidationError):
            _validator("bet_recommendation_result").validate(payload)

    def test_rejects_missing_away_team(self) -> None:
        payload = build_bet_recommendation_result()
        del payload["away_team"]
        with pytest.raises(ValidationError):
            _validator("bet_recommendation_result").validate(payload)

    def test_rejects_missing_bet_on(self) -> None:
        payload = build_bet_recommendation_result()
        del payload["bet_on"]
        with pytest.raises(ValidationError):
            _validator("bet_recommendation_result").validate(payload)

    def test_rejects_missing_elo_prob(self) -> None:
        payload = build_bet_recommendation_result()
        del payload["elo_prob"]
        with pytest.raises(ValidationError):
            _validator("bet_recommendation_result").validate(payload)

    def test_rejects_missing_market_prob(self) -> None:
        payload = build_bet_recommendation_result()
        del payload["market_prob"]
        with pytest.raises(ValidationError):
            _validator("bet_recommendation_result").validate(payload)

    def test_rejects_missing_edge(self) -> None:
        payload = build_bet_recommendation_result()
        del payload["edge"]
        with pytest.raises(ValidationError):
            _validator("bet_recommendation_result").validate(payload)

    def test_rejects_missing_confidence(self) -> None:
        payload = build_bet_recommendation_result()
        del payload["confidence"]
        with pytest.raises(ValidationError):
            _validator("bet_recommendation_result").validate(payload)

    # --- range / enum invaraints ---

    @pytest.mark.parametrize("bad_prob", [-0.01, 1.01, 1.5, -0.5])
    def test_rejects_market_prob_out_of_range(self, bad_prob: float) -> None:
        with pytest.raises(ValidationError):
            _validator("bet_recommendation_result").validate(
                build_bet_recommendation_result(market_prob=bad_prob)
            )

    @pytest.mark.parametrize("bad_prob", [-0.01, 1.01, 1.5, -0.5])
    def test_rejects_elo_prob_out_of_range(self, bad_prob: float) -> None:
        with pytest.raises(ValidationError):
            _validator("bet_recommendation_result").validate(
                build_bet_recommendation_result(elo_prob=bad_prob)
            )

    @pytest.mark.parametrize("bad_kelly", [-0.01, -0.5, -1.0])
    def test_rejects_negative_kelly_fraction(self, bad_kelly: float) -> None:
        with pytest.raises(ValidationError):
            _validator("bet_recommendation_result").validate(
                build_bet_recommendation_result(kelly_fraction=bad_kelly)
            )

    @pytest.mark.parametrize("bad_conf", ["medium", "low", "high", "", "UNKNOWN"])
    def test_rejects_invalid_confidence(self, bad_conf: str) -> None:
        with pytest.raises(ValidationError):
            _validator("bet_recommendation_result").validate(
                build_bet_recommendation_result(confidence=bad_conf)
            )

    def test_unknown_field_is_rejected(self) -> None:
        """additionalProperties: false — unknown keys should fail."""
        payload = build_bet_recommendation_result()
        payload["unknown_field"] = "anything"
        with pytest.raises(ValidationError):
            _validator("bet_recommendation_result").validate(payload)

    def test_governed_probability_fields_are_allowed(self) -> None:
        """Wave 3 governed probability fields remain inside the canonical boundary."""
        payload = build_bet_recommendation_result(
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
        _validator("bet_recommendation_result").validate(payload)

    def test_governed_approval_evidence_fields_are_allowed(self) -> None:
        """Wave 5 approval-grade evidence tiers remain inside the canonical boundary."""
        payload = build_bet_recommendation_result(
            clv_evidence_tier="approval_grade",
            calibration_evidence_tier="approval_grade",
            walk_forward_evidence_tier="approval_grade",
            approval_grade_evidence=True,
        )
        _validator("bet_recommendation_result").validate(payload)


# ---------------------------------------------------------------------------
# load_bets_summary
# ---------------------------------------------------------------------------


class TestLoadBetsSummary:
    """Contract tests for the load_bets_summary definition."""

    def test_canonical_payload_satisfies_contract(self) -> None:
        _validator("load_bets_summary").validate(
            build_load_bets_summary_payload()
        )

    def test_rejects_missing_sport(self) -> None:
        payload = build_load_bets_summary_payload()
        del payload["sport"]
        with pytest.raises(ValidationError):
            _validator("load_bets_summary").validate(payload)

    def test_rejects_missing_date_str(self) -> None:
        payload = build_load_bets_summary_payload()
        del payload["date_str"]
        with pytest.raises(ValidationError):
            _validator("load_bets_summary").validate(payload)

    def test_rejects_missing_bets_loaded(self) -> None:
        payload = build_load_bets_summary_payload()
        del payload["bets_loaded"]
        with pytest.raises(ValidationError):
            _validator("load_bets_summary").validate(payload)

    def test_rejects_negative_bets_loaded(self) -> None:
        with pytest.raises(ValidationError):
            _validator("load_bets_summary").validate(
                build_load_bets_summary_payload(bets_loaded=-1)
            )

    def test_rejects_non_integer_bets_loaded(self) -> None:
        with pytest.raises(ValidationError):
            _validator("load_bets_summary").validate(
                build_load_bets_summary_payload(bets_loaded=3.5)
            )

    def test_unknown_field_is_rejected(self) -> None:
        payload = build_load_bets_summary_payload()
        payload["extra_field"] = "nope"
        with pytest.raises(ValidationError):
            _validator("load_bets_summary").validate(payload)
