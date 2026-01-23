#!/usr/bin/env python3
"""
Ligue1 Lift/Gain Analysis

Analyzes Elo prediction quality for French Ligue 1 by probability decile.
Similar to other league analyses but for 3-way (Home/Draw/Away) outcomes.
"""

import sys
sys.path.insert(0, 'plugins')

from plugins.elo import Ligue1EloRating
import duckdb
import pandas as pd
from datetime import datetime

def analyze_ligue1(season=None):
    """
    Analyze Ligue1 Elo predictions by decile.

    Args:
        season: Optional season to filter (e.g., 2024 for 2024/25 season)
                None = all historical data

    Returns:
        DataFrame with decile statistics
    """
    print(f"\n{'='*80}")
    print(f"🇫🇷 LIGUE1 ELO LIFT/GAIN ANALYSIS")
    if season:
        print(f"Season: {season}/{season+1}")
    else:
        print(f"All Historical Data (2021-2026)")
    print(f"{'='*80}\n")

    # Load games from database
    conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)

    if season:
        query = f"""
            SELECT game_date, home_team, away_team, home_score, away_score, result, season
            FROM ligue1_games
            WHERE season = {season}
            ORDER BY game_date
        """
        print(f"Loading {season}/{season+1} season data...")
    else:
        query = """
            SELECT game_date, home_team, away_team, home_score, away_score, result, season
            FROM ligue1_games
            ORDER BY game_date
        """
        print(f"Loading all historical data...")

    games_df = conn.execute(query).fetchdf()
    conn.close()

    print(f"✓ Loaded {len(games_df)} games")
    print(f"  Date range: {games_df['game_date'].min()} to {games_df['game_date'].max()}")
    print(f"  Unique teams: {games_df['home_team'].nunique()}")

    # Initialize Elo system with standard parameters
    elo = Ligue1EloRating(k_factor=20, home_advantage=60)

    # Track predictions and outcomes
    predictions = []

    for _, game in games_df.iterrows():
        # Predict home win probability
        home_prob = elo.predict(game['home_team'], game['away_team'])

        # Actual outcome (1 if home win, 0 otherwise)
        home_won = 1 if game['result'] == 'H' else 0

        predictions.append({
            'date': game['game_date'],
            'home_team': game['home_team'],
            'away_team': game['away_team'],
            'elo_prob': home_prob,
            'home_won': home_won,
            'result': game['result'],
            'season': game['season']
        })

        # Update Elo ratings
        elo.update(game['home_team'], game['away_team'], game['result'])

    pred_df = pd.DataFrame(predictions)

    # Calculate deciles
    pred_df['decile'] = pd.qcut(pred_df['elo_prob'], q=10, labels=False, duplicates='drop') + 1

    # Aggregate by decile
    decile_stats = pred_df.groupby('decile').agg(
        games=('elo_prob', 'count'),
        avg_prob=('elo_prob', 'mean'),
        home_wins=('home_won', 'sum')
    ).reset_index()

    decile_stats['win_rate'] = decile_stats['home_wins'] / decile_stats['games']
    baseline_win_rate = pred_df['home_won'].mean()
    decile_stats['lift'] = decile_stats['win_rate'] / baseline_win_rate

    # Cumulative gain
    pred_df_sorted = pred_df.sort_values('elo_prob', ascending=False)
    pred_df_sorted['cumulative_wins'] = pred_df_sorted['home_won'].cumsum()
    total_wins = pred_df['home_won'].sum()
    pred_df_sorted['pct_wins_captured'] = pred_df_sorted['cumulative_wins'] / total_wins * 100
    pred_df_sorted['pct_games'] = range(1, len(pred_df_sorted) + 1)
    pred_df_sorted['pct_games'] = pred_df_sorted['pct_games'] / len(pred_df_sorted) * 100

    # Display results
    print(f"\n📊 DECILE ANALYSIS")
    print(f"{'='*80}")
    print(f"{'Decile':<8} {'Games':<8} {'Avg Prob':<12} {'Home Wins':<12} {'Win Rate':<12} {'Lift':<8}")
    print(f"{'='*80}")

    for _, row in decile_stats.iterrows():
        print(f"{int(row['decile']):<8} {int(row['games']):<8} "
              f"{row['avg_prob']:.1%}{'':<6} {int(row['home_wins']):<12} "
              f"{row['win_rate']:.1%}{'':<6} {row['lift']:.2f}")

    print(f"{'='*80}")
    print(f"Overall: {len(pred_df)} games, {pred_df['home_won'].sum()} home wins ({baseline_win_rate:.1%} rate)")

    # Top decile performance
    top_decile = decile_stats[decile_stats['decile'] == 10].iloc[0]
    print(f"\n🎯 TOP DECILE (90th-100th percentile):")
    print(f"   {int(top_decile['games'])} games @ {top_decile['avg_prob']:.1%} avg probability")
    print(f"   {int(top_decile['home_wins'])} wins ({top_decile['win_rate']:.1%} rate)")
    print(f"   Lift: {top_decile['lift']:.2f}x baseline")

    # Gain at 20% cutoff
    gain_20pct = pred_df_sorted[pred_df_sorted['pct_games'] <= 20]['home_won'].sum()
    gain_20pct_rate = gain_20pct / total_wins * 100
    print(f"\n📈 CUMULATIVE GAIN:")
    print(f"   Top 20% of games capture {gain_20pct_rate:.1f}% of all wins")

    # 3-way outcome distribution
    result_dist = pred_df['result'].value_counts()
    print(f"\n⚽ MATCH OUTCOME DISTRIBUTION:")
    print(f"   Home Wins (H): {result_dist.get('H', 0)} ({result_dist.get('H', 0)/len(pred_df)*100:.1f}%)")
    print(f"   Draws (D):     {result_dist.get('D', 0)} ({result_dist.get('D', 0)/len(pred_df)*100:.1f}%)")
    print(f"   Away Wins (A): {result_dist.get('A', 0)} ({result_dist.get('A', 0)/len(pred_df)*100:.1f}%)")

    return decile_stats, pred_df_sorted

if __name__ == '__main__':
    # Analyze all-time
    print("=" * 80)
    print("ANALYZING ALL-TIME LIGUE1 DATA")
    print("=" * 80)
    overall_deciles, _ = analyze_ligue1()

    # Analyze current season (2025/26)
    print("\n\n" + "=" * 80)
    print("ANALYZING 2025/26 SEASON TO DATE")
    print("=" * 80)
    current_deciles, _ = analyze_ligue1(season=2025)

    print("\n\n" + "=" * 80)
    print("✅ ANALYSIS COMPLETE")
    print("=" * 80)
