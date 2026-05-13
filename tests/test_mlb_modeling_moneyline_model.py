"""Tests for calibrated MLB moneyline model helpers."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import joblib
import pytest

from tests.contracts.helpers import validate_contract_payload

from plugins.mlb_modeling.models import (
    BinaryCalibrationMetrics,
    CalibratedMoneylineModel,
    MoneylineTrainingRow,
    artifact_passes_gate,
    evaluate_binary_predictions,
    load_moneyline_model_artifact,
    save_moneyline_model_artifact,
    train_logistic_moneyline_model,
)


SCHEMAS_ROOT = Path(__file__).resolve().parent / "contracts" / "schemas"


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_ROOT / filename).read_text(encoding="utf-8"))


def _training_rows() -> list[MoneylineTrainingRow]:
    return [
        MoneylineTrainingRow(date(2026, 4, 1), {"elo": 0.55, "woba": 0.01}, 1),
        MoneylineTrainingRow(date(2026, 4, 2), {"elo": 0.45, "woba": -0.02}, 0),
        MoneylineTrainingRow(date(2026, 4, 3), {"elo": 0.62, "woba": 0.03}, 1),
        MoneylineTrainingRow(date(2026, 4, 4), {"elo": 0.40, "woba": -0.04}, 0),
    ]


def test_evaluate_binary_predictions_computes_expected_metrics() -> None:
    metrics = evaluate_binary_predictions([1, 0, 1, 0], [0.8, 0.2, 0.7, 0.3])

    assert metrics.sample_count == 4
    assert metrics.accuracy == 1.0
    assert metrics.brier_score < 0.1
    assert metrics.expected_calibration_error >= 0.0


def test_artifact_gate_requires_baseline_improvement_and_ece_target() -> None:
    baseline = BinaryCalibrationMetrics(
        accuracy=0.57,
        brier_score=0.24,
        log_loss=0.68,
        expected_calibration_error=0.04,
        sample_count=1000,
    )
    candidate = BinaryCalibrationMetrics(
        accuracy=0.59,
        brier_score=0.22,
        log_loss=0.64,
        expected_calibration_error=0.03,
        sample_count=1000,
    )

    assert artifact_passes_gate(candidate, baseline) is True


def test_train_logistic_moneyline_model_produces_enabled_artifact() -> None:
    artifact = train_logistic_moneyline_model(
        _training_rows(),
        model_version="mlb_moneyline_public_test_v1",
    )

    assert artifact.enabled is True
    assert artifact.feature_names == ["elo", "woba"]
    assert 0.0 <= artifact.predict_proba({"elo": 0.58, "woba": 0.02}) <= 1.0


def test_calibrated_moneyline_prediction_payload_matches_contract() -> None:
    artifact = train_logistic_moneyline_model(
        _training_rows(),
        model_version="mlb_moneyline_public_test_v1",
    )
    model = CalibratedMoneylineModel(artifact)

    payload = model.prediction_payload(
        game_id="745431",
        outcome_name="home",
        run_date=date(2026, 5, 10),
        features={"elo": 0.58, "woba": 0.02},
        feature_hash="abc123def4567890",
        market_prob=0.54,
    )

    validate_contract_payload(payload, _load_schema("mlb_model_prediction_v1.json"))
    assert payload["edge"] == payload["model_prob"] - payload["market_prob"]


def test_save_and_load_moneyline_artifact_round_trips_runtime_contract(tmp_path) -> None:
    artifact = train_logistic_moneyline_model(
        _training_rows(),
        model_version="mlb_moneyline_public_test_v1",
    )
    model_path = tmp_path / "mlb_moneyline_public_test_v1.joblib"

    save_moneyline_model_artifact(artifact, model_path=model_path)
    loaded = load_moneyline_model_artifact(model_path)

    assert loaded.model_version == artifact.model_version
    assert loaded.feature_names == artifact.feature_names
    assert 0.0 <= loaded.predict_proba({"elo": 0.58, "woba": 0.02}) <= 1.0


def test_load_moneyline_artifact_rejects_runtime_feature_drift(tmp_path) -> None:
    artifact = train_logistic_moneyline_model(
        _training_rows(),
        model_version="mlb_moneyline_public_test_v1",
    )
    model_path = tmp_path / "mlb_moneyline_public_test_v1.joblib"

    save_moneyline_model_artifact(artifact, model_path=model_path)
    payload = joblib.load(model_path)
    payload["feature_names"] = ["elo", "missing_feature"]
    joblib.dump(payload, model_path)

    with pytest.raises(ValueError, match="feature names"):
        load_moneyline_model_artifact(model_path)
