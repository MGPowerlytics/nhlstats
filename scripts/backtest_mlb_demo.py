#!/usr/bin/env python3
"""
MLB Probability Backtesting - Demo & Framework

This script demonstrates the backtesting methodology and can run in:
1. Demo mode: Uses synthetic data to show the approach
2. Database mode: Extracts real data when PostgreSQL is accessible

To use this script, ensure you have:
- Python 3.8+
- pandas, numpy
- Database access (optional)

Usage:
    python backtest_mlb_demo.py [--demo] [--db]
"""

import sys
import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import argparse

# Try to import database module
try:
    from db_manager import default_db
    HAS_DB = True
except ImportError:
    HAS_DB = False

print(f"⚙️  Database available: {HAS_DB}")

# Constants
SPORT = "mlb"
START_DATE = "2021-01-01"
END_DATE = datetime.now().strftime("%Y-%m-%d")

METRICS = ["log_loss", "brier_score", "accuracy", "roi_pct", "expected_value"]


def generate_synthetic_data() -> pd.DataFrame:
    """
    Generate synthetic MLB game data for demo purposes.
    Creates 1000 games with realistic probabilities and outcomes.
    """
    np.random.seed(42)
    n_games = 1000

    data = {
        "game_id": [f"MLG_{i:06d}" for i in range(n_games)],
        "game_date": pd.date_range("2021-01-01", periods=n_games, freq="1D"),
        "home_team": np.random.choice(["NYY", "BOS", "LAD", "NYM", "CHC", "ATL"], n_games),
        "away_team": np.random.choice(["NYY", "BOS", "LAD", "NYM", "CHC", "ATL"], n_games),
        "home_score": np.random.randint(0, 10, n_games),
        "away_score": np.random.randint(0, 10, n_games),
        "status": "Final",
    }

    df = pd.DataFrame(data)

    # Generate Elo probabilities (calibrated to be around 0.5 for evenly matched teams)
    # Add some variation to simulate team strength differences
    base_elo = 0.5
    team_strengths = pd.Series(
        np.random.normal(0, 0.1, len(df["home_team"].unique())),
        index=df["home_team"].unique()
    )
    df["home_elo_prob"] = base_elo + df["home_team"].map(team_strengths) - df["away_team"].map(team_strengths)
    df["home_elo_prob"] = df["home_elo_prob"].clip(0.01, 0.99)

    # Generate market probabilities (correlated with Elo but with noise)
    df["market_prob"] = df["home_elo_prob"] * 0.8 + np.random.normal(0.1, 0.1, n_games)
    df["market_prob"] = df["market_prob"].clip(0.01, 0.99)

    # Generate BetMGM probabilities (sharper, more accurate)
    df["betmgm_prob"] = df["home_elo_prob"] * 0.9 + np.random.normal(0, 0.05, n_games)
    df["betmgm_prob"] = df["betmgm_prob"].clip(0.01, 0.99)

    # Add some missing data to simulate real-world conditions
    df.loc[np.random.rand(n_games) < 0.1, ["market_prob", "betmgm_prob"]] = np.nan

    return df


def load_real_data() -> pd.DataFrame:
    """
    Load real MLB data from the database.
    This function is ready to use when database access is available.
    """
    if not HAS_DB:
        raise RuntimeError("Database module not available. Use demo mode instead.")

    query = """
    SELECT
        g.game_id,
        g.game_date,
        g.home_team_name as home_team,
        g.away_team_name as away_team,
        g.home_score,
        g.away_score,
        g.status,
        r.elo_prob,
        r.market_prob,
        r.betmgm_prob,
        r.edge,
        r.confidence
    FROM unified_games g
    JOIN bet_recommendations r ON g.game_id = r.game_id
    WHERE g.sport = 'MLB'
        AND g.game_date >= :start_date
        AND g.game_date <= :end_date
        AND g.status IN ('Final', 'Completed')
    ORDER BY g.game_date
    """

    params = {
        "start_date": START_DATE,
        "end_date": END_DATE
    }

    df = default_db.fetch_df(query, params)
    print(f"✓ Loaded {len(df)} real MLB games from database")
    return df


def calculate_glicko2_prob(df: pd.DataFrame) -> pd.DataFrame:
    """Placeholder for Glicko-2 probability calculation."""
    # In real implementation, this would use historical Glicko-2 ratings
    # For demo, we'll create a synthetic Glicko-2 probability
    df["glicko2_prob"] = df["elo_prob"] * 1.02  # Slight adjustment
    df["glicko2_prob"] = df["glicko2_prob"].clip(0.01, 0.99)
    return df


def calculate_sharp_blend(df: pd.DataFrame) -> pd.DataFrame:
    """Blend Elo with sharp bookmaker probabilities."""
    # Test different blend ratios
    for w in [0.6, 0.7, 0.8]:
        col = f"blend_{w}"
        df[col] = w * df["elo_prob"] + (1 - w) * df["betmgm_prob"]
        df[col] = df[col].clip(0.01, 0.99)
    return df


def calculate_metrics(df: pd.DataFrame, prob_col: str, model_name: str) -> Dict:
    """Calculate performance metrics for a probability model."""
    # Filter for valid probabilities
    valid_mask = df[prob_col].notna() & df["home_score"].notna()
    if not valid_mask.any():
        return {"error": f"No valid data for {model_name}"}

    subset = df[valid_mask].copy()
    subset["home_won"] = subset["home_score"] > subset["away_score"]

    probs = subset[prob_col].values
    outcomes = subset["home_won"].astype(int).values

    # Log loss
    log_loss = -np.mean(outcomes * np.log(probs + 1e-10) + (1 - outcomes) * np.log(1 - probs + 1e-10))

    # Brier score
    brier_score = np.mean((probs - outcomes) ** 2)

    # Accuracy (threshold 0.5)
    predictions = (probs > 0.5).astype(int)
    accuracy = (predictions == outcomes).mean()

    # ROI simulation (assuming betting with Kelly criterion)
    # Use min odds of 1.9 (2.0 before vig)
    subset["kelly"] = (probs - (1/1.9)) / (probs * (1 - 1/1.9))
    subset["kelly"] = subset["kelly"].clip(lower=0.01, upper=0.1)
    subset["payout"] = np.where(
        predictions == outcomes,
        subset["kelly"] * (1.9 - 1),
        -subset["kelly"]
    )
    expected_value = subset["payout"].sum()
    roi_pct = (expected_value / len(subset)) * 100 if len(subset) > 0 else 0

    return {
        "model": model_name,
        "log_loss": log_loss,
        "brier_score": brier_score,
        "accuracy": accuracy,
        "expected_value": expected_value,
        "roi_pct": roi_pct,
        "num_games": len(subset),
    }


def run_backtest(df: pd.DataFrame, mode: str = "demo") -> pd.DataFrame:
    """Run backtest on provided DataFrame."""
    print(f"\n📊 Running backtest ({mode})...")
    print(f"Games: {len(df)}")
    print(f"Valid games: {df.dropna(subset=['elo_prob']).shape[0]}")

    # Calculate enhanced probabilities
    if "elo_prob" in df.columns:
        df = calculate_glicko2_prob(df)
        df = calculate_sharp_blend(df)

    # Models to test
    models = []

    if "elo_prob" in df.columns:
        models.append(("Pure Elo", "elo_prob"))

    if "blend_0.6" in df.columns:
        models.append(("BetMGM Blend 60%", "blend_0.6"))

    if "blend_0.7" in df.columns:
        models.append(("BetMGM Blend 70%", "blend_0.7"))

    if "blend_0.8" in df.columns:
        models.append(("BetMGM Blend 80%", "blend_0.8"))

    if "glicko2_prob" in df.columns:
        models.append(("Glicko-2 Blend", "glicko2_prob"))

    # Evaluate each model
    results = []
    for model_name, prob_col in models:
        metrics = calculate_metrics(df, prob_col, model_name)
        if "error" not in metrics:
            results.append(metrics)

    # Create results DataFrame
    results_df = pd.DataFrame(results)
    return results_df


def print_results(results_df: pd.DataFrame) -> None:
    """Print formatted results table."""
    print("\n" + "=" * 80)
    print("MLB PROBABILITY BACKTEST RESULTS")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'DEMO' if results_df['model'].iloc[0].startswith('Pure') else 'REAL'}")
    print("-" * 80)
    print(f"{'Model':<25} {'Log Loss':<10} {'Brier':<10} {'Accuracy':<10} {'EV ($)':<10} {'ROI (%)':<10} {'Games':<6}")
    print("-" * 80)

    for _, row in results_df.iterrows():
        print(f"{row['model']:<25} "
              f"{row['log_loss']:<10.4f} "
              f"{row['brier_score']:<10.4f} "
              f"{row['accuracy']:<10.4f} "
              f"{row['expected_value']:<10.2f} "
              f"{row['roi_pct']:<10.2f} "
              f"{row['num_games']:<6}")

    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="MLB Probability Backtesting")
    parser.add_argument("--demo", action="store_true", help="Run in demo mode with synthetic data")
    parser.add_argument("--db", action="store_true", help="Run with real database data (if available)")
    args = parser.parse_args()

    # Generate or load data
    if args.demo:
        print("🎯 RUNNING IN DEMO MODE")
        df = generate_synthetic_data()
        mode = "demo"
    elif args.db and HAS_DB:
        print("🎯 RUNNING WITH REAL DATABASE DATA")
        try:
            df = load_real_data()
            mode = "real"
        except Exception as e:
            print(f"✗ Error loading database data: {e}")
            print("Switching to demo mode...")
            df = generate_synthetic_data()
            mode = "demo"
    else:
        print("⚠️  No valid mode specified. Running demo mode by default.")
        df = generate_synthetic_data()
        mode = "demo"

    # Run backtest
    results_df = run_backtest(df, mode)

    # Print results
    print_results(results_df)

    # Save results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = Path(f"/mnt/data2/nhlstats/reports/mlb_backtest_{timestamp}.csv")
    results_df.to_csv(output_file, index=False)
    print(f"\n💾 Results saved to: {output_file}")

    # Summary
    best_model = results_df.loc[results_df["roi_pct"].idxmax()]
    print(f"\n🏆 Best Model: {best_model['model']} (ROI: {best_model['roi_pct']:.2f}%)")


if __name__ == "__main__":
    main()
