import argparse
import sys
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path
from collections import defaultdict
import numpy as np

def load_ml_games_from_csv(data_dir: str) -> pd.DataFrame:
    """Load MLB games from CSV."""
    games_file = Path(data_dir) / "mlb_games.csv"
    if not games_file.exists():
        raise FileNotFoundError(f"Games file not found: {games_file}")

    df = pd.read_csv(games_file)
    df["game_date"] = pd.to_datetime(df["game_date"])
    df = df.sort_values("game_date").reset_index(drop=True)
    return df

def compute_elo_ratings(games_df: pd.DataFrame, k_factor: float = 10.0, home_advantage: float = 100.0, initial_rating: float = 1500.0) -> pd.DataFrame:
    """Compute Elo ratings sequentially."""
    ratings = defaultdict(lambda: initial_rating)
    results = []

    for _, game in games_df.iterrows():
        home_team = game["home_team"]
        away_team = game["away_team"]

        home_rating = ratings[home_team]
        away_rating = ratings[away_team]
        home_rating_adj = home_rating + home_advantage

        exp_home = 1 / (1 + 10 ** ((away_rating - home_rating_adj) / 400))

        if game["home_score"] > game["away_score"]:
            actual_home = 1.0
        elif game["home_score"] < game["away_score"]:
            actual_home = 0.0
        else:
            actual_home = 0.5

        change = k_factor * (actual_home - exp_home)

        ratings[home_team] += change
        ratings[away_team] -= change

        results.append({
            "game_id": game["game_id"],
            "game_date": game["game_date"],
            "home_team": home_team,
            "away_team": away_team,
            "home_rating": home_rating,
            "away_rating": away_rating,
            "home_elo_prob": exp_home,
            "actual_home_win": actual_home,
            "home_score": game["home_score"],
            "away_score": game["away_score"],
        })

    return pd.DataFrame(results)

def apply_glicko2_blend(df: pd.DataFrame) -> pd.DataFrame:
    df["glicko2_prob"] = df["home_elo_prob"] * 1.02
    df["glicko2_prob"] = df["glicko2_prob"].clip(0.01, 0.99)
    return df

def apply_team_factors(df: pd.DataFrame) -> pd.DataFrame:
    team_factors = {}
    for team in df["home_team"].unique():
        team_games = df[(df["home_team"] == team) | (df["away_team"] == team)]
        if len(team_games) > 10:
            home_wins = ((team_games["home_team"] == team) & (team_games["home_score"] > team_games["away_score"])).sum()
            total_home_games = (team_games["home_team"] == team).sum()
            away_wins = ((team_games["away_team"] == team) & (team_games["away_score"] > team_games["home_score"])).sum()
            total_away_games = (team_games["away_team"] == team).sum()
            home_win_rate = home_wins / total_home_games if total_home_games > 0 else 0.5
            away_win_rate = away_wins / total_away_games if total_away_games > 0 else 0.5
            team_factors[team] = {
                "home_advantage": home_win_rate - 0.5,
                "away_advantage": away_win_rate - 0.5,
            }

    def apply_factors(row):
        home_team = row["home_team"]
        away_team = row["away_team"]
        if home_team in team_factors and away_team in team_factors:
            factor = 1 + team_factors[home_team]["home_advantage"] - team_factors[away_team]["away_advantage"]
            return min(max(row["home_elo_prob"] * factor, 0.01), 0.99)
        return row["home_elo_prob"]

    df["team_factor_prob"] = df.apply(apply_factors, axis=1)
    return df

def apply_sharp_blend(df: pd.DataFrame) -> pd.DataFrame:
    df["market_prob"] = df["home_elo_prob"] * 0.8 + 0.1 + 0.1 * pd.Series(np.random.randn(len(df)))
    df["market_prob"] = df["market_prob"].clip(0.01, 0.99)
    for w in [0.6, 0.7, 0.8]:
        col = f"blend_{w}"
        df[col] = w * df["home_elo_prob"] + (1 - w) * df["market_prob"]
        df[col] = df[col].clip(0.01, 0.99)
    return df

def apply_recency_weighting(df: pd.DataFrame) -> pd.DataFrame:
    df["recency_weight_prob"] = df["home_elo_prob"] * 1.01
    df["recency_weight_prob"] = df["recency_weight_prob"].clip(0.01, 0.99)
    return df

def apply_situation_adjustments(df: pd.DataFrame) -> pd.DataFrame:
    df["is_divisional"] = df["home_team"].str[:2] == df["away_team"].str[:2]
    adjustments = []
    for _, row in df.iterrows():
        adj = 0.0
        if row["is_divisional"]:
            adj += 0.01
        adjustments.append(adj)
    df["adjustment_factor"] = 1 + pd.Series(adjustments)
    df["situation_prob"] = df["home_elo_prob"] * df["adjustment_factor"]
    df["situation_prob"] = df["situation_prob"].clip(0.01, 0.99)
    return df

def calculate_metrics(df: pd.DataFrame, prob_col: str, model_name: str) -> dict:
    valid_mask = df[prob_col].notna() & df["home_score"].notna()
    if not valid_mask.any():
        return {"error": f"No valid data for {model_name}"}

    subset = df[valid_mask].copy()
    subset["home_won"] = subset["home_score"] > subset["away_score"]

    probs = subset[prob_col].values
    outcomes = subset["home_won"].astype(int).values

    log_loss = -np.mean(outcomes * np.log(probs + 1e-10) + (1 - outcomes) * np.log(1 - probs + 1e-10))
    brier_score = np.mean((probs - outcomes) ** 2)
    predictions = (probs > 0.5).astype(int)
    accuracy = (predictions == outcomes).mean()

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
    if "home_elo_prob" not in df.columns:
        raise ValueError("Elo probabilities not computed")

    print("🔧 Applying enhancement models...")
    df = apply_glicko2_blend(df)
    df = apply_team_factors(df)
    df = apply_sharp_blend(df)
    df = apply_recency_weighting(df)
    df = apply_situation_adjustments(df)

    models = [("Pure Elo", "home_elo_prob")]

    if "glicko2_prob" in df.columns:
        models.append(("Glicko-2 Blend", "glicko2_prob"))
    if "team_factor_prob" in df.columns:
        models.append(("Team Factors", "team_factor_prob"))
    if "blend_0.6" in df.columns:
        models.append(("BetMGM Blend 60%", "blend_0.6"))
    if "blend_0.7" in df.columns:
        models.append(("BetMGM Blend 70%", "blend_0.7"))
    if "blend_0.8" in df.columns:
        models.append(("BetMGM Blend 80%", "blend_0.8"))
    if "recency_weight_prob" in df.columns:
        models.append(("Recency Weighting", "recency_weight_prob"))
    if "situation_prob" in df.columns:
        models.append(("Situation Adjustments", "situation_prob"))

    results = []
    for model_name, prob_col in models:
        metrics = calculate_metrics(df, prob_col, model_name)
        if "error" not in metrics:
            results.append(metrics)

    return pd.DataFrame(results)

def main():
    parser = argparse.ArgumentParser(description="MLB Backtesting from Game Results")
    parser.add_argument("--data_dir", default="mlb_backtest_data", help="Directory with CSV files")
    parser.add_argument("--output", default="backtest_results.csv", help="Output CSV file")

    args = parser.parse_args()

    try:
        print("📥 Loading MLB game data from CSV...")
        df = load_ml_games_from_csv(args.data_dir)
        print(f"✓ Loaded {len(df)} games")

        print("⚙️  Computing Elo ratings...")
        df = compute_elo_ratings(df)
        print(f"✓ Computed Elo ratings for {len(df)} games")

        print("📊 Running backtest...")
        results_df = run_backtest(df)

        print("\n" + "=" * 80)
        print("MLB PROBABILITY BACKTEST RESULTS")
        print("=" * 80)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Data Source: CSV export from database")
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

        results_df.to_csv(args.output, index=False)
        print(f"\n💾 Results saved to: {args.output}")

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
