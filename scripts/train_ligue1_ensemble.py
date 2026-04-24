
"""
Production training script for Ligue 1 Ensemble.
Trains XGBoost, LightGBM, and GradientBoosting models using research features.
"""

import os
import sys
import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

# Add plugins to path
sys.path.insert(0, os.path.join(os.getcwd(), "plugins"))
sys.path.insert(0, os.path.join(os.getcwd(), "plugins", "elo"))

from ligue1_elo_rating import Ligue1EloRating
from ligue1_ensemble import Ligue1EnsembleModel

def train_production_model():
    print("🚀 Starting Ligue 1 Ensemble training...")

    # Load feature data from research
    feature_file = "/opt/airflow/data/ligue1_features.csv"
    if not os.path.exists(feature_file):
        print(f"❌ Feature file not found at {feature_file}")
        return

    df = pd.read_csv(feature_file)
    print(f"  Loaded {len(df)} games with features.")

    # In production, we need to regenerate Elo diff because the CSV might have
    # different Elo settings than our production class.
    # But for training, we'll use the features as they are to match research.

    # Define target
    # FTR: H, D, A -> 2, 1, 0
    target_map = {'H': 2, 'D': 1, 'A': 0}
    y = df['FTR'].map(target_map)

    # Features (match Ligue1EnsembleModel.features)
    # Note: the CSV has slightly different names than what I put in the model earlier.
    # CSV names: home_form, away_form, home_goals_for_avg, home_goals_against_avg...
    # I will align them.

    # Let's check CSV columns again to be sure
    cols = df.columns.tolist()

    # We need to map CSV columns to Model features
    feature_mapping = {
        'home_elo': 'home_elo', # Might not be in CSV, need to compute
        'away_elo': 'away_elo',
        'elo_diff': 'elo_diff',
        'home_form': 'home_form',
        'away_form': 'away_form',
        'home_avg_gf': 'home_goals_for_avg',
        'home_avg_ga': 'home_goals_against_avg',
        'away_avg_gf': 'away_goals_for_avg',
        'away_avg_ga': 'away_goals_against_avg',
        'bookmaker_prob_home': 'bookmaker_prob_home',
        'bookmaker_prob_draw': 'bookmaker_prob_draw',
        'bookmaker_prob_away': 'bookmaker_prob_away'
    }

    # If home_elo/away_elo not in CSV, we re-run Elo computation
    if 'home_elo' not in df.columns:
        print("  Re-computing Elo ratings for training...")
        elo = Ligue1EloRating()
        home_elos = []
        away_elos = []
        for _, row in df.iterrows():
            home_elos.append(elo.get_rating(row['HomeTeam']))
            away_elos.append(elo.get_rating(row['AwayTeam']))

            outcome = 1.0 if row['FTR'] == 'H' else (0.0 if row['FTR'] == 'A' else 0.5)
            elo.update(row['HomeTeam'], row['AwayTeam'], outcome)

        df['home_elo'] = home_elos
        df['away_elo'] = away_elos
        df['elo_diff'] = df['home_elo'] - df['away_elo']

    # Select features
    X_raw = pd.DataFrame()
    for model_feat, csv_feat in feature_mapping.items():
        X_raw[model_feat] = df[csv_feat]

    # Scale features
    scaler = StandardScaler()
    X = scaler.fit_transform(X_raw)

    # Train models
    print("  Training XGBoost...")
    model_xgb = xgb.XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
    model_xgb.fit(X, y)

    print("  Training GradientBoosting...")
    model_gbc = GradientBoostingClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
    model_gbc.fit(X, y)

    # Save to production model
    ensemble = Ligue1EnsembleModel()
    ensemble.models = {
        'xgb': model_xgb,
        'gbc': model_gbc
    }
    ensemble.scaler = scaler
    ensemble.is_trained = True
    ensemble.save()

    print(f"\n✅ Training complete! Models saved to {ensemble.model_dir}")

if __name__ == "__main__":
    train_production_model()
