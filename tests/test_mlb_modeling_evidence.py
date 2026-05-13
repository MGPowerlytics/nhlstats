"""Tests for MLB model-improvement evidence utilities."""

from __future__ import annotations

import pandas as pd
import pytest

from plugins.mlb_modeling.evidence import (
    EloBacktestConfig,
    audit_clv_snapshot_fidelity,
    build_betting_evidence_frame,
    build_value_recommendations,
    compare_model_metrics,
    evaluate_prediction_records,
    expected_calibration_error,
    prepare_mlb_games,
    run_elo_backtest,
    summarize_betting_evidence_by_edge_bucket,
)


def _sample_games() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "game_id": "spring",
                "game_date": "2026-03-01",
                "home_team": "A",
                "away_team": "B",
                "home_score": 1,
                "away_score": 2,
            },
            {
                "game_id": "regular-1",
                "game_date": "2026-04-01",
                "home_team": "A",
                "away_team": "B",
                "home_score": 5,
                "away_score": 2,
            },
            {
                "game_id": "regular-2",
                "game_date": "2026-04-02",
                "home_team": "B",
                "away_team": "A",
                "home_score": 4,
                "away_score": 7,
            },
        ]
    )


def test_prepare_mlb_games_requires_core_columns() -> None:
    """Backtests must fail loudly on malformed evidence inputs."""
    with pytest.raises(ValueError, match="missing required MLB game columns"):
        prepare_mlb_games(pd.DataFrame({"game_id": ["x"]}))


def test_run_elo_backtest_filters_spring_training_before_prediction() -> None:
    """Spring-training filtering is part of the production evidence config."""
    records = run_elo_backtest(
        _sample_games(),
        EloBacktestConfig(
            model_name="test",
            k_factor=4.0,
            home_advantage=20.0,
            use_mov=False,
            skip_spring_training=True,
        ),
    )

    assert list(records["game_id"]) == ["regular-1", "regular-2"]
    assert records["home_prob"].between(0.0, 1.0).all()


def test_expected_calibration_error_rejects_mismatched_inputs() -> None:
    """ECE requires aligned labels and probabilities."""
    with pytest.raises(ValueError, match="equal length"):
        expected_calibration_error([1, 0], [0.7])


def test_compare_model_metrics_passes_only_probability_improvements() -> None:
    """Promotion gate requires lower log loss, Brier, and ECE."""
    baseline_records = pd.DataFrame(
        {
            "model_name": ["baseline"] * 4,
            "home_prob": [0.55, 0.55, 0.45, 0.45],
            "home_won": [1, 1, 0, 0],
            "favorite_prob": [0.55, 0.55, 0.55, 0.55],
            "favorite_won": [1, 1, 1, 1],
        }
    )
    candidate_records = baseline_records.copy()
    candidate_records["model_name"] = "candidate"
    candidate_records["home_prob"] = [0.70, 0.70, 0.30, 0.30]
    candidate_records["favorite_prob"] = [0.70, 0.70, 0.70, 0.70]

    delta = compare_model_metrics(
        evaluate_prediction_records(baseline_records),
        evaluate_prediction_records(candidate_records),
    )

    assert delta.accuracy_delta == 0
    assert delta.log_loss_delta < 0
    assert delta.brier_score_delta < 0
    assert delta.ece_delta <= 0
    assert delta.passes_probability_gate is True


def test_build_value_recommendations_uses_opening_market_edge() -> None:
    """Value recommendations should choose the side with qualifying opening edge."""
    predictions = pd.DataFrame(
        [
            {
                "model_name": "candidate",
                "game_id": "MLB_20230704_LOSANGELESDODGERS_SAN DIEGOPADRES".replace(
                    " ", ""
                ),
                "game_date": "2023-07-04",
                "home_team": "Los Angeles Dodgers",
                "away_team": "San Diego Padres",
                "home_prob": 0.62,
                "home_won": 1,
                "favorite_prob": 0.62,
                "favorite_won": 1,
            }
        ]
    )
    odds = pd.DataFrame(
        [
            {
                "game_id": "MLB_20230704_LOSANGELESDODGERS_SANDIEGOPADRES",
                "commence_time": "2023-07-04T23:10:00Z",
                "source_snapshot_at": "2023-07-04T00:00:00Z",
                "snapshot_type": "open",
                "outcome_role": "home",
                "implied_probability": 0.54,
            },
            {
                "game_id": "MLB_20230704_LOSANGELESDODGERS_SANDIEGOPADRES",
                "commence_time": "2023-07-04T23:10:00Z",
                "source_snapshot_at": "2023-07-04T00:00:00Z",
                "snapshot_type": "open",
                "outcome_role": "away",
                "implied_probability": 0.49,
            },
        ]
    )

    recommendations = build_value_recommendations(predictions, odds)

    assert len(recommendations) == 1
    recommendation = recommendations.iloc[0]
    assert recommendation["bet_on"] == "Los Angeles Dodgers"
    assert recommendation["confidence"] == "MEDIUM"
    assert recommendation["edge"] == pytest.approx(0.08)


def test_build_betting_evidence_frame_prefers_explicit_close_snapshots() -> None:
    """Evidence rows should use explicit open/close snapshots when available."""
    recommendations = pd.DataFrame(
        [
            {
                "game_id": "MLB_20230704_LOSANGELESDODGERS_SANDIEGOPADRES",
                "game_date": "2023-07-04",
                "bet_on": "Los Angeles Dodgers",
                "confidence": "MEDIUM",
                "edge": 0.08,
                "model_prob": 0.62,
                "market_prob": 0.54,
            }
        ]
    )
    odds = pd.DataFrame(
        [
            {
                "game_id": "MLB_20230704_LOSANGELESDODGERS_SANDIEGOPADRES",
                "bookmaker_key": "draftkings",
                "commence_time": "2023-07-04T23:10:00Z",
                "source_snapshot_at": "2023-07-04T00:00:00Z",
                "snapshot_type": "open",
                "outcome_role": "home",
                "decimal_price": 1.90,
                "implied_probability": 0.52631579,
            },
            {
                "game_id": "MLB_20230704_LOSANGELESDODGERS_SANDIEGOPADRES",
                "bookmaker_key": "draftkings",
                "commence_time": "2023-07-04T23:10:00Z",
                "source_snapshot_at": "2023-07-04T23:09:00Z",
                "snapshot_type": "close",
                "outcome_role": "home",
                "decimal_price": 1.75,
                "implied_probability": 0.57142857,
            },
        ]
    )
    games = pd.DataFrame(
        [
            {
                "game_id": "MLB_20230704_LOSANGELESDODGERS_SANDIEGOPADRES",
                "home_team": "Los Angeles Dodgers",
                "away_team": "San Diego Padres",
                "home_score": 5,
                "away_score": 3,
            }
        ]
    )

    evidence = build_betting_evidence_frame(
        recommendations=recommendations,
        odds_snapshots=odds,
        games=games,
    )

    assert len(evidence) == 1
    row = evidence.iloc[0]
    assert row["entry_snapshot_type"] == "open"
    assert row["close_snapshot_type"] == "close"
    assert bool(row["clv_hit"]) is True
    assert row["pnl"] == pytest.approx(0.90)


def test_summarize_betting_evidence_by_edge_bucket_groups_expected_ranges() -> None:
    """Edge-bucket summary should group ROI and CLV by configured ranges."""
    evidence = pd.DataFrame(
        [
            {"edge": 0.04, "pnl": 0.10, "clv_hit": True, "won": True},
            {"edge": 0.07, "pnl": -1.00, "clv_hit": False, "won": False},
            {"edge": 0.10, "pnl": 0.20, "clv_hit": True, "won": True},
            {"edge": 0.20, "pnl": 0.50, "clv_hit": True, "won": True},
        ]
    )

    summary = summarize_betting_evidence_by_edge_bucket(evidence)

    assert list(summary["edge_bucket"]) == ["3-5%", "5-8%", "8-15%", "15%+"]
    assert list(summary["bet_count"]) == [1, 1, 1, 1]
    assert list(summary["flat_roi"]) == [0.10, -1.00, 0.20, 0.50]


def test_audit_clv_snapshot_fidelity_reports_explicit_close_rates() -> None:
    """CLV audit should surface explicit close usage versus proxy closes."""
    evidence = pd.DataFrame(
        [
            {
                "bookmaker_key": "draftkings",
                "entry_snapshot_type": "open",
                "close_snapshot_type": "close",
                "snapshot_count": 2,
                "clv_hit": True,
                "clv_decimal_delta": 0.10,
            },
            {
                "bookmaker_key": "draftkings",
                "entry_snapshot_type": "open",
                "close_snapshot_type": "intraday",
                "snapshot_count": 3,
                "clv_hit": False,
                "clv_decimal_delta": -0.05,
            },
        ]
    )

    audit = audit_clv_snapshot_fidelity(evidence)

    assert len(audit) == 1
    row = audit.iloc[0]
    assert row["bookmaker_key"] == "draftkings"
    assert row["explicit_open_rate"] == pytest.approx(1.0)
    assert row["explicit_close_rate"] == pytest.approx(0.5)
    assert row["proxy_close_rate"] == pytest.approx(0.5)
    assert row["avg_snapshots_per_bet"] == pytest.approx(2.5)
