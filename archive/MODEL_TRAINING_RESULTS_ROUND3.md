# Model Training Results - Round 3

## Feature Implementation

### Batch 3: Situational Complete + Special Teams + Momentum (Tasks 81-85 + 5 new)

**Implementation Date**: 2026-01-17

**Features Added**: 10 new features across 3 categories:

1. **Situational & Context Complete (5 more features - Tasks 81-85)**:
   - Revenge game detection (lost to opponent recently)
   - Division rival matchup flag
   - Conference matchup flag
   - Win streak length (0-5)
   - Losing streak length (0-5)

2. **Special Teams & Season Stats (5 features)**:
   - Team shooting percentage (season to date)
   - Team save percentage (season approximation)
   - Power play percentage (season)
   - Penalty kill percentage (season)
   - Faceoff win percentage (season)

**Total Features**: 93 (was 73)
**Total Games**: 4,426 (2021-2025 seasons)
**Features Completed**: 30/155 (19%)

## Hyperparameter Tuning

**Custom Loss Function**:
```python
loss = 1 - (val_auc - abs(train_auc - val_auc))
```

This penalizes overfitting while maximizing validation AUC.

**Search Space**: 50 trials using Hyperopt TPE
- max_depth: [3-8]
- learning_rate: [0.01-0.3]
- reg_alpha/reg_lambda: [0.001-10]
- n_estimators: [50-300]

## Results

### Performance Comparison

| Metric | Round 2 (73 features) | Round 3 (93 features) | Change |
|--------|----------------------|----------------------|--------|
| Test Accuracy | 58.0% | 57.7% | **-0.3%** |
| Test ROC-AUC | 0.585 | 0.590 | **+0.005** |
| Train-Test Gap | 7.9% | 8.7% | +0.8% |
| vs Baseline | +0.9% | +0.6% | -0.3% |

### Best Hyperparameters

```json
{
  "max_depth": 3,
  "min_child_weight": 10,
  "learning_rate": 0.0102,
  "subsample": 0.6925,
  "colsample_bytree": 0.9943,
  "gamma": 4.8455,
  "reg_alpha": 0.1901,
  "reg_lambda": 0.0057,
  "n_estimators": 150
}
```

**Key Changes from Round 2**:
- **learning_rate**: 0.0102 (was 0.0134) - even slower learning
- **n_estimators**: 150 (was 75) - more trees to compensate
- **min_child_weight**: 10 (was 6) - more conservative splits
- **gamma**: 4.85 (was 2.52) - higher regularization

### Top 10 Features

| Feature | Importance | Category |
|---------|-----------|----------|
| home_points_pct | 0.0346 | **Situational** ⭐ |
| away_shots_l10 | 0.0284 | Rolling |
| away_corsi_for_l10 | 0.0265 | Rolling |
| away_fenwick_for_l10 | 0.0262 | Rolling |
| away_points_pct | 0.0249 | **Situational** ⭐ |
| home_fenwick_against_l10 | 0.0238 | Rolling |
| away_fenwick_against_l10 | 0.0220 | Rolling |
| away_shots_l3 | 0.0216 | Rolling |
| home_corsi_against_l10 | 0.0211 | Rolling |
| away_corsi_against_l3 | 0.0205 | Rolling |

**Note**: No new features (streaks, special teams) appear in top 10. Points percentage still dominates.

### Confusion Matrix (Test Set)

```
                Predicted
              Away    Home
Actual Away   103     182
       Home    99     280
```

- **True Positives** (Home predicted as Home): 280
- **True Negatives** (Away predicted as Away): 103
- **False Positives** (Away predicted as Home): 182
- **False Negatives** (Home predicted as Away): 99

## Analysis

### ⚠️ Diminishing Returns

1. **Accuracy Declined**: Test accuracy dropped from 58.0% to 57.7% despite adding 20 more features
2. **ROC-AUC Slight Gain**: +0.005 improvement, barely measurable
3. **No Feature Impact**: New features (win streaks, special teams) didn't appear in top 10
4. **Overfitting Risk**: Gap increased slightly from 7.9% to 8.7%

### 🔍 Why New Features Didn't Help

1. **Feature Redundancy**: Win streaks correlate with points_pct (already top feature)
2. **Low Variance**: Special teams stats (PP%, PK%) don't vary much game-to-game
3. **Season Stats**: Shooting %, save % are cumulative and slow to change
4. **Noise vs Signal**: Adding more features without strong predictive power dilutes model

### ✅ What's Working

1. **Points Percentage**: Consistently #1 feature (standings position matters!)
2. **Rolling Metrics**: L10/L3 shot metrics capture recent form well
3. **Regularization**: Hyperopt successfully prevents overfitting despite 93 features
4. **Stable Model**: Only 0.6% above baseline, but doesn't overfit wildly

### ⚠️ Areas for Concern

1. **Feature Saturation**: Adding more basic features isn't helping
2. **Still Close to Baseline**: Only +0.6% better than "always predict home"
3. **High FP Rate**: 182 false positives vs 99 false negatives (bias toward home)
4. **Limited Improvement**: 3 rounds of feature engineering, minimal gains

## 🎯 Next Steps - Strategic Pivot

### Stop Adding Basic Features
- 30/155 features implemented but diminishing returns evident
- Need quality over quantity

### Focus on High-Impact Changes

1. **External Data Sources**:
   - **Goalie assignments**: Starting goalie is critical (top 5 feature in NHL models)
   - **Injuries**: Key player absences drastically affect outcomes
   - **Line combinations**: Top line matchups matter
   - **Betting lines**: Market wisdom (opening/closing lines)

2. **Feature Engineering**:
   - **Interaction terms**: `rest_days × points_pct`, `h2h_wins × win_streak`
   - **Non-linear transforms**: Log, sqrt of cumulative stats
   - **Time decay weights**: Recent games matter more
   - **Opponent adjustments**: Normalize stats by opponent strength

3. **Model Improvements**:
   - **Try different models**: LightGBM, CatBoost, Neural Networks
   - **Ensemble methods**: Blend XGBoost + LightGBM + LogisticRegression
   - **Calibration**: Platt scaling to improve probability estimates
   - **Class weights**: Balance FP/FN ratio

4. **Data Quality**:
   - **Verify H2H calculation**: Are they computing correctly?
   - **Check data leakage**: Ensure no future information in features
   - **Add more seasons**: 2018-2020 data for more training examples
   - **Playoff vs Regular**: Separate models for different contexts

## Files Generated

- `data/nhl_training_data.csv` - Training dataset with 93 features
- `data/nhl_xgboost_hyperopt_model.json` - Tuned model (Round 3)
- `data/nhl_best_params.json` - Best hyperparameters
- `model_training_output.txt` - Full training log

## Completion Status

**NHL_FEATURES_TASKLIST.md**: 30/155 features complete (19%)
- ✅ Tasks 1-10: Schedule & Fatigue
- ✅ Tasks 76-85: Situational Context (ALL 10)
- ✅ Tasks 96-100: Head-to-Head History
- ✅ Special Teams: 5 features (PP%, PK%, FO%, Shooting%, Save%)

## Recommendations

1. **Pause feature engineering**: Diminishing returns on basic stats
2. **Get external data**: Goalie starters, injuries are game-changers
3. **Feature interactions**: Combine existing features creatively
4. **Try ensemble**: XGBoost + LightGBM + logistic regression
5. **Betting integration**: Use this model for selective betting, not all games

## Conclusion

Round 3 shows we've hit the limit of basic feature engineering. Test accuracy: **57.7%** (only 0.6% above baseline). While the model is stable and doesn't overfit, it's not achieving the predictive power needed for profitable betting.

**Key Takeaway**: More features ≠ better model. Need qualitatively different data (goalies, injuries) or more sophisticated feature engineering (interactions, transformations).

The hyperparameter tuning is working well (overfitting gap only 8.7%), but we're optimizing a model with insufficient signal. Time to pivot strategy.
