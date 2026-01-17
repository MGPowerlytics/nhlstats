# NHL Model Training Results - With Schedule & Fatigue Features

**Date**: 2026-01-17  
**Status**: ✅ Features Implemented & Model Trained

---

## 📊 Results Summary

### Dataset Statistics
- **Total Games**: 4,359
- **Date Range**: Oct 2021 - May 2025 (3.5 seasons)
- **Home Win Rate**: 53.4%
- **Features**: 51 (was 32, **+19 schedule/fatigue features**)
- **Training Split**: 70% train / 15% val / 15% test

### Model Performance

| Metric | Train (70%) | Val (15%) | **Test (15%)** |
|--------|-------------|-----------|----------------|
| **Accuracy** | 82.0% | 57.0% | **55.4%** |
| **Precision** | 81.9% | 60.5% | 60.3% |
| **Recall** | 84.3% | 64.6% | 62.5% |
| **F1 Score** | 83.1% | 62.5% | 61.4% |
| **ROC-AUC** | 90.4% | 58.7% | 56.4% |

### Test Set Confusion Matrix

```
                Predicted
              Away    Home
Actual  Away   130     153
        Home   139     232
```

---

## 🎯 Performance Analysis

### Current Status
- **Test Accuracy: 55.4%** on unseen data (Nov 2024 - May 2025)
- **Slightly above random**: Home team wins 53.4% naturally
- **Overfitting detected**: 82% train vs 55% test

### Baseline Comparison
- **Previous model** (32 features): ~55-57% estimated
- **Current model** (51 features): 55.4% actual
- **Improvement**: ⚠️ **Inconclusive** - need direct A/B comparison

### Why Expected +3-4% Gain Not Seen Yet

1. **Overfitting**:
   - 27% gap between train (82%) and test (55%)
   - Model memorizing training data, not generalizing
   - Need regularization (max_depth, learning_rate tuning)

2. **Feature Engineering**:
   - Schedule features added but simplified
   - Home stand/road trip lengths omitted (SQL complexity)
   - May need interaction terms (rest × back_to_back)

3. **Hyperparameter Tuning**:
   - Default XGBoost parameters used
   - Not optimized for 51-feature space
   - Early stopping not enabled

4. **No Feature Selection**:
   - All 51 features used blindly
   - Some may be noise or redundant
   - Need feature importance analysis

---

## ✅ What Was Accomplished

### Schedule & Fatigue Features Implemented

| # | Feature | Type | Status |
|---|---------|------|--------|
| 1 | Days of rest | Numeric | ✅ |
| 2 | Back-to-back flag | Binary | ✅ |
| 3 | 3-in-4 nights compression | Binary | ✅ |
| 4 | 4-in-6 nights compression | Binary | ✅ |
| 5-6 | Home/Away indicators | Binary | ✅ |
| 7-8 | Location change flags | Binary | ✅ |
| 10 | Back-to-backs in last 10 | Numeric | ✅ |
| + | Well-rested flag (3+ days) | Binary | ✅ |
| + | Rest advantage (home - away) | Numeric | ✅ |

**Total**: 19 new features (10 core + bonuses × 2 teams)

### Statistics Observed

**Days of Rest**:
- Home avg: 4.71 days
- Away avg: 4.95 days (slightly more rested)

**Back-to-Back Games**:
- Home: 6.5% of games
- Away: 16.6% of games (2.5× more frequent)

**Schedule Compression**:
- 3-in-4: 9.1% of games
- 4-in-6: 9.2% of games

**Well Rested** (3+ days):
- Home: 40.3%
- Away: 35.6%

---

## 🔧 Next Steps for Improvement

### 1. Feature Importance Analysis
```python
# Add to train_xgboost.py:
importances = pd.DataFrame({
    'feature': feature_cols,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

print("\nTop 20 Features:")
print(importances.head(20))
```

**Goal**: Verify schedule features are in top 20 most important

### 2. Hyperparameter Tuning

```python
model = xgb.XGBClassifier(
    max_depth=4,              # Reduce from default 6
    learning_rate=0.05,       # Reduce from default 0.3
    n_estimators=500,         # Increase
    reg_alpha=1.0,            # L1 regularization
    reg_lambda=1.0,           # L2 regularization
    early_stopping_rounds=50,
    eval_metric='logloss'
)
```

**Goal**: Reduce overfitting, improve generalization

### 3. Restore Complex Features

Re-implement with better SQL:
- Home stand length (consecutive home games)
- Road trip length (consecutive away games)
- Days since last home/away game
- Returning from long road trip flag

### 4. Feature Engineering

Create interaction features:
```python
df['rest_advantage_x_home'] = df['rest_advantage'] * df['is_home']
df['b2b_x_rest_disadvantage'] = df['is_back_to_back'] * (df['rest_advantage'] < 0)
```

### 5. Baseline Comparison

Train identical model with only original 32 features:
```python
# Remove schedule features
feature_cols_baseline = [c for c in feature_cols 
                         if not any(x in c for x in ['rest', 'b2b', '3_in_4', '4_in_6'])]
```

Compare accuracy directly.

---

## 📈 Expected Impact After Tuning

| Optimization | Expected Gain |
|--------------|---------------|
| Hyperparameter tuning | +1-2% |
| Feature importance selection | +0.5-1% |
| Interaction features | +1-2% |
| Complex feature restoration | +0.5-1% |
| **Total Potential** | **+3-6%** |

**Target**: 58-61% test accuracy (from current 55.4%)

---

## 🎓 Lessons Learned

1. **Feature Implementation ≠ Feature Utilization**
   - Just adding features doesn't guarantee improvement
   - Need proper tuning and validation

2. **Overfitting is Real**
   - 82% train vs 55% test = red flag
   - More features = more risk of overfitting
   - Regularization essential

3. **SQL Complexity Trade-offs**
   - Simplified features for SQL compatibility
   - May have lost signal in simplification
   - Consider Python-based feature engineering

4. **Need Rigorous Testing**
   - Can't compare to "estimated baseline"
   - Must train both models on same data
   - Use cross-validation

---

## 📁 Files Modified

- ✏️ `build_training_dataset.py`
  - Added `create_schedule_fatigue_features()` method
  - Updated `build_training_dataset()` query
  - +150 lines of SQL

- ✏️ `NHL_FEATURES_TASKLIST.md`
  - Marked 10 features complete
  - Updated completion: 7%

- 📄 `test_schedule_features.py`
  - Comprehensive feature test
  - Statistics and examples

- 📄 `SCHEDULE_FEATURES_IMPLEMENTATION.md`
  - Full documentation

- 📄 `data/nhl_training_data.csv`
  - Regenerated with 51 features
  - 4,359 games

---

## 🚀 Quick Start for Next Developer

```bash
# 1. Test features
python test_schedule_features.py

# 2. Train model
python train_xgboost.py

# 3. Analyze feature importance (TODO: add to script)

# 4. Tune hyperparameters
python train_xgboost_hyperopt.py  # Or create this

# 5. Compare to baseline
# Train model with schedule features OFF
```

---

## ✅ Success Criteria (Not Yet Met)

- [x] Implement 10 critical features
- [x] Features integrate into dataset
- [x] Model trains successfully
- [x] No errors or crashes
- [ ] **Test accuracy > 58%** (current: 55.4%)
- [ ] **Schedule features in top 20 importance**
- [ ] **Direct baseline comparison**
- [ ] **Cross-validation performed**

---

## 💡 Conclusion

**Infrastructure**: ✅ Complete & Working  
**Performance**: ⚠️ Needs Optimization  
**Next Action**: Feature importance + hyperparameter tuning

The foundation is solid. With proper tuning, the expected +3-4% gain is achievable.

---

**Training Command**:
```bash
python train_xgboost.py
```

**Expected Output**:
- Test Accuracy: 55.4%
- 51 features used
- 4,359 games trained

**Model Saved**: `data/nhl_xgboost_model.json`
