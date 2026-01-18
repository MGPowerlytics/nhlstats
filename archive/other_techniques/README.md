# Alternative Modeling Techniques for NHL Game Prediction

This folder contains both **traditional statistical methods** and **machine learning approaches** for predicting NHL game outcomes.

## 🏆 Key Finding

**Traditional statistical methods (Elo rating) match or beat complex ML models!**

- **Elo Rating**: 59.3% accuracy, 0.591 AUC (3 parameters, instant predictions)
- **XGBoost**: 57.7% accuracy, 0.590 AUC (93 features, hours of training)

**Recommendation**: Start with Elo for production betting. Simple, fast, interpretable.

---

## 📊 Performance Summary

| Model | Test Accuracy | Test AUC | Complexity | Speed |
|-------|---------------|----------|------------|-------|
| **Elo Rating** ⭐ | 59.3% | **0.591** | Very Low | Instant |
| Bradley-Terry | **59.6%** | 0.575 | Low | Fast |
| XGBoost | 57.7% | 0.590 | Very High | Slow |
| LightGBM | 60.8% | 0.619 | High | Medium |
| Random Forest | 56.5% | 0.627 | Medium | Medium |
| Logistic Regression | 56.0% | 0.570 | Low | Fast |
| Neural Net | 56.2% | 0.596 | Very High | Slow |
| **Baseline** | 57.1% | - | - | - |

**See [TRADITIONAL_STATS_COMPARISON.md](TRADITIONAL_STATS_COMPARISON.md) for detailed analysis.**

---

## Traditional Statistical Methods



### 1. Elo Rating (`train_traditional_stats.py`)
**Simple chess-style ratings that update after each game**
- Each team has a rating that increases with wins, decreases with losses
- Home advantage built in (+100 Elo points)
- K-factor controls rating volatility
- **Best traditional method**: 59.3% accuracy, 0.591 AUC

**Run:**
```bash
python other_techniques/train_traditional_stats.py
```

**Why It Works:**
- Captures temporal dynamics (recent form matters)
- Naturally regularized (no overfitting)
- Interpretable (team ratings show relative strength)
- Fast (instant predictions, no training)

---

### 2. Bradley-Terry Model (`train_traditional_stats.py`)
**Pairwise comparison model with maximum likelihood estimation**
- Models team strength as exponential parameters
- Iterative updates until convergence
- Home advantage as multiplicative factor
- **Best accuracy**: 59.6%, 0.575 AUC

---

### 3. Logistic Regression (`train_traditional_stats.py`)
**Simple linear model with L2 regularization**
- Uses all 98 features
- StandardScaler normalization
- C=1.0 regularization
- Performance: 56.0% accuracy, 0.570 AUC

---

## Machine Learning Methods
**Gradient boosting with a different tree-building approach**
- Similar to XGBoost but uses leaf-wise tree growth instead of level-wise
- Often faster training with similar or better accuracy
- Hyperparameter tuning with hyperopt (50 trials)
- Same custom loss function as XGBoost: `1 - (val_auc - abs(train_auc - val_auc))`

**Run:**
```bash
python other_techniques/train_lightgbm.py
```

**Output:**
- `lightgbm_model.txt` - Trained model
- `lightgbm_results.json` - Performance metrics

---

### 5. Random Forest (`train_random_forest.py`)
**Classic ensemble method - bagging-based trees**
- No boosting - trees trained independently
- Good baseline to compare against gradient boosting methods
- Less prone to overfitting than boosted methods
- Hyperparameter tuning with hyperopt (30 trials)

**Run:**
```bash
python other_techniques/train_random_forest.py
```

**Output:**
- `random_forest_results.json` - Performance metrics
- `random_forest_feature_importance.csv` - Feature rankings

---

### 6. Neural Network (`train_neural_net.py`)
**Deep learning with PyTorch**
- Multi-layer perceptron (MLP) with 3 hidden layers [128, 64, 32]
- Batch normalization and dropout for regularization
- Early stopping to prevent overfitting
- Adam optimizer with learning rate 0.001

**Run:**
```bash
python other_techniques/train_neural_net.py
```

**Output:**
- `neural_net_model.pt` - PyTorch model checkpoint
- `neural_net_results.json` - Performance metrics

---

## Requirements

Additional dependencies needed:
```bash
pip install lightgbm torch scikit-learn
```

## Data

All models use the same training data: `../data/nhl_training_data.csv`

**Features:**
- Rolling statistics (L3, L10 games)
- Corsi For/Against (home & away)
- Fenwick For/Against (home & away)
- Shots, goals, high-danger chances
- Save percentage
- Team-level aggregated stats

**Target:** `home_win` (binary: 1 = home team wins, 0 = away team wins)

---

## Evaluation Metrics

All models report:
- **AUC-ROC** on train, validation, and test sets
- **Accuracy** on test set
- **Baseline accuracy** (always predict home win)
- **Classification report** (precision, recall, F1)
- **Feature importance** (where applicable)

**Data Split:** 70% train, 15% validation, 15% test (same split across all models)

---

## Comparison

After running all models, compare results:

```bash
# View all results
cat other_techniques/*_results.json

# Compare test AUC scores
jq '.model, .test_auc' other_techniques/*_results.json
```

Expected considerations:
- **XGBoost/LightGBM** typically perform best on tabular data
- **Random Forest** provides good baseline without hyperparameter sensitivity
- **Neural Network** may need more data to outperform tree-based methods
- All models use same train/val/test split for fair comparison

---

## Notes

- All models respect the same evaluation protocol as the main XGBoost model
- No changes to existing `train_xgboost_hyperopt.py`
- Results are independent and can be compared directly
- Models trained on same data snapshot (4,206 games as of 2026-01-17)
