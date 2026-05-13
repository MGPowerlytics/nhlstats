#!/usr/bin/env python3
"""One-time calibration of Elo probabilities using real PostgreSQL data.

Fits a Platt-scaling logistic regression per sport using historical
(elo_prob, actual_outcome) pairs from the placed_bets table. Persists
the fitted coefficients to ``data/calibration/platt_coefficients.json``.

Usage
-----
    python scripts/calibrate_elo_real_data.py

Requires PostgreSQL at localhost:5432 (db=airflow, user=airflow, password=airflow).
Set ``POSTGRES_HOST`` to ``localhost`` before importing ``DBManager``.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Environment – must be set *before* importing DBManager
# ---------------------------------------------------------------------------
os.environ.setdefault("POSTGRES_HOST", "localhost")

# ---------------------------------------------------------------------------
# Ensure plugins/ is on sys.path
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "plugins"))

from plugins.db_manager import DBManager, default_db  # noqa: E402
from plugins.probability_calibration import (  # noqa: E402
    MIN_BETS_FOR_FIT,
    ProbabilityCalibrator,
    CalibratorNotFittedError,
    _raw_to_calibrated,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
QUALIFYING_SPORTS_CACHE: list[str] | None = None
OUTPUT_PATH = ROOT / "data" / "calibration" / "platt_coefficients.json"


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def _get_all_sports(db: DBManager) -> list[str]:
    """Return distinct sport values from ``placed_bets`` (sorted, non-null)."""
    df = db.fetch_df("SELECT DISTINCT sport FROM placed_bets WHERE sport IS NOT NULL ORDER BY sport")
    return df["sport"].tolist()


def _get_sport_counts(db: DBManager) -> dict[str, dict[str, int]]:
    """Return a dict mapping sport → {total, with_elo, settled_with_elo}.

    This mirrors the reconnaissance query to avoid re-running ad-hoc SQL
    in the main flow.
    """
    query = """
        SELECT
            sport,
            COUNT(*) AS total,
            SUM(CASE WHEN elo_prob IS NOT NULL THEN 1 ELSE 0 END) AS with_elo,
            SUM(CASE WHEN status IN ('won', 'lost') AND elo_prob IS NOT NULL THEN 1 ELSE 0 END) AS settled_with_elo
        FROM placed_bets
        WHERE sport IS NOT NULL
        GROUP BY sport
        ORDER BY sport
    """
    df = db.fetch_df(query)
    return {
        row["sport"]: {
            "total": int(row["total"]),
            "with_elo": int(row["with_elo"]),
            "settled_with_elo": int(row["settled_with_elo"]),
        }
        for _, row in df.iterrows()
    }


# ---------------------------------------------------------------------------
# Calibration logic
# ---------------------------------------------------------------------------


def _calibrate_sport(
    calibrator: ProbabilityCalibrator, sport: str
) -> dict[str, Any] | None:
    """Fit a calibrator for *sport* and return coefficient info, or None on failure.

    Returns a dict with keys::
        sport, coef, intercept, n_train, avg_raw_bias, avg_cal_bias
    """
    try:
        calibrator.fit(sport, force_retrain=True)
    except CalibratorNotFittedError as exc:
        print(f"  ⚠  {exc}")
        return None

    model = calibrator._models[sport]
    coef = model.coef_.tolist()[0]   # shape (1, 1) → scalar list
    intercept = model.intercept_.tolist()

    # ---- Re-fetch training data to compute biases ---------------------------
    X, y = ProbabilityCalibrator._fetch_training_data(calibrator.db, sport)
    n_train = len(X)
    if n_train == 0:
        print(f"  ⚠  {sport}: no training data after fit (unexpected)")
        return None

    # Inverse logit: convert logits back to raw probabilities
    raw_probs = 1.0 / (1.0 + np.exp(-X.flatten()))

    # Average bias before calibration: mean(raw_elo - actual_outcome)
    avg_raw_bias = float(np.mean(raw_probs - y))

    # Average bias after calibration
    calibrated_probs = np.array([_raw_to_calibrated(p, model) for p in raw_probs])
    avg_cal_bias = float(np.mean(calibrated_probs - y))

    # ---- Sample calibration table -------------------------------------------
    raw_samples = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    cal_samples = [_raw_to_calibrated(p, model) for p in raw_samples]

    print(f"\n  ── {sport} Calibration Table ──")
    print(f"  Training samples : {n_train}")
    print(f"  Coef             : {coef}")
    print(f"  Intercept        : {intercept}")
    print(f"  Avg raw bias     : {avg_raw_bias:+.6f}")
    print(f"  Avg cal bias     : {avg_cal_bias:+.6f}")
    print(f"  {'Raw prob':>10s} → {'Calibrated':>12s}")
    print(f"  {'─' * 10}   {'─' * 12}")
    for r, c in zip(raw_samples, cal_samples):
        print(f"  {r:>10.1f} → {c:>12.6f}")

    return {
        "sport": sport,
        "coef": coef,
        "intercept": intercept,
        "n_train": n_train,
        "avg_raw_bias": avg_raw_bias,
        "avg_cal_bias": avg_cal_bias,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point.

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    # ---- Connection ----------------------------------------------------------
    print("=" * 60)
    print("  ELO CALIBRATION WITH REAL DATA")
    print("=" * 60)

    try:
        db: DBManager = default_db
        # Verify connectivity
        db.fetch_scalar("SELECT 1")
    except Exception as exc:
        print(f"❌ Database connection failed: {exc}")
        return 1

    print("  Connected to PostgreSQL at localhost:5432\n")

    # ---- Discover sports -----------------------------------------------------
    counts = _get_sport_counts(db)
    all_sports = sorted(counts.keys())

    print(f"  Found {len(all_sports)} sports in placed_bets:\n")
    print(f"  {'Sport':<12s} {'Total':>6s} {'With elo_prob':>14s} {'Settled+elo':>14s}")
    print(f"  {'─' * 12} {'─' * 6} {'─' * 14} {'─' * 14}")
    for sport in all_sports:
        c = counts[sport]
        print(
            f"  {sport:<12s} {c['total']:>6d} {c['with_elo']:>14d} {c['settled_with_elo']:>14d}"
        )
    print()

    # ---- Categorise sports ---------------------------------------------------
    qualifying: list[str] = []
    non_qualifying: list[tuple[str, int, int]] = []

    for sport in all_sports:
        n = counts[sport]["settled_with_elo"]
        if n >= MIN_BETS_FOR_FIT:
            qualifying.append(sport)
        else:
            non_qualifying.append((sport, n, MIN_BETS_FOR_FIT - n))

    # ---- Print qualification status ------------------------------------------
    print(f"  ── Qualifying sports (≥{MIN_BETS_FOR_FIT} settled bets) ──")
    if qualifying:
        for s in qualifying:
            print(f"    ✅ {s} ({counts[s]['settled_with_elo']} bets)")
    else:
        print("    (none)")

    print("\n  ── Non-qualifying sports ──")
    if non_qualifying:
        for sport, have, need in non_qualifying:
            print(f"    ❌ {sport}: {have} settled bets with elo_prob (needs {need} more)")
    else:
        print("    (none)")

    # ---- Fit calibrators -----------------------------------------------------
    calibrator = ProbabilityCalibrator(db=db)
    results: list[dict[str, Any]] = []
    errors: list[str] = []

    print(f"\n{'=' * 60}")
    print("  FITTING CALIBRATORS")
    print(f"{'=' * 60}\n")

    for sport in qualifying:
        print(f"  ▶  Calibrating {sport} ...")
        try:
            result = _calibrate_sport(calibrator, sport)
            if result is not None:
                result["trained_at"] = datetime.now(timezone.utc).isoformat()
                results.append(result)
        except Exception as exc:
            msg = f"  ✗  {sport} failed: {exc}"
            print(msg)
            errors.append(msg)

    # ---- Persist coefficients ------------------------------------------------
    if results:
        print(f"\n  ── Saving {len(results)} calibration(s) to {OUTPUT_PATH} ──")
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(results, indent=2) + "\n")
        print("  ✅ Coefficients written.")
    else:
        print("\n  ⚠  No calibration results to save.")

    # ---- Summary -------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("  SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Sports processed       : {len(qualifying)}")
    print(f"  Sports calibrated      : {len(results)}")
    print(f"  Sports below threshold : {len(non_qualifying)}")
    print(f"  Errors                 : {len(errors)}")

    if errors:
        for e in errors:
            print(f"    {e}")

    # Exit with success only if at least one calibration succeeded
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
