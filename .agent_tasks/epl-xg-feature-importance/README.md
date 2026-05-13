# EPL xG/xGA Feature Importance Analysis

**Date**: 2025-07-17
**Author**: Explorer (Henchman)
**Status**: Complete

---

## Objective

Quantify the contribution of the 4 new xG/xGA rolling features (`home_avg_xg`, `away_avg_xg`, `home_avg_xga`, `away_avg_xga`) added to the EPL ensemble model relative to the existing 13 features. The model is a multinomial LogisticRegression with 3 classes (0=Away, 1=Draw, 2=Home) trained on 7,932 EPL matches from football-data.co.uk CSVs (2005–2025).

---

## 1. Coefficient Magnitudes per Class

| Feature | Away Win | Draw | Home Win | Avg |coef| |
|---|---|---|---|---|---|
| `elo_prob_home` | +0.1036 | -0.0114 | -0.0922 | 0.0691 |
| `elo_prob_draw` | +0.0062 | -0.0197 | +0.0135 | 0.0131 |
| `elo_prob_away` | -0.1193 | +0.0205 | +0.0988 | 0.0795 |
| `elo_diff` | -0.2290 | +0.0097 | +0.2193 | 0.1527 |
| `home_form` | -0.0285 | +0.0705 | -0.0420 | 0.0470 |
| `away_form` | -0.0653 | -0.0171 | +0.0824 | 0.0550 |
| `home_avg_gf` | +0.0410 | -0.0459 | +0.0049 | 0.0306 |
| `away_avg_gf` | -0.0229 | +0.0442 | -0.0213 | 0.0294 |
| `home_avg_ga` | -0.0156 | +0.0407 | -0.0251 | 0.0271 |
| `away_avg_ga` | -0.0022 | -0.0292 | +0.0314 | 0.0209 |
| **`home_avg_xg`** | **+0.0020** | **+0.0035** | **-0.0056** | **0.0037** |
| **`away_avg_xg`** | **-0.0187** | **+0.0116** | **+0.0072** | **0.0125** |
| **`home_avg_xga`** | **+0.0154** | **+0.0208** | **-0.0362** | **0.0241** |
| **`away_avg_xga`** | **-0.0246** | **-0.0006** | **+0.0252** | **0.0168** |
| `bookmaker_prob_home` | -0.3049 | +0.0273 | +0.2776 | 0.2033 |
| `bookmaker_prob_draw` | -0.0506 | +0.1337 | -0.0831 | 0.0891 |
| `bookmaker_prob_away` | +0.3517 | -0.0687 | -0.2830 | 0.2345 |

**Sign interpretation**: Coefficients are scaled (StandardScaler). Positive coefficients push probability toward that class. For example, `bookmaker_prob_away` has +0.3517 for Away Win → high bookmaker away probability strongly predicts away wins, as expected.

---

## 2. Relative Feature Importance Ranking (avg |coefficient|)

| Rank | Feature | Avg |coef| | Group |
|---|---|---|---|---|
| 1 | `bookmaker_prob_away` | **0.2345** | Bookmaker |
| 2 | `bookmaker_prob_home` | **0.2033** | Bookmaker |
| 3 | `elo_diff` | **0.1527** | Elo |
| 4 | `bookmaker_prob_draw` | 0.0891 | Bookmaker |
| 5 | `elo_prob_away` | 0.0795 | Elo |
| 6 | `elo_prob_home` | 0.0691 | Elo |
| 7 | `away_form` | 0.0550 | Form |
| 8 | `home_form` | 0.0470 | Form |
| 9 | `home_avg_gf` | 0.0306 | Goals |
| 10 | `away_avg_gf` | 0.0294 | Goals |
| 11 | `home_avg_ga` | 0.0271 | Goals |
| **12** | **`home_avg_xga`** | **0.0241** | **xG (NEW)** |
| 13 | `away_avg_ga` | 0.0209 | Goals |
| **14** | **`away_avg_xga`** | **0.0168** | **xG (NEW)** |
| 15 | `elo_prob_draw` | 0.0131 | Elo |
| **16** | **`away_avg_xg`** | **0.0125** | **xG (NEW)** |
| **17** | **`home_avg_xg`** | **0.0037** | **xG (NEW)** |

**Key finding**: The 4 xG features rank **12th, 14th, 16th, and 17th** out of 17 features. `home_avg_xg` is the single least important feature by coefficient magnitude.

---

## 3. Group Importance (sum of |coefficient| by feature group)

| Group | Sum |coef| (all classes) | Features | Avg |coef|/Feat |
|---|---|---|---|---|
| **Bookmaker** | **1.5807** | 3 | **0.1756** |
| Elo | 0.9432 | 4 | 0.0786 |
| Form | 0.3060 | 2 | 0.0510 |
| Goals | 0.3244 | 4 | 0.0270 |
| **xG (NEW)** | **0.1713** | **4** | **0.0143** |

**Key finding**: The xG group contributes the **least** of all 5 groups. Bookmaker probabilities dominate with ~9× the per-feature impact of xG features. Even the Goals group (simple rolling goals averages) has ~1.9× the per-feature contribution of xG.

---

## 4. Permutation Importance (accuracy drop, n_repeats=10)

Permutation importance measures how much accuracy drops when a feature's values are randomly shuffled — more robust than raw coefficient magnitude.

| Rank | Feature | Importance (ΔAcc) | Std Dev | Group |
|---|---|---|---|---|
| 1 | `bookmaker_prob_away` | **+0.059783** | 0.002655 | Bookmaker |
| 2 | `bookmaker_prob_home` | +0.034228 | 0.003868 | Bookmaker |
| 3 | `elo_diff` | +0.019100 | 0.001916 | Elo |
| 4 | `elo_prob_home` | +0.001841 | 0.002226 | Elo |
| 5 | `away_form` | +0.001828 | 0.001408 | Form |
| 6 | `elo_prob_away` | +0.001551 | 0.001892 | Elo |
| 7 | `home_form` | +0.001172 | 0.000742 | Form |
| **8** | **`away_avg_xg`** | **+0.000845** | **0.000469** | **xG (NEW)** |
| 9 | `home_avg_gf` | +0.000441 | 0.000751 | Goals |
| 10 | `elo_prob_draw` | +0.000328 | 0.000289 | Elo |
| 11 | `away_avg_gf` | +0.000290 | 0.000541 | Goals |
| **12** | **`home_avg_xga`** | **+0.000227** | **0.000468** | **xG (NEW)** |
| 13 | `bookmaker_prob_draw` | +0.000151 | 0.000864 | Bookmaker |
| **14** | **`away_avg_xga`** | **+0.000076** | **0.000686** | **xG (NEW)** |
| 15 | `away_avg_ga` | -0.000076 | 0.000663 | Goals |
| 16 | `home_avg_ga` | -0.000340 | 0.000451 | Goals |
| **17** | **`home_avg_xg`** | **-0.000479** | **0.000238** | **xG (NEW)** |

**Permutation importance by group**:

| Group | Sum Importance | Avg Importance/Feat |
|---|---|---|
| **Bookmaker** | **0.094163** | **0.031388** |
| Elo | 0.022819 | 0.005705 |
| Form | 0.003001 | 0.001500 |
| **xG (NEW)** | **0.000668** | **0.000167** |
| Goals | 0.000315 | 0.000079 |

**Key finding**: xG permutation importance is **~188× smaller** than Bookmaker and **~34× smaller** than Elo. `home_avg_xg` has a **negative** permutation importance (−0.0005), meaning shuffling it actually *improves* accuracy (it's noise). The xG group sum (0.000668) is barely above zero.

---

## 5. Marginal Gain Analysis: With vs Without xG Features

Refit two models from scratch on the full 7,932-row dataset, with identical hyperparameters (LogisticRegression, max_iter=2000, solver='lbfgs'), and compare 5-fold cross-validation accuracy.

| Model | Mean Accuracy | Std Dev |
|---|---|---|
| With xG (17 features) | **0.5435** | 0.0022 |
| Without xG (13 features) | **0.5444** | 0.0019 |
| **Delta** | **−0.0009 (−0.09%)** | |

**Individual fold comparison**:

| Fold | With xG | Without xG | Delta |
|---|---|---|---|
| 1 | 0.5476 | 0.5463 | +0.0013 |
| 2 | 0.5438 | 0.5432 | +0.0006 |
| 3 | 0.5429 | 0.5441 | −0.0013 |
| 4 | 0.5410 | 0.5416 | −0.0006 |
| 5 | 0.5422 | 0.5467 | −0.0044 |

**Key finding**: The model **without** xG features achieves *higher* mean accuracy (0.5444 vs 0.5435). The xG features produce a **negative marginal gain of −0.09%**. The difference is within the cross-validation noise (overlapping std devs), meaning the xG features add zero predictive value.

---

## 6. Interpretation & Recommendations

### Why xG Features Don't Help

1. **High correlation with existing features**: Rolling avg xG/xGA correlates with rolling avg goals-for/goals-against (r ≈ 0.54–0.62 per prior analysis). The Goals features already capture team scoring form — xG adds mostly redundant information.
2. **Sparse data**: Only 5 seasons (2021–2026) have xG data, covering ~4,600 of 7,932 training rows (58%). The remaining 42% of rows use fallback defaults (1.5/1.3 xG), diluting signal. The model can't learn from default values.
3. **Small feature scales**: The xG features have coefficient magnitudes (0.0037–0.0241) that are 5–70× smaller than the dominant features (Bookmaker: 0.0891–0.2345).
4. **Permutation importance confirms**: xG permutation importance sum (0.00067) is negligible. `home_avg_xg` actually has *negative* importance — it degrades accuracy when shuffled, suggesting it's noise.

### Recommendation

**Drop the 4 xG features** from the EPL ensemble model. They add complexity with zero accuracy benefit. Keep the model at 13 features. The xG data may become useful if:
- More seasons accumulate (need ~5+ more full Understat-enriched seasons)
- The feature engineering is improved (e.g., form window >5 games, or using xG ratios instead of rolling averages)
- The feature is used in a different model architecture (e.g., gradient boosting where non-linearities could capture xG-specific information)

### Current Model Performance

| Metric | Value |
|---|---|
| Baseline accuracy (predict home every time) | 45.5% |
| 13-feature model accuracy (5-fold CV) | **54.44%** |
| Improvement over baseline | **+8.94 pp** |
| 17-feature model accuracy (5-fold CV) | 54.35% |

The model provides a ~9 percentage point improvement over a naive "predict home" baseline.

---

## Artifacts

| File | Purpose |
|---|---|
| `.agent_tasks/epl-xg-feature-importance/analyze_importance.py` | Full reproducible analysis script |
| `.agent_tasks/epl-xg-feature-importance/check_data.py` | Data validation script |
| `.agent_tasks/epl-xg-feature-importance/README.md` | This report |
