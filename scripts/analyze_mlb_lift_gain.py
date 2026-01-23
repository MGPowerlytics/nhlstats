#!/usr/bin/env python3
"""
Lift/Gain Analysis for MLB Elo Ratings.
Generates charts for overall performance and season-by-season breakdown.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import duckdb
import sys
from pathlib import Path

# Add plugins to path
sys.path.append('plugins')
from plugins.elo import MLBEloRating

def load_mlb_games():
    """Load MLB games from DuckDB."""
    conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)
    query = """
        SELECT
            game_date,
            season,
            home_team,
            away_team,
            home_score,
            away_score,
            CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
        FROM mlb_games
        WHERE status = 'Final'
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
        ORDER BY game_date
    """
    df = conn.execute(query).fetchdf()
    conn.close()
    return df

def generate_predictions(games_df):
    """Generate Elo predictions for all games."""
    elo = MLBEloRating(k_factor=20, home_advantage=50)

    probs = []

    # Iterate through all games to simulate season
    for _, game in games_df.iterrows():
        # Predict
        prob = elo.predict(game['home_team'], game['away_team'])
        probs.append(prob)

        # Update
        elo.update(game['home_team'], game['away_team'],
                   game['home_score'], game['away_score'])

    games_df['elo_prob'] = probs
    return games_df

def calculate_deciles(df):
    """Calculate lift/gain metrics by decile."""
    df = df.copy()
    df['decile'] = pd.qcut(df['elo_prob'], q=10, labels=False, duplicates='drop') + 1

    baseline = df['home_win'].mean()
    results = []

    for decile in sorted(df['decile'].unique()):
        subset = df[df['decile'] == decile]
        games = len(subset)
        wins = subset['home_win'].sum()
        win_rate = wins / games
        avg_prob = subset['elo_prob'].mean()
        lift = win_rate / baseline if baseline > 0 else 0

        results.append({
            'decile': decile,
            'games': games,
            'wins': wins,
            'win_rate': win_rate,
            'avg_prob': avg_prob,
            'lift': lift,
            'baseline': baseline
        })

    return pd.DataFrame(results)

def plot_charts(overall_stats, season_stats, output_dir='data'):
    """Generate visualization charts."""
    output_dir = Path(output_dir)

    # 1. Overall Lift Chart
    plt.figure(figsize=(10, 6))
    plt.bar(overall_stats['decile'], overall_stats['lift'], color='#002D72', alpha=0.7)
    plt.axhline(1.0, color='r', linestyle='--', label='Baseline')
    plt.xlabel('Probability Decile (1=Low, 10=High)')
    plt.ylabel('Lift')
    plt.title('MLB Elo Model Lift by Decile (Overall)')
    plt.legend()
    plt.grid(axis='y', alpha=0.3)
    plt.savefig(output_dir / 'mlb_lift_overall.png')
    plt.close()

    # 2. Calibration Chart
    plt.figure(figsize=(8, 8))
    plt.scatter(overall_stats['avg_prob'], overall_stats['win_rate'], s=overall_stats['games']/5, color='#002D72')
    plt.plot([0, 1], [0, 1], 'r--', label='Perfect Calibration')
    plt.xlabel('Predicted Probability')
    plt.ylabel('Actual Win Rate')
    plt.title('MLB Elo Model Calibration')
    plt.legend()
    plt.grid(alpha=0.3)
    plt.savefig(output_dir / 'mlb_calibration.png')
    plt.close()

    # 3. Season Lift Comparison
    plt.figure(figsize=(12, 6))
    for season, stats in season_stats.items():
        plt.plot(stats['decile'], stats['lift'], marker='o', label=str(season))

    plt.axhline(1.0, color='black', linestyle='--', alpha=0.5)
    plt.xlabel('Probability Decile')
    plt.ylabel('Lift')
    plt.title('MLB Elo Lift by Season')
    plt.legend()
    plt.grid(alpha=0.3)
    plt.savefig(output_dir / 'mlb_lift_by_season.png')
    plt.close()

def main():
    print("⚾ MLB Lift/Gain Analysis")
    print("=" * 60)

    # 1. Load Data
    print("Loading games from database...")
    games = load_mlb_games()
    print(f"Loaded {len(games)} games")

    # 2. Generate Predictions
    print("Running Elo simulation...")
    games_with_preds = generate_predictions(games)

    # 3. Overall Analysis
    print("\nOverall Performance:")
    overall_deciles = calculate_deciles(games_with_preds)
    print(overall_deciles[['decile', 'games', 'win_rate', 'lift']].to_string(index=False))

    # 4. Season Analysis
    season_stats = {}
    print("\nPerformance by Season:")
    for season in sorted(games_with_preds['season'].unique()):
        season_df = games_with_preds[games_with_preds['season'] == season]
        if len(season_df) < 100: continue

        print(f"\nSeason {season}:")
        stats = calculate_deciles(season_df)
        season_stats[season] = stats

        # Print top decile stats
        top = stats.iloc[-1]
        print(f"  Top Decile: Win Rate {top['win_rate']:.1%}, Lift {top['lift']:.2f}x ({int(top['games'])} games)")

    # 5. Charts
    print("\nGenerating charts...")
    plot_charts(overall_deciles, season_stats)
    print("Charts saved to data/mlb_lift_overall.png, data/mlb_calibration.png, and data/mlb_lift_by_season.png")

if __name__ == "__main__":
    main()
