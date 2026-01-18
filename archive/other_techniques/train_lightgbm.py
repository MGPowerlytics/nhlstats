"""
Train LightGBM model for NHL game prediction with hyperopt tuning.
Alternative to XGBoost with different tree-building approach.
"""

import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score, classification_report
from hyperopt import hp, fmin, tpe, Trials, STATUS_OK
import json
from pathlib import Path


def load_data():
    """Load training data"""
    data_path = Path(__file__).parent.parent / "data" / "nhl_training_data.csv"
    df = pd.read_csv(data_path)
    
    # Separate features and target
    X = df.drop(['game_id', 'game_date', 'home_team_name', 'away_team_name', 'home_win'], axis=1)
    y = df['home_win']
    
    return X, y


def train_lgb_model(params, X_train, y_train, X_val, y_val):
    """Train LightGBM model with given parameters"""
    
    # Create datasets
    train_data = lgb.Dataset(X_train, label=y_train)
    val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
    
    # Train model
    model = lgb.train(
        params,
        train_data,
        num_boost_round=int(params['n_estimators']),
        valid_sets=[val_data],
        callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)]
    )
    
    # Evaluate
    train_pred = model.predict(X_train, num_iteration=model.best_iteration)
    val_pred = model.predict(X_val, num_iteration=model.best_iteration)
    
    train_auc = roc_auc_score(y_train, train_pred)
    val_auc = roc_auc_score(y_val, val_pred)
    
    return model, train_auc, val_auc


def objective(params, X_train, y_train, X_val, y_val):
    """Hyperopt objective function"""
    
    # Convert params to LightGBM format
    lgb_params = {
        'objective': 'binary',
        'metric': 'auc',
        'boosting_type': 'gbdt',
        'verbosity': -1,
        'num_leaves': int(params['num_leaves']),
        'max_depth': int(params['max_depth']),
        'learning_rate': params['learning_rate'],
        'n_estimators': int(params['n_estimators']),
        'min_child_samples': int(params['min_child_samples']),
        'subsample': params['subsample'],
        'colsample_bytree': params['colsample_bytree'],
        'reg_alpha': params['reg_alpha'],
        'reg_lambda': params['reg_lambda'],
    }
    
    model, train_auc, val_auc = train_lgb_model(lgb_params, X_train, y_train, X_val, y_val)
    
    # Custom loss: penalize overfitting
    loss = 1 - (val_auc - abs(train_auc - val_auc))
    
    return {
        'loss': loss,
        'status': STATUS_OK,
        'model': model,
        'train_auc': train_auc,
        'val_auc': val_auc
    }


def main():
    print("🏒 Training LightGBM Model for NHL Game Prediction\n")
    
    # Load data
    print("Loading training data...")
    X, y = load_data()
    print(f"  Dataset: {len(X)} games, {X.shape[1]} features")
    print(f"  Home win rate: {y.mean():.1%}\n")
    
    # Split data: 70% train, 15% validation, 15% test
    X_temp, X_test, y_temp, y_test = train_test_split(X, y, test_size=0.15, random_state=42)
    X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=0.1765, random_state=42)  # 0.1765 of 0.85 = 0.15 overall
    
    print(f"Train set: {len(X_train)} games")
    print(f"Val set:   {len(X_val)} games")
    print(f"Test set:  {len(X_test)} games\n")
    
    # Define hyperparameter search space
    space = {
        'num_leaves': hp.quniform('num_leaves', 20, 150, 1),
        'max_depth': hp.quniform('max_depth', 3, 12, 1),
        'learning_rate': hp.loguniform('learning_rate', np.log(0.01), np.log(0.3)),
        'n_estimators': hp.quniform('n_estimators', 50, 500, 1),
        'min_child_samples': hp.quniform('min_child_samples', 5, 50, 1),
        'subsample': hp.uniform('subsample', 0.6, 1.0),
        'colsample_bytree': hp.uniform('colsample_bytree', 0.6, 1.0),
        'reg_alpha': hp.loguniform('reg_alpha', np.log(0.0001), np.log(10)),
        'reg_lambda': hp.loguniform('reg_lambda', np.log(0.0001), np.log(10)),
    }
    
    # Run hyperparameter optimization
    print("Starting hyperparameter optimization (50 trials)...")
    trials = Trials()
    
    best = fmin(
        fn=lambda params: objective(params, X_train, y_train, X_val, y_val),
        space=space,
        algo=tpe.suggest,
        max_evals=50,
        trials=trials,
        verbose=False
    )
    
    print("\n✅ Optimization complete!\n")
    
    # Get best trial
    best_trial = min(trials.trials, key=lambda t: t['result']['loss'])
    best_model = best_trial['result']['model']
    train_auc = best_trial['result']['train_auc']
    val_auc = best_trial['result']['val_auc']
    
    print("Best parameters:")
    for key, value in best.items():
        if key in ['num_leaves', 'max_depth', 'n_estimators', 'min_child_samples']:
            print(f"  {key}: {int(value)}")
        else:
            print(f"  {key}: {value:.4f}")
    
    print(f"\nBest model performance:")
    print(f"  Train AUC: {train_auc:.4f}")
    print(f"  Val AUC:   {val_auc:.4f}")
    print(f"  Overfit:   {abs(train_auc - val_auc):.4f}\n")
    
    # Evaluate on test set
    print("Evaluating on test set...")
    test_pred_proba = best_model.predict(X_test, num_iteration=best_model.best_iteration)
    test_pred = (test_pred_proba > 0.5).astype(int)
    
    test_auc = roc_auc_score(y_test, test_pred_proba)
    test_acc = accuracy_score(y_test, test_pred)
    
    print(f"\n📊 Test Set Results:")
    print(f"  Test AUC:      {test_auc:.4f}")
    print(f"  Test Accuracy: {test_acc:.4f}")
    print(f"  Baseline Acc:  {y_test.mean():.4f} (always predict home win)")
    print(f"  Improvement:   {(test_acc - y_test.mean()):.4f}\n")
    
    print("Classification Report:")
    print(classification_report(y_test, test_pred, target_names=['Away Win', 'Home Win']))
    
    # Feature importance
    print("\nTop 10 Features:")
    feature_importance = pd.DataFrame({
        'feature': X.columns,
        'importance': best_model.feature_importance(importance_type='gain')
    }).sort_values('importance', ascending=False)
    
    for idx, row in feature_importance.head(10).iterrows():
        print(f"  {row['feature']:30} {row['importance']:8.0f}")
    
    # Save model and results
    output_dir = Path(__file__).parent
    
    # Save model
    model_path = output_dir / "lightgbm_model.txt"
    best_model.save_model(str(model_path))
    print(f"\n✅ Model saved to {model_path}")
    
    # Save parameters and results
    results = {
        'model': 'LightGBM',
        'best_params': {k: int(v) if k in ['num_leaves', 'max_depth', 'n_estimators', 'min_child_samples'] else float(v) for k, v in best.items()},
        'train_auc': float(train_auc),
        'val_auc': float(val_auc),
        'test_auc': float(test_auc),
        'test_accuracy': float(test_acc),
        'baseline_accuracy': float(y_test.mean()),
        'num_games': len(X),
        'num_features': X.shape[1]
    }
    
    results_path = output_dir / "lightgbm_results.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"✅ Results saved to {results_path}")


if __name__ == "__main__":
    main()
