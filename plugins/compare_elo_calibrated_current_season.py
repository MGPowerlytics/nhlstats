#!/usr/bin/env python3
"""Compare raw Elo vs calibrated Elo for the current season (NBA/NHL).

Calibration approach:
- Fit a Platt-style logistic calibrator on *pre-season* games only
  (all games with game_date < season_start).
- Apply that calibrator to current-season Elo probabilities.

This is intended as a quick, leakage-safe test to see if calibration improves
probabilistic metrics (log loss, Brier) over the raw Elo baseline.

Usage:
    python plugins/compare_elo_calibrated_current_season.py --sport nba
    python plugins/compare_elo_calibrated_current_season.py --sport nhl

    # Fit calibrator on a recent window of pre-season history
    python plugins/compare_elo_calibrated_current_season.py --sport nhl --train-window-days 730

    # Fit on most recent N games before season start
    python plugins/compare_elo_calibrated_current_season.py --sport nhl --train-max-games 2000

"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from lift_gain_analysis import (
    calculate_elo_predictions,
    calculate_lift_gain_by_decile,
    get_current_season_start,
    load_games,
    print_decile_table,
)


def _clamp_probs(p: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    return np.clip(p.astype(float), eps, 1.0 - eps)


def _logit(p: np.ndarray) -> np.ndarray:
    p = _clamp_probs(p)
    return np.log(p / (1.0 - p))


@dataclass
class Metrics:
    n_games: int
    baseline_home_win_rate: float
    accuracy: float
    brier: float
    log_loss: float


@dataclass
class AccuracySummary:
    threshold: float
    accuracy: float


def compute_metrics(df: pd.DataFrame, prob_col: str) -> Metrics:
    """Compute basic probabilistic prediction metrics."""

    y = df["home_win"].astype(int).to_numpy()
    p = _clamp_probs(df[prob_col].to_numpy())

    preds = (p >= 0.5).astype(int)
    accuracy = float((preds == y).mean()) if len(y) else float("nan")

    brier = float(np.mean((p - y) ** 2)) if len(y) else float("nan")

    log_loss = (
        float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
        if len(y)
        else float("nan")
    )

    return Metrics(
        n_games=int(len(y)),
        baseline_home_win_rate=float(df["home_win"].mean()) if len(y) else float("nan"),
        accuracy=accuracy,
        brier=brier,
        log_loss=log_loss,
    )


def _accuracy_at_threshold(df: pd.DataFrame, prob_col: str, threshold: float) -> float:
    y = df["home_win"].astype(int).to_numpy()
    p = _clamp_probs(df[prob_col].to_numpy())
    preds = (p >= float(threshold)).astype(int)
    return float((preds == y).mean()) if len(y) else float("nan")


def find_best_threshold(
    train_df: pd.DataFrame,
    prob_col: str,
    grid_step: float = 0.01,
) -> AccuracySummary:
    """Find threshold that maximizes accuracy on a training set.

    Note:
        This is intentionally fit on pre-season training data only to avoid
        leaking the current season label distribution.
    """

    if train_df.empty:
        return AccuracySummary(threshold=0.5, accuracy=float("nan"))

    thresholds = np.unique(
        np.clip(np.arange(0.01, 1.0, grid_step, dtype=float), 0.01, 0.99)
    )
    if 0.5 not in thresholds:
        thresholds = np.sort(np.append(thresholds, 0.5))

    best_threshold = 0.5
    best_accuracy = -1.0
    for t in thresholds:
        acc = _accuracy_at_threshold(train_df, prob_col, float(t))
        if acc > best_accuracy:
            best_accuracy = acc
            best_threshold = float(t)

    return AccuracySummary(threshold=best_threshold, accuracy=float(best_accuracy))


def fit_platt_calibrator(
    train_df: pd.DataFrame,
    prob_col: str,
    c: float,
    max_iter: int,
) -> Optional[object]:
    """Fit a Platt-style calibrator: logistic regression on logit(prob).

    Returns:
        A fitted sklearn LogisticRegression, or None if fitting is not possible.
    """

    y = train_df["home_win"].astype(int).to_numpy()
    if len(np.unique(y)) < 2:
        return None

    x = _logit(train_df[prob_col].to_numpy()).reshape(-1, 1)

    from sklearn.linear_model import LogisticRegression

    model = LogisticRegression(
        solver="lbfgs",
        C=float(c),
        max_iter=int(max_iter),
    )
    model.fit(x, y)
    return model


def apply_platt_calibrator(model: object, probs: np.ndarray) -> np.ndarray:
    x = _logit(probs).reshape(-1, 1)
    return model.predict_proba(x)[:, 1]


def _select_training_set(
    all_with_elo: pd.DataFrame,
    season_start: str,
    train_window_days: Optional[int],
    train_max_games: Optional[int],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    all_with_elo = all_with_elo.copy()
    all_with_elo["game_date"] = pd.to_datetime(all_with_elo["game_date"])

    season_start_dt = pd.to_datetime(season_start)
    pre_season = all_with_elo[all_with_elo["game_date"] < season_start_dt]
    season_df = all_with_elo[all_with_elo["game_date"] >= season_start_dt]

    if train_window_days is not None:
        window_start = season_start_dt - pd.Timedelta(days=int(train_window_days))
        pre_season = pre_season[pre_season["game_date"] >= window_start]

    if train_max_games is not None and train_max_games > 0:
        pre_season = pre_season.sort_values("game_date").tail(int(train_max_games))

    return pre_season, season_df


def run_for_sport(
    sport: str,
    train_window_days: Optional[int],
    train_max_games: Optional[int],
    platt_c: float,
    platt_max_iter: int,
    threshold_grid_step: float,
) -> None:
    print("=" * 110)
    print(f"📊 Raw Elo vs Calibrated Elo (Current Season) — {sport.upper()}")
    print("=" * 110)

    season_start = get_current_season_start(sport)

    print(f"📥 Loading all {sport.upper()} games (for pre-season calibration fit)...")
    all_games = load_games(sport, season_only=False)
    if all_games.empty:
        print(f"⚠️  No {sport.upper()} games found")
        return

    print(f"   Found {len(all_games):,} games")

    print("🎯 Computing Elo probabilities...")
    all_with_elo = calculate_elo_predictions(sport, all_games)
    if all_with_elo.empty:
        print("⚠️  No valid games after preprocessing")
        return

    train_df, season_df = _select_training_set(
        all_with_elo,
        season_start=season_start,
        train_window_days=train_window_days,
        train_max_games=train_max_games,
    )

    if season_df.empty:
        print(f"⚠️  No {sport.upper()} games since {season_start}")
        return

    print(
        f"📅 Evaluating current season since {season_start}: {len(season_df):,} games"
    )
    window_desc = []
    if train_window_days is not None:
        window_desc.append(f"last {int(train_window_days)}d")
    if train_max_games is not None:
        window_desc.append(f"max {int(train_max_games):,} games")

    window_str = f" ({', '.join(window_desc)})" if window_desc else " (all pre-season)"
    print(
        f"🧪 Calibration training set (pre-season){window_str}: {len(train_df):,} games"
    )

    calibrator = fit_platt_calibrator(
        train_df, prob_col="elo_prob", c=platt_c, max_iter=platt_max_iter
    )
    season_df = season_df.copy()

    if calibrator is None:
        print("⚠️  Calibration skipped (insufficient label variation in training)")
        season_df["elo_calibrated_prob"] = season_df["elo_prob"]
    else:
        season_df["elo_calibrated_prob"] = apply_platt_calibrator(
            calibrator, season_df["elo_prob"].to_numpy()
        )

    metrics: Dict[str, Metrics] = {
        "elo": compute_metrics(season_df, "elo_prob"),
        "elo_calibrated": compute_metrics(season_df, "elo_calibrated_prob"),
    }

    # Accuracy with tuned threshold (fit on training set only; applied to season)
    tuned_elo = find_best_threshold(
        train_df, prob_col="elo_prob", grid_step=threshold_grid_step
    )
    if calibrator is None:
        tuned_cal = AccuracySummary(threshold=0.5, accuracy=float("nan"))
    else:
        train_df = train_df.copy()
        train_df["elo_calibrated_prob"] = apply_platt_calibrator(
            calibrator, train_df["elo_prob"].to_numpy()
        )
        tuned_cal = find_best_threshold(
            train_df, prob_col="elo_calibrated_prob", grid_step=threshold_grid_step
        )

    print("\n**Metrics**")
    for key, m in metrics.items():
        print(
            f"- {key}: n={m.n_games:,}, baseline={m.baseline_home_win_rate:.3f}, "
            f"acc={m.accuracy:.3f}, brier={m.brier:.4f}, logloss={m.log_loss:.4f}"
        )

    print("\n**Accuracy (tuned threshold from pre-season only)**")
    print(
        f"- elo: threshold={tuned_elo.threshold:.2f}, "
        f"season_acc={_accuracy_at_threshold(season_df, 'elo_prob', tuned_elo.threshold):.3f}"
    )
    if calibrator is None:
        print("- elo_calibrated: skipped (no calibrator)")
    else:
        print(
            f"- elo_calibrated: threshold={tuned_cal.threshold:.2f}, "
            f"season_acc={_accuracy_at_threshold(season_df, 'elo_calibrated_prob', tuned_cal.threshold):.3f}"
        )

    # Lift/gain by decile
    print("\n📈 Lift/Gain by decile (Raw Elo)")
    elo_deciles = calculate_lift_gain_by_decile(season_df, prob_col="elo_prob")
    print_decile_table(
        elo_deciles, sport, f"CURRENT SEASON — Elo (Since {season_start})"
    )

    print("\n📈 Lift/Gain by decile (Calibrated Elo)")
    cal_deciles = calculate_lift_gain_by_decile(
        season_df, prob_col="elo_calibrated_prob"
    )
    print_decile_table(
        cal_deciles, sport, f"CURRENT SEASON — Calibrated Elo (Since {season_start})"
    )


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sport",
        action="append",
        choices=["nba", "nhl"],
        help="Sport to analyze. Can be passed multiple times. Default: nba and nhl.",
    )
    parser.add_argument(
        "--train-window-days",
        type=int,
        default=None,
        help=(
            "If set, trains calibration only on pre-season games within this many "
            "days before season start (still leakage-safe)."
        ),
    )
    parser.add_argument(
        "--train-max-games",
        type=int,
        default=None,
        help=(
            "If set, limits calibration training set to the most recent N pre-season "
            "games before season start (applied after --train-window-days filter)."
        ),
    )
    parser.add_argument(
        "--platt-c",
        type=float,
        default=1.0,
        help="Inverse regularization strength for Platt calibrator (LogisticRegression).",
    )
    parser.add_argument(
        "--platt-max-iter",
        type=int,
        default=2000,
        help="Max iterations for Platt calibrator.",
    )
    parser.add_argument(
        "--threshold-grid-step",
        type=float,
        default=0.01,
        help="Grid step size for finding the accuracy-optimal threshold on training.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    args = parse_args(argv)
    sports = args.sport if args.sport else ["nba", "nhl"]

    for sport in sports:
        run_for_sport(
            sport,
            train_window_days=args.train_window_days,
            train_max_games=args.train_max_games,
            platt_c=args.platt_c,
            platt_max_iter=args.platt_max_iter,
            threshold_grid_step=args.threshold_grid_step,
        )


if __name__ == "__main__":
    main()
