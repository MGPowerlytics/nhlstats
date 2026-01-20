"""Probability calibration utilities.

This module currently provides Platt scaling (logistic regression on the logit of
an uncalibrated probability). It's intended for leakage-safe offline evaluation
and for production use when a stable training split is available.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np


def clamp_probs(probs: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    r"""Clamp probabilities into $(\epsilon, 1-\epsilon)$.

    Args:
        probs: Input probabilities.
        eps: Clamp epsilon.

    Returns:
        Clamped probabilities.
    """

    return np.clip(np.asarray(probs, dtype=float), float(eps), 1.0 - float(eps))


def logit(probs: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Compute logit(probs) with clamping for numerical safety."""

    p = clamp_probs(probs, eps=eps)
    return np.log(p / (1.0 - p))


def sigmoid(x: np.ndarray) -> np.ndarray:
    """Numerically stable-ish sigmoid for numpy arrays."""

    x = np.asarray(x, dtype=float)
    return 1.0 / (1.0 + np.exp(-x))


@dataclass(frozen=True)
class PlattParams:
    """Serializable Platt scaling parameters.

    Platt scaling here is defined as:

        p' = sigmoid(alpha * logit(p) + beta)
    """

    alpha: float
    beta: float


def platt_params_from_model(model: object) -> PlattParams:
    """Extract Platt parameters from a fitted sklearn LogisticRegression."""

    alpha = float(getattr(model, "coef_")[0][0])
    beta = float(getattr(model, "intercept_")[0])
    return PlattParams(alpha=alpha, beta=beta)


def apply_platt_params(params: PlattParams, probs: np.ndarray) -> np.ndarray:
    """Apply Platt scaling parameters to probabilities."""

    x = logit(np.asarray(probs, dtype=float))
    return sigmoid(params.alpha * x + params.beta)


def fit_platt_params(
    *,
    y: np.ndarray,
    probs: np.ndarray,
    c: float = 1.0,
    max_iter: int = 1000,
) -> Optional[PlattParams]:
    """Fit Platt scaling and return serializable parameters."""

    model = fit_platt_scaler(y=y, probs=probs, c=c, max_iter=max_iter)
    if model is None:
        return None
    return platt_params_from_model(model)


@dataclass(frozen=True)
class BucketedPlattModel:
    """Bucketed Platt scaling models.

    Attributes:
        global_model: Fallback model trained on all training data.
        bucket_models: Per-bucket models.
        min_samples: Minimum samples required to train a bucket model.
    """

    global_model: Optional[object]
    bucket_models: Dict[str, object]
    min_samples: int


def fit_platt_scaler(
    *,
    y: np.ndarray,
    probs: np.ndarray,
    c: float = 1.0,
    max_iter: int = 1000,
) -> Optional[object]:
    """Fit a Platt scaler: logistic regression on logit(prob).

    Args:
        y: Binary labels (0/1).
        probs: Raw probabilities.
        c: Inverse regularization strength for sklearn LogisticRegression.
        max_iter: Maximum iterations.

    Returns:
        Fitted sklearn LogisticRegression model, or None if fitting isn't possible
        (e.g., only one class present).
    """

    y_arr = np.asarray(y, dtype=int)
    if y_arr.size == 0 or np.unique(y_arr).size < 2:
        return None

    x = logit(np.asarray(probs, dtype=float)).reshape(-1, 1)

    from sklearn.linear_model import LogisticRegression

    model = LogisticRegression(solver="lbfgs", C=float(c), max_iter=int(max_iter))
    model.fit(x, y_arr)
    return model


def apply_platt_scaler(model: object, probs: np.ndarray) -> np.ndarray:
    """Apply a fitted Platt scaler to probabilities."""

    x = logit(np.asarray(probs, dtype=float)).reshape(-1, 1)
    return np.asarray(model.predict_proba(x)[:, 1], dtype=float)


def fit_bucketed_platt_scaler(
    *,
    y: np.ndarray,
    probs: np.ndarray,
    buckets: np.ndarray,
    min_samples: int = 500,
    c: float = 1.0,
    max_iter: int = 1000,
) -> BucketedPlattModel:
    """Fit per-bucket Platt scalers with a global fallback.

    Args:
        y: Binary labels.
        probs: Raw probabilities.
        buckets: Bucket key per row (e.g., tour/league).
        min_samples: Minimum samples needed to fit a bucket model.
        c: Inverse regularization strength.
        max_iter: Maximum iterations.

    Returns:
        BucketedPlattModel containing a global model (may be None) and per-bucket
        models.
    """

    y_arr = np.asarray(y, dtype=int)
    p_arr = np.asarray(probs, dtype=float)
    b_arr = np.asarray(buckets, dtype=str)

    global_model = fit_platt_scaler(y=y_arr, probs=p_arr, c=c, max_iter=max_iter)

    bucket_models: Dict[str, object] = {}
    for b in np.unique(b_arr):
        mask = b_arr == b
        if int(mask.sum()) < int(min_samples):
            continue

        m = fit_platt_scaler(y=y_arr[mask], probs=p_arr[mask], c=c, max_iter=max_iter)
        if m is not None:
            bucket_models[str(b)] = m

    return BucketedPlattModel(
        global_model=global_model,
        bucket_models=bucket_models,
        min_samples=int(min_samples),
    )


def apply_bucketed_platt_scaler(
    model: BucketedPlattModel,
    *,
    probs: np.ndarray,
    buckets: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Apply bucketed Platt scalers.

    Args:
        model: BucketedPlattModel.
        probs: Raw probabilities.
        buckets: Bucket key per row.

    Returns:
        (calibrated_probs, used_bucket_model_mask)
        where used_bucket_model_mask is a boolean array indicating rows that were
        calibrated with a bucket-specific model (vs global fallback).
    """

    p_arr = np.asarray(probs, dtype=float)
    b_arr = np.asarray(buckets, dtype=str)

    out = np.empty_like(p_arr, dtype=float)
    used_bucket = np.zeros_like(p_arr, dtype=bool)

    if model.global_model is None and not model.bucket_models:
        return clamp_probs(p_arr), used_bucket

    for i, (p, b) in enumerate(zip(p_arr, b_arr)):
        m = model.bucket_models.get(str(b))
        if m is not None:
            out[i] = float(apply_platt_scaler(m, np.asarray([p]))[0])
            used_bucket[i] = True
        elif model.global_model is not None:
            out[i] = float(apply_platt_scaler(model.global_model, np.asarray([p]))[0])
        else:
            out[i] = float(clamp_probs(np.asarray([p]))[0])

    return out, used_bucket
