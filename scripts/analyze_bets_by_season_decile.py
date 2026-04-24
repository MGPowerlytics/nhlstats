#!/usr/bin/env python3
"""Analyze placed bets by season-calibrated Elo deciles."""

import sys

sys.path.insert(0, "/opt/airflow/plugins")
from db_manager import default_db
from elo import NCAABEloRating, NHLEloRating, NBAEloRating, TennisEloRating
import pandas as pd
import numpy as np


def compute_season_deciles(
    sport, elo_class, season_start="2025-11-01", history_start="2024-11-01"
):
    """Compute Elo predictions for all games and return decile thresholds."""
    query = f"""
    SELECT game_id, game_date, home_team_name, away_team_name, home_score, away_score
    FROM unified_games
    WHERE sport = '{sport}'
      AND game_date >= '{history_start}'
      AND home_score IS NOT NULL AND away_score IS NOT NULL
    ORDER BY game_date
    """
    df = default_db.fetch_df(query)

    if len(df) == 0:
        return None, None

    elo = elo_class()
    predictions = []
    for _, row in df.iterrows():
        home = row["home_team_name"]
        away = row["away_team_name"]
        home_prob = elo.predict(home, away)
        home_won = row["home_score"] > row["away_score"]
        if row["game_date"] >= pd.Timestamp(season_start):
            predictions.append({"home_prob": home_prob})
        elo.update(home, away, home_won)

    pred_df = pd.DataFrame(predictions)
    if len(pred_df) == 0:
        return None, None

    # Calculate decile thresholds from ALL season games
    decile_thresholds = (
        pred_df["home_prob"]
        .quantile([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
        .tolist()
    )
    return decile_thresholds, pred_df


def assign_decile(elo_prob, thresholds):
    """Assign decile based on pre-computed thresholds."""
    if thresholds is None:
        return None
    for i, thresh in enumerate(thresholds):
        if elo_prob <= thresh:
            return i + 1
    return 10


def main():
    print("Computing season-wide Elo decile thresholds...")
    print("=" * 80)

    sport_configs = {
        "NCAAB": NCAABEloRating,
        "NHL": NHLEloRating,
        "NBA": NBAEloRating,
    }

    thresholds = {}
    for sport, elo_class in sport_configs.items():
        thresh, _ = compute_season_deciles(sport, elo_class)
        thresholds[sport] = thresh
        if thresh:
            print(f"\n{sport} Decile Thresholds (from all 2025-26 season games):")
            for i, t in enumerate(thresh):
                print(f"  D{i + 1} upper bound: {t * 100:.1f}%")
            print(f"  D10: > {thresh[-1] * 100:.1f}%")

    print("\nTENNIS: Using raw Elo probabilities from placed bets (player-based)")

    # Now get our placed bets and assign deciles based on season thresholds
    print("\n" + "=" * 80)
    print("PLACED BETS BY SEASON-CALIBRATED ELO DECILE")
    print("=" * 80)

    query = """
    SELECT
        bet_id, sport, ticker, bet_on,
        elo_prob, market_prob,
        cost_dollars, profit_dollars, status,
        placed_date
    FROM placed_bets
    WHERE placed_date >= '2026-01-28'
      AND status IN ('won', 'lost', 'settled')
    ORDER BY sport, elo_prob DESC
    """
    bets_df = default_db.fetch_df(query)

    # Assign deciles using season thresholds
    def get_decile(row):
        sport = row["sport"]
        if sport in thresholds and thresholds[sport]:
            return assign_decile(row["elo_prob"], thresholds[sport])
        return None

    bets_df["decile"] = bets_df.apply(get_decile, axis=1)

    # For Tennis, compute deciles within the sport's bets (approximation)
    tennis_bets = bets_df[bets_df["sport"] == "TENNIS"].copy()
    if len(tennis_bets) > 0:
        tennis_thresholds = (
            tennis_bets["elo_prob"]
            .quantile([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
            .tolist()
        )
        bets_df.loc[bets_df["sport"] == "TENNIS", "decile"] = bets_df.loc[
            bets_df["sport"] == "TENNIS", "elo_prob"
        ].apply(lambda x: assign_decile(x, tennis_thresholds))

    for sport in sorted(bets_df["sport"].unique()):
        sport_df = bets_df[bets_df["sport"] == sport].copy()

        print(f"\n{sport} ({len(sport_df)} bets)")
        if sport in thresholds and thresholds[sport]:
            print(
                f"Season thresholds: D1<{thresholds[sport][0] * 100:.1f}%, D10>{thresholds[sport][-1] * 100:.1f}%"
            )
        print("-" * 80)
        print(
            f"{'Dec':>4} {'Elo Range':>15} {'Bets':>6} {'Wins':>5} {'WinRate':>8} {'Wagered':>10} {'P/L':>10} {'ROI':>8}"
        )
        print("-" * 80)

        sport_wagered = 0
        sport_pl = 0

        for d in range(10, 0, -1):
            dec = sport_df[sport_df["decile"] == d]
            if len(dec) > 0:
                min_elo = dec["elo_prob"].min()
                max_elo = dec["elo_prob"].max()
                wins = len(dec[dec["status"] == "won"])
                wr = wins / len(dec)
                wagered = dec["cost_dollars"].sum()
                pl = dec["profit_dollars"].sum()
                roi = pl / wagered * 100 if wagered > 0 else 0

                sport_wagered += wagered
                sport_pl += pl

                roi_str = f"{roi:+.1f}%"
                print(
                    f"{d:>4} {min_elo * 100:>6.1f}-{max_elo * 100:<6.1f}% {len(dec):>6} {wins:>5} {wr * 100:>7.1f}% {wagered:>9.2f} {pl:>+9.2f} {roi_str:>8}"
                )

        sport_roi = sport_pl / sport_wagered * 100 if sport_wagered > 0 else 0
        print("-" * 80)
        wins_total = len(sport_df[sport_df["status"] == "won"])
        print(
            f"{'Total':>4} {'':>15} {len(sport_df):>6} {wins_total:>5} {wins_total / len(sport_df) * 100:>7.1f}% {sport_wagered:>9.2f} {sport_pl:>+9.2f} {sport_roi:>+7.1f}%"
        )

    print("\n" + "=" * 80)
    print("SUMMARY: Which deciles are we betting in?")
    print("=" * 80)
    for sport in sorted(bets_df["sport"].unique()):
        sport_df = bets_df[bets_df["sport"] == sport]
        decile_counts = sport_df["decile"].value_counts().sort_index()
        print(f"\n{sport}:")
        for d, count in decile_counts.items():
            pct = count / len(sport_df) * 100
            bar = "#" * int(pct / 2)
            print(f"  D{int(d):>2}: {count:>3} bets ({pct:>5.1f}%) {bar}")


if __name__ == "__main__":
    main()
