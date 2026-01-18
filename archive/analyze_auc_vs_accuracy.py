"""
Deep dive: Why did AUC increase but accuracy decrease?

Investigate probability distributions and calibration
"""

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import accuracy_score, roc_auc_score, roc_curve
import matplotlib.pyplot as plt


def train_test_split_temporal(df, train_frac=0.7, val_frac=0.15):
    """Split data by date"""
    df_sorted = df.sort_values('game_date')
    n = len(df_sorted)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))
    return df_sorted.iloc[:train_end], df_sorted.iloc[train_end:val_end], df_sorted.iloc[val_end:]


def prepare_features(df, include_elo=True):
    """Prepare feature matrix"""
    exclude = ['game_id', 'game_date', 'home_team_name', 'away_team_name', 'home_win']
    if not include_elo:
        exclude.extend(['home_elo', 'away_elo', 'elo_diff', 'elo_prob'])
    feature_cols = [col for col in df.columns if col not in exclude and df[col].dtype in [np.float64, np.int64]]
    return df[feature_cols].fillna(0), df['home_win'].values, feature_cols


def train_model(X_train, y_train, X_val, y_val):
    """Train XGBoost"""
    params = {
        'max_depth': 3, 'learning_rate': 0.01, 'n_estimators': 150,
        'objective': 'binary:logistic', 'eval_metric': 'auc', 'random_state': 42,
        'min_child_weight': 10, 'subsample': 0.7, 'colsample_bytree': 0.99,
        'gamma': 4.8, 'reg_alpha': 0.19, 'reg_lambda': 0.01
    }
    model = xgb.XGBClassifier(**params)
    model.fit(X_train, y_train, eval_set=[(X_train, y_train), (X_val, y_val)], verbose=False)
    return model


def analyze_predictions(y_true, y_pred_proba_no_elo, y_pred_proba_with_elo):
    """Detailed analysis of prediction differences"""
    
    print("\n" + "=" * 70)
    print("DETAILED ANALYSIS: AUC vs Accuracy")
    print("=" * 70)
    
    # Basic metrics
    print("\n📊 Basic Metrics:")
    print(f"{'Metric':<25} {'Without Elo':<15} {'With Elo':<15} {'Δ':<10}")
    print("-" * 70)
    
    # AUC
    auc_no_elo = roc_auc_score(y_true, y_pred_proba_no_elo)
    auc_with_elo = roc_auc_score(y_true, y_pred_proba_with_elo)
    print(f"{'AUC':<25} {auc_no_elo:<15.4f} {auc_with_elo:<15.4f} {auc_with_elo - auc_no_elo:+.4f}")
    
    # Accuracy at 0.5 threshold
    acc_no_elo = accuracy_score(y_true, (y_pred_proba_no_elo >= 0.5).astype(int))
    acc_with_elo = accuracy_score(y_true, (y_pred_proba_with_elo >= 0.5).astype(int))
    print(f"{'Accuracy @ 0.5 threshold':<25} {acc_no_elo:<15.4f} {acc_with_elo:<15.4f} {acc_with_elo - acc_no_elo:+.4f}")
    
    # Try different thresholds for accuracy
    print("\n🎯 Accuracy at Different Thresholds:")
    print(f"{'Threshold':<15} {'Without Elo':<15} {'With Elo':<15} {'Δ':<10}")
    print("-" * 70)
    
    best_threshold_no_elo = 0.5
    best_acc_no_elo = 0
    best_threshold_with_elo = 0.5
    best_acc_with_elo = 0
    
    for threshold in [0.45, 0.50, 0.55, 0.60]:
        acc_no = accuracy_score(y_true, (y_pred_proba_no_elo >= threshold).astype(int))
        acc_with = accuracy_score(y_true, (y_pred_proba_with_elo >= threshold).astype(int))
        print(f"{threshold:<15.2f} {acc_no:<15.4f} {acc_with:<15.4f} {acc_with - acc_no:+.4f}")
        
        if acc_no > best_acc_no_elo:
            best_acc_no_elo = acc_no
            best_threshold_no_elo = threshold
        if acc_with > best_acc_with_elo:
            best_acc_with_elo = acc_with
            best_threshold_with_elo = threshold
    
    print(f"\n📌 Best thresholds:")
    print(f"   Without Elo: {best_threshold_no_elo:.2f} → {best_acc_no_elo:.4f} accuracy")
    print(f"   With Elo: {best_threshold_with_elo:.2f} → {best_acc_with_elo:.4f} accuracy")
    
    # Probability distribution
    print("\n📈 Probability Distribution:")
    print(f"{'Statistic':<25} {'Without Elo':<15} {'With Elo':<15} {'Δ':<10}")
    print("-" * 70)
    print(f"{'Mean probability':<25} {np.mean(y_pred_proba_no_elo):<15.4f} {np.mean(y_pred_proba_with_elo):<15.4f} {np.mean(y_pred_proba_with_elo) - np.mean(y_pred_proba_no_elo):+.4f}")
    print(f"{'Std deviation':<25} {np.std(y_pred_proba_no_elo):<15.4f} {np.std(y_pred_proba_with_elo):<15.4f} {np.std(y_pred_proba_with_elo) - np.std(y_pred_proba_no_elo):+.4f}")
    print(f"{'Min probability':<25} {np.min(y_pred_proba_no_elo):<15.4f} {np.min(y_pred_proba_with_elo):<15.4f} {np.min(y_pred_proba_with_elo) - np.min(y_pred_proba_no_elo):+.4f}")
    print(f"{'Max probability':<25} {np.max(y_pred_proba_no_elo):<15.4f} {np.max(y_pred_proba_with_elo):<15.4f} {np.max(y_pred_proba_with_elo) - np.max(y_pred_proba_no_elo):+.4f}")
    
    # Count predictions above/below 0.5
    print("\n🎲 Predictions by Threshold (0.5):")
    print(f"{'Category':<25} {'Without Elo':<15} {'With Elo':<15} {'Δ':<10}")
    print("-" * 70)
    
    pred_home_no_elo = np.sum(y_pred_proba_no_elo >= 0.5)
    pred_home_with_elo = np.sum(y_pred_proba_with_elo >= 0.5)
    actual_home = np.sum(y_true)
    
    print(f"{'Predicted Home Wins':<25} {pred_home_no_elo:<15d} {pred_home_with_elo:<15d} {pred_home_with_elo - pred_home_no_elo:+10d}")
    print(f"{'Predicted Away Wins':<25} {len(y_true) - pred_home_no_elo:<15d} {len(y_true) - pred_home_with_elo:<15d} {(len(y_true) - pred_home_with_elo) - (len(y_true) - pred_home_no_elo):+10d}")
    print(f"{'Actual Home Wins':<25} {actual_home:<15d} {actual_home:<15d} {'':10s}")
    
    # Calibration analysis
    print("\n🎯 Calibration Analysis (Binned by predicted probability):")
    print(f"{'Prob Bin':<15} {'Without Elo':<20} {'With Elo':<20}")
    print(f"{'':15} {'Count':<10} {'Actual':<10} {'Count':<10} {'Actual':<10}")
    print("-" * 70)
    
    bins = [(0, 0.4), (0.4, 0.5), (0.5, 0.6), (0.6, 1.0)]
    for low, high in bins:
        # Without Elo
        mask_no = (y_pred_proba_no_elo >= low) & (y_pred_proba_no_elo < high)
        count_no = np.sum(mask_no)
        actual_no = np.mean(y_true[mask_no]) if count_no > 0 else 0
        
        # With Elo
        mask_with = (y_pred_proba_with_elo >= low) & (y_pred_proba_with_elo < high)
        count_with = np.sum(mask_with)
        actual_with = np.mean(y_true[mask_with]) if count_with > 0 else 0
        
        print(f"{low:.1f}-{high:.1f}{'':7} {count_no:<10d} {actual_no:<10.3f} {count_with:<10d} {actual_with:<10.3f}")
    
    # Explanation
    print("\n" + "=" * 70)
    print("💡 EXPLANATION")
    print("=" * 70)
    print("""
AUC measures the model's ability to RANK predictions correctly.
It doesn't depend on a specific threshold - it tests ALL possible thresholds.

Accuracy measures correctness at ONE specific threshold (0.5 by default).

A model can be better at ranking (higher AUC) but worse at the 0.5 threshold
if its probability calibration shifts. This happens when:

1. The model becomes more confident (spreads predictions further from 0.5)
2. The optimal threshold moves away from 0.5
3. The model changes its trade-off between false positives and false negatives

In this case, the Elo features likely helped the model:
✅ Better separate winning and losing teams (better ranking → higher AUC)
❌ Shifted probability distribution, making 0.5 less optimal (lower accuracy @ 0.5)

Solution: Use a different threshold OR use AUC as the primary metric!
    """)


def main():
    print("=" * 70)
    print("Deep Dive: AUC Up, Accuracy Down")
    print("=" * 70)
    
    # Load data
    print("\n📂 Loading data...")
    df = pd.read_csv('data/nhl_training_data_with_elo.csv')
    df['game_date'] = pd.to_datetime(df['game_date'])
    
    # Split
    train_df, val_df, test_df = train_test_split_temporal(df)
    print(f"   Test set: {len(test_df)} games")
    
    # Train both models
    print("\n🤖 Training models...")
    
    # Without Elo
    X_train_no, y_train, _ = prepare_features(train_df, include_elo=False)
    X_val_no, y_val, _ = prepare_features(val_df, include_elo=False)
    X_test_no, y_test, _ = prepare_features(test_df, include_elo=False)
    model_no_elo = train_model(X_train_no, y_train, X_val_no, y_val)
    
    # With Elo
    X_train_with, _, _ = prepare_features(train_df, include_elo=True)
    X_val_with, _, _ = prepare_features(val_df, include_elo=True)
    X_test_with, _, _ = prepare_features(test_df, include_elo=True)
    model_with_elo = train_model(X_train_with, y_train, X_val_with, y_val)
    
    # Predictions
    print("   ✅ Models trained")
    print("\n🔍 Analyzing predictions...")
    
    y_pred_proba_no_elo = model_no_elo.predict_proba(X_test_no)[:, 1]
    y_pred_proba_with_elo = model_with_elo.predict_proba(X_test_with)[:, 1]
    
    # Deep analysis
    analyze_predictions(y_test, y_pred_proba_no_elo, y_pred_proba_with_elo)


if __name__ == "__main__":
    main()
