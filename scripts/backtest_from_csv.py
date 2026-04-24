#!/usr/bin/env python3
"""
MLB Backtesting from CSV Files

This script runs backtests using exported CSV data, so it can be used
in any environment without database access.

Usage:
    python backtest_from_csv.py --data_dir mlb_backtest_data

It will load the CSV files and run the same analyses as before.
"""

import sys
from datetime import datetime
import pandas as pd
from pathlib import Path
import argparse

def load_mlb_data_from_csv(data_dir: str) -> pd.DataFrame:
    """Load MLB data from CSV files."""
    data_path = Path(data_dir)

    # Load games
    games_file = data_path / "mlb_games.csv"
    if not games_file.exists():
        raise FileNotFoundError(f"Games file not found: {games_file}")
    games_df = pd.read_csv(games_file)
    games_df["game_date"] = pd.to_datetime(games_df["game_date"])

    # Load Elo probabilities
    elo_file = data_path / "mlb_elo_probabilities.csv"
    if not elo_file.exists():
        raise FileNotFoundError(f"Elo probabilities file not found: {elo_file}")
    elo_df = pd.read_csv(elo_file)

    # Load market odds
    odds_file = data_path / "mlb_market_odds.csv"
    if not odds_file.exists():
        raise FileNotFoundError(f"Odds file not found: {odds_file}")
    odds_df = pd.read_csv(odds_file)

    # Merge all data
    df = pd.merge(games_df, elo_df, on="game_id", how="left")
    df = pd.merge(df, odds_df, on="game_id", how="left")

    # For simplicity, take the last known odds per game
    # In a real implementation, we'd use closing odds
    df = df.sort_values("last_update").groupby("game_id").last().reset_index()

    print(f"📊 Loaded data from: {data_dir}")
    print(f"   Games: {len(df)}")
    print(f"   With Elo probabilities: {df['elo_prob'].notna().sum()}")
    print(f"   With market probabilities: {df['market_prob'].notna().sum()}")
    print(f"   With BetMGM probabilities: {df['betmgm_prob'].notna().sum()}")

    return df


def calculate_sharp_blend(df: pd.DataFrame) -> pd.DataFrame:
    """Blend Elo with sharp bookmaker probabilities."""
    # Test different blend ratios
    for w in [0.6, 0.7, 0.8]:
        col = f"blend_{w}"
        if 'betmgm_prob' in df.columns:
            df[col] = w * df["elo_prob"] + (1 - w) * df["betmgm_prob"]
            df[col] = df[col].clip(0.01, 0.99)
    return df


def calculate_metrics(df: pd.DataFrame, prob_col: str, model_name: str) -> dict:
    """Calculate performance metrics for a probability model."""
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

    # ROI simulation (Kelly criterion, min odds 1.9)
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


def run_backtest(df: pd.DataFrame) -> pd.DataFrame:
    """Run backtest on provided DataFrame."""
    if "elo_prob" not in df.columns:
        raise ValueError("Elo probabilities not found in data")

    # Calculate enhanced probabilities
    df = calculate_sharp_blend(df)

    # Models to test
    models = [("Pure Elo", "elo_prob")]

    if "blend_0.6" in df.columns:
        models.append(("BetMGM Blend 60%", "blend_0.6"))
    if "blend_0.7" in df.columns:
        models.append(("BetMGM Blend 70%", "blend_0.7"))
    if "blend_0.8" in df.columns:
        models.append(("BetMGM Blend 80%", "blend_0.8"))

    # Evaluate each model
    results = []
    for model_name, prob_col in models:
        metrics = calculate_metrics(df, prob_col, model_name)
        if "error" not in metrics:
            results.append(metrics)

    return pd.DataFrame(results)


def print_results(results_df: pd.DataFrame) -> None:
    """Print formatted results table."""
    print("\n" + "=" * 80)
    print("MLB PROBABILITY BACKTEST RESULTS")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Data Source: CSV export")
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
    parser = argparse.ArgumentParser(description="MLB Backtesting from CSV files")
    parser.add_argument("--data_dir", default="mlb_backtest_data", help="Directory with CSV files")
    parser.add_argument("--output", default="backtest_results.csv", help="Output CSV file")

    args = parser.parse_args()

    try:
        # Load data from CSV
        df = load_mlb_data_from_csv(args.data_dir)

        # Run backtest
        results_df = run_backtest(df)

        # Print results
        print_results(results_df)

        # Save results
        results_df.to_csv(args.output, index=False)
        print(f"\n💾 Results saved to: {args.output}")

        # Summary
        if not results_df.empty:
            best_model = results_df.loc[results_df["roi_pct"].idxmax()]
            print(f"\n🏆 Best Model: {best_model['model']} (ROI: {best_model['roi_pct']:.2f}%)")
        else:
            print("\n⚠️  No valid results to display")

        return 0

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    main()
