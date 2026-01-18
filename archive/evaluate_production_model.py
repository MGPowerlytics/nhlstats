"""
Evaluate the production XGBoost model on recent games.
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from sklearn.metrics import roc_auc_score, accuracy_score, classification_report, confusion_matrix
import json

def load_model():
    """Load the trained XGBoost model"""
    import xgboost as xgb
    
    # Try hyperopt model first (production model)
    model_path = Path(__file__).parent / "data" / "nhl_xgboost_hyperopt_model.json"
    
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found at {model_path}. Run train_xgboost_hyperopt.py first.")
    
    # Load model
    model = xgb.Booster()
    model.load_model(str(model_path))
    
    # Get feature names from training data
    data_path = Path(__file__).parent / "data" / "nhl_training_data.csv"
    df = pd.read_csv(data_path, nrows=1)
    
    # Extract feature columns (exclude metadata and target)
    exclude_cols = ['game_id', 'game_date', 'home_team_name', 'away_team_name', 'home_win']
    feature_names = [col for col in df.columns if col not in exclude_cols]
    
    return model, feature_names

def load_recent_games(n_games=200):
    """Load the most recent N games from training data"""
    data_path = Path(__file__).parent / "data" / "nhl_training_data.csv"
    df = pd.read_csv(data_path)
    
    # Sort by game_date to get most recent
    df['game_date'] = pd.to_datetime(df['game_date'])
    df = df.sort_values('game_date', ascending=False)
    
    # Take most recent N games
    recent_games = df.head(n_games).copy()
    
    return recent_games

def evaluate_model(model, feature_names, games_df):
    """Evaluate model on given games"""
    import xgboost as xgb
    
    # Prepare features
    X = games_df[feature_names]
    y = games_df['home_win']
    
    # Convert to DMatrix for XGBoost
    dtest = xgb.DMatrix(X, feature_names=feature_names)
    
    # Get predictions
    y_pred_proba = model.predict(dtest)
    y_pred = (y_pred_proba > 0.5).astype(int)
    
    # Calculate metrics
    auc = roc_auc_score(y, y_pred_proba)
    accuracy = accuracy_score(y, y_pred)
    
    # Confusion matrix
    cm = confusion_matrix(y, y_pred)
    
    # Classification report
    report = classification_report(y, y_pred, target_names=['Away Win', 'Home Win'], output_dict=True)
    
    # Baseline (always predict home win)
    baseline_accuracy = y.mean()
    
    # Betting performance simulation
    betting_results = simulate_betting(y, y_pred_proba, games_df)
    
    return {
        'auc': auc,
        'accuracy': accuracy,
        'baseline_accuracy': baseline_accuracy,
        'improvement': accuracy - baseline_accuracy,
        'confusion_matrix': cm,
        'classification_report': report,
        'betting_results': betting_results,
        'predictions_df': games_df[['game_date', 'home_team_name', 'away_team_name', 'home_win']].copy().assign(
            home_win_prob=y_pred_proba,
            predicted_winner=y_pred
        )
    }

def simulate_betting(y_true, y_pred_proba, games_df, threshold=0.60):
    """
    Simulate betting performance.
    Only bet when model confidence > threshold.
    Assume 50/50 odds for simplicity.
    """
    
    # Identify high-confidence bets
    home_bets = y_pred_proba > threshold
    away_bets = y_pred_proba < (1 - threshold)
    
    # Calculate wins
    home_bet_wins = ((y_true == 1) & home_bets).sum()
    away_bet_wins = ((y_true == 0) & away_bets).sum()
    
    total_bets = home_bets.sum() + away_bets.sum()
    total_wins = home_bet_wins + away_bet_wins
    
    if total_bets > 0:
        win_rate = total_wins / total_bets
        roi = (total_wins - total_bets) / total_bets  # Assuming $1 bet, even odds
    else:
        win_rate = 0
        roi = 0
    
    return {
        'threshold': threshold,
        'total_bets': int(total_bets),
        'total_wins': int(total_wins),
        'win_rate': win_rate,
        'roi': roi,
        'home_bets': int(home_bets.sum()),
        'away_bets': int(away_bets.sum()),
        'home_wins': int(home_bet_wins),
        'away_wins': int(away_bet_wins)
    }

def main():
    print("🏒 Evaluating Production XGBoost Model on Recent Games\n")
    print("="*70)
    
    # Load model
    print("\n📦 Loading production model...")
    model, feature_names = load_model()
    print(f"   ✅ Model loaded with {len(feature_names)} features")
    
    # Load recent games
    print("\n📊 Loading recent 200 games...")
    recent_games = load_recent_games(n_games=200)
    
    date_range = f"{recent_games['game_date'].min().date()} to {recent_games['game_date'].max().date()}"
    print(f"   ✅ Loaded 200 games from {date_range}")
    print(f"   Home win rate: {recent_games['home_win'].mean():.1%}")
    
    # Evaluate
    print("\n🔮 Generating predictions and evaluating...")
    results = evaluate_model(model, feature_names, recent_games)
    
    # Print results
    print("\n" + "="*70)
    print("📈 PRODUCTION MODEL PERFORMANCE (Last 200 Games)")
    print("="*70)
    
    print(f"\n🎯 Overall Metrics:")
    print(f"   AUC:              {results['auc']:.4f}")
    print(f"   Accuracy:         {results['accuracy']:.1%}")
    print(f"   Baseline:         {results['baseline_accuracy']:.1%} (always predict home win)")
    print(f"   Improvement:      {results['improvement']:+.1%}")
    
    print(f"\n📊 Confusion Matrix:")
    cm = results['confusion_matrix']
    print(f"                    Predicted")
    print(f"                Away Win  Home Win")
    print(f"   Actual  Away     {cm[0,0]:4d}      {cm[0,1]:4d}")
    print(f"           Home     {cm[1,0]:4d}      {cm[1,1]:4d}")
    
    print(f"\n📋 Classification Report:")
    report = results['classification_report']
    print(f"   Away Win: Precision={report['Away Win']['precision']:.3f}, "
          f"Recall={report['Away Win']['recall']:.3f}, "
          f"F1={report['Away Win']['f1-score']:.3f}")
    print(f"   Home Win: Precision={report['Home Win']['precision']:.3f}, "
          f"Recall={report['Home Win']['recall']:.3f}, "
          f"F1={report['Home Win']['f1-score']:.3f}")
    
    # Betting simulation
    betting = results['betting_results']
    print(f"\n💰 Betting Simulation (confidence > {betting['threshold']:.0%}):")
    print(f"   Total Bets:       {betting['total_bets']}")
    print(f"   Total Wins:       {betting['total_wins']}")
    print(f"   Win Rate:         {betting['win_rate']:.1%}")
    print(f"   ROI:              {betting['roi']:+.1%}")
    print(f"   Home Bets:        {betting['home_bets']} ({betting['home_wins']} wins)")
    print(f"   Away Bets:        {betting['away_bets']} ({betting['away_wins']} wins)")
    
    # Show some sample predictions
    print(f"\n🎲 Sample Predictions (10 most recent games):")
    print("="*70)
    
    preds_df = results['predictions_df'].head(10)
    for idx, row in preds_df.iterrows():
        actual = "HOME" if row['home_win'] == 1 else "AWAY"
        predicted = "HOME" if row['predicted_winner'] == 1 else "AWAY"
        correct = "✅" if actual == predicted else "❌"
        
        print(f"{correct} {row['game_date'].date()} | "
              f"{row['away_team_name']} @ {row['home_team_name']}")
        print(f"   Model: {row['home_win_prob']:.1%} home win | "
              f"Predicted: {predicted} | Actual: {actual}")
    
    # Save detailed results
    output_path = Path(__file__).parent / "production_model_evaluation.json"
    
    save_results = {
        'n_games': 200,
        'date_range': date_range,
        'auc': float(results['auc']),
        'accuracy': float(results['accuracy']),
        'baseline_accuracy': float(results['baseline_accuracy']),
        'improvement': float(results['improvement']),
        'confusion_matrix': results['confusion_matrix'].tolist(),
        'betting_simulation': betting
    }
    
    with open(output_path, 'w') as f:
        json.dump(save_results, f, indent=2)
    
    # Save predictions CSV
    csv_path = Path(__file__).parent / "production_model_predictions.csv"
    results['predictions_df'].to_csv(csv_path, index=False)
    
    print(f"\n✅ Detailed results saved to {output_path}")
    print(f"✅ Predictions saved to {csv_path}")
    print("\n" + "="*70)

if __name__ == "__main__":
    main()
