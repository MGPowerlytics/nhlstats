#!/usr/bin/env python3
"""Compare raw tennis Elo vs Platt-calibrated probabilities.

This is a leakage-safe evaluation:
- Compute sequential Elo probabilities with a walk-forward simulation.
- Fit a Platt calibrator on matches strictly before an evaluation cutoff.
- Apply it to matches on/after the cutoff.

Usage:
    python3 plugins/compare_tennis_calibrated.py --tour ALL --eval-since 2025-01-01
    python3 plugins/compare_tennis_calibrated.py --tour ATP --eval-since 2025-01-01
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from probability_calibration import (
    apply_bucketed_platt_scaler,
    apply_platt_scaler,
    clamp_probs,
    fit_bucketed_platt_scaler,
    fit_platt_scaler,
)


def _logloss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1.0 - 1e-9)
    y = np.asarray(y, dtype=float)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def _brier(y: np.ndarray, p: np.ndarray) -> float:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    return float(np.mean((p - y) ** 2))


def _accuracy(y: np.ndarray, p: np.ndarray) -> float:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    return float(np.mean((p >= 0.5) == (y == 1.0)))


@dataclass(frozen=True)
class Metrics:
    n: int
    accuracy: float
    logloss: float
    brier: float


def _metrics(df: pd.DataFrame, prob_col: str) -> Metrics:
    y = df["y"].to_numpy(dtype=float)
    p = clamp_probs(df[prob_col].to_numpy(dtype=float))
    return Metrics(
        n=int(len(df)),
        accuracy=_accuracy(y, p),
        logloss=_logloss(y, p),
        brier=_brier(y, p),
    )


def _build_sequential_elo_dataset(
    *,
    db_path: Path,
    tour: str,
    since: Optional[str],
    until: Optional[str],
) -> pd.DataFrame:
    # Reuse the loader + baseline Elo used in the recency comparison script.
    from compare_tennis_recency_models import BaselineTennisElo, load_tennis_matches

    matches = load_tennis_matches(db_path=db_path, tour=tour, since=since, until=until)
    if not matches:
        return pd.DataFrame(columns=["date", "tour", "y", "p_raw"])

    elo = BaselineTennisElo()

    rows: List[Dict[str, object]] = []
    for m in matches:
        # Outcome-independent ordering (lexicographic)
        a, b = sorted([m.winner, m.loser])
        y = 1.0 if a == m.winner else 0.0

        p = float(elo.predict(a, b))
        rows.append(
            {
                "date": pd.to_datetime(m.date),
                "tour": str(m.tour).upper(),
                "y": y,
                "p_raw": p,
            }
        )

        # Update with the true winner/loser
        elo.update(m.winner, m.loser)

    return pd.DataFrame(rows).sort_values("date")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare raw vs calibrated tennis Elo")
    parser.add_argument("--db-path", default="data/nhlstats.duckdb")
    parser.add_argument("--tour", default="ALL", choices=["ALL", "ATP", "WTA"])
    parser.add_argument(
        "--eval-since", default="2025-01-01", help="Evaluation start date YYYY-MM-DD"
    )
    parser.add_argument("--train-window-days", type=int, default=None)
    parser.add_argument("--train-max-matches", type=int, default=None)
    parser.add_argument("--platt-c", type=float, default=1.0)
    parser.add_argument("--platt-max-iter", type=int, default=1000)
    parser.add_argument(
        "--by-tour",
        action="store_true",
        help="Fit separate calibrators by tour (ATP/WTA) when tour=ALL",
    )
    parser.add_argument(
        "--min-bucket-samples",
        type=int,
        default=1000,
        help="Minimum train samples to fit a per-bucket calibrator",
    )

    args = parser.parse_args()

    df = _build_sequential_elo_dataset(
        db_path=Path(args.db_path),
        tour=args.tour,
        since=None,
        until=None,
    )

    if df.empty:
        print("⚠️  No tennis matches found")
        return

    eval_since_dt = pd.to_datetime(args.eval_since)
    train_df = df[df["date"] < eval_since_dt].copy()
    eval_df = df[df["date"] >= eval_since_dt].copy()

    if args.train_window_days is not None:
        window_start = eval_since_dt - pd.Timedelta(days=int(args.train_window_days))
        train_df = train_df[train_df["date"] >= window_start]

    if args.train_max_matches is not None and args.train_max_matches > 0:
        train_df = train_df.sort_values("date").tail(int(args.train_max_matches))

    if eval_df.empty:
        print(f"⚠️  No matches since {args.eval_since}")
        return

    print("=" * 110)
    print("📊 Tennis Elo Calibration (Platt) — Leakage-safe")
    print("=" * 110)
    print(f"📥 Matches total: {len(df):,}")
    print(f"🧪 Training: {len(train_df):,} (date < {args.eval_since})")
    print(f"📅 Evaluation: {len(eval_df):,} (date >= {args.eval_since})")

    y_train = train_df["y"].to_numpy(dtype=int)
    p_train = train_df["p_raw"].to_numpy(dtype=float)

    eval_df["p_calibrated"] = eval_df["p_raw"].astype(float)
    used_bucket = None

    if args.by_tour and args.tour == "ALL":
        bm = fit_bucketed_platt_scaler(
            y=y_train,
            probs=p_train,
            buckets=train_df["tour"].to_numpy(dtype=str),
            min_samples=int(args.min_bucket_samples),
            c=float(args.platt_c),
            max_iter=int(args.platt_max_iter),
        )
        cal, used_bucket = apply_bucketed_platt_scaler(
            bm,
            probs=eval_df["p_raw"].to_numpy(dtype=float),
            buckets=eval_df["tour"].to_numpy(dtype=str),
        )
        eval_df["p_calibrated"] = cal
        print(
            "🎯 Calibrator: bucketed by tour "
            f"(trained buckets={sorted(bm.bucket_models.keys())}, min_samples={bm.min_samples})"
        )
    else:
        model = fit_platt_scaler(
            y=y_train,
            probs=p_train,
            c=float(args.platt_c),
            max_iter=int(args.platt_max_iter),
        )
        if model is None:
            print("⚠️  Calibration skipped (insufficient label variation in training)")
        else:
            eval_df["p_calibrated"] = apply_platt_scaler(
                model, eval_df["p_raw"].to_numpy(dtype=float)
            )
            print("🎯 Calibrator: global Platt scaler")

    m_raw = _metrics(eval_df, "p_raw")
    m_cal = _metrics(eval_df, "p_calibrated")

    print("\n**Evaluation Metrics**")
    print(
        f"Raw:       n={m_raw.n:,}  acc={m_raw.accuracy:.4f}  logloss={m_raw.logloss:.6f}  brier={m_raw.brier:.6f}"
    )
    print(
        f"Calibrated:n={m_cal.n:,}  acc={m_cal.accuracy:.4f}  logloss={m_cal.logloss:.6f}  brier={m_cal.brier:.6f}"
    )

    if used_bucket is not None:
        print(
            f"\nUsed bucket-specific calibrator for {int(np.sum(used_bucket)):,} / {len(used_bucket):,} eval matches"
        )


if __name__ == "__main__":
    main()
