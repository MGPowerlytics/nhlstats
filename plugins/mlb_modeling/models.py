"""Calibrated MLB moneyline model helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

import joblib

import numpy as np
from sklearn.linear_model import LogisticRegression

from plugins.mlb_modeling.features import stable_feature_hash


EPSILON = 1e-12
DEFAULT_MONEYLINE_MODEL_PATH = Path("data/models/mlb_moneyline_model_v1.joblib")
_RUNTIME_VALID_FEATURE_STATUSES = {"available", "derived"}


@dataclass(frozen=True)
class BinaryCalibrationMetrics:
    """Binary classifier performance metrics used for model gates."""

    accuracy: float
    brier_score: float
    log_loss: float
    expected_calibration_error: float
    sample_count: int


@dataclass(frozen=True)
class MoneylineTrainingRow:
    """Leakage-safe training row for the MLB moneyline model."""

    game_date: date
    features: Dict[str, float]
    label_home_win: int


@dataclass
class MoneylineModelArtifact:
    """Trained moneyline model plus metadata needed for reproducible scoring."""

    model_version: str
    feature_names: list[str]
    model: Any
    calibration_method: str
    metrics: BinaryCalibrationMetrics
    enabled: bool = False

    def predict_proba(self, features: Mapping[str, float]) -> float:
        """Return calibrated P(home win) for a feature mapping."""
        x = np.array(
            [[float(features[name]) for name in self.feature_names]], dtype=float
        )
        return float(self.model.predict_proba(x)[0, 1])


def save_moneyline_model_artifact(
    artifact: MoneylineModelArtifact,
    *,
    model_path: Path = DEFAULT_MONEYLINE_MODEL_PATH,
) -> None:
    """Persist a moneyline artifact for reproducible runtime scoring."""
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model_version": artifact.model_version,
            "feature_names": list(artifact.feature_names),
            "feature_names_hash": stable_feature_hash(
                {"feature_names": list(artifact.feature_names)}
            ),
            "model": artifact.model,
            "calibration_method": artifact.calibration_method,
            "metrics": {
                "accuracy": artifact.metrics.accuracy,
                "brier_score": artifact.metrics.brier_score,
                "log_loss": artifact.metrics.log_loss,
                "expected_calibration_error": (
                    artifact.metrics.expected_calibration_error
                ),
                "sample_count": artifact.metrics.sample_count,
            },
            "enabled": bool(artifact.enabled),
        },
        model_path,
    )


def load_moneyline_model_artifact(
    model_path: Path = DEFAULT_MONEYLINE_MODEL_PATH,
) -> MoneylineModelArtifact:
    """Load and validate a persisted moneyline artifact."""
    if not model_path.exists():
        raise FileNotFoundError(model_path)
    payload = joblib.load(model_path)
    if not isinstance(payload, dict):
        raise ValueError("Moneyline model artifact payload must be a mapping")

    required_keys = {
        "model_version",
        "feature_names",
        "feature_names_hash",
        "model",
        "calibration_method",
        "metrics",
        "enabled",
    }
    missing = sorted(required_keys.difference(payload.keys()))
    if missing:
        raise ValueError(f"Moneyline model artifact missing keys: {', '.join(missing)}")

    feature_names = payload["feature_names"]
    if (
        not isinstance(feature_names, list)
        or not feature_names
        or any(not isinstance(name, str) or not name for name in feature_names)
        or len(set(feature_names)) != len(feature_names)
    ):
        raise ValueError("Moneyline model artifact feature names are invalid")

    expected_hash = stable_feature_hash({"feature_names": feature_names})
    if payload["feature_names_hash"] != expected_hash:
        raise ValueError("Moneyline model artifact feature names do not match runtime")

    model = payload["model"]
    if not hasattr(model, "predict_proba"):
        raise ValueError("Moneyline model artifact model must expose predict_proba")

    metrics_payload = payload["metrics"]
    if not isinstance(metrics_payload, Mapping):
        raise ValueError("Moneyline model artifact metrics must be a mapping")

    metrics = BinaryCalibrationMetrics(
        accuracy=float(metrics_payload["accuracy"]),
        brier_score=float(metrics_payload["brier_score"]),
        log_loss=float(metrics_payload["log_loss"]),
        expected_calibration_error=float(
            metrics_payload["expected_calibration_error"]
        ),
        sample_count=int(metrics_payload["sample_count"]),
    )
    return MoneylineModelArtifact(
        model_version=str(payload["model_version"]),
        feature_names=list(feature_names),
        model=model,
        calibration_method=str(payload["calibration_method"]),
        metrics=metrics,
        enabled=bool(payload["enabled"]),
    )


def validate_runtime_feature_inputs(
    *,
    feature_vector: Mapping[str, Any],
    feature_availability: Optional[Mapping[str, Any]],
    abstention_reasons: Sequence[Any],
    expected_feature_names: Sequence[str],
) -> Dict[str, float]:
    """Return validated runtime features or raise on missing/invalid inputs."""
    if abstention_reasons:
        raise ValueError(
            "Runtime feature row is abstaining: "
            + ", ".join(str(reason) for reason in abstention_reasons)
        )

    flattened = _flatten_feature_mapping(feature_vector)
    availability = dict(feature_availability or {})
    validated: Dict[str, float] = {}
    missing: list[str] = []
    invalid: list[str] = []
    unavailable: list[str] = []

    for feature_name in expected_feature_names:
        if feature_name not in flattened:
            missing.append(feature_name)
            continue
        status = availability.get(feature_name)
        if status is not None and str(status).lower() not in _RUNTIME_VALID_FEATURE_STATUSES:
            unavailable.append(feature_name)
            continue
        try:
            value = float(flattened[feature_name])
        except (TypeError, ValueError):
            invalid.append(feature_name)
            continue
        if not np.isfinite(value):
            invalid.append(feature_name)
            continue
        validated[feature_name] = value

    if missing:
        raise ValueError(f"Missing required runtime features: {', '.join(missing)}")
    if unavailable:
        raise ValueError(
            "Required runtime features unavailable: " + ", ".join(unavailable)
        )
    if invalid:
        raise ValueError(f"Invalid runtime feature values: {', '.join(invalid)}")
    return validated


def _flatten_feature_mapping(
    payload: Mapping[str, Any],
    *,
    prefix: str = "",
) -> Dict[str, Any]:
    flattened: Dict[str, Any] = {}
    for key, value in payload.items():
        if key in {"schema_version", "sport", "payload_kind"}:
            continue
        qualified_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            flattened.update(_flatten_feature_mapping(value, prefix=qualified_key))
        else:
            flattened[qualified_key] = value
            if prefix == "":
                flattened[str(key)] = value
    return flattened


def evaluate_binary_predictions(
    y_true: Sequence[int],
    y_prob: Sequence[float],
    n_bins: int = 10,
) -> BinaryCalibrationMetrics:
    """Compute accuracy, Brier score, log loss, and ECE."""
    labels = np.array(y_true, dtype=int)
    probs = np.clip(np.array(y_prob, dtype=float), EPSILON, 1.0 - EPSILON)
    if labels.size == 0 or labels.size != probs.size:
        raise ValueError("y_true and y_prob must be non-empty and equal length")

    predictions = (probs >= 0.5).astype(int)
    accuracy = float(np.mean(predictions == labels))
    brier = float(np.mean((probs - labels) ** 2))
    log_loss = float(
        -np.mean(labels * np.log(probs) + (1 - labels) * np.log(1 - probs))
    )
    ece = _expected_calibration_error(labels, probs, n_bins=n_bins)
    return BinaryCalibrationMetrics(
        accuracy=accuracy,
        brier_score=brier,
        log_loss=log_loss,
        expected_calibration_error=ece,
        sample_count=int(labels.size),
    )


def _expected_calibration_error(
    labels: np.ndarray,
    probs: np.ndarray,
    n_bins: int,
) -> float:
    bin_count = max(1, int(n_bins))
    edges = np.linspace(0.0, 1.0, bin_count + 1)
    ece = 0.0
    for idx in range(bin_count):
        left, right = edges[idx], edges[idx + 1]
        if idx == bin_count - 1:
            mask = (probs >= left) & (probs <= right)
        else:
            mask = (probs >= left) & (probs < right)
        if not np.any(mask):
            continue
        confidence = float(np.mean(probs[mask]))
        observed = float(np.mean(labels[mask]))
        ece += float(np.mean(mask)) * abs(confidence - observed)
    return ece


def artifact_passes_gate(
    candidate: BinaryCalibrationMetrics,
    baseline: BinaryCalibrationMetrics,
    max_ece: float = 0.031,
) -> bool:
    """Return True when a candidate beats baseline and calibration target."""
    return (
        candidate.log_loss < baseline.log_loss
        and candidate.brier_score <= baseline.brier_score
        and candidate.expected_calibration_error <= max_ece
    )


def train_logistic_moneyline_model(
    rows: Iterable[MoneylineTrainingRow],
    model_version: str,
    baseline_metrics: Optional[BinaryCalibrationMetrics] = None,
) -> MoneylineModelArtifact:
    """Train a transparent logistic MLB moneyline model.

    Rows are sorted chronologically before training to keep the artifact
    reproducible. Caller-owned train/validation splitting should ensure rows do
    not contain future information relative to the scoring date.
    """
    ordered_rows = sorted(rows, key=lambda row: row.game_date)
    if not ordered_rows:
        raise ValueError("training rows must be non-empty")

    feature_names = sorted(ordered_rows[0].features.keys())
    x = np.array(
        [[float(row.features[name]) for name in feature_names] for row in ordered_rows],
        dtype=float,
    )
    y = np.array([int(row.label_home_win) for row in ordered_rows], dtype=int)

    model = LogisticRegression(C=1.0, max_iter=1000)
    model.fit(x, y)
    probabilities = model.predict_proba(x)[:, 1]
    metrics = evaluate_binary_predictions(y.tolist(), probabilities.tolist())
    enabled = baseline_metrics is None or artifact_passes_gate(
        metrics, baseline_metrics
    )
    return MoneylineModelArtifact(
        model_version=model_version,
        feature_names=feature_names,
        model=model,
        calibration_method="logistic",
        metrics=metrics,
        enabled=enabled,
    )


@dataclass
class CalibratedMoneylineModel:
    """Drop-in MLB moneyline predictor backed by a trained artifact."""

    artifact: MoneylineModelArtifact

    def predict(self, features: Mapping[str, float]) -> float:
        """Return P(home win), refusing disabled artifacts."""
        if not self.artifact.enabled:
            raise RuntimeError(
                f"Model artifact {self.artifact.model_version} is disabled"
            )
        return self.artifact.predict_proba(features)

    def prediction_payload(
        self,
        *,
        game_id: str,
        outcome_name: str,
        run_date: date,
        features: Mapping[str, float],
        feature_hash: str,
        market_prob: Optional[float] = None,
        abstain: bool = False,
        abstention_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return a payload matching ``mlb_model_prediction_v1.json``."""
        model_prob = self.predict(features) if not abstain else 0.5
        edge = model_prob - market_prob if market_prob is not None else None
        expected_value = (
            edge / market_prob if edge is not None and market_prob else None
        )
        return {
            "schema_version": "v1",
            "sport": "MLB",
            "payload_kind": "model_prediction",
            "prediction_id": (
                f"{self.artifact.model_version}_{game_id}_{outcome_name}_{run_date.isoformat()}"
            ),
            "model_version": self.artifact.model_version,
            "game_id": game_id,
            "market_name": "moneyline",
            "outcome_name": outcome_name,
            "run_date": run_date.isoformat(),
            "model_prob": model_prob,
            "market_prob": market_prob,
            "edge": edge,
            "expected_value": expected_value,
            "calibration_method": self.artifact.calibration_method,
            "ece_at_train": self.artifact.metrics.expected_calibration_error,
            "feature_hash": feature_hash,
            "simulation_summary": None,
            "abstain": abstain,
            "abstention_reason": abstention_reason,
        }
