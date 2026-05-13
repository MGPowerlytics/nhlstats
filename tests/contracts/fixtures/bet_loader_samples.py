"""Deterministic BetLoader contract fixtures.

Builders for bet_recommendation persisted rows and load_bets summaries
that satisfy the ``bet_loader_contract_v1.json`` schema.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_BASE_BET_RECOMMENDATION_RESULT: dict[str, Any] = {
    "bet_id": "TEST_2026-04-07_KXMLBGAME-26APR07NYYBOS-NYY_home",
    "sport": "TEST",
    "recommendation_date": "2026-04-07",
    "home_team": "New York Yankees",
    "away_team": "Boston Red Sox",
    "bet_on": "New York Yankees",
    "ticker": "KXMLBGAME-26APR07NYYBOS-NYY",
    "market_prob": 0.47,
    "elo_prob": 0.58,
    "edge": 0.11,
    "kelly_fraction": 0.1037,
    "expected_value": 0.2340,
    "confidence": "MEDIUM",
    "home_rating": 1612.4,
    "away_rating": 1498.2,
    "yes_ask": 47,
    "no_ask": 53,
    "probability_source": "elo_prob",
    "quote_price_cents": 47,
    "quote_price_role": "executable",
    "quote_source_system": "bet_recommendation_payload",
    "quote_bookmaker": "Kalshi",
    "quote_observed_at": None,
    "quote_loaded_at": None,
    "quote_payload_ref": "KXMLBGAME-26APR07NYYBOS-NYY",
    "quote_freshness_result": "missing_source_timestamp",
    "quote_fallback_status": "payload_only_quote",
    "evidence_state": "shadow_only",
    "evidence_state_reason": "Monitoring only until approval evidence is reviewable.",
    "evidence_state_source_artifact": "docs/plan/2026-05-12-betting-pipeline-audit/governed-probability-spec.md",
    "governance_status": "descriptive_only",
    "sizing_eligible": False,
    "abstain": False,
    "abstention_reason": None,
    "clv_evidence_tier": "approval_grade",
    "calibration_evidence_tier": "approval_grade",
    "walk_forward_evidence_tier": "approval_grade",
    "approval_grade_evidence": True,
}

_BASE_LOAD_BETS_SUMMARY: dict[str, Any] = {
    "sport": "MLB",
    "date_str": "2026-04-07",
    "bets_loaded": 5,
}


def build_bet_recommendation_result(**overrides: Any) -> dict[str, Any]:
    """Build a canonical bet_recommendation_result payload.

    Represents the output of ``BetRecommendation.to_sql_params()`` as
    validated against the ``bet_recommendation_result`` contract definition.
    """
    payload = deepcopy(_BASE_BET_RECOMMENDATION_RESULT)
    payload.update(overrides)
    return payload


def build_load_bets_summary_payload(**overrides: Any) -> dict[str, Any]:
    """Build a canonical load_bets_summary payload.

    Represents the summary output from ``BetLoader.get_bets_summary()``
    as validated against the ``load_bets_summary`` contract definition.
    """
    payload = deepcopy(_BASE_LOAD_BETS_SUMMARY)
    payload.update(overrides)
    return payload


def build_epl_recommendation_result(**overrides: Any) -> dict[str, Any]:
    """Build an EPL-specific bet_recommendation_result payload.

    Uses EPL sport and typical EPL bet_id pattern.
    """
    payload = deepcopy(_BASE_BET_RECOMMENDATION_RESULT)
    payload["sport"] = "EPL"
    payload["bet_id"] = "EPL-2026-04-07-LIVERPOOL-MANCHESTERUNITED-home"
    payload["home_team"] = "Liverpool"
    payload["away_team"] = "Manchester United"
    payload["bet_on"] = "home"
    payload["ticker"] = None
    payload["market_prob"] = 0.52
    payload["elo_prob"] = 0.61
    payload["edge"] = 0.09
    payload["kelly_fraction"] = 0.0823
    payload["expected_value"] = 0.1731
    payload["confidence"] = "LOW"
    payload["home_rating"] = 1750.0
    payload["away_rating"] = 1680.0
    payload["yes_ask"] = None
    payload["no_ask"] = None
    payload["quote_price_cents"] = None
    payload["quote_source_system"] = "quote_lineage_placeholder"
    payload["quote_bookmaker"] = None
    payload["quote_payload_ref"] = None
    payload["quote_fallback_status"] = "missing_quote"
    payload.update(overrides)
    return payload


def build_mlb_recommendation_result(**overrides: Any) -> dict[str, Any]:
    """Build an MLB-specific bet_recommendation_result payload.

    Uses MLB sport, Kalshi ticker format, and typical MLB values.
    """
    payload = deepcopy(_BASE_BET_RECOMMENDATION_RESULT)
    payload["sport"] = "MLB"
    payload["bet_id"] = "MLB_2026-04-07_KXMLBGAME-26APR07NYYBOS-NYY_home"
    payload["home_team"] = "New York Yankees"
    payload["away_team"] = "Boston Red Sox"
    payload["bet_on"] = "New York Yankees"
    payload["ticker"] = "KXMLBGAME-26APR07NYYBOS-NYY"
    payload["market_prob"] = 0.47
    payload["elo_prob"] = 0.58
    payload["edge"] = 0.11
    payload["kelly_fraction"] = 0.1037
    payload["expected_value"] = 0.2340
    payload["confidence"] = "MEDIUM"
    payload["home_rating"] = 1612.4
    payload["away_rating"] = 1498.2
    payload["yes_ask"] = 47
    payload["no_ask"] = 53
    payload.update(overrides)
    return payload
