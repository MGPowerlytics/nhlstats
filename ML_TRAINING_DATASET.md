# NHL Machine Learning Training Dataset

## Overview
This builds a complete ML training dataset for predicting NHL game winners using advanced hockey analytics.

## Features Included

### Advanced Hockey Metrics (Calculated from Play-by-Play)

1. **Corsi** - All shot attempts (shots + blocks + misses)
   - Measures puck possession and offensive pressure
   
2. **Fenwick** - Unblocked shot attempts (shots + misses)
   - Like Corsi but excludes blocked shots (more predictive)
   
3. **High Danger Chances** - Shots from the slot (prime scoring area)
   - x-coordinate: -20 to 20 feet from center
   - y-coordinate: > 55 feet (close to net)
   
4. **Save Percentage** - Goalie performance
   - Calculated from goalie stats per game
   
5. **Shots For/Against** - Basic shot metrics
6. **Goals For/Against** - Scoring metrics

### Rolling Time Windows

Each metric is calculated as:
- **Last 3 Games (L3)** - Recent form
- **Last 10 Games (L10)** - Longer trend

### Features Per Game

For **HOME team** (12 features):
```
- home_corsi_l3, home_corsi_l10
- home_fenwick_l3, home_fenwick_l10  
- home_shots_l3, home_shots_l10
- home_goals_l3, home_goals_l10
- home_hd_chances_l3, home_hd_chances_l10
- home_save_pct_l3, home_save_pct_l10
```

For **AWAY team** (12 features):
```
- away_corsi_l3, away_corsi_l10
- away_fenwick_l3, away_fenwick_l10
- away_shots_l3, away_shots_l10
- away_goals_l3, away_goals_l10
- away_hd_chances_l3, away_hd_chances_l10
- away_save_pct_l3, away_save_pct_l10
```

**Total: 24 features** + target variable (`home_win`)

## Usage

### 1. Build Training Dataset

```python
from build_training_dataset import NHLTrainingDataset

builder = NHLTrainingDataset()
builder.connect()

# Build full dataset
df = builder.build_training_dataset()

# Or filter by date
df = builder.build_training_dataset(min_date='2021-11-01')

# Save to CSV
df.to_csv('data/nhl_training_data.csv', index=False)

builder.close()
```

### 2. Train XGBoost Model

```python
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score

# Load dataset
df = pd.read_csv('data/nhl_training_data.csv')

# Split features and target
X = df.drop(['game_id', 'game_date', 'home_team_id', 'away_team_id', 'home_win'], axis=1)
y = df['home_win']

# Time-series split (don't shuffle!)
split_idx = int(len(df) * 0.8)
X_train, X_test = X[:split_idx], X[split_idx:]
y_train, y_test = y[:split_idx], y[split_idx:]

# Train XGBoost
model = xgb.XGBClassifier(
    n_estimators=100,
    max_depth=6,
    learning_rate=0.1,
    random_state=42
)

model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
y_pred_proba = model.predict_proba(X_test)[:, 1]

print(f'Accuracy: {accuracy_score(y_test, y_pred):.3f}')
print(f'ROC-AUC: {roc_auc_score(y_test, y_pred_proba):.3f}')

# Feature importance
importance = pd.DataFrame({
    'feature': X.columns,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

print('\nTop 10 Most Important Features:')
print(importance.head(10))
```

### 3. Make Predictions for Betting

```python
import duckdb

# Get today's games
conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)

todays_games = conn.execute("""
    SELECT game_id, home_team_name, away_team_name
    FROM games
    WHERE game_date = CURRENT_DATE
""").fetchall()

# Build features for today's games
builder = NHLTrainingDataset()
builder.connect()
today_features = builder.build_training_dataset(min_date=str(pd.Timestamp.today().date()))

# Predict
X_today = today_features.drop(['game_id', 'game_date', 'home_team_id', 'away_team_id', 'home_win'], axis=1)
win_probs = model.predict_proba(X_today)[:, 1]

# Show predictions
for (game_id, home, away), prob in zip(todays_games, win_probs):
    print(f'{home} vs {away}: {prob:.1%} home win probability')
    
    # Betting value example
    if prob > 0.60:
        print(f'  → BET HOME (high confidence)')
    elif prob < 0.40:
        print(f'  → BET AWAY (high confidence)')
```

## TODO: Additional Features

These can be added later:

1. **Average Player Age** - Team age from player birth dates
2. **Travel Distance** - Away team distance from home arena
3. **Rest Days** - Days since last game
4. **Back-to-Back** - Playing on consecutive nights
5. **Home/Away Streaks** - Win/loss streaks by location
6. **Head-to-Head** - Historical matchup performance
7. **Time of Season** - Early/mid/late season effects
8. **Injuries** - Key player availability (if data available)

## Data Quality Notes

- **Minimum History**: Games excluded if teams don't have 10 games of history
- **Time-Series Safety**: Rolling windows use ONLY prior games (no data leakage)
- **Missing Values**: Handled with COALESCE to 0 where appropriate
- **Completed Games Only**: Filters for games with winning_team_id set

## Expected Performance

Based on similar NHL prediction models:
- **Baseline (Home Team Always Wins)**: ~54% accuracy
- **Simple Model (L10 stats)**: ~56-58% accuracy  
- **Advanced Model (with all features)**: ~59-62% accuracy
- **Professional Models**: ~60-65% accuracy

**Key**: Beat the odds market by 2-3% to be profitable after vig!

## Next Steps

1. ✅ Built feature calculation framework
2. ⏳ Collect more historical data (backfill still running)
3. ⏳ Add additional features (age, distance, rest)
4. ⏳ Train initial XGBoost model
5. ⏳ Backtest on historical games
6. ⏳ Deploy for daily predictions

The foundation is ready - now let the data accumulate! 🏒💰
