#!/usr/bin/env python3
"""
MLB Probability Backtesting Framework

Tests different probability models against historical MLB data (2021-present).
Compares pure Elo vs. enhanced models with:
- Glicko-2 blending
- Team-specific factors
- Sharp bookmaker blending
- Recency weighting
- Situation adjustments
"""

import sys
import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Add plugins directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugins"))

# Try to import database module if available
try:
    from db_manager import default_db
    HAS_DB = True
except ImportError as e:
    print(f"⚠️  Database module not available: {e}")
    HAS_DB = False

# Constants
SPORT = "mlb"
DATA_DIR = Path("/mnt/data2/nhlstats/data/mlb")
START_DATE = "2021-01-01"
END_DATE = datetime.now().strftime("%Y-%m-%d")

# Performance metrics to track
METRICS = [
    "log_loss",
    "brier_score",
    "accuracy",
    "precision",
    "recall",
    "f1_score",
    "expected_value",
    "roi"
]


def load_ml_data() -> pd.DataFrame:
    """
    Load MLB game data from files or database.
    Returns DataFrame with: game_id, game_date, home_team, away_team,
                           home_score, away_score, status,
                           elo_prob, market_prob, betmgm_prob, etc.
    """
    print("📥 Loading MLB data...")

    if HAS_DB:
        return load_from_database()
    else:
        return load_from_files()


def load_from_database() -> pd.DataFrame:
    """Load data from PostgreSQL database."""
    # Query to get all MLB games with probabilities and odds
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
        r.confidence,
        o.yes_ask as kalshi_yes_ask,
        o.no_ask as kalshi_no_ask,
        CASE
            WHEN r.elo_prob > 0.5 THEN r.elo_prob
            ELSE 1 - r.elo_prob
        END as win_prob,
        CASE
            WHEN r.market_prob > 0.5 THEN r.market_prob
            ELSE 1 - r.market_prob
        END as market_win_prob
    FROM unified_games g
    JOIN bet_recommendations r ON g.game_id = r.game_id
    LEFT JOIN game_odds o ON g.game_id = o.game_id
        AND o.bookmaker = 'Kalshi'
        AND o.market_name = 'moneyline'
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
    print(f"✓ Loaded {len(df)} MLB games from database")
    return df


def load_from_files() -> pd.DataFrame:
    """Load data from JSON files as fallback."""
    # This is a simplified version - in reality we'd need to reconstruct
    # probabilities from Elo ratings and game results
    print("⚠️  Loading from files (simplified version)")

    # Get list of all game files
    game_files = list(DATA_DIR.glob("schedule_*.json"))
    bet_files = list(DATA_DIR.glob("bets_*.json"))

    print(f"Found {len(game_files)} schedule files and {len(bet_files)} bet files")

    # For now, return empty DataFrame for demonstration
    return pd.DataFrame()


def calculate_glicko2_probabilities(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate probabilities using Glicko-2 ratings."""
    # This would require historical Glicko-2 ratings
    # For now, create a placeholder
    df["glicko2_prob"] = df["elo_prob"]  # Simplified
    return df


def calculate_team_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Add team-specific performance factors."""
    # Calculate team performance metrics from historical data
    team_factors = {}

    for team in set(df["home_team"]).union(df["away_team"]):
        home_games = df[df["home_team"] == team]
        away_games = df[df["away_team"] == team]

        # Example factors
        if len(home_games) > 10:
            home_win_rate = (home_games["home_score"] > home_games["away_score"]).mean()
            team_factors[team] = {
                "home_advantage": home_win_rate - 0.5,
                "offense_rating": (home_games["home_score"] / away_games["away_score"]).mean(),
            }

    # Apply factors to probabilities
    df["team_factor"] = df["home_team"].map(team_factors)
    return df


def calculate_sharp_blend(df: pd.DataFrame) -> pd.DataFrame:
    """Blend Elo with sharp bookmaker probabilities."""
    # Use BetMGM odds which are already in the data
    # Optimal weights vary by sport and season - we'll test different weights
    for w in [0.6, 0.7, 0.8]:
        col_name = f"blend_{w}"
        df[col_name] = w * df["elo_prob"] + (1 - w) * df["betmgm_prob"]
    return df


def calculate_recency_weight(df: pd.DataFrame) -> pd.DataFrame:
    """Apply recency weighting to games."""
    # Calculate days since each game
    df["game_date"] = pd.to_datetime(df["game_date"])
    df["days_ago"] = (datetime.now() - df["game_date"]).dt.days

    # Apply exponential decay weighting (more recent games weighted higher)
    # This would affect how we calculate Elo ratings themselves
    # For backtesting, we'd recalculate ratings with different decay factors
    df["recency_weight"] = np.exp(-0.01 * df["days_ago"])
    return df


def calculate_situation_adjustments(df: pd.DataFrame) -> pd.DataFrame:
    """Add situation-specific adjustments."""
    # Identify situations:
    # - Back-to-back games
    # - Rest days
    # - Playoff vs regular season
    # - Rivalry games

    # For now, add placeholder columns
    df["back_to_back"] = False  # Would need to check game schedule
    df["rest_days"] = 3  # Average rest days
    df["is_playoff"] = df["game_date"].dt.month.isin([10, 11])  # Approximate

    return df


def evaluate_probabilities(df: pd.DataFrame, models: Dict[str, str]) -> Dict:
    """Evaluate different probability models."""
    results = {}

    for model_name, prob_col in models.items():
        if prob_col not in df.columns:
            print(f"   Skipping {model_name}: {prob_col} not found")
            continue

        # Filter for games with valid probabilities
        valid_games = df[df[prob_col].notna()].copy()

        # Calculate metrics
        metrics = calculate_metrics(valid_games, prob_col)
        results[model_name] = metrics

    return results


def calculate_metrics(df: pd.DataFrame, prob_col: str) -> Dict:
    """Calculate performance metrics for a probability model."""
    # Actual outcomes: 1 if home team won, 0 if away team won
    df["home_won"] = df["home_score"] > df["away_score"]
    df["away_won"] = df["away_score"] > df["home_score"]

    # For probability calibration, we want probability of favorite winning
    # Use the probability for the team that was predicted to win
    # This is tricky with moneyline - need to know which side was predicted

    # For simplicity, let's assume we're always predicting the home team win probability
    # and we're evaluating calibration of that prediction
    probs = df[prob_col].values
    outcomes = df["home_won"].astype(int).values

    # Log loss
    log_loss = -np.mean(outcomes * np.log(probs + 1e-10) + (1 - outcomes) * np.log(1 - probs + 1e-10))

    # Brier score
    brier_score = np.mean((probs - outcomes) ** 2)

    # Accuracy (using a threshold, e.g., 0.5)
    predictions = (probs > 0.5).astype(int)
    accuracy = (predictions == outcomes).mean()

    # Expected value if we bet with Kelly fraction
    # Assume min odds of 1.9 (2.0 before vig)
    df["kelly_fraction"] = (probs - (1/1.9)) / (probs * (1 - 1/1.9)) if "kelly_fraction" in df else 0.01
    df["kelly_fraction"] = df["kelly_fraction"].clip(lower=0.01, upper=0.1)
    df["bet_size"] = 100 * df["kelly_fraction"]  # Assuming $100 bankroll
    df["payout"] = df["kelly_fraction"] * (1.9 if predictions == outcomes else -1)
    expected_value = df["payout"].sum()
    roi = expected_value / 100

    return {
        "log_loss": log_loss,
        "brier_score": brier_score,
        "accuracy": accuracy,
        "expected_value": expected_value,
        "roi_pct": roi * 100,
        "num_games": len(df),
    }


def compare_models() -> None:
    """Main function to compare all probability models."""
    print("=" * 80)
    print("MLB PROBABILITY BACKTESTING FRAMEWORK")
    print("=" * 80)
    print(f"Sport: {SPORT}")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"Period: {START_DATE} to {END_DATE}")
    print("-" * 80)

    # Load data
    df = load_ml_data()
    if df.empty:
        print("✗ No data loaded. Exiting.")
        return

    print(f"✓ Loaded {len(df)} games")
    print(f"   With Elo probabilities: {df['elo_prob'].notna().sum()}")
    print(f"   With market probabilities: {df['market_prob'].notna().sum()}")

    # Calculate enhanced probabilities
    print("\n🔧 Calculating enhanced probability models...")

    # 1. Glicko-2 blending
    df = calculate_glicko2_probabilities(df)

    # 2. Team-specific factors
    df = calculate_team_factors(df)

    # 3. Sharp bookmaker blending
    df = calculate_sharp_blend(df)

    # 4. Recency weighting
    df = calculate_recency_weight(df)

    # 5. Situation adjustments
    df = calculate_situation_adjustments(df)

    # Define models to test
    models = {
        "Pure Elo": "elo_prob",
        "Market Implied": "market_prob",  # From Kalshi
        "BetMGM Blend 60%": "blend_0.6",
        "BetMGM Blend 70%": "blend_0.7",
        "BetMGM Blend 80%": "blend_0.8",
        "Glicko-2 Blend": "glicko2_prob",
        "Elo + Team Factors": "elo_prob",  # Would need to be computed
    }

    # Evaluate all models
    print("\n📊 Evaluating models...")
    results = evaluate_probabilities(df, models)

    # Print comparison table
    print("\n📈 MODEL COMPARISON")
    print("-" * 80)
    print(f"{'Model':<25} {'Log Loss':<10} {'Brier':<10} {'Accuracy':<10} {'EV ($)':<10} {'ROI (%)':<10} {'Games':<6}")
    print("-" * 80)

    for model_name, metrics in sorted(results.items(), key=lambda x: x[1]["roi_pct"], reverse=True):
        print(f"{model_name:<25} "
              f"{metrics['log_loss']:<10.4f} "
              f"{metrics['brier_score']:<10.4f} "
              f"{metrics['accuracy']:<10.4f} "
              f"{metrics['expected_value']:<10.2f} "
              f"{metrics['roi_pct']:<10.2f} "
              f"{metrics['num_games']:<6}")

    print("=" * 80)

    # Save results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = Path(f"/mnt/data2/nhlstats/reports/mlb_backtest_{timestamp}.csv")

    # Convert results to DataFrame for saving
    results_df = pd.DataFrame.from_dict(results, orient="index")
    results_df.to_csv(output_file)
    print(f"\n💾 Results saved to: {output_file}")


if __name__ == "__main__":
    compare_models()
