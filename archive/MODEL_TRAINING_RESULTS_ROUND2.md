# Model Training Results - Round 2

## Feature Implementation

### Batch 2: Head-to-Head + Situational Features (Tasks 76-80, 96-100)

**Implementation Date**: 2026-01-17

**Features Added**: 10 new features across 2 categories:

1. **Head-to-Head History (5 features)**:
   - H2H win percentage (all-time, last season, last 5 games)
   - Average goals scored/allowed vs opponent
   - Games count tracking

2. **Situational Context (5 features)**:
   - Points percentage (standings position)
   - Playoff spot flags (in playoffs, bubble team, eliminated)
   - Playoff matchup preview detection

**Total Features**: 73 (was 51)
**Total Games**: 4,426 (2021-2025 seasons)

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

| Metric | Round 1 (51 features) | Round 2 (73 features) | Change |
|--------|----------------------|----------------------|--------|
| Test Accuracy | 55.4% | 58.0% | **+2.6%** |
| Test ROC-AUC | ~0.55 | 0.585 | **+0.035** |
| Train-Test Gap | 27% | 7.9% | **-19.1%** |
| vs Baseline | +2.0% | +0.9% | -1.1% |

### Best Hyperparameters

```json
{
  "max_depth": 3,
  "min_child_weight": 6,
  "learning_rate": 0.0134,
  "subsample": 0.8185,
  "colsample_bytree": 0.9036,
  "gamma": 2.5229,
  "reg_alpha": 2.7732,
  "reg_lambda": 0.0042,
  "n_estimators": 75
}
```

**Key Changes from Defaults**:
- **max_depth**: 3 (was 6) - prevents overfitting
- **learning_rate**: 0.0134 (was 0.3) - slower, more stable learning
- **reg_alpha**: 2.77 (was 0) - L1 regularization added
- **n_estimators**: 75 (was 100) - fewer trees needed

### Top 10 Features

| Feature | Importance | Category |
|---------|-----------|----------|
| home_points_pct | 0.0537 | **Situational** ⭐ |
| away_shots_l10 | 0.0361 | Rolling |
| away_fenwick_for_l10 | 0.0360 | Rolling |
| away_points_pct | 0.0335 | **Situational** ⭐ |
| home_fenwick_against_l10 | 0.0328 | Rolling |
| away_corsi_for_l10 | 0.0327 | Rolling |
| away_corsi_against_l3 | 0.0283 | Rolling |
| away_fenwick_against_l10 | 0.0281 | Rolling |
| home_corsi_for_l3 | 0.0276 | Rolling |
| away_shots_l3 | 0.0270 | Rolling |

**Note**: New **Situational** features (points_pct) appear in top 4! 🎯

### Confusion Matrix (Test Set)

```
                Predicted
              Away    Home
Actual Away    90     195
       Home    84     295
```

- **True Positives** (Home predicted as Home): 295
- **True Negatives** (Away predicted as Away): 90
- **False Positives** (Away predicted as Home): 195
- **False Negatives** (Home predicted as Away): 84

## Analysis

### ✅ Major Improvements

1. **Overfitting Reduced**: Train-test gap dropped from 27% to 8% through aggressive regularization
2. **Test Accuracy Up**: 58.0% from 55.4% (+2.6 points)
3. **New Features Valuable**: Situational features (points_pct) ranked #1 and #4
4. **Stable Model**: Low learning rate + regularization = generalization

### ⚠️ Areas for Improvement

1. **Still Close to Baseline**: Only +0.9% better than predicting home team always wins
2. **High False Positives**: Model over-predicts home wins (195 FP vs 84 FN)
3. **H2H Features Not in Top 10**: Head-to-head features didn't make top 10 importance
4. **Low Precision on Away Wins**: Only 33% of predicted away wins are correct

### 🎯 Next Steps

1. **Add More Features**: 20/150 implemented (13%). Need:
   - Travel & Geography (timezone changes, distance)
   - Goalie performance metrics
   - Special teams (PP/PK rates)
   - Recent injury data

2. **Feature Engineering**:
   - Interaction terms (e.g., rest_advantage × points_pct)
   - Non-linear transformations
   - Time-based weights (recent games matter more)

3. **Model Improvements**:
   - Try ensembles (XGBoost + LightGBM + CatBoost)
   - Calibration (Platt scaling) to improve probabilities
   - Class weights to balance FP/FN ratio

4. **Data Quality**:
   - Verify H2H features are calculating correctly
   - Check for data leakage
   - Add more historical seasons (2018-2020)

## Files Generated

- `data/nhl_training_data.csv` - Training dataset with 73 features
- `data/nhl_xgboost_hyperopt_model.json` - Tuned model
- `data/nhl_best_params.json` - Best hyperparameters

## Completion Status

**NHL_FEATURES_TASKLIST.md**: 20/150 features complete (13%)
- ✅ Tasks 1-10: Schedule & Fatigue
- ✅ Tasks 76-80: Situational Context  
- ✅ Tasks 96-100: Head-to-Head History

**Next Batch Recommendation**: Tasks 16-25 (Travel & Geography) or Tasks 31-40 (Goalie Stats)

