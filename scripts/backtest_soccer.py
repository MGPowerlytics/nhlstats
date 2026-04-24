#!/usr/bin/env python3
"""
Soccer Backtesting Framework

Tests different probability models against historical soccer data (EPL, Ligue1, etc.).
Compares pure Elo vs. enhanced models with:
- 3-way outcome prediction (Home, Draw, Away)
- Margin of Victory adjustments
- Team-specific factors
- Bookmaker blending
- Recency weighting
- Situation adjustments
"""

import argparse
import sys
from datetime import datetime
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict

def load_soccer_games_from_csv(data_dir: str, league: str = "F1") -> pd.DataFrame:
    """Load soccer games from CSV files in data_dir.

    Args:
        data_dir: Directory containing CSV files
        league: League identifier (F1 for Ligue1, E0 for EPL, etc.)

    Returns:
        DataFrame with game data
    """
    csv_files = list(Path(data_dir).glob("F1_*.csv"))  # For Ligue1; adjust pattern for other leagues

    if not csv_files:
        # Fallback to all CSV files
        csv_files = list(Path(data_dir).glob("*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in {data_dir}")

    df_list = []
    for csv_file in sorted(csv_files):
        df = pd.read_csv(csv_file)
        df["source_file"] = csv_file.name
        df_list.append(df)

    if not df_list:
        raise ValueError(f"No data loaded from {data_dir}")

    df = pd.concat(df_list, ignore_index=True)

    # Convert date column (assuming column named 'Date')
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%y', errors='coerce')
    elif 'date' in df.columns:
        df['Date'] = pd.to_datetime(df['date'], format='%d/%m/%y', errors='coerce')
    else:
        raise ValueError("Could not find date column in CSV files")

    # Sort by date
    df = df.sort_values('Date').reset_index(drop=True)

    return df

def compute_soccer_elo_ratings(games_df: pd.DataFrame, k_factor: float = 20.0, home_advantage: float = 60.0, initial_rating: float = 1500.0) -> pd.DataFrame:
    """Compute Elo ratings sequentially for soccer games.

    Args:
        games_df: DataFrame with game data
        k_factor: K-factor for rating updates
        home_advantage: Home advantage in Elo points
        initial_rating: Initial rating for new teams

    Returns:
        DataFrame with computed Elo ratings and probabilities
    """
    ratings = defaultdict(lambda: initial_rating)
    results = []

    for idx, game in games_df.iterrows():
        home_team = game['HomeTeam']
        away_team = game['AwayTeam']

        # Skip if team names are missing or are these placeholders
        if not home_team or not away_team:
            continue
        if home_team in ['', 'None', 'nan'] or away_team in ['', 'None', 'nan']:
            continue

        home_rating = ratings[home_team]
        away_rating = ratings[away_team]
        home_rating_adj = home_rating + home_advantage

        # Calculate expected score for home team (win probability)
        # Using logistic function with 400 scaling factor
        exp_home = 1 / (1 + 10 ** ((away_rating - home_rating_adj) / 400))

        # Determine actual outcome:
        # 1.0 = home win, 0.0 = away win, 0.5 = draw
        home_score = game.get('FTHG')
        away_score = game.get('FTAG')

        if not isinstance(home_score, (int, float)) or not isinstance(away_score, (int, float)):
            continue

        if home_score > away_score:
            actual_home = 1.0
            result = 'H'
        elif away_score > home_score:
            actual_home = 0.0
            result = 'A'
        else:
            actual_home = 0.5
            result = 'D'

        # Calculate rating change
        change = k_factor * (actual_home - exp_home)

        # Update ratings (zero-sum)
        ratings[home_team] += change
        ratings[away_team] -= change

        results.append({
            'game_id': idx,
            'Date': game['Date'],
            'home_team': home_team,
            'away_team': away_team,
            'home_rating': home_rating,
            'away_rating': away_rating,
            'home_elo_prob': exp_home,
            'draw_prob': 0.5,  # Placeholder, will be calculated later
            'away_elo_prob': 1 - exp_home,
            'actual_result': result,
            'home_score': home_score,
            'away_score': away_score,
            'k_factor': k_factor,
            'home_advantage': home_advantage,
        })

    return pd.DataFrame(results)

def calculate_3way_probs(df: pd.DataFrame, draw_coefficient: float = 0.25, draw_width: float = 200.0) -> pd.DataFrame:
    """Calculate 3-way probabilities (home, draw, away) using soccer-specific formula.

    Args:
        df: DataFrame with game data including home_elo_prob
        draw_coefficient: Peak draw probability (at 0 rating difference)
        draw_width: Controls how quickly draw probability drops as rating gap grows

    Returns:
        DataFrame with updated probabilities
    """
    probs_list = []
    for _, row in df.iterrows():
        home_rating = row['home_rating']
        away_rating = row['away_rating']
        home_rating_adj = home_rating + row['home_advantage']
        dr = home_rating_adj - away_rating

        # Expected points (standard Elo win prob + 0.5 * draw prob)
        expected_points = 1 / (1 + 10 ** (dr / 400))

        # Estimate draw probability using Gaussian-like function
        p_draw = draw_coefficient * np.exp(-((dr / draw_width) ** 2))

        # Clamp draw probability to reasonable bounds for soccer
        p_draw = max(0.05, min(0.35, p_draw))

        # Derive win/loss probabilities
        p_home = max(0.01, expected_points - 0.5 * p_draw)
        p_away = max(0.01, 1.0 - p_home - p_draw)

        # Normalize to sum to 1.0
        total = p_home + p_draw + p_away
        p_home_norm = p_home / total
        p_draw_norm = p_draw / total
        p_away_norm = p_away / total

        probs_list.append({
            'draw_prob': p_draw_norm,
            'away_elo_prob': p_away_norm
        })

    probs_df = pd.DataFrame(probs_list)
    df = pd.concat([df, probs_df], axis=1)
    return df

def calculate_3way_metrics(df: pd.DataFrame, prob_col: str, model_name: str) -> dict:
    """Calculate metrics for 3-way prediction.

    Args:
        df: DataFrame with game data
        prob_col: Base probability column name (e.g., 'home_elo_prob')
        model_name: Name of the model

    Returns:
        Dictionary with metrics
    """
    # Define the three probability columns
    home_prob_col = f"{prob_col}_home"
    draw_prob_col = f"{prob_col}_draw"
    away_prob_col = f"{prob_col}_away"

    valid_mask = df[home_prob_col].notna() & df['home_score'].notna()
    if not valid_mask.any():
        return {"error": f"No valid data for {model_name}"}

    subset = df[valid_mask].copy()

    # Determine actual outcomes: 0 = away win, 1 = draw, 2 = home win
    subset['actual_home'] = (subset['home_score'] > subset['away_score']).astype(int)
    subset['actual_draw'] = (subset['home_score'] == subset['away_score']).astype(int)
    subset['actual_away'] = (subset['home_score'] < subset['away_score']).astype(int)

    # Extract probabilities
    home_probs = subset[home_prob_col].values
    draw_probs = subset[draw_prob_col].values
    away_probs = subset[away_prob_col].values

    # Calculate log loss for 3 classes
    n = len(subset)
    log_loss = 0.0
    for i in range(n):
        # One-hot encoding of actual outcome
        actual = [subset['actual_away'].iloc[i], subset['actual_draw'].iloc[i], subset['actual_home'].iloc[i]]
        preds = [away_probs[i], draw_probs[i], home_probs[i]]
        for j in range(3):
            if actual[j] == 1:
                log_loss -= np.log(preds[j] + 1e-10)
                break

    log_loss /= n

    # Calculate Brier score (mean squared error for 3 classes)
    brier_score = 0.0
    for i in range(n):
        actual = [subset['actual_away'].iloc[i], subset['actual_draw'].iloc[i], subset['actual_home'].iloc[i]]
        preds = [away_probs[i], draw_probs[i], home_probs[i]]
        brier_score += np.sum((np.array(actual) - np.array(preds)) ** 2)
    brier_score /= n

    # Calculate accuracy
    predictions = []
    for i in range(n):
        probs = [away_probs[i], draw_probs[i], home_probs[i]]
        predictions.append(np.argmax(probs))

    actuals = []
    for i in range(n):
        actual = [subset['actual_away'].iloc[i], subset['actual_draw'].iloc[i], subset['actual_home'].iloc[i]]
        actuals.append(np.argmax(actual))

    accuracy = np.mean(np.array(predictions) == np.array(actuals))

    # For expected value and ROI, we'd need bet simulation
    # For now, return placeholder values
    expected_value = 0.0
    roi_pct = 0.0

    return {
        "model": model_name,
        "log_loss": log_loss,
        "brier_score": brier_score,
        "accuracy": accuracy,
        "expected_value": expected_value,
        "roi_pct": roi_pct,
        "num_games": n,
    }

def apply_mov_multiplier(df: pd.DataFrame, mov_constant: float = 2.2, mov_scaling: float = 0.001) -> pd.DataFrame:
    """Apply Margin of Victory multiplier to probabilities.

    Args:
        df: DataFrame with game data
        mov_constant: Constant in MOV formula
        mov_scaling: Scaling factor for Elo difference

    Returns:
        DataFrame with updated probabilities
    """
    def calculate_mov_factor(row):
        if row['home_score'] == row['away_score']:
            return 1.0

        mov = abs(row['home_score'] - row['away_score'])
        margin = min(max(mov, 1), 10)  # Cap MOV effect

        # Use log(margin + 1) to dampen large blowouts
        mov_effect = 1 + mov_scaling * margin * np.log(mov + 1)
        return mov_effect

    df['mov_factor'] = df.apply(calculate_mov_factor, axis=1)

    # Apply MOV to home win probability
    df['home_elo_prob_mov'] = df['home_elo_prob'] * df['mov_factor']
    df['home_elo_prob_mov'] = df['home_elo_prob_mov'].clip(0.01, 0.99)
    df['away_elo_prob_mov'] = 1 - df['home_elo_prob_mov']

    return df

def apply_recency_weighting(df: pd.DataFrame, days_back: int = 365) -> pd.DataFrame:
    """Apply recency weighting to games (more weight to recent games).

    Args:
        df: DataFrame with game data
        days_back: Lookback period for recency weighting

    Returns:
        DataFrame with recency weights
    """
    if 'Date' not in df.columns:
        return df

    latest_date = df['Date'].max()
    df['days_since'] = (latest_date - df['Date']).dt.days
    df['recency_weight'] = np.clip(1.0 - (df['days_since'] / days_back), 0.5, 1.0)

    # Apply weighting to probabilities
    df['home_elo_prob_recency'] = df['home_elo_prob'] * df['recency_weight']
    df['home_elo_prob_recency'] = df['home_elo_prob_recency'].clip(0.01, 0.99)
    df['away_elo_prob_recency'] = 1 - df['home_elo_prob_recency']

    return df

def apply_team_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Apply team-specific factors based on historical performance.

    Args:
        df: DataFrame with game data

    Returns:
        DataFrame with team factor adjustments
    """
    team_factors = {}

    for team in df['home_team'].unique():
        team_games = df[(df['home_team'] == team) | (df['away_team'] == team)]
        if len(team_games) > 10:
            home_wins = ((team_games['home_team'] == team) & (team_games['home_score'] > team_games['away_score'])).sum()
            total_home_games = (team_games['home_team'] == team).sum()
            away_wins = ((team_games['away_team'] == team) & (team_games['away_score'] > team_games['home_score'])).sum()
            total_away_games = (team_games['away_team'] == team).sum()

            home_win_rate = home_wins / total_home_games if total_home_games > 0 else 0.5
            away_win_rate = away_wins / total_away_games if total_away_games > 0 else 0.5

            team_factors[team] = {
                'home_advantage': home_win_rate - 0.5,
                'away_advantage': away_win_rate - 0.5,
            }

    def apply_factors(row):
        home_team = row['home_team']
        away_team = row['away_team']
        if home_team in team_factors and away_team in team_factors:
            factor = 1 + team_factors[home_team]['home_advantage'] - team_factors[away_team]['away_advantage']
            return min(max(row['home_elo_prob'] * factor, 0.01), 0.99)
        return row['home_elo_prob']

    df['team_factor_prob'] = df.apply(apply_factors, axis=1)
    return df

def apply_bookmaker_blend(df: pd.DataFrame, blend_weight: float = 0.7) -> pd.DataFrame:
    """Blend Elo probabilities with synthetic bookmaker probabilities.

    Args:
        df: DataFrame with game data
        blend_weight: Weight for Elo vs synthetic market

    Returns:
        DataFrame with blended probabilities
    """
    # Create synthetic market probabilities (for demonstration)
    # In practice, you'd use actual market odds
    df['market_prob'] = df['home_elo_prob'] * 0.8 + 0.1 + 0.05 * np.random.randn(len(df))
    df['market_prob'] = df['market_prob'].clip(0.01, 0.99)

    df[f'blend_{blend_weight}'] = blend_weight * df['home_elo_prob'] + (1 - blend_weight) * df['market_prob']
    df[f'blend_{blend_weight}'] = df[f'blend_{blend_weight}'].clip(0.01, 0.99)

    return df

def apply_situation_adjustments(df: pd.DataFrame) -> pd.DataFrame:
    """Apply situation-based adjustments (e.g., divisional games).

    Args:
        df: DataFrame with game data

    Returns:
        DataFrame with situation adjustments
    """
    # For soccer, we could adjust for factors like:
    # - Rivalry games
    # - European competition fatigue
    # - Home/away form streaks
    # For now, add a small random adjustment to test
    df['situation_factor'] = 1.0  # Placeholder
    df['situation_prob'] = df['home_elo_prob'] * df['situation_factor']
    df['situation_prob'] = df['situation_prob'].clip(0.01, 0.99)
    return df

def main():
    parser = argparse.ArgumentParser(description="Soccer Backtesting from CSV Data")
    parser.add_argument("--data_dir", default="data/ligue1", help="Directory with CSV files")
    parser.add_argument("--output", default="soccer_backtest_results.csv", help="Output CSV file")
    parser.add_argument("--league", default="F1", help="League code (F1=Ligue1, E0=Premier League, etc.)")
    parser.add_argument("--k_factor", type=float, default=20.0, help="K-factor for Elo updates")
    parser.add_argument("--home_advantage", type=float, default=60.0, help="Home advantage in Elo points")
    parser.add_argument("--initial_rating", type=float, default=1500.0, help="Initial rating for teams")
    parser.add_argument("--draw_coefficient", type=float, default=0.25, help="Draw coefficient for probability calculation")
    parser.add_argument("--draw_width", type=float, default=200.0, help="Draw width for probability calculation")

    args = parser.parse_args()

    try:
        print(f"📥 Loading {args.league} game data from CSV...")
        df = load_soccer_games_from_csv(args.data_dir, args.league)
        print(f"✓ Loaded {len(df)} games")

        print("⚙️  Computing Elo ratings...")
        df = compute_soccer_elo_ratings(df, args.k_factor, args.home_advantage, args.initial_rating)
        print(f"✓ Computed Elo ratings for {len(df)} games")

        print("📊 Calculating 3-way probabilities...")
        df = calculate_3way_probs(df, args.draw_coefficient, args.draw_width)

        print("🔧 Applying enhancement models...")
        df = apply_mov_multiplier(df)
        df = apply_recency_weighting(df)
        df = apply_team_factors(df)
        df = apply_bookmaker_blend(df, blend_weight=0.7)
        df = apply_situation_adjustments(df)

        print("📈 Running backtest...")
        models = []

        # Base Elo probabilities
        models.append(("Pure Elo", "home_elo_prob"))

        # MOV adjusted
        if "home_elo_prob_mov" in df.columns:
            models.append(("MOV Adjusted", "home_elo_prob_mov"))

        # Recency weighted
        if "home_elo_prob_recency" in df.columns:
            models.append(("Recency Weighted", "home_elo_prob_recency"))

        # Team factors
        if "team_factor_prob" in df.columns:
            models.append(("Team Factors", "team_factor_prob"))

        # Bookmaker blend
        if f"blend_{0.7}" in df.columns:
            models.append(("Bookmaker Blend 70%", f"blend_{0.7}"))

        # Situation adjustments
        if "situation_prob" in df.columns:
            models.append(("Situation Adjustments", "situation_prob"))

        results = []
        for model_name, prob_col in models:
            metrics = calculate_3way_metrics(df, prob_col, model_name)
            if "error" not in metrics:
                results.append(metrics)

        results_df = pd.DataFrame(results)

        print("\n" + "=" * 80)
        print("SOCCER PROBABILITY BACKTEST RESULTS")
        print("=" * 80)
        print(f"League: {args.league}")
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Data Source: CSV files from {args.data_dir}")
        print("-" * 80)
        print(f"{'Model':<30} {'Log Loss':<10} {'Brier':<10} {'Accuracy':<10} {'Games':<6}")
        print("-" * 80)

        for _, row in results_df.iterrows():
            print(f"{row['model']:<30} "
                  f"{row['log_loss']:<10.4f} "
                  f"{row['brier_score']:<10.4f} "
                  f"{row['accuracy']:<10.4f} "
                  f"{row['num_games']:<6}")

        print("=" * 80)

        results_df.to_csv(args.output, index=False)
        print(f"\n💾 Results saved to: {args.output}")

        if not results_df.empty:
            best_model = results_df.loc[results_df["accuracy"].idxmax()]
            print(f"\n🏆 Best Model: {best_model['model']} (Accuracy: {best_model['accuracy']:.2%})")
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
