#!/usr/bin/env python3
"""
Quick start script - Run this once you have enough data collected

This script will:
1. Build the training dataset
2. Train a simple XGBoost model
3. Show feature importance
4. Make sample predictions
"""

import sys
from pathlib import Path

# Check if we have the required data
db_path = Path("data/nhlstats.duckdb")
if not db_path.exists():
    print("❌ Database not found. Run the data collection first!")
    sys.exit(1)

print("🏒 NHL ML Model - Quick Start")
print("=" * 50)

# Step 1: Build dataset
print("\n📊 Step 1: Building training dataset...")
from build_training_dataset import NHLTrainingDataset

builder = NHLTrainingDataset()
builder.connect()

try:
    df = builder.build_training_dataset()
    
    if len(df) < 100:
        print(f"\n⚠️  Warning: Only {len(df)} games available.")
        print("   Need more data for reliable predictions.")
        print("   Let the backfill collect more history first!")
        builder.close()
        sys.exit(0)
    
    # Save dataset
    output_file = Path("data/nhl_training_data.csv")
    df.to_csv(output_file, index=False)
    print(f"✅ Saved {len(df)} games to {output_file}")
    
finally:
    builder.close()

# Step 2: Train model
print("\n🤖 Step 2: Training XGBoost model...")

try:
    import xgboost as xgb
    from sklearn.metrics import accuracy_score, classification_report
    import pandas as pd
    
    # Prepare data
    X = df.drop(['game_id', 'game_date', 'home_team_id', 'away_team_id', 'home_win'], axis=1)
    y = df['home_win']
    
    # Time-series split (80/20)
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    print(f"  Training on {len(X_train)} games, testing on {len(X_test)} games")
    
    # Train
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        random_state=42,
        use_label_encoder=False,
        eval_metric='logloss'
    )
    
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\n✅ Model trained!")
    print(f"   Test Accuracy: {accuracy:.3f}")
    print(f"   Baseline (always home): {y_test.mean():.3f}")
    
    # Feature importance
    print("\n📈 Top 10 Most Important Features:")
    importance = pd.DataFrame({
        'feature': X.columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    for idx, row in importance.head(10).iterrows():
        print(f"   {row['feature']:30} {row['importance']:.4f}")
    
    # Save model
    model_file = Path("data/nhl_model.json")
    model.save_model(str(model_file))
    print(f"\n💾 Model saved to {model_file}")
    
    # Show sample predictions
    print("\n🎯 Sample Predictions (last 5 test games):")
    probs = model.predict_proba(X_test)[:, 1]
    
    for i in range(max(0, len(X_test)-5), len(X_test)):
        game_row = df.iloc[split_idx + i]
        prob = probs[i]
        actual = y_test.iloc[i]
        
        prediction = "HOME" if prob > 0.5 else "AWAY"
        result = "✅" if (prob > 0.5) == actual else "❌"
        
        print(f"   {result} {game_row['game_date']}: Predicted {prediction} ({prob:.1%}), Actual: {'HOME' if actual else 'AWAY'}")
    
except ImportError as e:
    print(f"\n⚠️  Missing dependencies: {e}")
    print("   Install with: pip install xgboost scikit-learn")
    print("   Then re-run this script")

print("\n" + "=" * 50)
print("✅ Setup complete! You're ready to start betting!")
print("\nNext steps:")
print("  1. Let more data collect (backfill is still running)")
print("  2. Retrain model periodically with: python quick_start.py")
print("  3. Make predictions with analyze_betting.py")
print("  4. Track performance and refine!")
