"""
Train Random Forest model for NHL game prediction.
Classic ensemble method - good baseline comparison.
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
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


def train_rf_model(params, X_train, y_train, X_val, y_val):
    """Train Random Forest model with given parameters"""
    
    model = RandomForestClassifier(
        n_estimators=int(params['n_estimators']),
        max_depth=int(params['max_depth']) if params['max_depth'] > 0 else None,
        min_samples_split=int(params['min_samples_split']),
        min_samples_leaf=int(params['min_samples_leaf']),
        max_features=params['max_features'],
        bootstrap=True,
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(X_train, y_train)
    
    # Evaluate
    train_pred = model.predict_proba(X_train)[:, 1]
    val_pred = model.predict_proba(X_val)[:, 1]
    
    train_auc = roc_auc_score(y_train, train_pred)
    val_auc = roc_auc_score(y_val, val_pred)
    
    return model, train_auc, val_auc


def objective(params, X_train, y_train, X_val, y_val):
    """Hyperopt objective function"""
    
    model, train_auc, val_auc = train_rf_model(params, X_train, y_train, X_val, y_val)
    
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
    print("🏒 Training Random Forest Model for NHL Game Prediction\n")
    
    # Load data
    print("Loading training data...")
    X, y = load_data()
    print(f"  Dataset: {len(X)} games, {X.shape[1]} features")
    print(f"  Home win rate: {y.mean():.1%}\n")
    
    # Split data: 70% train, 15% validation, 15% test
    X_temp, X_test, y_temp, y_test = train_test_split(X, y, test_size=0.15, random_state=42)
    X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=0.1765, random_state=42)
    
    print(f"Train set: {len(X_train)} games")
    print(f"Val set:   {len(X_val)} games")
    print(f"Test set:  {len(X_test)} games\n")
    
    # Define hyperparameter search space
    space = {
        'n_estimators': hp.quniform('n_estimators', 100, 500, 50),
        'max_depth': hp.quniform('max_depth', 0, 30, 1),  # 0 means None
        'min_samples_split': hp.quniform('min_samples_split', 2, 20, 1),
        'min_samples_leaf': hp.quniform('min_samples_leaf', 1, 10, 1),
        'max_features': hp.choice('max_features', ['sqrt', 'log2', 0.5, 0.7, 0.9]),
    }
    
    # Run hyperparameter optimization
    print("Starting hyperparameter optimization (30 trials)...")
    trials = Trials()
    
    best = fmin(
        fn=lambda params: objective(params, X_train, y_train, X_val, y_val),
        space=space,
        algo=tpe.suggest,
        max_evals=30,
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
    print(f"  n_estimators: {int(best['n_estimators'])}")
    print(f"  max_depth: {int(best['max_depth']) if best['max_depth'] > 0 else 'None'}")
    print(f"  min_samples_split: {int(best['min_samples_split'])}")
    print(f"  min_samples_leaf: {int(best['min_samples_leaf'])}")
    max_features_opts = ['sqrt', 'log2', 0.5, 0.7, 0.9]
    print(f"  max_features: {max_features_opts[int(best['max_features'])]}")
    
    print(f"\nBest model performance:")
    print(f"  Train AUC: {train_auc:.4f}")
    print(f"  Val AUC:   {val_auc:.4f}")
    print(f"  Overfit:   {abs(train_auc - val_auc):.4f}\n")
    
    # Evaluate on test set
    print("Evaluating on test set...")
    test_pred_proba = best_model.predict_proba(X_test)[:, 1]
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
        'importance': best_model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    for idx, row in feature_importance.head(10).iterrows():
        print(f"  {row['feature']:30} {row['importance']:.4f}")
    
    # Save results
    output_dir = Path(__file__).parent
    
    results = {
        'model': 'Random Forest',
        'best_params': {
            'n_estimators': int(best['n_estimators']),
            'max_depth': int(best['max_depth']) if best['max_depth'] > 0 else None,
            'min_samples_split': int(best['min_samples_split']),
            'min_samples_leaf': int(best['min_samples_leaf']),
            'max_features': max_features_opts[int(best['max_features'])]
        },
        'train_auc': float(train_auc),
        'val_auc': float(val_auc),
        'test_auc': float(test_auc),
        'test_accuracy': float(test_acc),
        'baseline_accuracy': float(y_test.mean()),
        'num_games': len(X),
        'num_features': X.shape[1]
    }
    
    results_path = output_dir / "random_forest_results.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to {results_path}")
    
    # Save feature importance
    feature_importance.to_csv(output_dir / "random_forest_feature_importance.csv", index=False)


if __name__ == "__main__":
    main()
