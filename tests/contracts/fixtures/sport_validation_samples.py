"""Deterministic sport-validation fixtures for governed contract tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

SUPPORTED_SPORTS: tuple[str, ...] = (
    "MLB",
    "TENNIS",
    "EPL",
    "LIGUE1",
    "NBA",
    "NHL",
    "NFL",
    "NCAAB",
    "WNCAAB",
)

SHADOW_ONLY_SPORTS: tuple[str, ...] = ("MLB", "TENNIS", "EPL", "LIGUE1")
BLOCKED_SPORTS: tuple[str, ...] = ("NBA", "NHL", "NFL", "NCAAB", "WNCAAB")

_REVIEWED_AT = "2026-05-12T00:00:00Z"


def _missing_dimension(status_reason: str) -> dict[str, Any]:
    return {
        "status": "missing",
        "missing_reason_codes": [status_reason],
        "contamination_reason_codes": [],
    }


def _shadow_dimension() -> dict[str, Any]:
    return {
        "status": "shadow_only",
        "missing_reason_codes": [],
        "contamination_reason_codes": [],
    }


def _candidate_dimension() -> dict[str, Any]:
    return {
        "status": "candidate",
        "missing_reason_codes": [],
        "contamination_reason_codes": [],
    }


def _approval_dimension() -> dict[str, Any]:
    return {
        "status": "approval_grade",
        "missing_reason_codes": [],
        "contamination_reason_codes": [],
    }


def _contaminated_dimension(*reason_codes: str) -> dict[str, Any]:
    return {
        "status": "contaminated",
        "missing_reason_codes": [],
        "contamination_reason_codes": list(reason_codes),
    }


def _empty_blockers() -> dict[str, list[str]]:
    return {
        "missing_evidence": [],
        "contamination": [],
        "parity_failures": [],
    }


_BASELINE_STATE_BY_SPORT: dict[str, dict[str, Any]] = {
    "MLB": {
        "schema_version": "v1",
        "contract_kind": "sport_validation_state",
        "sport": "MLB",
        "market_type": "moneyline",
        "validation_status": "shadow_only",
        "sizing_eligible": False,
        "cohort_provenance": {
            "cohort_type": "mixed_executed_and_recommendation",
            "placed_bet_only": False,
            "includes_recommendation_only": True,
            "includes_backfilled_recommendations": False,
            "includes_synthetic_tickers": False,
        },
        "artifact_provenance": {
            "artifact_id": "mlb_model_predictions",
            "artifact_version": "descriptive-shadow-baseline",
            "runtime_consumer": "dags.multi_sport_betting_workflow.identify_good_mlb_bets",
            "evidence_runtime_consumer": "dashboard.model_health.mlb_model_predictions",
            "holdout_window": None,
            "walk_forward_window": None,
            "reviewed_at": _REVIEWED_AT,
        },
        "runtime_parity": {
            "status": "divergent",
            "reason_codes": ["reporting_runtime_divergence"],
        },
        "evidence_dimensions": {
            "clv": _contaminated_dimension("binary_result_clv_contamination"),
            "calibration": _shadow_dimension(),
            "walk_forward": _shadow_dimension(),
        },
        "approval_blockers": {
            "missing_evidence": [],
            "contamination": ["binary_result_clv_contamination"],
            "parity_failures": ["reporting_runtime_divergence"],
        },
    },
    "TENNIS": {
        "schema_version": "v1",
        "contract_kind": "sport_validation_state",
        "sport": "TENNIS",
        "market_type": "match_winner",
        "validation_status": "shadow_only",
        "sizing_eligible": False,
        "cohort_provenance": {
            "cohort_type": "synthetic_identifier_recommendations",
            "placed_bet_only": False,
            "includes_recommendation_only": True,
            "includes_backfilled_recommendations": False,
            "includes_synthetic_tickers": True,
        },
        "artifact_provenance": {
            "artifact_id": "tennis_calibrated_elo",
            "artifact_version": "descriptive-shadow-baseline",
            "runtime_consumer": "plugins.elo.tennis_elo_rating.predict_with_payload",
            "evidence_runtime_consumer": "plugins.elo.tennis_elo_rating.predict_with_payload",
            "holdout_window": None,
            "walk_forward_window": None,
            "reviewed_at": _REVIEWED_AT,
        },
        "runtime_parity": {
            "status": "aligned",
            "reason_codes": [],
        },
        "evidence_dimensions": {
            "clv": _contaminated_dimension(
                "binary_result_clv_contamination",
                "synthetic_ticker_contamination",
            ),
            "calibration": _shadow_dimension(),
            "walk_forward": _shadow_dimension(),
        },
        "approval_blockers": {
            "missing_evidence": [],
            "contamination": [
                "binary_result_clv_contamination",
                "synthetic_ticker_contamination",
            ],
            "parity_failures": [],
        },
    },
    "EPL": {
        "schema_version": "v1",
        "contract_kind": "sport_validation_state",
        "sport": "EPL",
        "market_type": "match_winner",
        "validation_status": "shadow_only",
        "sizing_eligible": False,
        "cohort_provenance": {
            "cohort_type": "descriptive_only",
            "placed_bet_only": False,
            "includes_recommendation_only": True,
            "includes_backfilled_recommendations": False,
            "includes_synthetic_tickers": False,
        },
        "artifact_provenance": {
            "artifact_id": "epl_offline_ensemble",
            "artifact_version": "descriptive-shadow-baseline",
            "runtime_consumer": "dags.multi_sport_betting_workflow.identify_good_epl_bets",
            "evidence_runtime_consumer": "dashboard.pages.calibration.epl_shadow",
            "holdout_window": None,
            "walk_forward_window": None,
            "reviewed_at": _REVIEWED_AT,
        },
        "runtime_parity": {
            "status": "divergent",
            "reason_codes": [
                "runtime_consumer_mismatch",
                "governed_artifact_not_consumed",
            ],
        },
        "evidence_dimensions": {
            "clv": _contaminated_dimension("binary_result_clv_contamination"),
            "calibration": _shadow_dimension(),
            "walk_forward": _missing_dimension("missing_walk_forward_evidence"),
        },
        "approval_blockers": {
            "missing_evidence": [
                "missing_walk_forward_evidence",
                "missing_governed_holdout_evidence",
            ],
            "contamination": ["binary_result_clv_contamination"],
            "parity_failures": [
                "runtime_consumer_mismatch",
                "governed_artifact_not_consumed",
            ],
        },
    },
    "LIGUE1": {
        "schema_version": "v1",
        "contract_kind": "sport_validation_state",
        "sport": "LIGUE1",
        "market_type": "match_winner",
        "validation_status": "shadow_only",
        "sizing_eligible": False,
        "cohort_provenance": {
            "cohort_type": "descriptive_only",
            "placed_bet_only": False,
            "includes_recommendation_only": True,
            "includes_backfilled_recommendations": False,
            "includes_synthetic_tickers": False,
        },
        "artifact_provenance": {
            "artifact_id": "ligue1_live_ensemble",
            "artifact_version": "descriptive-shadow-baseline",
            "runtime_consumer": "dags.multi_sport_betting_workflow.identify_good_epl_bets",
            "evidence_runtime_consumer": "replay.ligue1.shadow_validation",
            "holdout_window": None,
            "walk_forward_window": None,
            "reviewed_at": _REVIEWED_AT,
        },
        "runtime_parity": {
            "status": "divergent",
            "reason_codes": ["governed_artifact_not_consumed"],
        },
        "evidence_dimensions": {
            "clv": _contaminated_dimension("binary_result_clv_contamination"),
            "calibration": _shadow_dimension(),
            "walk_forward": _shadow_dimension(),
        },
        "approval_blockers": {
            "missing_evidence": [],
            "contamination": ["binary_result_clv_contamination"],
            "parity_failures": ["governed_artifact_not_consumed"],
        },
    },
}

for blocked_sport in BLOCKED_SPORTS:
    _BASELINE_STATE_BY_SPORT[blocked_sport] = {
        "schema_version": "v1",
        "contract_kind": "sport_validation_state",
        "sport": blocked_sport,
        "market_type": "moneyline",
        "validation_status": "blocked",
        "sizing_eligible": False,
        "cohort_provenance": {
            "cohort_type": "descriptive_only",
            "placed_bet_only": False,
            "includes_recommendation_only": True,
            "includes_backfilled_recommendations": False,
            "includes_synthetic_tickers": False,
        },
        "artifact_provenance": {
            "artifact_id": None,
            "artifact_version": None,
            "runtime_consumer": None,
            "evidence_runtime_consumer": None,
            "holdout_window": None,
            "walk_forward_window": None,
            "reviewed_at": _REVIEWED_AT,
        },
        "runtime_parity": {
            "status": "missing",
            "reason_codes": [],
        },
        "evidence_dimensions": {
            "clv": _missing_dimension("missing_market_clv_evidence"),
            "calibration": _missing_dimension("missing_calibration_evidence"),
            "walk_forward": _missing_dimension("missing_walk_forward_evidence"),
        },
        "approval_blockers": {
            "missing_evidence": [
                "missing_market_clv_evidence",
                "missing_calibration_evidence",
                "missing_walk_forward_evidence",
                "missing_governed_artifact_lineage",
            ],
            "contamination": [],
            "parity_failures": [],
        },
    }


def build_sport_validation_state(sport: str) -> dict[str, Any]:
    """Return the deterministic Wave-1 audited baseline for one supported sport."""
    return deepcopy(_BASELINE_STATE_BY_SPORT[sport])


def build_candidate_validation_state() -> dict[str, Any]:
    """Return a deterministic future-state candidate fixture."""
    return {
        "schema_version": "v1",
        "contract_kind": "sport_validation_state",
        "sport": "MLB",
        "market_type": "moneyline",
        "validation_status": "candidate",
        "sizing_eligible": False,
        "cohort_provenance": {
            "cohort_type": "placed_bets_only",
            "placed_bet_only": True,
            "includes_recommendation_only": False,
            "includes_backfilled_recommendations": False,
            "includes_synthetic_tickers": False,
        },
        "artifact_provenance": {
            "artifact_id": "mlb_model_predictions",
            "artifact_version": "2026-05-12-candidate",
            "runtime_consumer": "dags.multi_sport_betting_workflow.identify_good_mlb_bets",
            "evidence_runtime_consumer": "dags.multi_sport_betting_workflow.identify_good_mlb_bets",
            "holdout_window": {
                "start_date": "2025-03-01",
                "end_date": "2025-05-31",
            },
            "walk_forward_window": {
                "start_date": "2025-06-01",
                "end_date": "2025-08-31",
            },
            "reviewed_at": _REVIEWED_AT,
        },
        "runtime_parity": {
            "status": "aligned",
            "reason_codes": [],
        },
        "evidence_dimensions": {
            "clv": _candidate_dimension(),
            "calibration": _candidate_dimension(),
            "walk_forward": _candidate_dimension(),
        },
        "approval_blockers": _empty_blockers(),
    }


def build_approval_grade_validation_state() -> dict[str, Any]:
    """Return a deterministic approval-grade fixture with no fail-closed blockers."""
    return {
        "schema_version": "v1",
        "contract_kind": "sport_validation_state",
        "sport": "MLB",
        "market_type": "moneyline",
        "validation_status": "approval_grade",
        "sizing_eligible": True,
        "cohort_provenance": {
            "cohort_type": "placed_bets_only",
            "placed_bet_only": True,
            "includes_recommendation_only": False,
            "includes_backfilled_recommendations": False,
            "includes_synthetic_tickers": False,
        },
        "artifact_provenance": {
            "artifact_id": "mlb_model_predictions",
            "artifact_version": "2026-05-12-approval",
            "runtime_consumer": "dags.multi_sport_betting_workflow.identify_good_mlb_bets",
            "evidence_runtime_consumer": "dags.multi_sport_betting_workflow.identify_good_mlb_bets",
            "holdout_window": {
                "start_date": "2025-03-01",
                "end_date": "2025-05-31",
            },
            "walk_forward_window": {
                "start_date": "2025-06-01",
                "end_date": "2025-08-31",
            },
            "reviewed_at": _REVIEWED_AT,
        },
        "runtime_parity": {
            "status": "aligned",
            "reason_codes": [],
        },
        "evidence_dimensions": {
            "clv": _approval_dimension(),
            "calibration": _approval_dimension(),
            "walk_forward": _approval_dimension(),
        },
        "approval_blockers": _empty_blockers(),
    }


def build_contaminated_validation_state() -> dict[str, Any]:
    """Return a deterministic contaminated validation fixture."""
    state = build_sport_validation_state("TENNIS")
    state["cohort_provenance"]["cohort_type"] = "mixed_executed_and_recommendation"
    state["cohort_provenance"]["includes_synthetic_tickers"] = True
    state["approval_blockers"]["contamination"] = [
        "binary_result_clv_contamination",
        "mixed_cohort_contamination",
        "synthetic_ticker_contamination",
    ]
    state["evidence_dimensions"]["clv"] = _contaminated_dimension(
        "binary_result_clv_contamination",
        "synthetic_ticker_contamination",
    )
    return state


def build_validation_eligibility_matrix() -> dict[str, Any]:
    """Return the deterministic audited Wave-1 validation baseline matrix."""
    states_by_sport = {
        sport: build_sport_validation_state(sport) for sport in SUPPORTED_SPORTS
    }
    return {
        "schema_version": "v1",
        "contract_kind": "validation_eligibility_matrix",
        "baseline_name": "wave_1_audited_baseline",
        "reviewed_at": _REVIEWED_AT,
        "supported_sports": list(SUPPORTED_SPORTS),
        "states_by_sport": states_by_sport,
        "status_index": {
            "blocked": list(BLOCKED_SPORTS),
            "shadow_only": list(SHADOW_ONLY_SPORTS),
            "candidate": [],
            "approval_grade": [],
            "contaminated": ["MLB", "TENNIS", "EPL", "LIGUE1"],
            "sizing_eligible": [],
        },
    }
