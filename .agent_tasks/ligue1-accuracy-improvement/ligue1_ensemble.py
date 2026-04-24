"""
Enhanced Ligue1 prediction model with feature engineering and ensemble methods.
Aims to improve accuracy from 54.5% to 59.5%+ (5% improvement).
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, log_loss
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import lightgbm as lgb
from pathlib import Path

def load_featured_data():
    """Load the featured dataset."""
    df = pd.read_csv("ligue1_features.csv")
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    return df

def prepare_features(df):
    """Prepare features for ML model."""
    # Feature columns (exclude target and metadata)
    exclude_cols = [
        'Div', 'Date', 'Time', 'HomeTeam', 'AwayTeam',
        'FTHG', 'FTAG', 'FTR', 'HTHG', 'HTAG', 'HTR',
        'B365H', 'B365D', 'B365A', 'BWH', 'BWD', 'BWA',
        'IWH', 'IWD', 'IWA', 'PSH', 'PSD', 'PSA',
        'WHH', 'WHD', 'WHA', 'VCH', 'VCD', 'VCA',
        'MaxH', 'MaxD', 'MaxA', 'AvgH', 'AvgD', 'AvgA',
        'B365>2.5', 'B365<2.5', 'P>2.5', 'P<2.5',
        'Max>2.5', 'Max<2.5', 'Avg>2.5', 'Avg<2.5',
        'AHh', 'B365AHH', 'B365AHA', 'PAHH', 'PAHA',
        'MaxAHH', 'MaxAHA', 'AvgAHH', 'AvgAHA',
        'source_file',
        # Bookmaker probabilities (will add separately)
        'bookmaker_prob_home', 'bookmaker_prob_draw', 'bookmaker_prob_away',
    ]

    # Also exclude all bookmaker odds columns (many are redundant)
    exclude_cols += [c for c in df.columns if 'B365' in c or 'BWH' in c or 'IW' in c or 'PS' in c or 'WH' in c or 'VCH' in c or 'Max' in c or 'Avg' in c or 'BF' in c or '1XB' in c or 'BV' in c or 'CL' in c or 'LB' in c]

    feature_cols = [c for c in df.columns if c not in exclude_cols]

    # Also exclude specific odds columns we don't need
    feature_cols = [c for c in feature_cols if not c.startswith('BFD') and not c.startswith('BFE')]

    print(f"Using {len(feature_cols)} features: {feature_cols[:10]}...")

    X = df[feature_cols].fillna(0)

    # Target: 0=Home win, 1=Draw, 2=Away win
    y = df['FTR'].map({'H': 0, 'D': 1, 'A': 2})

    return X, y, feature_cols

def add_elo_features(df):
    """Add ELO rating features (simulated)."""
    # In production, this would use actual ELO ratings from plugins/elo/ligue1_elo_rating.py
    # For now, compute a simple ELO-like rating

    teams = set(df['HomeTeam'].unique()) | set(df['AwayTeam'].unique())
    ratings = {team: 1500 for team in teams}

    home_elo = []
    away_elo = []
    elo_diff = []

    for _, game in df.iterrows():
        home = game['HomeTeam']
        away = game['AwayTeam']

        home_elo.append(ratings[home])
        away_elo.append(ratings[away])
        elo_diff.append(ratings[home] - ratings[away])

        # Update ratings (simplified)
        home_goals = game['FTHG']
        away_goals = game['FTAG']

        if home_goals > away_goals:
            winner_elo, loser_elo = ratings[home], ratings[away]
            ratings[home] = winner_elo + 20
            ratings[away] = loser_elo - 20
        elif home_goals < away_goals:
            winner_elo, loser_elo = ratings[away], ratings[home]
            ratings[away] = winner_elo + 20
            ratings[home] = loser_elo - 20
        else:
            # Draw: smaller adjustment
            if ratings[home] > ratings[away]:
                ratings[home] -= 10
                ratings[away] += 10

    df['home_elo'] = home_elo
    df['away_elo'] = away_elo
    df['elo_diff'] = elo_diff

    return df

def train_ensemble_models(X_train, y_train):
    """Train multiple models for ensemble."""
    models = {}

    # XGBoost
    print("Training XGboost...")
    xgb_model = xgb.XGBClassifier(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=6,
        random_state=42,
        objective='multi:softmax',
        num_class=3
    )
    xgb_model.fit(X_train, y_train)
    models['xgboost'] = xgb_model

    # LightGBM
    print("Training LightGBM...")
    lgb_model = lgb.LGBMClassifier(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=6,
        random_state=42,
        objective='multiclass',
        num_class=3
    )
    lgb_model.fit(X_train, y_train)
    models['lightgbm'] = lgb_model

    # Gradient Boosting
    print("Training GradientBoosting...")
    gb_model = GradientBoostingClassifier(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=6,
        random_state=42
    )
    gb_model.fit(X_train, y_train)
    models['gradient_boosting'] = gb_model

    return models

def predict_ensemble(models, X, df_subset=None, elo_weight=0.3, ml_weight=0.7):
    """Ensemble prediction blending ELO and ML models."""
    n_samples = len(X)
    n_classes = 3

    # Get ML predictions (average of all models)
    ml_probs = np.zeros((n_samples, n_classes))

    for name, model in models.items():
        probs = model.predict_proba(X)
        ml_probs += probs

    ml_probs /= len(models)

    # If we have ELO-like features, use them
    if df_subset is not None and 'elo_diff' in df_subset.columns:
        # Simple ELO-based probability
        elo_diff = df_subset['elo_diff'].values

        elo_probs = np.zeros((n_samples, n_classes))
        for i, diff in enumerate(elo_diff):
            # Convert ELO diff to probability (logistic function)
            p_home = 1 / (1 + np.exp(-diff/400))
            p_away = 1 / (1 + np.exp(diff/400))
            p_draw = 1 - p_home - p_away
            p_draw = max(0.15, p_draw)  # Floor for draw

            # Normalize
            total = p_home + p_away + p_draw
            elo_probs[i] = [p_home/total, p_draw/total, p_away/total]

        # Blend
        final_probs = elo_weight * elo_probs + ml_weight * ml_probs
    else:
        final_probs = ml_probs

    # Add bookmaker consensus if available
    if df_subset is not None and 'bookmaker_prob_home' in df_subset.columns:
        bookie_probs = np.column_stack([
            df_subset['bookmaker_prob_home'].values,
            df_subset['bookmaker_prob_draw'].values,
            df_subset['bookmaker_prob_away'].values
        ]) * 0.2  # 20% weight to bookmakers

        final_probs = final_probs * 0.8 + bookie_probs * 0.2

    # Ensure probabilities sum to 1
    final_probs = final_probs / final_probs.sum(axis=1, keepdims=True)

    # Predictions
    y_pred = np.argmax(final_probs, axis=1)

    return y_pred, final_probs

def evaluate_model(y_true, y_pred, probs, label="Model"):
    """Evaluate model performance."""
    accuracy = accuracy_score(y_true, y_pred)
    ll = log_loss(y_true, probs, labels=[0, 1, 2])

    print(f"\n{label} Results:")
    print(f"  Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
    print(f"  Log Loss: {ll:.4f}")

    # Per-class accuracy
    for cls, name in enumerate(['Home', 'Draw', 'Away']):
        mask = y_true == cls
        if mask.sum() > 0:
            cls_acc = (y_pred[mask] == cls).sum() / mask.sum()
            print(f"  {name} Accuracy: {cls_acc:.4f} ({mask.sum()} samples)")

    return accuracy, ll

def main():
    print("=" * 60)
    print("LIGUE1 PREDICTION ACCURACY IMPROVEMENT")
    print("=" * 60)

    # Load data
    print("\nLoading featured data...")
    df = load_featured_data()
    df = add_elo_features(df)

    # Split: train on older seasons, test on recent
    # Use 2021-2023 for training, 2024+ for testing
    train_mask = df['Date'] < '2024-01-01'
    test_mask = df['Date'] >= '2024-01-01'

    train_df = df[train_mask].copy()
    test_df = df[test_mask].copy()

    print(f"Train samples: {len(train_df)}")
    print(f"Test samples: {len(test_df)}")

    # Prepare features
    X_train, y_train, feature_cols = prepare_features(train_df)
    X_test, y_test, _ = prepare_features(test_df)

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train ensemble
    print("\nTraining ensemble models...")
    models = train_ensemble_models(X_train_scaled, y_train)

    # Evaluate on test set
    print("\n" + "=" * 60)
    print("TEST SET EVALUATION")
    print("=" * 60)

    # Baseline: Pure ELO (from elo_diff)
    elo_probs = np.zeros((len(test_df), 3))
    for i, diff in enumerate(test_df['elo_diff'].values):
        p_home = 1 / (1 + np.exp(-diff/400))
        p_away = 1 / (1 + np.exp(diff/400))
        p_draw = max(0.15, 1 - p_home - p_away)
        total = p_home + p_away + p_draw
        elo_probs[i] = [p_home/total, p_draw/total, p_away/total]

    elo_pred = np.argmax(elo_probs, axis=1)
    evaluate_model(y_test.values, elo_pred, elo_probs, "Pure ELO (Baseline)")

    # Bookmaker consensus
    bookie_probs = np.column_stack([
        test_df['bookmaker_prob_home'].values,
        test_df['bookmaker_prob_draw'].values,
        test_df['bookmaker_prob_away'].values
    ])
    bookie_pred = np.argmax(bookie_probs, axis=1)
    evaluate_model(y_test.values, bookie_pred, bookie_probs, "Bookmaker Consensus")

    # ML Ensemble
    ml_pred, ml_probs = predict_ensemble(models, X_test_scaled, test_df, elo_weight=0.0, ml_weight=1.0)
    evaluate_model(y_test.values, ml_pred, ml_probs, "ML Ensemble (Pure)")

    # Blended: ELO + ML + Bookmaker
    blended_pred, blended_probs = predict_ensemble(models, X_test_scaled, test_df, elo_weight=0.2, ml_weight=0.6)
    # Add bookmaker weight
    blended_probs = blended_probs * 0.8 + bookie_probs * 0.2
    blended_probs = blended_probs / blended_probs.sum(axis=1, keepdims=True)
    blended_pred = np.argmax(blended_probs, axis=1)
    acc, ll = evaluate_model(y_test.values, blended_pred, blended_probs, "BLENDED (ELO+ML+Bookmaker)")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Baseline (Pure ELO): ~54.5%")
    print(f"BLENDED Model: {acc*100:.2f}%")
    print(f"Improvement: {(acc - 0.545)*100:.2f}%")

    if acc >= 0.595:
        print("\n✓ SUCCESS: Achieved 5%+ improvement target!")
    else:
        print(f"\n✗ Need {(0.595 - acc)*100:.2f}% more to reach target")

    return acc

if __name__ == "__main__":
    main()
