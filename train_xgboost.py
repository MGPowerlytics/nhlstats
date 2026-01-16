#!/usr/bin/env python3
"""
Train XGBoost model for NHL game prediction
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Load dataset
print("🏒 NHL XGBoost Model Training")
print("=" * 80)

df = pd.read_csv('data/nhl_training_data.csv')
print(f"\n📊 Loaded {len(df)} games from {df.game_date.min()} to {df.game_date.max()}")
print(f"   Home win rate: {df.home_win.mean():.1%}")

# Prepare features and target
feature_cols = [col for col in df.columns if col not in ['game_id', 'game_date', 'home_team_id', 'away_team_id', 'home_win']]
X = df[feature_cols]
y = df['home_win']

print(f"\n📈 Features: {len(feature_cols)}")
print(f"   {', '.join(feature_cols[:6])}...")

# 70-15-15 split (time-series, no shuffle)
n = len(df)
train_end = int(n * 0.70)
val_end = int(n * 0.85)

X_train, y_train = X[:train_end], y[:train_end]
X_val, y_val = X[train_end:val_end], y[train_end:val_end]
X_test, y_test = X[val_end:], y[val_end:]

print(f"\n📦 Split:")
print(f"   Train: {len(X_train)} games ({len(X_train)/n:.1%})")
print(f"   Val:   {len(X_val)} games ({len(X_val)/n:.1%})")
print(f"   Test:  {len(X_test)} games ({len(X_test)/n:.1%})")

# Train XGBoost
print("\n🤖 Training XGBoost...")

try:
    import xgboost as xgb
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, f1_score,
        roc_auc_score, confusion_matrix, classification_report
    )
    
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,  # Shallow for small dataset
        learning_rate=0.1,
        min_child_weight=3,  # Regularization
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric='logloss'
    )
    
    # Train with validation set
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False
    )
    
    print("✅ Model trained!")
    
    # Predictions
    y_train_pred = model.predict(X_train)
    y_val_pred = model.predict(X_val)
    y_test_pred = model.predict(X_test)
    
    y_train_proba = model.predict_proba(X_train)[:, 1]
    y_val_proba = model.predict_proba(X_val)[:, 1]
    y_test_proba = model.predict_proba(X_test)[:, 1]
    
    # Evaluation
    print("\n" + "=" * 80)
    print("📊 BINARY CLASSIFICATION METRICS")
    print("=" * 80)
    
    for split_name, y_true, y_pred, y_proba in [
        ('TRAIN', y_train, y_train_pred, y_train_proba),
        ('VAL', y_val, y_val_pred, y_val_proba),
        ('TEST', y_test, y_test_pred, y_test_proba)
    ]:
        print(f"\n{split_name} SET:")
        print(f"  Accuracy:  {accuracy_score(y_true, y_pred):.3f}")
        print(f"  Precision: {precision_score(y_true, y_pred, zero_division=0):.3f} (of predicted home wins, % correct)")
        print(f"  Recall:    {recall_score(y_true, y_pred, zero_division=0):.3f} (of actual home wins, % caught)")
        print(f"  F1 Score:  {f1_score(y_true, y_pred, zero_division=0):.3f} (harmonic mean)")
        
        if len(np.unique(y_true)) > 1:
            print(f"  ROC-AUC:   {roc_auc_score(y_true, y_proba):.3f} (ability to distinguish)")
        
        # Confusion matrix
        cm = confusion_matrix(y_true, y_pred)
        print(f"\n  Confusion Matrix:")
        print(f"                 Predicted")
        print(f"               Away    Home")
        print(f"    Actual Away  {cm[0,0]:3d}     {cm[0,1]:3d}")
        print(f"          Home  {cm[1,0]:3d}     {cm[1,1]:3d}")
    
    # Baseline comparison
    baseline_acc = y_test.mean()  # Always predict home wins
    print(f"\n🎯 Baseline (always predict home): {baseline_acc:.3f}")
    print(f"   Model improvement: {accuracy_score(y_test, y_test_pred) - baseline_acc:+.3f}")
    
    # Feature importance
    print("\n" + "=" * 80)
    print("🔍 TOP 10 FEATURE IMPORTANCE")
    print("=" * 80)
    
    importance_df = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    for idx, row in importance_df.head(10).iterrows():
        print(f"  {row['feature']:30s} {row['importance']:.4f}")
    
    # Sample predictions
    print("\n" + "=" * 80)
    print("🎲 SAMPLE PREDICTIONS (Test Set)")
    print("=" * 80)
    
    test_df = df.iloc[val_end:].copy()
    test_df['pred_home_win_prob'] = y_test_proba
    test_df['predicted'] = y_test_pred
    test_df['correct'] = test_df['predicted'] == test_df['home_win']
    
    print(f"\n{'Date':<12} {'Prediction':<12} {'Probability':<12} {'Actual':<10} {'Result':<10}")
    print("-" * 70)
    
    for _, row in test_df.iterrows():
        pred_label = "HOME" if row['predicted'] == 1 else "AWAY"
        actual_label = "HOME" if row['home_win'] == 1 else "AWAY"
        result = "✅ CORRECT" if row['correct'] else "❌ WRONG"
        prob = row['pred_home_win_prob']
        
        print(f"{row['game_date']:<12} {pred_label:<12} {prob:>6.1%}        {actual_label:<10} {result}")
    
    # Save model
    model_path = Path('data/nhl_xgboost_model.json')
    model.save_model(str(model_path))
    print(f"\n💾 Model saved to {model_path}")
    
    print("\n" + "=" * 80)
    print("✅ Training Complete!")
    print("=" * 80)
    
except ImportError as e:
    print(f"\n❌ Error: {e}")
    print("   Install required packages:")
    print("   pip install xgboost scikit-learn")
