#!/usr/bin/env python3
"""Compare raw Elo vs Platt-calibrated probabilities for NCAAB/WNCAAB.

This script uses Massey Ratings game downloads (via existing loaders) and runs
a leakage-safe evaluation:
- Build sequential Elo probabilities by iterating games in chronological order.
- Fit a Platt calibrator on *prior seasons*.
- Evaluate on a chosen season (default: latest season in the dataset).

Usage:
    python3 plugins/compare_college_basketball_calibrated.py --league ncaab
    python3 plugins/compare_college_basketball_calibrated.py --league wncaab --eval-season 2026
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from probability_calibration import apply_platt_scaler, clamp_probs, fit_platt_scaler


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


def _load_games(league: str) -> pd.DataFrame:
    league = league.lower().strip()
    if league == "ncaab":
        from ncaab_games import NCAABGames

        return NCAABGames().load_games()
    if league == "wncaab":
        from wncaab_games import WNCAABGames

        return WNCAABGames().load_games()

    raise ValueError(f"Unsupported league: {league}")


def _make_elo(league: str):
    league = league.lower().strip()
    if league == "ncaab":
        from plugins.elo import NCAABEloRating

        return NCAABEloRating()
    if league == "wncaab":
        from plugins.elo import WNCAABEloRating

        return WNCAABEloRating()
    raise ValueError(f"Unsupported league: {league}")


def _apply_season_reversion(elo, mean: float = 1500.0, keep: float = 0.65) -> None:
    # College roster churn: revert toward mean between seasons.
    for t in list(getattr(elo, "ratings", {}).keys()):
        elo.ratings[t] = float(keep) * float(elo.ratings[t]) + (
            1.0 - float(keep)
        ) * float(mean)


def build_sequential_dataset(league: str) -> pd.DataFrame:
    """Build a sequential dataset of (date, season, y, p_raw) for the league."""

    games = _load_games(league)
    if games.empty:
        return pd.DataFrame(columns=["date", "season", "y", "p_raw"])

    games = games.copy()
    games["date"] = pd.to_datetime(games["date"])
    games = games.sort_values("date")

    elo = _make_elo(league)
    last_season = None

    rows: List[Dict[str, object]] = []
    for _, g in games.iterrows():
        season = int(g.get("season")) if pd.notna(g.get("season")) else None
        if season is not None and last_season is not None and season != last_season:
            _apply_season_reversion(elo)
        if season is not None:
            last_season = season

        home_team = str(g["home_team"])
        away_team = str(g["away_team"])
        neutral = bool(g.get("neutral", False))

        home_score = float(g["home_score"])
        away_score = float(g["away_score"])
        y = 1.0 if home_score > away_score else 0.0

        p = float(elo.predict(home_team, away_team, is_neutral=neutral))
        rows.append(
            {"date": pd.to_datetime(g["date"]), "season": season, "y": y, "p_raw": p}
        )

        elo.update(home_team, away_team, y, is_neutral=neutral)

    df = pd.DataFrame(rows)
    df = df.dropna(subset=["season"])  # keep only season-tagged rows
    df["season"] = df["season"].astype(int)
    return df.sort_values("date")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare raw vs calibrated Elo for college basketball"
    )
    parser.add_argument("--league", required=True, choices=["ncaab", "wncaab"])
    parser.add_argument(
        "--eval-season",
        type=int,
        default=None,
        help="Season to evaluate (default: latest)",
    )
    parser.add_argument(
        "--train-seasons",
        type=int,
        default=None,
        help="Train using only last N seasons before eval",
    )
    parser.add_argument("--train-max-games", type=int, default=None)
    parser.add_argument("--platt-c", type=float, default=1.0)
    parser.add_argument("--platt-max-iter", type=int, default=1000)

    args = parser.parse_args()

    df = build_sequential_dataset(args.league)
    if df.empty:
        print(f"⚠️  No games found for {args.league.upper()}")
        return

    eval_season = (
        int(args.eval_season)
        if args.eval_season is not None
        else int(df["season"].max())
    )
    train_df = df[df["season"] < eval_season].copy()
    eval_df = df[df["season"] == eval_season].copy()

    if args.train_seasons is not None and args.train_seasons > 0:
        seasons = sorted(train_df["season"].unique())
        keep_seasons = set(seasons[-int(args.train_seasons) :])
        train_df = train_df[train_df["season"].isin(keep_seasons)]

    if args.train_max_games is not None and args.train_max_games > 0:
        train_df = train_df.sort_values("date").tail(int(args.train_max_games))

    if eval_df.empty:
        print(f"⚠️  No games found for eval season {eval_season}")
        return

    print("=" * 110)
    print(f"📊 {args.league.upper()} Elo Calibration (Platt) — Leakage-safe")
    print("=" * 110)
    print(f"📥 Games total: {len(df):,}")
    print(f"🧪 Training seasons < {eval_season}: {len(train_df):,}")
    print(f"📅 Evaluation season = {eval_season}: {len(eval_df):,}")

    model = fit_platt_scaler(
        y=train_df["y"].to_numpy(dtype=int),
        probs=train_df["p_raw"].to_numpy(dtype=float),
        c=float(args.platt_c),
        max_iter=int(args.platt_max_iter),
    )

    eval_df["p_calibrated"] = eval_df["p_raw"].astype(float)
    if model is None:
        print("⚠️  Calibration skipped (insufficient label variation in training)")
    else:
        eval_df["p_calibrated"] = apply_platt_scaler(
            model, eval_df["p_raw"].to_numpy(dtype=float)
        )

    m_raw = _metrics(eval_df, "p_raw")
    m_cal = _metrics(eval_df, "p_calibrated")

    print("\n**Evaluation Metrics**")
    print(
        f"Raw:       n={m_raw.n:,}  acc={m_raw.accuracy:.4f}  logloss={m_raw.logloss:.6f}  brier={m_raw.brier:.6f}"
    )
    print(
        f"Calibrated:n={m_cal.n:,}  acc={m_cal.accuracy:.4f}  logloss={m_cal.logloss:.6f}  brier={m_cal.brier:.6f}"
    )


if __name__ == "__main__":
    main()
