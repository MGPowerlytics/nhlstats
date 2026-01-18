"""
Train XGBoost with Elo Rating Features

Compare performance with and without Elo features
"""

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report
from pathlib import Path
import json


def train_test_split_temporal(df, train_frac=0.7, val_frac=0.15):
    """Split data by date (no shuffle for time series)"""
    df_sorted = df.sort_values('game_date')
    
    n = len(df_sorted)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))
    
    train = df_sorted.iloc[:train_end]
    val = df_sorted.iloc[train_end:val_end]
    test = df_sorted.iloc[val_end:]
    
    return train, val, test


def prepare_features(df, include_elo=True):
    """Prepare feature matrix"""
    # Exclude columns
    exclude = ['game_id', 'game_date', 'home_team_name', 'away_team_name', 'home_win']
    
    if not include_elo:
        exclude.extend(['home_elo', 'away_elo', 'elo_diff', 'elo_prob'])
    
    feature_cols = [col for col in df.columns if col not in exclude and df[col].dtype in [np.float64, np.int64]]
    
    X = df[feature_cols].fillna(0)
    y = df['home_win'].values
    
    return X, y, feature_cols


def train_model(X_train, y_train, X_val, y_val, params=None):
    """Train XGBoost model"""
    
    if params is None:
        # Default params (similar to Round 3)
        params = {
            'max_depth': 3,
            'learning_rate': 0.01,
            'n_estimators': 150,
            'objective': 'binary:logistic',
            'eval_metric': 'auc',
            'random_state': 42,
            'min_child_weight': 10,
            'subsample': 0.7,
            'colsample_bytree': 0.99,
            'gamma': 4.8,
            'reg_alpha': 0.19,
            'reg_lambda': 0.01
        }
    
    model = xgb.XGBClassifier(**params)
    
    model.fit(
        X_train, y_train,
        eval_set=[(X_train, y_train), (X_val, y_val)],
        verbose=False
    )
    
    return model


def evaluate_model(model, X, y, dataset_name="Test"):
    """Evaluate model performance"""
    
    # Predictions
    y_pred_proba = model.predict_proba(X)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)
    
    # Metrics
    accuracy = accuracy_score(y, y_pred)
    auc = roc_auc_score(y, y_pred_proba)
    
    baseline = np.mean(y)  # Always predict home win
    
    print(f"\n{dataset_name} Set:")
    print(f"  Accuracy: {accuracy:.3f}")
    print(f"  ROC-AUC: {auc:.3f}")
    print(f"  Baseline: {baseline:.3f}")
    print(f"  Improvement: {accuracy - baseline:+.3f} ({(accuracy - baseline) / baseline * 100:+.1f}%)")
    
    return {
        'accuracy': accuracy,
        'auc': auc,
        'baseline': baseline,
        'improvement': accuracy - baseline
    }


def main():
    print("=" * 70)
    print("XGBoost Training with Elo Rating Features")
    print("=" * 70)
    
    # Load datasets
    print("\n📂 Loading datasets...")
    df_with_elo = pd.read_csv('data/nhl_training_data_with_elo.csv')
    df_with_elo['game_date'] = pd.to_datetime(df_with_elo['game_date'])
    
    print(f"   ✅ With Elo: {len(df_with_elo)} games, {len(df_with_elo.columns)} columns")
    
    # Check if Elo columns exist
    elo_cols = ['home_elo', 'away_elo', 'elo_diff', 'elo_prob']
    has_elo = all(col in df_with_elo.columns for col in elo_cols)
    
    if not has_elo:
        print("   ❌ Elo features not found! Run add_elo_features.py first")
        return
    
    # Split data
    print("\n🔪 Splitting data by date...")
    train_df, val_df, test_df = train_test_split_temporal(df_with_elo)
    print(f"   Train: {len(train_df)} ({len(train_df)/len(df_with_elo):.0%})")
    print(f"   Val: {len(val_df)} ({len(val_df)/len(df_with_elo):.0%})")
    print(f"   Test: {len(test_df)} ({len(test_df)/len(df_with_elo):.0%})")
    
    # ========================================
    # Experiment 1: WITHOUT Elo features
    # ========================================
    print("\n" + "=" * 70)
    print("EXPERIMENT 1: XGBoost WITHOUT Elo Features (Baseline)")
    print("=" * 70)
    
    X_train_no_elo, y_train, feature_cols_no_elo = prepare_features(train_df, include_elo=False)
    X_val_no_elo, y_val, _ = prepare_features(val_df, include_elo=False)
    X_test_no_elo, y_test, _ = prepare_features(test_df, include_elo=False)
    
    print(f"\n📊 Features: {len(feature_cols_no_elo)} (no Elo)")
    
    print("\n🤖 Training model...")
    model_no_elo = train_model(X_train_no_elo, y_train, X_val_no_elo, y_val)
    
    # Evaluate
    train_metrics_no_elo = evaluate_model(model_no_elo, X_train_no_elo, y_train, "Train")
    val_metrics_no_elo = evaluate_model(model_no_elo, X_val_no_elo, y_val, "Val")
    test_metrics_no_elo = evaluate_model(model_no_elo, X_test_no_elo, y_test, "Test")
    
    overfit_gap_no_elo = train_metrics_no_elo['auc'] - test_metrics_no_elo['auc']
    print(f"\n📉 Overfitting gap: {overfit_gap_no_elo:.3f} ({overfit_gap_no_elo*100:.1f}%)")
    
    # ========================================
    # Experiment 2: WITH Elo features
    # ========================================
    print("\n" + "=" * 70)
    print("EXPERIMENT 2: XGBoost WITH Elo Features")
    print("=" * 70)
    
    X_train_with_elo, y_train, feature_cols_with_elo = prepare_features(train_df, include_elo=True)
    X_val_with_elo, y_val, _ = prepare_features(val_df, include_elo=True)
    X_test_with_elo, y_test, _ = prepare_features(test_df, include_elo=True)
    
    print(f"\n📊 Features: {len(feature_cols_with_elo)} (+4 Elo features)")
    
    # Check which Elo features are included
    elo_features_included = [col for col in feature_cols_with_elo if 'elo' in col]
    print(f"   Elo features: {', '.join(elo_features_included)}")
    
    print("\n🤖 Training model...")
    model_with_elo = train_model(X_train_with_elo, y_train, X_val_with_elo, y_val)
    
    # Evaluate
    train_metrics_with_elo = evaluate_model(model_with_elo, X_train_with_elo, y_train, "Train")
    val_metrics_with_elo = evaluate_model(model_with_elo, X_val_with_elo, y_val, "Val")
    test_metrics_with_elo = evaluate_model(model_with_elo, X_test_with_elo, y_test, "Test")
    
    overfit_gap_with_elo = train_metrics_with_elo['auc'] - test_metrics_with_elo['auc']
    print(f"\n📉 Overfitting gap: {overfit_gap_with_elo:.3f} ({overfit_gap_with_elo*100:.1f}%)")
    
    # ========================================
    # Comparison
    # ========================================
    print("\n" + "=" * 70)
    print("COMPARISON: With vs Without Elo")
    print("=" * 70)
    
    print("\n📊 Test Set Performance:")
    print(f"{'Metric':<20} {'Without Elo':<15} {'With Elo':<15} {'Δ Change':<15}")
    print("-" * 70)
    print(f"{'Accuracy':<20} {test_metrics_no_elo['accuracy']:<15.3f} {test_metrics_with_elo['accuracy']:<15.3f} {test_metrics_with_elo['accuracy'] - test_metrics_no_elo['accuracy']:+.3f}")
    print(f"{'ROC-AUC':<20} {test_metrics_no_elo['auc']:<15.3f} {test_metrics_with_elo['auc']:<15.3f} {test_metrics_with_elo['auc'] - test_metrics_no_elo['auc']:+.3f}")
    print(f"{'Improvement':<20} {test_metrics_no_elo['improvement']:<15.3f} {test_metrics_with_elo['improvement']:<15.3f} {test_metrics_with_elo['improvement'] - test_metrics_no_elo['improvement']:+.3f}")
    print(f"{'Overfit Gap':<20} {overfit_gap_no_elo:<15.3f} {overfit_gap_with_elo:<15.3f} {overfit_gap_with_elo - overfit_gap_no_elo:+.3f}")
    
    # Feature importance for model WITH Elo
    print("\n🔝 Top 10 Features (Model WITH Elo):")
    feature_importance = pd.DataFrame({
        'feature': feature_cols_with_elo,
        'importance': model_with_elo.feature_importances_
    }).sort_values('importance', ascending=False)
    
    for i, row in feature_importance.head(10).iterrows():
        elo_marker = "⭐" if 'elo' in row['feature'] else "  "
        print(f"   {elo_marker} {row['feature']:<40} {row['importance']:.4f}")
    
    # Save results
    results = {
        'without_elo': {
            'test_accuracy': test_metrics_no_elo['accuracy'],
            'test_auc': test_metrics_no_elo['auc'],
            'overfit_gap': overfit_gap_no_elo,
            'features': len(feature_cols_no_elo)
        },
        'with_elo': {
            'test_accuracy': test_metrics_with_elo['accuracy'],
            'test_auc': test_metrics_with_elo['auc'],
            'overfit_gap': overfit_gap_with_elo,
            'features': len(feature_cols_with_elo),
            'elo_features': elo_features_included
        },
        'improvement': {
            'accuracy_gain': test_metrics_with_elo['accuracy'] - test_metrics_no_elo['accuracy'],
            'auc_gain': test_metrics_with_elo['auc'] - test_metrics_no_elo['auc']
        }
    }
    
    output_path = Path('data/xgboost_with_elo_results.json')
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_path}")
    
    # Verdict
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)
    
    auc_gain = results['improvement']['auc_gain']
    acc_gain = results['improvement']['accuracy_gain']
    
    if auc_gain > 0.01 or acc_gain > 0.01:
        print("\n✅ SUCCESS: Elo features significantly improve XGBoost!")
        print(f"   AUC improvement: {auc_gain:+.3f}")
        print(f"   Accuracy improvement: {acc_gain:+.3f}")
        print("\n   🎯 Recommendation: Use Elo features in production model")
    elif auc_gain > 0:
        print("\n🟡 MARGINAL: Elo features provide small improvement")
        print(f"   AUC improvement: {auc_gain:+.3f}")
        print("\n   🤔 Recommendation: Consider using Elo features")
    else:
        print("\n❌ NO BENEFIT: Elo features don't improve XGBoost")
        print(f"   AUC change: {auc_gain:+.3f}")
        print("\n   💡 Recommendation: Use standalone Elo or original XGBoost")


if __name__ == "__main__":
    main()
