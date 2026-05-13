"""Focused unit tests for the governed dashboard data layer."""

from __future__ import annotations

import re
import traceback
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import pytest
from sqlalchemy.exc import ProgrammingError

from dashboard import data_layer


class FakeDashboardDB:
    """Small DBManager test double that records SQL and returns DataFrames."""

    def __init__(
        self,
        frames: dict[str, pd.DataFrame] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.frames = frames or {}
        self.error = error
        self.queries: list[str] = []

    def fetch_df(
        self, query: str, params: dict[str, Any] | None = None
    ) -> pd.DataFrame:
        """Record query text and return the configured view frame."""

        self.queries.append(query)
        if self.error is not None:
            raise self.error
        match = re.search(r"\bFROM\s+([a-z_]+_v1)\b", query)
        view_name = match.group(1) if match else ""
        return self.frames.get(view_name, pd.DataFrame())


@pytest.fixture(autouse=True)
def clear_dashboard_caches() -> None:
    """Clear Streamlit caches between tests so monkeypatched DBs are isolated."""

    data_layer.bust_cache()


def _portfolio_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "snapshot_hour_utc": datetime(2026, 5, 3, 12, tzinfo=timezone.utc),
                "balance_dollars": 1200.0,
                "portfolio_value_dollars": 1500.0,
                "cumulative_deposits_dollars": 1000.0,
                "realized_profit_dollars": 250.0,
                "open_risk_dollars": 75.0,
                "settled_bet_count": 10,
                "open_bet_count": 2,
                "roi": 0.5,
                "created_at_utc": datetime(2026, 5, 3, 12, 1, tzinfo=timezone.utc),
            }
        ]
    )


def _live_markets_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "market_external_id": "KXNHL-26MAY03NYRBOS-NYR",
                "game_date": "2026-05-03",
                "commence_time": "2026-05-03T23:00:00Z",
                "home_team_name": "New York Rangers",
                "away_team_name": "Boston Bruins",
                "bookmaker": "Kalshi",
                "market_name": "moneyline",
                "outcome_name": "New York Rangers",
                "price": 0.57,
                "last_update": "2026-05-03T13:55:00Z",
                "recommendation_bet_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME",
                "edge": 0.08,
                "expected_value": 0.14,
                "confidence": "HIGH",
                "ticker": "KXNHL-26MAY03NYRBOS-NYR",
            }
        ],
        columns=data_layer.LIVE_MARKET_COLUMNS,
    )


def _tennis_predictions_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "bet_id": "TENNIS_2026-05-04_KXATPMATCH-26MAY04ALPBRA-ALP_home",
                "sport": "TENNIS",
                "recommendation_date": "2026-05-04",
                "commence_time": "2026-05-04T16:00:00Z",
                "home_team": "Alpha A.",
                "away_team": "Bravo B.",
                "bet_on": "Alpha A.",
                "ticker": "KXATPMATCH-26MAY04ALPBRA-ALP",
                "model_prob": 0.64,
                "market_prob": 0.56,
                "edge": 0.08,
                "expected_value": 0.1429,
                "kelly_fraction": 0.18,
                "confidence": "HIGH",
                "yes_ask": 56,
                "no_ask": 44,
                "created_at": "2026-05-03T14:00:00Z",
            }
        ],
        columns=data_layer.TENNIS_PREDICTION_COLUMNS,
    )


def _tennis_model_health_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "run_date": "2026-05-11",
                "model_version": "tennis_probability_model_v2",
                "data_source": "postgres_tennis_games",
                "rows": 960,
                "holdout_rows": 192,
                "betmgm_holdout_rows": 144,
                "enabled": True,
                "beats_betmgm": True,
                "baseline_log_loss": 0.6221,
                "ensemble_log_loss": 0.5982,
                "ensemble_market_log_loss": 0.6034,
                "betmgm_log_loss": 0.6178,
                "baseline_brier": 0.2174,
                "ensemble_brier": 0.2091,
                "ensemble_market_brier": 0.2108,
                "betmgm_brier": 0.2156,
                "baseline_accuracy": 0.6771,
                "ensemble_accuracy": 0.6979,
                "ensemble_market_accuracy": 0.6944,
                "betmgm_accuracy": 0.6875,
                "baseline_actionable_count": 81,
                "ensemble_actionable_count": 104,
                "log_loss_delta": -0.0239,
                "brier_delta": -0.0083,
                "accuracy_delta": 0.0208,
                "ensemble_vs_betmgm_log_loss_delta": -0.0144,
                "ensemble_vs_betmgm_brier_delta": -0.0048,
                "ensemble_vs_betmgm_accuracy_delta": 0.0069,
                "created_at": "2026-05-11T19:45:00Z",
            }
        ],
        columns=data_layer.TENNIS_MODEL_HEALTH_COLUMNS,
    )


def _calibration_frame(settled_count: int = 8) -> pd.DataFrame:
    observed_win_rate = 0.625 if settled_count else None
    return pd.DataFrame(
        [
            {
                "bucket_start": 0.5,
                "bucket_end": 0.6,
                "prediction_count": 10,
                "avg_elo_prob": 0.55,
                "avg_market_prob": 0.51,
                "observed_win_rate": observed_win_rate,
                "avg_edge": 0.04,
                "avg_expected_value": 0.02,
                "settled_count": settled_count,
                "unsettled_count": 10 - settled_count,
            }
        ],
        columns=data_layer.CALIBRATION_COLUMNS,
    )


def _bet_detail_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "bet_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME",
                "recommendation_date": "2026-05-03",
                "placed_time_utc": "2026-05-03T14:15:00Z",
                "home_team": "New York Rangers",
                "away_team": "Boston Bruins",
                "bet_on": "New York Rangers",
                "ticker": "KXNHL-26MAY03NYRBOS-NYR",
                "elo_prob": 0.62,
                "market_prob": 0.54,
                "edge": 0.08,
                "expected_value": 0.14,
                "kelly_fraction": 0.11,
                "confidence": "HIGH",
                "yes_ask": 54,
                "no_ask": 46,
                "status": "open",
                "cost_dollars": 10.0,
                "payout_dollars": 18.5,
                "profit_dollars": 8.5,
                "created_at": "2026-05-03T14:00:00Z",
            }
        ],
        columns=data_layer.BET_DETAIL_COLUMNS,
    )


def _sport_validation_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "sport": "NHL",
                "market_type": "moneyline",
                "cohort_type": "approval_review",
                "evidence_dimension": "validation",
                "canonical_game_id": None,
                "market_ticker": None,
                "selection_key": None,
                "source_relation": "audit_specification",
                "source_record_id": "NHL",
                "evidence_state_scope": "sport",
                "evidence_state": "blocked",
                "evidence_state_reason": "NHL remains blocked until governed approval evidence exists.",
                "evidence_state_as_of": "2026-05-12T00:00:00Z",
                "evidence_state_source_artifact": "docs/plan/2026-05-12-betting-pipeline-audit/evidence-readmodel-spec.md",
                "governance_status": "descriptive_only",
                "descriptive_only_flag": True,
                "contamination_flag": False,
                "contamination_reason": None,
                "excluded_from_approval_flag": True,
                "observed_at": "2026-05-12T00:00:00Z",
                "loaded_at": None,
                "last_updated_at": "2026-05-12T00:00:00Z",
                "review_timestamp": "2026-05-12T00:00:00Z",
                "runtime_consumer": None,
                "artifact_id": None,
                "artifact_version": "v1",
                "artifact_family": "approval_evidence_read_model",
                "artifact_available_flag": False,
                "placed_bet_only_flag": False,
                "synthetic_identity_flag": False,
                "backfill_flag": False,
            }
        ],
        columns=data_layer.SPORT_VALIDATION_COLUMNS,
    )


def _governed_evidence_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "sport": "NHL",
                "market_type": "moneyline",
                "cohort_type": "recommendation_rows",
                "evidence_dimension": "read_model",
                "canonical_game_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS",
                "market_ticker": "KXNHL-26MAY03NYRBOS-NYR",
                "selection_key": "New York Rangers",
                "source_relation": "bet_recommendations",
                "source_record_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME",
                "evidence_state_scope": "sport",
                "evidence_state": "blocked",
                "evidence_state_reason": "NHL remains blocked until governed approval evidence exists.",
                "evidence_state_as_of": "2026-05-12T00:00:00Z",
                "evidence_state_source_artifact": "docs/plan/2026-05-12-betting-pipeline-audit/evidence-readmodel-spec.md",
                "governance_status": "descriptive_only",
                "descriptive_only_flag": True,
                "contamination_flag": False,
                "contamination_reason": None,
                "excluded_from_approval_flag": True,
                "observed_at": "2026-05-03T14:00:00Z",
                "loaded_at": "2026-05-03T13:56:00Z",
                "last_updated_at": "2026-05-03T14:00:00Z",
                "recommendation_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME",
                "recommendation_created_at": "2026-05-03T14:00:00Z",
                "recommendation_source_surface": "bet_recommendations",
                "probability_source": "elo_prob",
                "calibrated_probability": 0.62,
                "market_probability": 0.54,
                "edge": 0.08,
                "expected_value": 0.14,
                "kelly_fraction": 0.11,
                "confidence_label": "HIGH",
                "quote_source_system": "bet_recommendation_payload",
                "quote_bookmaker": "Kalshi",
                "quote_observed_at": "2026-05-03T13:55:00Z",
                "quote_loaded_at": "2026-05-03T13:56:00Z",
                "quote_payload_ref": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-KALSHI-HOME",
                "quote_lineage_status": "linked_market_quote",
                "quote_price_cents": 54,
                "quote_price_role": "executable",
                "quote_freshness_result": "fresh",
                "quote_fallback_status": "direct_quote",
            }
        ],
        columns=data_layer.GOVERNED_EVIDENCE_COLUMNS,
    )


def _governed_execution_link_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "sport": "NHL",
                "market_type": "moneyline",
                "cohort_type": "execution_rows",
                "evidence_dimension": "read_model",
                "canonical_game_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS",
                "market_ticker": "KXNHL-26MAY03NYRBOS-NYR",
                "selection_key": "New York Rangers",
                "source_relation": "placed_bets",
                "source_record_id": "DASHBOARD-SEED-NHL-ORDER-20260503-NYR-BOS-HOME",
                "evidence_state_scope": "sport",
                "evidence_state": "blocked",
                "evidence_state_reason": "NHL remains blocked until governed approval evidence exists.",
                "evidence_state_as_of": "2026-05-12T00:00:00Z",
                "evidence_state_source_artifact": "docs/plan/2026-05-12-betting-pipeline-audit/evidence-readmodel-spec.md",
                "governance_status": "descriptive_only",
                "descriptive_only_flag": True,
                "contamination_flag": False,
                "contamination_reason": None,
                "excluded_from_approval_flag": True,
                "observed_at": "2026-05-03T14:15:00Z",
                "loaded_at": "2026-05-03T14:15:00Z",
                "last_updated_at": "2026-05-03T14:15:00Z",
                "placed_bet_id": "DASHBOARD-SEED-NHL-ORDER-20260503-NYR-BOS-HOME",
                "recommendation_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME",
                "execution_source_surface": "placed_bets",
                "execution_status": "open",
                "submitted_at": "2026-05-03T14:15:00Z",
                "filled_at": None,
                "contracts": 10,
                "execution_cost_dollars": 10.0,
                "notional_exposure": 10.0,
                "entry_probability": 0.54,
                "entry_quote_role": "executable",
                "entry_price_source": "dashboard_seed",
                "linkage_status": "linked",
                "linkage_basis": "market_ticker_selection_key_canonical_game_id",
                "linked_canonical_game_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS",
                "linked_market_ticker": "KXNHL-26MAY03NYRBOS-NYR",
                "linked_selection_key": "New York Rangers",
                "entry_quote_source_system": "kalshi_market_details",
                "entry_quote_bookmaker": "Kalshi",
                "entry_quote_observed_at": "2026-05-03T13:55:00Z",
                "entry_quote_loaded_at": "2026-05-03T13:56:00Z",
                "entry_quote_payload_ref": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-KALSHI-HOME",
                "entry_quote_lineage_status": "linked_market_quote",
                "entry_price_cents": 54,
                "entry_quote_freshness_result": "fresh",
                "entry_quote_fallback_status": "direct_market_quote",
            }
        ],
        columns=data_layer.GOVERNED_RECOMMENDATION_EXECUTION_LINK_COLUMNS,
    )


def _governed_clv_evidence_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "sport": "NHL",
                "market_type": "moneyline",
                "cohort_type": "execution_rows",
                "evidence_dimension": "pricing_clv",
                "canonical_game_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS",
                "market_ticker": "KXNHL-26MAY03NYRBOS-NYR",
                "selection_key": "New York Rangers",
                "source_relation": "placed_bets",
                "source_record_id": "DASHBOARD-SEED-NHL-ORDER-20260503-NYR-BOS-HOME",
                "evidence_state_scope": "sport",
                "evidence_state": "blocked",
                "evidence_state_reason": "NHL remains blocked until governed approval evidence exists.",
                "evidence_state_as_of": "2026-05-12T00:00:00Z",
                "evidence_state_source_artifact": "docs/plan/2026-05-12-betting-pipeline-audit/evidence-readmodel-spec.md",
                "governance_status": "descriptive_only",
                "descriptive_only_flag": True,
                "contamination_flag": False,
                "contamination_reason": None,
                "excluded_from_approval_flag": True,
                "observed_at": "2026-05-03T14:15:00Z",
                "loaded_at": "2026-05-03T14:15:00Z",
                "last_updated_at": "2026-05-03T14:15:00Z",
                "placed_bet_id": "DASHBOARD-SEED-NHL-ORDER-20260503-NYR-BOS-HOME",
                "recommendation_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME",
                "linked_canonical_game_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS",
                "linked_market_ticker": "KXNHL-26MAY03NYRBOS-NYR",
                "linked_selection_key": "New York Rangers",
                "clv_source_type": "market_close",
                "clv_computed_at": "2026-05-03T22:56:00Z",
                "entry_probability": 0.54,
                "entry_price_role": "executable",
                "closing_probability": 0.57,
                "clv_delta": 0.03,
                "clv_direction": "positive",
                "closing_quote_source": "dashboard_seed",
                "closing_quote_at": "2026-05-03T22:55:00Z",
                "close_price_role": "close",
                "close_freshness_result": "fresh",
                "selected_close_rule": "latest_admissible_pregame_quote",
                "selected_close_provenance": "dashboard_seed|New York Rangers|2026-05-03T22:55:00Z",
                "clv_evidence_tier": "partially_evidenced",
                "binary_result_placeholder_flag": False,
                "stale_close_flag": False,
                "proxy_close_flag": False,
                "clv_contaminated_flag": False,
                "entry_price_cents": 54,
                "entry_price_source": "dashboard_seed",
                "entry_quote_source_system": "kalshi_market_details",
                "entry_quote_bookmaker": "Kalshi",
                "entry_quote_observed_at": "2026-05-03T14:15:00Z",
                "entry_quote_loaded_at": "2026-05-03T14:15:00Z",
                "entry_quote_payload_ref": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME",
                "entry_freshness_result": "fresh",
                "entry_fallback_status": "direct_market_quote",
                "closing_quote_loaded_at": "2026-05-03T22:56:00Z",
                "closing_quote_payload_ref": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-CLOSE",
                "close_fallback_status": "latest_admissible_pregame_quote",
            }
        ],
        columns=data_layer.GOVERNED_CLV_EVIDENCE_COLUMNS,
    )


def _governed_portfolio_risk_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "sport": "NHL",
                "market_type": "moneyline",
                "cohort_type": "sport_open_exposure",
                "evidence_dimension": "portfolio_risk",
                "canonical_game_id": None,
                "market_ticker": None,
                "selection_key": None,
                "source_relation": "placed_bets",
                "source_record_id": "NHL",
                "evidence_state_scope": "sport",
                "evidence_state": "blocked",
                "evidence_state_reason": "NHL remains blocked until governed approval evidence exists.",
                "evidence_state_as_of": "2026-05-12T00:00:00Z",
                "evidence_state_source_artifact": "docs/plan/2026-05-12-betting-pipeline-audit/evidence-readmodel-spec.md",
                "governance_status": "descriptive_only",
                "descriptive_only_flag": True,
                "contamination_flag": False,
                "contamination_reason": None,
                "excluded_from_approval_flag": True,
                "observed_at": "2026-05-03T14:15:00Z",
                "loaded_at": "2026-05-03T14:01:00Z",
                "last_updated_at": "2026-05-03T14:15:00Z",
                "snapshot_hour_utc": "2026-05-03T14:00:00Z",
                "open_exposure_flag": True,
                "open_exposure_amount": 22.0,
                "position_status": "open",
                "exposure_inclusion_state": "included_open_risk",
                "sport_exposure_amount": 22.0,
                "same_event_exposure_amount": None,
                "same_side_exposure_amount": None,
                "existing_position_flag": True,
                "resting_order_exposure_amount": 10.0,
                "resting_order_count": 1,
                "executed_unsettled_exposure_amount": 12.0,
                "executed_unsettled_count": 1,
                "exposure_state": "mixed_open_exposure",
                "daily_risk_cap_dollars": 368.94,
                "remaining_daily_risk_budget_dollars": 346.94,
                "peak_portfolio_value_dollars": 1600.0,
                "current_portfolio_value_dollars": 1475.75,
                "drawdown_amount_dollars": 124.25,
                "drawdown_ratio": 0.07765625,
                "drawdown_state": "drawdown_active",
                "risk_of_ruin_state": "capital_available",
                "portfolio_guardrail_state": "eligible",
                "portfolio_guardrail_reason_code": None,
                "portfolio_guardrail_reason_detail": None,
                "concentration_bucket": "same_side",
                "concentration_state": "descriptive_only_no_governed_limit",
                "existing_position_state": "mixed_open_exposure",
                "same_match_conflict": True,
                "rejection_reason_code": "missing_evidence",
                "rejection_reason_detail": "NHL remains blocked until governed approval evidence exists.",
                "operator_semantics_version": "portfolio_risk_state_v1",
                "bankroll_source": "portfolio_value_snapshots",
                "bankroll_amount": 1475.75,
                "bankroll_observed_at": "2026-05-03T14:00:00Z",
                "bankroll_snapshot_id": "2026-05-03T14:00:00",
            }
        ],
        columns=data_layer.GOVERNED_PORTFOLIO_RISK_COLUMNS,
    )


def _data_quality_frame(message: str = "Freshness within threshold.") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "check_name": "freshness_game_odds",
                "relation_name": "game_odds",
                "relation_type": "table",
                "status": "warn",
                "row_count": 7,
                "freshness_timestamp": datetime(
                    2026, 5, 3, 13, 55, tzinfo=timezone.utc
                ),
                "max_allowed_lag_minutes": 60,
                "actual_lag_minutes": 75,
                "message": message,
                "checked_at_utc": datetime(2026, 5, 3, 15, 10, tzinfo=timezone.utc),
            }
        ],
        columns=data_layer.DATA_QUALITY_COLUMNS,
    )


def _formatted_exception_text(error: BaseException) -> str:
    return "".join(traceback.format_exception(type(error), error, error.__traceback__))


def _assert_dashboard_error_does_not_leak(
    error: data_layer.DashboardDataError,
    forbidden_tokens: tuple[str, ...],
) -> None:
    assert error.__cause__ is None
    surfaces = {
        "message": str(error),
        "payload": repr(error.payload),
        "traceback": _formatted_exception_text(error),
    }
    for surface_name, text in surfaces.items():
        for token in forbidden_tokens:
            assert token not in text, f"{token!r} leaked via {surface_name}: {text}"


def test_portfolio_summary_reads_governed_view_and_maps_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Portfolio summary is derived from dashboard_portfolio_v1 only."""

    fake_db = FakeDashboardDB({"dashboard_portfolio_v1": _portfolio_frame()})
    monkeypatch.setattr(data_layer, "_db", fake_db)

    summary = data_layer.get_portfolio_summary()

    assert summary["portfolio_value"] == 1500.0
    assert summary["open_bets_count"] == 2
    assert summary["total_exposure"] == 75.0
    assert summary["settled_count"] == 10
    assert summary["empty_state"] is None
    assert fake_db.queries == [
        (
            "SELECT snapshot_hour_utc, balance_dollars, portfolio_value_dollars, "
            "cumulative_deposits_dollars, realized_profit_dollars, open_risk_dollars, "
            "settled_bet_count, open_bet_count, roi, created_at_utc "
            "FROM dashboard_portfolio_v1 ORDER BY snapshot_hour_utc DESC LIMIT 1"
        )
    ]


def test_zero_row_portfolio_summary_returns_explicit_empty_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zero rows are a valid empty state, not a query failure."""

    fake_db = FakeDashboardDB({"dashboard_portfolio_v1": pd.DataFrame()})
    monkeypatch.setattr(data_layer, "_db", fake_db)

    summary = data_layer.get_portfolio_summary()

    assert summary["portfolio_value"] == 0.0
    assert summary["empty_state"] == {
        "kind": "no_portfolio_snapshots",
        "title": "No portfolio snapshots",
        "message": "No governed portfolio snapshots are available yet.",
        "action": "Run the portfolio snapshot ingestion before relying on dashboard KPIs.",
        "severity": "info",
    }


def test_live_markets_reads_governed_view_and_preserves_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live Markets page data comes directly from dashboard_live_markets_v1."""

    fake_db = FakeDashboardDB({"dashboard_live_markets_v1": _live_markets_frame()})
    monkeypatch.setattr(data_layer, "_db", fake_db)

    markets = data_layer.get_live_markets()

    assert markets.attrs["empty_state"] is None
    assert list(markets.columns) == list(data_layer.LIVE_MARKET_COLUMNS)
    row = markets.iloc[0]
    assert row["home_team_name"] == "New York Rangers"
    assert row["away_team_name"] == "Boston Bruins"
    assert row["market_external_id"] == "KXNHL-26MAY03NYRBOS-NYR"
    assert row["ticker"] == "KXNHL-26MAY03NYRBOS-NYR"
    assert row["bookmaker"] == "Kalshi"
    assert row["market_name"] == "moneyline"
    assert row["outcome_name"] == "New York Rangers"
    assert row["price"] == 0.57
    assert row["edge"] == 0.08
    assert row["expected_value"] == 0.14
    assert row["confidence"] == "HIGH"
    assert fake_db.queries == [
        (
            "SELECT market_external_id, game_date, commence_time, home_team_name, "
            "away_team_name, bookmaker, market_name, outcome_name, price, "
            "last_update, recommendation_bet_id, edge, expected_value, confidence, "
            "ticker FROM dashboard_live_markets_v1 ORDER BY commence_time ASC, "
            "market_external_id ASC LIMIT 250"
        )
    ]


def test_zero_row_live_markets_returns_explicit_empty_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zero live-market rows return the governed no_live_markets empty state."""

    fake_db = FakeDashboardDB({"dashboard_live_markets_v1": pd.DataFrame()})
    monkeypatch.setattr(data_layer, "_db", fake_db)

    markets = data_layer.get_live_markets()

    assert markets.empty
    assert markets.attrs["empty_state"] == {
        "kind": "no_live_markets",
        "title": "No live markets",
        "message": "No governed live market rows are available right now.",
        "action": "Wait for market ingestion to complete or refresh later.",
        "severity": "info",
    }


def test_current_tennis_predictions_reads_governed_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Current-run tennis predictions come from the governed tennis read model."""
    fake_db = FakeDashboardDB(
        {"dashboard_tennis_predictions_v1": _tennis_predictions_frame()}
    )
    monkeypatch.setattr(data_layer, "_db", fake_db)

    predictions = data_layer.get_tomorrow_tennis_predictions(
        reference_date=datetime(2026, 5, 3).date()
    )

    assert predictions.attrs["empty_state"] is None
    assert list(predictions.columns) == list(data_layer.TENNIS_PREDICTION_COLUMNS)
    row = predictions.iloc[0]
    assert row["sport"] == "TENNIS"
    assert row["bet_on"] == "Alpha A."
    assert row["model_prob"] == 0.64
    assert row["edge"] == 0.08
    assert fake_db.queries == [
        (
            "SELECT bet_id, sport, recommendation_date, commence_time, home_team, "
            "away_team, bet_on, ticker, model_prob, market_prob, edge, "
            "expected_value, kelly_fraction, confidence, yes_ask, no_ask, "
            "created_at FROM dashboard_tennis_predictions_v1 WHERE "
            "recommendation_date = :recommendation_date ORDER BY edge DESC, "
            "expected_value DESC NULLS LAST, created_at DESC NULLS LAST LIMIT 100"
        )
    ]


def test_zero_row_current_tennis_predictions_returns_explicit_empty_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No current-run tennis predictions should render a governed empty state."""
    fake_db = FakeDashboardDB({"dashboard_tennis_predictions_v1": pd.DataFrame()})
    monkeypatch.setattr(data_layer, "_db", fake_db)

    predictions = data_layer.get_tomorrow_tennis_predictions(
        reference_date=datetime(2026, 5, 3).date()
    )

    assert predictions.empty
    assert predictions.attrs["empty_state"] == {
        "kind": "no_tennis_predictions",
        "title": "No actionable tennis predictions",
        "message": "No governed actionable TENNIS predictions are available for the current run date.",
        "action": "Run tennis market ingestion and recommendation loading before placing bets.",
        "severity": "info",
    }


def test_tennis_model_health_reads_governed_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tennis model health comes from the governed tennis health read model."""
    fake_db = FakeDashboardDB(
        {"dashboard_tennis_model_health_v1": _tennis_model_health_frame()}
    )
    monkeypatch.setattr(data_layer, "_db", fake_db)

    health = data_layer.get_tennis_model_health(limit=10)

    assert health.attrs["empty_state"] is None
    assert list(health.columns) == list(data_layer.TENNIS_MODEL_HEALTH_COLUMNS)
    row = health.iloc[0]
    assert bool(row["beats_betmgm"]) is True
    assert row["ensemble_vs_betmgm_log_loss_delta"] == -0.0144
    assert fake_db.queries == [
        (
            "SELECT run_date, model_version, data_source, rows, holdout_rows, "
            "betmgm_holdout_rows, enabled, beats_betmgm, baseline_log_loss, "
            "ensemble_log_loss, ensemble_market_log_loss, betmgm_log_loss, "
            "baseline_brier, ensemble_brier, ensemble_market_brier, betmgm_brier, "
            "baseline_accuracy, ensemble_accuracy, ensemble_market_accuracy, "
            "betmgm_accuracy, baseline_actionable_count, ensemble_actionable_count, "
            "log_loss_delta, brier_delta, accuracy_delta, "
            "ensemble_vs_betmgm_log_loss_delta, ensemble_vs_betmgm_brier_delta, "
            "ensemble_vs_betmgm_accuracy_delta, created_at "
            "FROM dashboard_tennis_model_health_v1 WHERE data_source = "
            ":data_source AND betmgm_holdout_rows > 0 ORDER BY run_date DESC, "
            "created_at DESC, model_version ASC LIMIT 10"
        )
    ]


def test_zero_row_tennis_model_health_returns_explicit_empty_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No tennis health rows should render a governed empty state."""
    fake_db = FakeDashboardDB({"dashboard_tennis_model_health_v1": pd.DataFrame()})
    monkeypatch.setattr(data_layer, "_db", fake_db)

    health = data_layer.get_tennis_model_health(limit=10)

    assert health.empty
    assert health.attrs["empty_state"] == {
        "kind": "no_tennis_model_health",
        "title": "No production tennis model health snapshots",
        "message": "No production PostgreSQL tennis model-vs-BetMGM evaluation rows are available yet.",
        "action": "Ingest tennis BetMGM odds and player-match stats, then run scripts/train_tennis_probability_model.py without --evaluate-only to publish production evidence to PostgreSQL.",
        "severity": "info",
    }


def test_missing_view_failure_raises_sanitized_typed_dashboard_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """View/query failures raise a typed sanitized error instead of empty data."""

    raw_error = ProgrammingError(
        "SELECT * FROM dashboard_portfolio_v1",
        {"password": "secret"},
        Exception("relation dashboard_portfolio_v1 does not exist at host postgres"),
    )
    fake_db = FakeDashboardDB(error=raw_error)
    monkeypatch.setattr(data_layer, "_db", fake_db)

    with pytest.raises(data_layer.DashboardDataError) as exc_info:
        data_layer.get_portfolio_summary()

    error = exc_info.value
    assert error.payload["kind"] == "dashboard_read_model_missing"
    message = str(error)
    assert "dashboard_read_model_missing" in message
    assert "SELECT" not in message
    assert "password" not in message
    assert "secret" not in message
    assert "postgres" not in message
    assert "Traceback" not in message
    _assert_dashboard_error_does_not_leak(
        error,
        (
            "SELECT * FROM dashboard_portfolio_v1",
            "password",
            "secret",
            "host postgres",
            "ProgrammingError",
            "sqlalchemy.exc",
        ),
    )


def test_contract_validation_error_sanitizes_rejected_provider_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Schema failures must not expose rejected SQL/DSN/secret-like values."""

    secret_value = "postgresql://user:secret@host/db SELECT password FROM accounts"
    invalid_row = _portfolio_frame().iloc[0].to_dict()
    invalid_row["balance_dollars"] = secret_value
    invalid_frame = pd.DataFrame([invalid_row], columns=data_layer.PORTFOLIO_COLUMNS)
    fake_db = FakeDashboardDB({"dashboard_portfolio_v1": invalid_frame})
    monkeypatch.setattr(data_layer, "_db", fake_db)

    with pytest.raises(data_layer.DashboardDataError) as exc_info:
        data_layer.get_portfolio_summary()

    error = exc_info.value
    payload_text = repr(error.payload)
    message = str(error)
    combined = f"{payload_text} {message}"
    assert error.payload["kind"] == "dashboard_contract_mismatch"
    assert "dashboard_portfolio_v1" in combined
    assert "balance_dollars" in combined
    assert "type" in combined
    assert "postgresql://" not in combined
    assert "user:secret" not in combined
    assert "password" not in combined
    assert "SELECT" not in combined
    assert "accounts" not in combined
    assert "Traceback" not in combined


def test_contract_validation_error_does_not_leak_exception_chain_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Formatted tracebacks must not expose rejected contract values."""

    secret_value = "postgresql://user:secret@host/db SELECT password FROM accounts"
    invalid_row = _portfolio_frame().iloc[0].to_dict()
    invalid_row["balance_dollars"] = secret_value
    invalid_frame = pd.DataFrame([invalid_row], columns=data_layer.PORTFOLIO_COLUMNS)
    fake_db = FakeDashboardDB({"dashboard_portfolio_v1": invalid_frame})
    monkeypatch.setattr(data_layer, "_db", fake_db)

    with pytest.raises(data_layer.DashboardDataError) as exc_info:
        data_layer.get_portfolio_summary()

    error = exc_info.value
    assert error.payload["kind"] == "dashboard_contract_mismatch"
    _assert_dashboard_error_does_not_leak(
        error,
        (
            "postgresql://",
            "user:secret",
            "SELECT password",
            "accounts",
            "ValidationError",
            "jsonschema",
            "secret@host",
        ),
    )


def test_query_failure_does_not_leak_sqlalchemy_exception_chain_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Formatted tracebacks must not expose SQLAlchemy SQL, params, or internals."""

    raw_error = ProgrammingError(
        "SELECT password FROM accounts WHERE dsn = %(dsn)s",
        {
            "dsn": "postgresql://user:secret@host/db",
            "password": "secret",
        },
        Exception("database failure on host postgres with password secret"),
    )
    fake_db = FakeDashboardDB(error=raw_error)
    monkeypatch.setattr(data_layer, "_db", fake_db)

    with pytest.raises(data_layer.DashboardDataError) as exc_info:
        data_layer.get_portfolio_summary()

    error = exc_info.value
    assert error.payload["kind"] == "dashboard_query_failed"
    _assert_dashboard_error_does_not_leak(
        error,
        (
            "postgresql://",
            "user:secret",
            "SELECT password",
            "accounts",
            "password secret",
            "ProgrammingError",
            "SQLAlchemyError",
            "sqlalchemy.exc",
            "host postgres",
        ),
    )


def test_bet_detail_unknown_id_raises_empty_state_not_query_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown bet IDs are explicit empty states."""

    fake_db = FakeDashboardDB({"dashboard_bet_detail_v1": pd.DataFrame()})
    monkeypatch.setattr(data_layer, "_db", fake_db)

    with pytest.raises(data_layer.DashboardEmptyState) as exc_info:
        data_layer.get_bet_detail("missing-bet")

    assert exc_info.value.payload["kind"] == "bet_not_found"


def test_bet_detail_merges_governed_execution_and_clv_traceability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_db = FakeDashboardDB(
        {
            "dashboard_bet_detail_v1": _bet_detail_frame(),
            "governed_recommendation_execution_link_v1": _governed_execution_link_frame(),
            "governed_clv_evidence_envelope_v1": _governed_clv_evidence_frame(),
        }
    )
    monkeypatch.setattr(data_layer, "_db", fake_db)

    detail = data_layer.get_bet_detail("DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME")

    assert detail["bet"]["sport"] == "NHL"
    assert detail["execution_link"]["linkage_status"] == "linked"
    assert detail["execution_link"]["entry_quote_role"] == "executable"
    assert detail["clv_evidence"]["clv_source_type"] == "market_close"
    assert detail["clv_evidence"]["close_price_role"] == "close"
    assert detail["clv_evidence"]["selected_close_rule"] == (
        "latest_admissible_pregame_quote"
    )


def test_data_quality_zero_rows_is_contract_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The data-quality view must not be empty."""

    fake_db = FakeDashboardDB({"dashboard_data_quality_v1": pd.DataFrame()})
    monkeypatch.setattr(data_layer, "_db", fake_db)

    with pytest.raises(data_layer.DashboardDataError) as exc_info:
        data_layer.get_data_quality_report()

    assert exc_info.value.payload["kind"] == "dashboard_contract_mismatch"


def test_data_quality_report_maps_checks_and_sanitizes_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Data-quality rows expose governed check fields with safe messages."""

    raw_message = "SELECT password FROM accounts postgresql://user:secret@host/db"
    fake_db = FakeDashboardDB(
        {"dashboard_data_quality_v1": _data_quality_frame(message=raw_message)}
    )
    monkeypatch.setattr(data_layer, "_db", fake_db)

    report = data_layer.get_data_quality_report()

    assert report["overall_health"] == 60
    assert report["empty_state"] is None
    assert report["checks"] == [
        {
            "check_name": "freshness_game_odds",
            "relation_name": "game_odds",
            "relation_type": "table",
            "status": "warn",
            "row_count": 7,
            "freshness_timestamp": "2026-05-03T13:55:00+00:00",
            "max_allowed_lag_minutes": 60,
            "actual_lag_minutes": 75,
            "message": "Details are hidden; check dashboard data-layer logs.",
            "checked_at_utc": "2026-05-03T15:10:00+00:00",
        }
    ]
    rendered = repr(report)
    assert "SELECT" not in rendered
    assert "password" not in rendered
    assert "postgresql://" not in rendered


def test_calibration_data_maps_governed_bucket_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calibration buckets expose the governed dashboard_calibration_v1 fields."""

    fake_db = FakeDashboardDB({"dashboard_calibration_v1": _calibration_frame()})
    monkeypatch.setattr(data_layer, "_db", fake_db)

    data = data_layer.get_calibration_data()

    assert data["empty_state"] is None
    assert data["settled_empty_state"] is None
    assert data["buckets"] == [
        {
            "label": "50%-60%",
            "bucket_start": 0.5,
            "bucket_end": 0.6,
            "predicted_min": 0.5,
            "predicted_max": 0.6,
            "count": 10,
            "prediction_count": 10,
            "avg_elo_prob": 0.55,
            "avg_market_prob": 0.51,
            "observed_win_rate": 0.625,
            "actual_win_rate": 0.625,
            "avg_edge": 0.04,
            "avg_expected_value": 0.02,
            "settled_count": 8,
            "unsettled_count": 2,
            "empty_state": None,
        }
    ]
    assert fake_db.queries == [
        (
            "SELECT bucket_start, bucket_end, prediction_count, avg_elo_prob, "
            "avg_market_prob, observed_win_rate, avg_edge, avg_expected_value, "
            "settled_count, unsettled_count FROM dashboard_calibration_v1 "
            "ORDER BY bucket_start ASC"
        )
    ]


def test_calibration_data_distinguishes_predictions_without_settled_outcomes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calibration predictions without outcomes use no_settled_calibration_outcomes."""

    fake_db = FakeDashboardDB(
        {"dashboard_calibration_v1": _calibration_frame(settled_count=0)}
    )
    monkeypatch.setattr(data_layer, "_db", fake_db)

    data = data_layer.get_calibration_data()

    assert data["empty_state"] is None
    assert data["buckets"][0]["observed_win_rate"] is None
    assert data["buckets"][0]["empty_state"] == "no_settled_calibration_outcomes"
    assert data["settled_empty_state"]["kind"] == "no_settled_calibration_outcomes"


def test_sport_validation_states_read_shared_governed_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_db = FakeDashboardDB({"sport_validation_state_v1": _sport_validation_frame()})
    monkeypatch.setattr(data_layer, "_db", fake_db)

    states = data_layer.get_sport_validation_states()

    assert list(states.columns) == list(data_layer.SPORT_VALIDATION_COLUMNS)
    row = states.iloc[0]
    assert row["sport"] == "NHL"
    assert row["evidence_state"] == "blocked"
    assert bool(row["descriptive_only_flag"]) is True
    assert fake_db.queries == [
        (
            "SELECT sport, market_type, cohort_type, evidence_dimension, "
            "canonical_game_id, market_ticker, selection_key, source_relation, "
            "source_record_id, evidence_state_scope, evidence_state, "
            "evidence_state_reason, evidence_state_as_of, "
            "evidence_state_source_artifact, governance_status, "
            "descriptive_only_flag, contamination_flag, contamination_reason, "
            "excluded_from_approval_flag, observed_at, loaded_at, "
            "last_updated_at, review_timestamp, runtime_consumer, artifact_id, "
            "artifact_version, artifact_family, artifact_available_flag, "
            "placed_bet_only_flag, synthetic_identity_flag, backfill_flag "
            "FROM sport_validation_state_v1 ORDER BY sport ASC"
        )
    ]


def test_sport_validation_state_reads_selected_sport_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_db = FakeDashboardDB({"sport_validation_state_v1": _sport_validation_frame()})
    monkeypatch.setattr(data_layer, "_db", fake_db)

    state = data_layer.get_sport_validation_state("NHL")

    assert state is not None
    assert state["sport"] == "NHL"
    assert state["evidence_state"] == "blocked"
    assert fake_db.queries == [
        (
            "SELECT sport, market_type, cohort_type, evidence_dimension, "
            "canonical_game_id, market_ticker, selection_key, source_relation, "
            "source_record_id, evidence_state_scope, evidence_state, "
            "evidence_state_reason, evidence_state_as_of, "
            "evidence_state_source_artifact, governance_status, "
            "descriptive_only_flag, contamination_flag, contamination_reason, "
            "excluded_from_approval_flag, observed_at, loaded_at, "
            "last_updated_at, review_timestamp, runtime_consumer, artifact_id, "
            "artifact_version, artifact_family, artifact_available_flag, "
            "placed_bet_only_flag, synthetic_identity_flag, backfill_flag "
            "FROM sport_validation_state_v1 WHERE sport = :sport ORDER BY sport ASC "
            "LIMIT 1"
        )
    ]


def test_calibration_data_includes_selected_sport_validation_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_db = FakeDashboardDB(
        {
            "dashboard_calibration_v1": _calibration_frame(),
            "sport_validation_state_v1": _sport_validation_frame(),
        }
    )
    monkeypatch.setattr(data_layer, "_db", fake_db)

    data = data_layer.get_calibration_data("NHL")

    assert data["sport_validation_state"] is not None
    assert data["sport_validation_state"]["sport"] == "NHL"


def test_governed_evidence_records_use_shared_approval_filter_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_db = FakeDashboardDB(
        {"governed_evidence_record_v1": _governed_evidence_frame()}
    )
    monkeypatch.setattr(data_layer, "_db", fake_db)

    records = data_layer.get_governed_evidence_records(approval_only=True)

    assert list(records.columns) == list(data_layer.GOVERNED_EVIDENCE_COLUMNS)
    assert records.iloc[0]["quote_lineage_status"] == "linked_market_quote"
    assert fake_db.queries == [
        (
            "SELECT sport, market_type, cohort_type, evidence_dimension, "
            "canonical_game_id, market_ticker, selection_key, source_relation, "
            "source_record_id, evidence_state_scope, evidence_state, "
            "evidence_state_reason, evidence_state_as_of, "
            "evidence_state_source_artifact, governance_status, "
            "descriptive_only_flag, contamination_flag, contamination_reason, "
            "excluded_from_approval_flag, observed_at, loaded_at, "
            "last_updated_at, recommendation_id, recommendation_created_at, "
            "recommendation_source_surface, probability_source, "
            "calibrated_probability, market_probability, edge, expected_value, "
            "kelly_fraction, confidence_label, quote_source_system, "
            "quote_bookmaker, quote_observed_at, quote_loaded_at, "
            "quote_payload_ref, quote_lineage_status, quote_price_cents, "
            "quote_price_role, quote_freshness_result, quote_fallback_status "
            "FROM governed_evidence_record_v1 WHERE descriptive_only_flag = "
            "FALSE AND excluded_from_approval_flag = FALSE ORDER BY "
            "observed_at DESC, recommendation_id ASC LIMIT 100"
        )
    ]


def test_governed_execution_links_surface_linkage_without_bet_id_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_db = FakeDashboardDB(
        {"governed_recommendation_execution_link_v1": _governed_execution_link_frame()}
    )
    monkeypatch.setattr(data_layer, "_db", fake_db)

    rows = data_layer.get_governed_recommendation_execution_links()

    assert list(rows.columns) == list(
        data_layer.GOVERNED_RECOMMENDATION_EXECUTION_LINK_COLUMNS
    )
    row = rows.iloc[0]
    assert row["placed_bet_id"] == "DASHBOARD-SEED-NHL-ORDER-20260503-NYR-BOS-HOME"
    assert row["recommendation_id"] == "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME"
    assert row["linkage_status"] == "linked"
    assert row["placed_bet_id"] != row["recommendation_id"]
    assert row["entry_price_cents"] == 54
    assert row["entry_quote_freshness_result"] == "fresh"
    assert row["entry_quote_fallback_status"] == "direct_market_quote"


def test_governed_clv_evidence_envelopes_surface_close_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_db = FakeDashboardDB(
        {"governed_clv_evidence_envelope_v1": _governed_clv_evidence_frame()}
    )
    monkeypatch.setattr(data_layer, "_db", fake_db)

    rows = data_layer.get_governed_clv_evidence_envelopes()

    assert list(rows.columns) == list(data_layer.GOVERNED_CLV_EVIDENCE_COLUMNS)
    row = rows.iloc[0]
    assert row["clv_source_type"] == "market_close"
    assert row["closing_quote_source"] == "dashboard_seed"
    assert row["close_price_role"] == "close"
    assert row["selected_close_rule"] == "latest_admissible_pregame_quote"


def test_governed_portfolio_risk_surfaces_resting_and_executed_exposure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_db = FakeDashboardDB(
        {"governed_portfolio_risk_state_v1": _governed_portfolio_risk_frame()}
    )
    monkeypatch.setattr(data_layer, "_db", fake_db)

    risk = data_layer.get_governed_portfolio_risk_state()

    assert list(risk.columns) == list(data_layer.GOVERNED_PORTFOLIO_RISK_COLUMNS)
    row = risk.iloc[0]
    assert row["resting_order_exposure_amount"] == 10.0
    assert row["executed_unsettled_exposure_amount"] == 12.0
    assert row["open_exposure_amount"] == 22.0
    assert row["exposure_state"] == "mixed_open_exposure"
    assert row["remaining_daily_risk_budget_dollars"] == 346.94
    assert row["drawdown_state"] == "drawdown_active"
    assert row["portfolio_guardrail_state"] == "eligible"
    assert pd.isna(row["portfolio_guardrail_reason_code"])
    assert row["existing_position_state"] == "mixed_open_exposure"
    assert row["rejection_reason_code"] == "missing_evidence"


def test_page_facing_data_layer_has_no_source_table_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dashboard data layer must only read governed dashboard_*_v1 views."""

    query_targets = set()
    for view_name in data_layer.VIEW_COLUMNS:
        fake_db = FakeDashboardDB({view_name: pd.DataFrame()})
        monkeypatch.setattr(data_layer, "_db", fake_db)
        try:
            data_layer._fetch_read_model(view_name)
        except data_layer.DashboardDataError:
            pass
        for query in fake_db.queries:
            query_targets.update(
                re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)", query)
            )

    assert query_targets == set(data_layer.VIEW_COLUMNS)
