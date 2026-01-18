# NHL Game Prediction - Model Comparison

Date: 2026-01-17  
Dataset: 4,426 games (2021-2025 seasons)  
Features: 98 advanced hockey statistics  
Split: 70% train / 15% val / 15% test  

---

## 📊 Model Performance Summary

| Model | Test AUC | Test Accuracy | Improvement | Train AUC | Overfit | Trials |
|-------|----------|---------------|-------------|-----------|---------|--------|
| **XGBoost** | **0.729** | 0.652 | +12.6% | 0.755 | 0.026 | 100 |
| **Random Forest** | 0.627 | 0.565 | +3.9% | 0.641 | 0.026 | 30 |
| **LightGBM** | 0.619 | 0.608 | +8.3% | 0.711 | 0.079 | 50 |
| **Neural Net (No Tuning)** | 0.596 | 0.562 | +3.6% | 0.848 | 0.263 | - |
| **Neural Net (Hyperopt)** | 0.555 | 0.559 | +4.7% | 0.497 | -0.086 | 30 |
| Baseline | - | 0.526 | - | - | - | - |

**Winner: XGBoost 🏆**

---

## 🔍 Detailed Analysis

### 1. XGBoost (Best Model)
**Hyperparameters:**
- max_depth: 8
- learning_rate: 0.0682
- n_estimators: 125
- min_child_weight: 1.49
- colsample_bytree: 0.8755

**Strengths:**
- Best overall test AUC (0.729)
- Minimal overfitting (2.6%)
- Best improvement over baseline
- Robust hyperparameter tuning (100 trials)

**Custom Loss:** `1 - (val_auc - abs(train_auc - val_auc))`

---

### 2. Random Forest
**Hyperparameters:**
- n_estimators: 400
- max_depth: 1 (very shallow!)
- min_samples_split: 14
- max_features: 0.5

**Strengths:**
- Second-best test AUC (0.627)
- Minimal overfitting (2.6%)
- Good interpretability

**Weaknesses:**
- Very shallow trees (max_depth=1) suggests data limitations
- Low precision on Away Win (0.65 precision, 0.18 recall)

---

### 3. LightGBM
**Hyperparameters:**
- max_depth: 3
- learning_rate: 0.2052
- n_estimators: 260
- num_leaves: 34

**Strengths:**
- Best test accuracy (60.8%)
- Fast training
- Leaf-wise tree growth

**Weaknesses:**
- More overfitting than XGBoost/RF (7.9%)
- Third place in AUC despite good accuracy

---

### 4. Neural Network (No Tuning)
**Architecture:** [128, 64, 32] with dropout=0.3

**Weaknesses:**
- Severe overfitting (26.3%!)
- Fourth place in test AUC (0.596)
- Not suited for tabular data with limited samples

---

### 5. Neural Network (Hyperopt)
**Architecture:** [224, 128, 40] with dropout=0.377

**Weaknesses:**
- Worst performance (0.555 test AUC)
- Actually underfitting (negative overfit)
- Hyperopt made it worse!
- Neural nets struggle with tabular sports data

---

## 🎯 Top Features (Common Across Models)

**Most Important Features:**
1. **home_points_pct** - Home team win percentage
2. **away_points_pct** - Away team win percentage
3. **away_corsi_against_l10** - Away team shots against (L10)
4. **home_fenwick_for_l10** - Home team unblocked shots (L10)
5. **away_fenwick_for_l10** - Away team unblocked shots (L10)

**Key Insight:** Recent team performance (points %) dominates predictions. Advanced hockey stats (Corsi/Fenwick) provide additional signal but secondary.

---

## 💡 Conclusions

### Why XGBoost Wins:
1. **Tree-based models excel at tabular data** - Better suited than neural nets for structured features
2. **Handles non-linear relationships** - Hockey stats have complex interactions
3. **Regularization prevents overfitting** - Only 2.6% train-val gap
4. **100 hyperopt trials** - More thorough optimization than other models

### Why Neural Nets Failed:
1. **Limited training data** - 4,426 games not enough for deep learning
2. **Tabular data disadvantage** - Neural nets shine with images/text, not structured data
3. **Feature engineering matters less** - Trees naturally find interactions, NNs need them pre-computed
4. **Overfitting issues** - Hard to regularize properly without massive datasets

### Why Random Forest is Competitive:
1. **Bagging reduces variance** - Multiple trees vote on prediction
2. **No overfitting** - Only 2.6% gap like XGBoost
3. **Interpretable** - Easy to understand feature importance
4. **Shallow trees** - max_depth=1 suggests need for more data or better features

---

## 🚀 Recommendations for Production

**Use XGBoost for betting system:**
- Highest test AUC (0.729)
- Proven custom loss function that penalizes overfitting
- Already integrated with Kalshi betting workflow
- Fast inference for daily predictions

**Continue data collection:**
- 4,426 games is good, but more data will improve all models
- Current backfill targeting 2021-2025 seasons (~6,500 games total)

**Feature engineering improvements:**
- Consider adding:
  - Rest days between games
  - Home/away back-to-back games
  - Injury reports (if available)
  - Head-to-head historical matchups
  - Goalie-specific stats

**Model ensembling:**
- Could combine XGBoost + LightGBM predictions for even better performance
- Weighted average: 70% XGBoost, 30% LightGBM

---

## 📁 Files Generated

- `train_xgboost_hyperopt.py` - XGBoost with 100 trials
- `train_lightgbm.py` - LightGBM with 50 trials  
- `train_random_forest.py` - Random Forest with 30 trials
- `train_neural_net.py` - Basic neural network
- `train_neural_net_hyperopt.py` - Neural network with 30 trials
- `lightgbm_model.txt` - Saved LightGBM model
- `neural_net_hyperopt_model.pt` - Saved PyTorch model
- `*_results.json` - Performance metrics for each model

---

**Final Verdict:** XGBoost is the clear winner for NHL betting predictions. Tree-based models dominate tabular sports data! 🏒🎰
