#!/usr/bin/env python3
"""Compare Elo vs Elo+Markov Momentum for the current season (NBA/NHL).

This script:
- Loads *all* available historical games for the sport.
- Computes Elo predictions sequentially.
- Computes Elo+Markov predictions sequentially (leakage-safe).
- Filters to the current season window for evaluation.
- Prints metrics and lift/gain-by-decile tables for both probability columns.

Usage:
    python plugins/compare_elo_markov_current_season.py --sport nba
    python plugins/compare_elo_markov_current_season.py --sport nhl --alpha 0.35

"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd

from lift_gain_analysis import (
    calculate_elo_markov_predictions,
    calculate_lift_gain_by_decile,
    get_current_season_start,
    load_games,
    print_decile_table,
)


def _clamp_probs(p: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    return np.clip(p.astype(float), eps, 1.0 - eps)


@dataclass
class Metrics:
    n_games: int
    baseline_home_win_rate: float
    accuracy: float
    brier: float
    log_loss: float


def compute_metrics(df: pd.DataFrame, prob_col: str) -> Metrics:
    """Compute basic probabilistic prediction metrics."""

    y = df["home_win"].astype(int).to_numpy()
    p = _clamp_probs(df[prob_col].to_numpy())

    preds = (p >= 0.5).astype(int)
    accuracy = float((preds == y).mean()) if len(y) else float("nan")

    brier = float(np.mean((p - y) ** 2)) if len(y) else float("nan")

    # Binary log loss
    log_loss = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))) if len(y) else float("nan")

    return Metrics(
        n_games=int(len(y)),
        baseline_home_win_rate=float(df["home_win"].mean()) if len(y) else float("nan"),
        accuracy=accuracy,
        brier=brier,
        log_loss=log_loss,
    )


def run_for_sport(sport: str, alpha: float, smoothing: float) -> None:
    print("=" * 110)
    print(f"📊 Elo vs Elo+Markov (Current Season) — {sport.upper()}")
    print("=" * 110)

    season_start = get_current_season_start(sport)

    print(f"📥 Loading all {sport.upper()} games (for leakage-safe training)...")
    all_games = load_games(sport, season_only=False)
    if all_games.empty:
        print(f"⚠️  No {sport.upper()} games found")
        return

    print(f"   Found {len(all_games):,} games")

    print("🎯 Computing Elo and Elo+Markov predictions...")
    all_with_preds = calculate_elo_markov_predictions(
        sport,
        all_games,
        markov_alpha=alpha,
        markov_smoothing=smoothing,
    )

    if all_with_preds.empty:
        print("⚠️  No valid games after preprocessing")
        return

    # Evaluate current season only
    season_df = all_with_preds.copy()
    season_df["game_date"] = pd.to_datetime(season_df["game_date"])
    season_df = season_df[season_df["game_date"] >= pd.to_datetime(season_start)]

    if season_df.empty:
        print(f"⚠️  No {sport.upper()} games since {season_start}")
        return

    print(f"📅 Evaluating current season since {season_start}: {len(season_df):,} games")

    metrics: Dict[str, Metrics] = {
        "elo": compute_metrics(season_df, "elo_prob"),
        "elo_markov": compute_metrics(season_df, "elo_markov_prob"),
    }

    print("\n**Metrics**")
    for key, m in metrics.items():
        print(
            f"- {key}: n={m.n_games:,}, baseline={m.baseline_home_win_rate:.3f}, "
            f"acc={m.accuracy:.3f}, brier={m.brier:.4f}, logloss={m.log_loss:.4f}"
        )

    # Lift/gain by decile
    print("\n📈 Lift/Gain by decile (Elo)")
    elo_deciles = calculate_lift_gain_by_decile(season_df, prob_col="elo_prob")
    print_decile_table(elo_deciles, sport, f"CURRENT SEASON — Elo (Since {season_start})")

    print("\n📈 Lift/Gain by decile (Elo+Markov)")
    markov_deciles = calculate_lift_gain_by_decile(season_df, prob_col="elo_markov_prob")
    print_decile_table(markov_deciles, sport, f"CURRENT SEASON — Elo+Markov (Since {season_start})")


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sport",
        action="append",
        choices=["nba", "nhl"],
        help="Sport to analyze. Can be passed multiple times. Default: nba and nhl.",
    )
    parser.add_argument("--alpha", type=float, default=0.35, help="Markov alpha scaling.")
    parser.add_argument("--smoothing", type=float, default=2.0, help="Markov smoothing strength.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    args = parse_args(argv)
    sports = args.sport if args.sport else ["nba", "nhl"]

    for sport in sports:
        run_for_sport(sport, alpha=args.alpha, smoothing=args.smoothing)


if __name__ == "__main__":
    main()
