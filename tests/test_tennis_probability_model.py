"""Tests for the tennis probability model service."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from plugins.elo.tennis_probability_model import (
    build_benchmark_history,
    build_training_frame,
    predict_with_artifact,
    save_artifact,
    save_metrics_to_db,
    should_publish_metrics_to_db,
    train_production_model,
    train_and_evaluate,
)


def test_build_training_frame_is_chronological_and_oriented() -> None:
    """Training frame should use historical rows only and mirror each result."""
    history = build_benchmark_history(match_count=60)

    frame = build_training_frame(history)

    assert not frame.empty
    assert set(frame["target"].unique()) == {0.0, 1.0}
    assert frame["date"].is_monotonic_increasing
    assert "intransitivity_complexity" in frame.columns
    assert "calibrated_elo_prob_a" in frame.columns


def test_train_and_evaluate_improves_benchmark_metrics() -> None:
    """Feature ensemble should improve the deterministic benchmark holdout."""
    model, metrics, frame = train_and_evaluate(
        build_benchmark_history(match_count=220),
        data_source="benchmark_fixture",
    )

    assert model is not None
    assert len(frame) == metrics.rows
    assert metrics.enabled is True
    assert metrics.ensemble_log_loss < metrics.baseline_log_loss
    assert metrics.ensemble_brier < metrics.baseline_brier
    assert metrics.ensemble_accuracy >= metrics.baseline_accuracy
    assert metrics.betmgm_holdout_rows > 0
    assert metrics.beats_betmgm is True
    assert metrics.ensemble_market_log_loss < metrics.betmgm_log_loss
    assert metrics.ensemble_market_brier < metrics.betmgm_brier


def test_predict_with_artifact_falls_back_when_artifact_missing(tmp_path) -> None:
    """Missing model artifact must never block tennis probability generation."""
    result = predict_with_artifact(
        player_a="Alpha A.",
        player_b="Bravo B.",
        tour="ATP",
        surface="Hard",
        as_of_date="2026-01-01",
        history=pd.DataFrame(),
        calibrated_elo_prob_a=0.61,
        model_path=tmp_path / "missing.joblib",
    )

    assert result.source == "calibrated_elo_fallback"
    assert result.prob_a == 0.61


def test_predict_with_artifact_uses_enabled_model(tmp_path) -> None:
    """Enabled artifacts should return ensemble probabilities with provenance."""
    model, metrics, _ = train_and_evaluate(
        build_benchmark_history(match_count=220),
        data_source="benchmark_fixture",
    )
    model_path = tmp_path / "tennis_model.joblib"
    save_artifact(model, metrics, model_path=model_path)

    result = predict_with_artifact(
        player_a="Alpha A.",
        player_b="Foxtrot F.",
        tour="ATP",
        surface="Hard",
        as_of_date="2025-09-01",
        history=build_benchmark_history(match_count=220),
        calibrated_elo_prob_a=0.62,
        model_path=model_path,
    )

    assert result.source == "ensemble"
    assert result.model_version == "tennis_probability_model_v2"
    assert result.feature_model_prob_a is not None
    assert 0.01 <= result.prob_a <= 0.99


def test_benchmark_metrics_are_not_publishable() -> None:
    """Synthetic benchmark evidence must never be surfaced as dashboard health."""
    _, metrics, _ = train_and_evaluate(
        build_benchmark_history(match_count=220),
        data_source="benchmark_fixture",
    )

    assert should_publish_metrics_to_db(metrics) is False
    assert save_metrics_to_db(metrics) is False


def test_train_production_model_requires_postgres_history(tmp_path) -> None:
    """Production retraining should fail closed when PostgreSQL history is empty."""
    with pytest.raises(ValueError, match="No PostgreSQL tennis history available"):
        train_production_model(
            history=pd.DataFrame(),
            model_path=tmp_path / "tennis_model.joblib",
            metrics_path=tmp_path / "tennis_metrics.json",
        )


def test_train_production_model_persists_artifact_without_db_publish(tmp_path) -> None:
    """Production retraining should write the runtime artifact and metrics JSON."""
    result = train_production_model(
        history=build_benchmark_history(match_count=220),
        model_path=tmp_path / "tennis_model.joblib",
        metrics_path=tmp_path / "tennis_metrics.json",
        publish_metrics=False,
    )

    assert result.data_source == "postgres_tennis_games"
    assert result.feature_frame_rows == result.rows
    assert Path(result.model_path).exists()
    assert Path(result.metrics_path).exists()
    assert result.metrics_published is False
