#!/usr/bin/env python3
"""Backtest NHL betting profitability vs sportsbook closing lines.

This backtest uses:
- Model win probabilities (Elo / TrueSkill / ensemble)
- Historical closing moneylines and implied probabilities from DuckDB

It then places a unit-stake bet when model edge exceeds a threshold.

Important:
- This is a research script; it does not modify any production betting logic.
- Profitability is evaluated against sportsbook moneylines (not Kalshi).
  If you later want Kalshi-specific PnL, we need historical Kalshi prices.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from typing import Optional

import duckdb
import numpy as np
import pandas as pd

from .betting_backtest import choose_side_by_edge, simulate_unit_bets
from .compare_elo_trueskill_nhl import (
    calculate_elo_probabilities,
    calculate_trueskill_probabilities,
)
from .lift_gain_analysis import get_current_season_start


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backtest NHL betting profitability vs sportsbook closing lines",
    )
    parser.add_argument(
        "--db-path",
        default="data/nhlstats.duckdb",
        help="Path to DuckDB database.",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="Start date (YYYY-MM-DD). Default: current season start.",
    )
    parser.add_argument(
        "--season-reversion-factor",
        type=float,
        default=0.35,
        help="Season reversion factor for ratings.",
    )

    parser.add_argument(
        "--trueskill-home-adv",
        type=float,
        default=1.0,
        help="TrueSkill home advantage (mu units).",
    )
    parser.add_argument(
        "--trueskill-beta",
        type=float,
        default=4.0,
        help="TrueSkill performance variance (beta).",
    )
    parser.add_argument(
        "--trueskill-tau",
        type=float,
        default=0.03,
        help="TrueSkill dynamics (tau).",
    )

    parser.add_argument(
        "--w-elo",
        type=float,
        default=0.44,
        help="Ensemble weight for Elo prob.",
    )
    parser.add_argument(
        "--w-ts",
        type=float,
        default=0.56,
        help="Ensemble weight for TrueSkill prob.",
    )

    parser.add_argument(
        "--min-edge",
        type=float,
        default=0.05,
        help="Minimum model edge over market implied probability.",
    )
    parser.add_argument(
        "--min-model-prob",
        type=float,
        default=0.55,
        help="Minimum model probability required to bet a side.",
    )

    return parser.parse_args(argv)


def load_games_with_abbrev(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Load NHL games from DuckDB with team abbreviations.

    This avoids relying on external mapping when joining to odds tables that are keyed
    by abbreviations.
    """

    return conn.execute(
        """
        SELECT
            game_id,
            game_date,
            home_team_abbrev,
            away_team_abbrev,
            home_team_name AS home_team,
            away_team_name AS away_team,
            home_score,
            away_score,
            CASE WHEN home_score > away_score THEN 1 ELSE 0 END AS home_win
        FROM games
        WHERE game_state = 'OFF'
        ORDER BY game_date, game_id
        """
    ).fetchdf()


def load_betting_lines_by_game_id(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Load closing lines keyed by game_id."""

    return conn.execute(
        """
        SELECT
            game_id,
            home_ml_close,
            away_ml_close,
            home_implied_prob,
            away_implied_prob,
            'betting_line_features' AS line_source
        FROM betting_line_features
        WHERE home_implied_prob IS NOT NULL
          AND away_implied_prob IS NOT NULL
          AND home_ml_close IS NOT NULL
          AND away_ml_close IS NOT NULL
        """
    ).fetchdf()


def load_betting_lines_by_date_abbrev(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Load closing lines keyed by (game_date, home_team_abbrev, away_team_abbrev)."""

    return conn.execute(
        """
        SELECT
            game_date,
            home_team AS home_team_abbrev,
            away_team AS away_team_abbrev,
            home_ml_close,
            away_ml_close,
            home_implied_prob_close AS home_implied_prob,
            away_implied_prob_close AS away_implied_prob,
            source AS line_source
        FROM historical_betting_lines
        WHERE home_implied_prob_close IS NOT NULL
          AND away_implied_prob_close IS NOT NULL
          AND home_ml_close IS NOT NULL
          AND away_ml_close IS NOT NULL
        """
    ).fetchdf()


def add_no_vig_probs(df: pd.DataFrame) -> pd.DataFrame:
    """Add no-vig normalized market probabilities.

    Sportsbooks embed vig; the raw implied probabilities usually sum > 1. Normalizing
    makes edges more realistic.
    """

    df = df.copy()
    total = df["home_implied_prob"].astype(float) + df["away_implied_prob"].astype(float)
    df["home_market_prob_nv"] = df["home_implied_prob"].astype(float) / total
    df["away_market_prob_nv"] = df["away_implied_prob"].astype(float) / total
    return df


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)

    season_start = get_current_season_start("nhl")
    since_ts = pd.to_datetime(args.since) if args.since else pd.to_datetime(season_start)

    print("📥 Loading NHL games + betting lines...")
    conn = duckdb.connect(args.db_path, read_only=True)

    games = load_games_with_abbrev(conn)
    games["game_date"] = pd.to_datetime(games["game_date"])
    games = games[games["game_date"] >= since_ts].copy()

    lines_game_id = load_betting_lines_by_game_id(conn)
    lines_abbrev = load_betting_lines_by_date_abbrev(conn)
    lines_abbrev["game_date"] = pd.to_datetime(lines_abbrev["game_date"])

    conn.close()

    df = games.merge(lines_game_id, on="game_id", how="left")
    missing_mask = df["home_implied_prob"].isna() | df["away_implied_prob"].isna()
    if missing_mask.any():
        fallback = (
            df.loc[missing_mask, ["game_date", "home_team_abbrev", "away_team_abbrev"]]
            .merge(
                lines_abbrev,
                on=["game_date", "home_team_abbrev", "away_team_abbrev"],
                how="left",
                suffixes=("", "_fb"),
            )
            .reset_index(drop=True)
        )
        for col in [
            "home_ml_close",
            "away_ml_close",
            "home_implied_prob",
            "away_implied_prob",
            "line_source",
        ]:
            df.loc[missing_mask, col] = fallback[col].to_numpy()

    df = df.dropna(
        subset=["home_ml_close", "away_ml_close", "home_implied_prob", "away_implied_prob"]
    ).copy()
    df = df.sort_values(["game_date", "game_id"], ascending=True)

    if df.empty:
        raise SystemExit("No joined games with betting lines found for the requested window")

    df = add_no_vig_probs(df)
    print(f"✅ Joined games with lines: {len(df)}")

    # Leakage-safe model probabilities
    df = calculate_elo_probabilities(
        df, season_reversion_factor=float(args.season_reversion_factor)
    )
    df["trueskill_prob"] = calculate_trueskill_probabilities(
        df,
        season_reversion_factor=float(args.season_reversion_factor),
        trueskill_home_advantage=float(args.trueskill_home_adv),
        trueskill_beta=float(args.trueskill_beta),
        trueskill_tau=float(args.trueskill_tau),
    )

    w_elo = float(args.w_elo)
    w_ts = float(args.w_ts)
    if not np.isfinite(w_elo) or not np.isfinite(w_ts) or abs((w_elo + w_ts) - 1.0) > 1e-6:
        raise SystemExit("--w-elo + --w-ts must sum to 1.0")

    df["model_prob"] = w_elo * df["elo_prob"] + w_ts * df["trueskill_prob"]

    # Decide bets
    decisions = []
    home_win = df["home_win"].astype(int).to_numpy()

    for row in df.itertuples(index=False):
        p_home = float(row.model_prob)
        p_away = 1.0 - p_home

        decision = choose_side_by_edge(
            home_model_prob=p_home,
            away_model_prob=p_away,
            home_market_prob=float(row.home_market_prob_nv),
            away_market_prob=float(row.away_market_prob_nv),
            home_american_odds=float(row.home_ml_close),
            away_american_odds=float(row.away_ml_close),
            min_edge=float(args.min_edge),
            min_model_prob=float(args.min_model_prob),
        )
        decisions.append(decision)

    summary = simulate_unit_bets(decisions=decisions, home_win=home_win)

    print("\n📊 Backtest Summary (unit stake)")
    for k, v in asdict(summary).items():
        if isinstance(v, float):
            print(f"- {k}: {v:.4f}")
        else:
            print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
