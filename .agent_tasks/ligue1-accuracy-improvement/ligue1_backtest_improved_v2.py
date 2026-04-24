"""
Improved Ligue1 backtesting with feature engineering and ensemble methods.
Targets 5%+ accuracy improvement (54.5% -> 59.5%+).
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, log_loss
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import lightgbm as lgb
from pathlib import Path
import sys
import argparse

def compute_elo_ratings(df):
    """Compute ELO ratings sequentially."""
    teams = set(df['HomeTeam'].unique()) | set(df['AwayTeam'].unique())
    ratings = {team: 1500 for team in teams}

    home_elo = []
    away_elo = []
    elo_diff = []

    for _, game in df.iterrows():
        home = game['HomeTeam']
        away = game['AwayTeam']

        home_rating = ratings[home]
        away_rating = ratings[away]

        home_elo.append(home_rating)
        away_elo.append(away_rating)
        elo_diff.append(home_rating - away_rating)

        # Expected scores
        exp_home = 1 / (1 + 10 ** ((away_rating - home_rating) / 400))

        # Actual score
        home_goals = game['FTHG']
        away_goals = game['FTAG']

        if home_goals > away_goals:
            actual_home = 1.0
            k = 30
        elif home_goals < away_goals:
            actual_home = 0.0
            k = 30
        else:
            actual_home = 0.5
            k = 20

        # Update
        ratings[home] = home_rating + k * (actual_home - exp_home)
        ratings[away] = ratings[away] + k * ((1 - actual_home) - (1 - exp_home))

    df = df.copy()
    df['home_elo'] = home_elo
    df['away_elo'] = away_elo
    df['elo_diff'] = elo_diff

    # ELO probabilities
    df['elo_prob_home'] = 1 / (1 + 10 ** ((df['away_elo'] - df['home_elo']) / 400))
    df['elo_prob_away'] = 1 / (1 + 10 ** ((df['home_elo'] - df['away_elo']) / 400))
    df['elo_prob_draw'] = (1 - df['elo_prob_home'] - df['elo_prob_away']).clip(0.15, 0.5)

    return df

def compute_team_form(df, window=5):
    """Add team form features."""
    df = df.copy()

    home_form = []
    away_form = []
    home_gf = []
    home_ga = []
    away_gf = []
    away_ga = []

    for idx, game in df.iterrows():
        home = game['HomeTeam']
        away = game['AwayTeam']
        date = game['Date']

        # Home team history
        home_hist = df[(df['Date'] < date) &
                      ((df['HomeTeam'] == home) | (df['AwayTeam'] == home))]
        home_recent = home_hist.tail(window)

        h_wins = 0
        h_goals_for = []
        h_goals_against = []

        for _, g in home_recent.iterrows():
            if g['HomeTeam'] == home:
                gf = g['FTHG']
                ga = g['FTAG']
            else:
                gf = g['FTAG']
                ga = g['FTHG']

            h_goals_for.append(gf)
            h_goals_against.append(ga)

            if gf > ga:
                h_wins += 1
            elif gf == ga:
                h_wins += 0.5

        home_form.append(h_wins / len(home_recent) if len(home_recent) > 0 else 0.5)
        home_gf.append(np.mean(h_goals_for) if h_goals_for else 1.0)
        home_ga.append(np.mean(h_goals_against) if h_goals_against else 1.0)

        # Away team history
        away_hist = df[(df['Date'] < date) &
                      ((df['HomeTeam'] == away) | (df['AwayTeam'] == away))]
        away_recent = away_hist.tail(window)

        a_wins = 0
        a_goals_for = []
        a_goals_against = []

        for _, g in away_recent.iterrows():
            if g['HomeTeam'] == away:
                gf = g['FTHG']
                ga = g['FTAG']
            else:
                gf = g['FTAG']
                ga = g['FTHG']

            a_goals_for.append(gf)
            a_goals_against.append(ga)

            if gf > ga:
                a_wins += 1
            elif gf == ga:
                a_wins += 0.5

        away_form.append(a_wins / len(away_recent) if len(away_recent) > 0 else 0.5)
        away_gf.append(np.mean(a_goals_for) if a_goals_for else 1.0)
        away_ga.append(np.mean(a_goals_against) if a_goals_against else 1.0)

    df['home_form'] = home_form
    df['away_form'] = away_form
    df['home_avg_gf'] = home_gf
    df['home_avg_ga'] = home_ga
    df['away_avg_gf'] = away_gf
    df['away_avg_ga'] = away_ga

    return df

def add_match_features(df):
    """Add match-specific features."""
    df = df.copy()

    df['shot_diff'] = df.apply(
        lambda r: (r['HS'] - r['AS']) if not pd.isna(r['HS']) and not pd.isna(r['AS']) else 0,
        axis=1
    )
    df['shot_on_target_diff'] = df.apply(
        lambda r: (r['HST'] - r['AST']) if not pd.isna(r['HST']) and not pd.isna(r['AST']) else 0,
        axis=1
    )

    # Bookmaker probabilities from average odds
    def calc_bookmaker_probs(row):
        avg_h = row.get('AvgH', 0)
        avg_d = row.get('AvgD', 0)
        avg_a = row.get('AvgA', 0)

        if avg_h > 0 and avg_d > 0 and avg_a > 0:
            inv_h = 1 / avg_h
            inv_d = 1 / avg_d
            inv_a = 1 / avg_a
            total = inv_h + inv_d + inv_a
            return pd.Series({
                'bookmaker_prob_home': inv_h / total,
                'bookmaker_prob_draw': inv_d / total,
                'bookmaker_prob_away': inv_a / total,
            })
        else:
            return pd.Series({
                'bookmaker_prob_home': 0.4,
                'bookmaker_prob_draw': 0.25,
                'bookmaker_prob_away': 0.35,
            })

    probs = df.apply(calc_bookmaker_probs, axis=1)
    df['bookmaker_prob_home'] = probs['bookmaker_prob_home']
    df['bookmaker_prob_draw'] = probs['bookmaker_prob_draw']
    df['bookmaker_prob_away'] = probs['bookmaker_prob_away']

    return df

def get_feature_columns():
    """Define feature columns for ML model."""
    return [
        'HS', 'AS', 'HST', 'AST',  # Shots
        'HF', 'AF', 'HC', 'AC',  # Fouls and corners
        'HY', 'AY', 'HR', 'AR',  # Cards
        'home_form', 'away_form',  # Form
        'home_avg_gf', 'home_avg_ga',  # Goals for/against
        'away_avg_gf', 'away_avg_ga',
        'home_elo', 'away_elo', 'elo_diff',  # ELO
        'shot_diff', 'shot_on_target_diff',  # Shot features
        'bookmaker_prob_home', 'bookmaker_prob_draw', 'bookmaker_prob_away'  # Bookmaker
    ]

def train_ensemble_models(X_train, y_train):
    """Train multiple models for ensemble."""
    models = {}

    print("  XGBoost...")
    xgb_model = xgb.XGBClassifier(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=6,
        random_state=42,
        objective='multi:softprob',
        num_class=3,
        eval_metric='mlogloss'
    )
    xgb_model.fit(X_train, y_train)
    models['xgboost'] = xgb_model

    print("  LightGBM...")
    lgb_model = lgb.LGBMClassifier(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=6,
        random_state=42,
        objective='multiclass',
        num_class=3,
        verbose=-1
    )
    lgb_model.fit(X_train, y_train)
    models['lightgbm'] = lgb_model

    print("  GradientBoosting...")
    gb_model = GradientBoostingClassifier(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=6,
        random_state=42
    )
    gb_model.fit(X_train, y_train)
    models['gradient_boosting'] = gb_model

    return models

def predict_ensemble(models, X, elo_probs=None, bookie_probs=None, weights=None):
    """Ensemble prediction with blending."""
    n_samples = len(X)
    n_classes = 3

    # ML predictions (average of all models)
    ml_probs = np.zeros((n_samples, n_classes))

    for name, model in models.items():
        probs = model.predict_proba(X)
        ml_probs += probs

    ml_probs /= len(models)

    # Default weights
    if weights is None:
        weights = {'ml': 0.6, 'elo': 0.2, 'bookie': 0.2}

    # Blend predictions
    final_probs = ml_probs * weights['ml']

    if elo_probs is not None:
        final_probs += elo_probs * weights['elo']

    if bookie_probs is not None:
        final_probs += bookie_probs * weights['bookie']

    # Normalize
    final_probs = final_probs / final_probs.sum(axis=1, keepdims=True)

    return final_probs

def evaluate_predictions(y_true, y_pred, probs, label="Model"):
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

    # Prediction distribution
    print(f"  Predicted Home: {(y_pred == 0).sum()}")
    print(f"  Predicted Draw: {(y_pred == 1).sum()}")
    print(f"  Predicted Away: {(y_pred == 2).sum()}")

    return accuracy, ll

def main():
    parser = argparse.ArgumentParser(description='Ligue1 Prediction Improvement')
    parser.add_argument('--data_dir', default='data/ligue1', help='Data directory')
    parser.add_argument('--output', default='ligue1_improved_results.csv', help='Output file')
    args = parser.parse_args()

    print("=" * 60)
    print("LIGUE1 PREDICTION ACCURACY IMPROVEMENT")
    print("=" * 60)

    # Load data
    print("\nLoading data...")
    csv_files = sorted(Path(args.data_dir).glob("F1_*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {args.data_dir}")

    df_list = []
    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        df['source_file'] = csv_file.name
        df_list.append(df)

    df = pd.concat(df_list, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
    df = df.sort_values('Date').reset_index(drop=True)
    print(f"Loaded {len(df)} games")

    # Add features
    print("\nComputing features...")
    print("  ELO ratings...")
    df = compute_elo_ratings(df)
    print("  Team form...")
    df = compute_team_form(df)
    print("  Match features...")
    df = add_match_features(df)

    # Split data chronologically
    split_idx = int(len(df) * 0.7)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]

    print(f"\nTrain samples: {len(train_df)}")
    print(f"Test samples: {len(test_df)}")

    # Prepare features
    feature_cols = get_feature_columns()
    print(f"Using {len(feature_cols)} features")

    X_train = train_df[feature_cols].fillna(0)
    y_train = train_df['FTR'].map({'H': 0, 'D': 1, 'A': 2})

    X_test = test_df[feature_cols].fillna(0)
    y_test = test_df['FTR'].map({'H': 0, 'D': 1, 'A': 2})

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train models
    print("\nTraining ensemble models...")
    models = train_ensemble_models(X_train_scaled, y_train)

    # Evaluate
    print("\n" + "=" * 60)
    print("TEST SET EVALUATION")
    print("=" * 60)

    # Baseline: Pure ELO
    elo_probs_baseline = test_df[['elo_prob_home', 'elo_prob_draw', 'elo_prob_away']].values
    elo_pred = np.argmax(elo_probs_baseline, axis=1)
    baseline_acc = accuracy_score(y_test.values, elo_pred)
    print(f"\nPure ELO (Baseline) Results:")
    print(f"  Accuracy: {baseline_acc:.4f} ({baseline_acc*100:.2f}%)")

    # Bookmaker consensus
    bookie_probs = test_df[['bookmaker_prob_home', 'bookmaker_prob_draw', 'bookmaker_prob_away']].values
    bookie_pred = np.argmax(bookie_probs, axis=1)
    bookie_acc = accuracy_score(y_test.values, bookie_pred)
    print(f"\nBookmaker Consensus Results:")
    print(f"  Accuracy: {bookie_acc:.4f} ({bookie_acc*100:.2f}%)")

    # ML Ensemble (pure)
    ml_probs = np.zeros((len(X_test), 3))
    for name, model in models.items():
        ml_probs += model.predict_proba(X_test_scaled)
    ml_probs /= len(models)
    ml_pred = np.argmax(ml_probs, axis=1)
    evaluate_predictions(y_test.values, ml_pred, ml_probs, "ML Ensemble (Pure)")

    # Blended: ELO + ML + Bookmaker
    elo_probs = test_df[['elo_prob_home', 'elo_prob_draw', 'elo_prob_away']].values
    bookie_probs = test_df[['bookmaker_prob_home', 'bookmaker_prob_draw', 'bookmaker_prob_away']].values

    blended_probs = predict_ensemble(models, X_test_scaled, elo_probs, bookie_probs)
    blended_pred = np.argmax(blended_probs, axis=1)
    acc, ll = evaluate_predictions(y_test.values, blended_pred, blended_probs, "BLENDED (ELO+ML+Bookmaker)")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Baseline (Pure ELO): {baseline_acc*100:.2f}%")
    print(f"Bookmaker Consensus: {bookie_acc*100:.2f}%")
    print(f"ML Ensemble (Pure): {accuracy_score(y_test.values, ml_pred)*100:.2f}%")
    print(f"BLENDED Model: {acc*100:.2f}%")
    print(f"Improvement over baseline: {(acc - baseline_acc)*100:.2f}%")
    print(f"Improvement over bookmaker: {(acc - bookie_acc)*100:.2f}%")

    target = 0.545 + 0.05  # 5% improvement over 54.5%
    if acc >= target:
        print(f"\n✓ SUCCESS: Achieved {target*100:.1f}%+ target!")
    else:
        print(f"\n✗ Need {(target - acc)*100:.2f}% more to reach target")

    # Save results
    results = test_df.copy()
    results['pred_home'] = blended_probs[:, 0]
    results['pred_draw'] = blended_probs[:, 1]
    results['pred_away'] = blended_probs[:, 2]
    results['prediction'] = np.argmax(blended_probs, axis=1).map({0: 'H', 1: 'D', 2: 'A'})
    results['correct'] = results['prediction'] == results['FTR']

    results.to_csv(args.output, index=False)
    print(f"\nResults saved to {args.output}")

    return acc

if __name__ == "__main__":
    acc = main()
    sys.exit(0 if acc >= 0.595 else 1)
