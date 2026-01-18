#!/usr/bin/env python3
"""
Train XGBoost model with Hyperopt for NHL game prediction.
Uses custom loss function that penalizes overfitting.
"""

import pandas as pd
import numpy as np
from pathlib import Path

print("🏒 NHL XGBoost Model Training with Hyperopt")
print("=" * 80)

# Load dataset
df = pd.read_csv('data/nhl_training_data.csv')
print(f"\n📊 Loaded {len(df)} games from {df.game_date.min()} to {df.game_date.max()}")
print(f"   Home win rate: {df.home_win.mean():.1%}")

# Prepare features and target
feature_cols = [col for col in df.columns if col not in ['game_id', 'game_date', 'home_team_id', 'away_team_id', 'home_team_name', 'away_team_name', 'home_win']]
X = df[feature_cols]
y = df['home_win']

print(f"\n📈 Features: {len(feature_cols)}")

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

# Import required libraries
try:
    import xgboost as xgb
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, f1_score,
        roc_auc_score, confusion_matrix, classification_report
    )
    from hyperopt import hp, fmin, tpe, Trials, STATUS_OK
    
    print("\n🔍 Starting Hyperopt optimization...")
    print("   Using custom loss: 1 - (val_auc - abs(train_auc - val_auc))")
    print("   This penalizes overfitting while maximizing validation AUC")
    
    # Define hyperparameter search space
    space = {
        'max_depth': hp.quniform('max_depth', 3, 8, 1),
        'min_child_weight': hp.quniform('min_child_weight', 1, 10, 1),
        'learning_rate': hp.loguniform('learning_rate', np.log(0.01), np.log(0.3)),
        'subsample': hp.uniform('subsample', 0.6, 1.0),
        'colsample_bytree': hp.uniform('colsample_bytree', 0.6, 1.0),
        'gamma': hp.uniform('gamma', 0, 5),
        'reg_alpha': hp.loguniform('reg_alpha', np.log(0.001), np.log(10)),
        'reg_lambda': hp.loguniform('reg_lambda', np.log(0.001), np.log(10)),
        'n_estimators': hp.quniform('n_estimators', 50, 300, 25),
    }
    
    # Objective function
    iteration = 0
    
    def objective(params):
        global iteration
        iteration += 1
        
        # Convert params to proper types
        params['max_depth'] = int(params['max_depth'])
        params['min_child_weight'] = int(params['min_child_weight'])
        params['n_estimators'] = int(params['n_estimators'])
        
        # Train model
        model = xgb.XGBClassifier(
            **params,
            random_state=42,
            eval_metric='logloss',
            use_label_encoder=False
        )
        
        model.fit(X_train, y_train, verbose=False)
        
        # Get predictions
        y_train_proba = model.predict_proba(X_train)[:, 1]
        y_val_proba = model.predict_proba(X_val)[:, 1]
        
        # Calculate AUC scores
        train_auc = roc_auc_score(y_train, y_train_proba)
        val_auc = roc_auc_score(y_val, y_val_proba)
        
        # Custom loss function: penalize overfitting
        loss = 1 - (val_auc - abs(train_auc - val_auc))
        
        # Print progress every 10 iterations
        if iteration % 10 == 0:
            print(f"   [{iteration:3d}] Train AUC: {train_auc:.4f}, Val AUC: {val_auc:.4f}, "
                  f"Gap: {abs(train_auc - val_auc):.4f}, Loss: {loss:.4f}")
        
        return {
            'loss': loss,
            'status': STATUS_OK,
            'train_auc': train_auc,
            'validation_auc': val_auc,
            'params': params
        }
    
    # Run optimization
    trials = Trials()
    best = fmin(
        fn=objective,
        space=space,
        algo=tpe.suggest,
        max_evals=50,  # Reduced from 100 to avoid memory issues
        trials=trials,
        rstate=np.random.default_rng(42)
    )
    
    print("\n" + "=" * 80)
    print("🏆 BEST HYPERPARAMETERS FOUND")
    print("=" * 80)
    
    # Convert best params to proper types
    best_params = {
        'max_depth': int(best['max_depth']),
        'min_child_weight': int(best['min_child_weight']),
        'learning_rate': best['learning_rate'],
        'subsample': best['subsample'],
        'colsample_bytree': best['colsample_bytree'],
        'gamma': best['gamma'],
        'reg_alpha': best['reg_alpha'],
        'reg_lambda': best['reg_lambda'],
        'n_estimators': int(best['n_estimators']),
    }
    
    for param, value in best_params.items():
        if isinstance(value, float):
            print(f"  {param:20s}: {value:.4f}")
        else:
            print(f"  {param:20s}: {value}")
    
    # Get best trial stats
    best_trial = min(trials.trials, key=lambda x: x['result']['loss'])
    print(f"\n  Best Train AUC:      {best_trial['result']['train_auc']:.4f}")
    print(f"  Best Val AUC:        {best_trial['result']['validation_auc']:.4f}")
    print(f"  Overfitting Gap:     {abs(best_trial['result']['train_auc'] - best_trial['result']['validation_auc']):.4f}")
    print(f"  Best Loss:           {best_trial['result']['loss']:.4f}")
    
    # Train final model with best parameters
    print("\n" + "=" * 80)
    print("🤖 Training Final Model with Best Parameters")
    print("=" * 80)
    
    final_model = xgb.XGBClassifier(
        **best_params,
        random_state=42,
        eval_metric='logloss',
        use_label_encoder=False
    )
    
    final_model.fit(X_train, y_train)
    
    # Evaluate on all sets
    print("\n📊 FINAL MODEL PERFORMANCE")
    print("=" * 80)
    
    for split_name, X_split, y_split in [
        ('TRAIN', X_train, y_train),
        ('VAL', X_val, y_val),
        ('TEST', X_test, y_test)
    ]:
        y_pred = final_model.predict(X_split)
        y_proba = final_model.predict_proba(X_split)[:, 1]
        
        print(f"\n{split_name} SET:")
        print(f"  Accuracy:  {accuracy_score(y_split, y_pred):.3f}")
        print(f"  Precision: {precision_score(y_split, y_pred, zero_division=0):.3f}")
        print(f"  Recall:    {recall_score(y_split, y_pred, zero_division=0):.3f}")
        print(f"  F1 Score:  {f1_score(y_split, y_pred, zero_division=0):.3f}")
        
        if len(np.unique(y_split)) > 1:
            auc = roc_auc_score(y_split, y_proba)
            print(f"  ROC-AUC:   {auc:.3f}")
        
        # Confusion matrix
        cm = confusion_matrix(y_split, y_pred)
        print(f"\n  Confusion Matrix:")
        print(f"                 Predicted")
        print(f"               Away    Home")
        print(f"    Actual Away  {cm[0,0]:3d}     {cm[0,1]:3d}")
        print(f"          Home  {cm[1,0]:3d}     {cm[1,1]:3d}")
    
    # Baseline comparison
    baseline_acc = y_test.mean()
    test_acc = accuracy_score(y_test, final_model.predict(X_test))
    print(f"\n🎯 Baseline (always predict home): {baseline_acc:.3f}")
    print(f"   Model improvement: {test_acc - baseline_acc:+.3f}")
    
    # Feature importance
    print("\n" + "=" * 80)
    print("🔍 TOP 10 FEATURE IMPORTANCE")
    print("=" * 80)
    
    importance_df = pd.DataFrame({
        'feature': feature_cols,
        'importance': final_model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    for idx, row in importance_df.head(10).iterrows():
        print(f"  {row['feature']:30s} {row['importance']:.4f}")
    
    # Save model
    model_path = Path('data/nhl_xgboost_hyperopt_model.json')
    final_model.save_model(str(model_path))
    print(f"\n💾 Model saved to {model_path}")
    
    # Save best params
    import json
    params_path = Path('data/nhl_best_params.json')
    with open(params_path, 'w') as f:
        json.dump(best_params, f, indent=2)
    print(f"💾 Best parameters saved to {params_path}")
    
    print("\n" + "=" * 80)
    print("✅ Training Complete!")
    print("=" * 80)
    
except ImportError as e:
    print(f"\n❌ Error: {e}")
    print("   Install required packages:")
    print("   pip install hyperopt")
