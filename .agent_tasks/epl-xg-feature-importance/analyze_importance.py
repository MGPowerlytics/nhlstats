#!/usr/bin/env python3
"""Feature importance analysis for EPL ensemble model.

Computes:
  1. Coefficient magnitudes per class for all 17 features
  2. Relative feature importance ranking (avg abs coeff across classes)
  3. Group importance (sum of abs coeffs by group: Elo, Form, Goals, xG, Bookmaker)
  4. Permutation importance on the full test set
  5. Marginal gain: with vs without xG features (5-fold CV accuracy)

Usage:
  python3 .agent_tasks/epl-xg-feature-importance/analyze_importance.py
"""

from __future__ import annotations

import os
import sys
import warnings
from copy import deepcopy

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

sys.path.insert(0, "/mnt/data2/nhlstats")
os.environ["POSTGRES_HOST"] = "172.20.0.2"

from plugins.elo.epl_ensemble import EPLEnsembleModel  # noqa: E402

# ── Feature grouping ──────────────────────────────────────────────────
FEATURE_GROUPS: dict[str, list[str]] = {
    "Elo": ["elo_prob_home", "elo_prob_draw", "elo_prob_away", "elo_diff"],
    "Form": ["home_form", "away_form"],
    "Goals": ["home_avg_gf", "away_avg_gf", "home_avg_ga", "away_avg_ga"],
    "xG (NEW)": ["home_avg_xg", "away_avg_xg", "home_avg_xga", "away_avg_xga"],
    "Bookmaker": ["bookmaker_prob_home", "bookmaker_prob_draw", "bookmaker_prob_away"],
}

CLASS_LABELS = {0: "Away Win", 1: "Draw", 2: "Home Win"}

# ── 0. Load model & data ─────────────────────────────────────────────
print("=" * 72)
print("  EPL Ensemble Model — Feature Importance Analysis")
print("=" * 72)

print("\n[1/5] Loading model and building training frame...")
model = EPLEnsembleModel(auto_train=False)
loaded = model.load()
if not loaded:
    print("ERROR: Could not load model")
    sys.exit(1)

frame = model.build_training_frame(data_dir="data/epl")
features_17 = list(model.features)
X = frame[features_17].values
y = frame["target"].values
n_samples, n_features = X.shape
print(f"  Training frame: {n_samples} rows, {n_features} features")
print(f"  Target distribution: away={sum(y==0)}, draw={sum(y==1)}, home={sum(y==2)}")

# ── 1. Coefficient Magnitudes per Class ──────────────────────────────
print("\n" + "=" * 72)
print("  1. Coefficient Magnitudes per Class")
print("=" * 72)

coef_matrix = model.model.coef_  # shape (3, 17)
print(f"\n{'Feature':<25} {'Away Win':>10} {'Draw':>10} {'Home Win':>10} {'Avg|Coef|':>10}")
print("-" * 65)

coef_table: list[tuple[str, float, float, float, float]] = []
for i, feat in enumerate(features_17):
    c0 = coef_matrix[0, i]
    c1 = coef_matrix[1, i]
    c2 = coef_matrix[2, i]
    avg_abs = (abs(c0) + abs(c1) + abs(c2)) / 3.0
    coef_table.append((feat, c0, c1, c2, avg_abs))
    print(f"{feat:<25} {c0:>+10.4f} {c1:>+10.4f} {c2:>+10.4f} {avg_abs:>10.4f}")

# ── 2. Relative Feature Importance Ranking ───────────────────────────
print("\n" + "=" * 72)
print("  2. Feature Importance Ranking (avg |coef| across classes)")
print("=" * 72)

ranked = sorted(coef_table, key=lambda r: r[4], reverse=True)
print(f"\n{'Rank':>4}  {'Feature':<25} {'Avg|Coef|':>10} {'Group':<15}")
print("-" * 56)
for rank, (feat, c0, c1, c2, avg_abs) in enumerate(ranked, 1):
    group = next(g for g, fl in FEATURE_GROUPS.items() if feat in fl)
    print(f"{rank:>4}  {feat:<25} {avg_abs:>10.4f}  {group:<15}")

# ── 3. Group Importance ──────────────────────────────────────────────
print("\n" + "=" * 72)
print("  3. Group Importance (sum of |coef| by feature group)")
print("=" * 72)

print(f"\n{'Group':<20} {'Sum |Coef|':>12} {'Features':>6} {'Avg |Coef|/Feat':>16}")
print("-" * 54)
for group_name, group_feats in FEATURE_GROUPS.items():
    indices = [features_17.index(f) for f in group_feats if f in features_17]
    group_sum = sum(
        abs(coef_matrix[cls, idx]) for cls in range(3) for idx in indices
    )
    n_feats = len(indices)
    avg_per_feat = group_sum / (3 * n_feats) if n_feats else 0.0
    print(f"{group_name:<20} {group_sum:>12.4f} {n_feats:>6} {avg_per_feat:>16.4f}")

# ── 4. Permutation Importance ────────────────────────────────────────
print("\n" + "=" * 72)
print("  4. Permutation Importance (accuracy drop, n_repeats=10)")
print("=" * 72)

# Scale data for permutation importance (same as during training)
scaler = deepcopy(model.scaler)
X_scaled = scaler.transform(X)

print("\n  Computing permutation importance on full dataset...")
perm_result = permutation_importance(
    model.model, X_scaled, y, n_repeats=10, random_state=42, scoring="accuracy"
)

perm_table: list[tuple[str, float, float]] = []
for i, feat in enumerate(features_17):
    importance_mean = perm_result.importances_mean[i]
    importance_std = perm_result.importances_std[i]
    perm_table.append((feat, importance_mean, importance_std))

perm_ranked = sorted(perm_table, key=lambda r: r[1], reverse=True)

print(f"\n{'Rank':>4}  {'Feature':<25} {'Importance':>12} {'Std Dev':>10} {'Group':<15}")
print("-" * 68)
for rank, (feat, imp_mean, imp_std) in enumerate(perm_ranked, 1):
    group = next(g for g, fl in FEATURE_GROUPS.items() if feat in fl)
    print(f"{rank:>4}  {feat:<25} {imp_mean:>+12.6f} {imp_std:>+10.6f}  {group:<15}")

# Permutation importance by group
print(f"\n{'Group':<20} {'Sum Import':>12} {'Avg Import/Feat':>16}")
print("-" * 48)
for group_name, group_feats in FEATURE_GROUPS.items():
    indices = [features_17.index(f) for f in group_feats if f in features_17]
    group_imp = sum(perm_result.importances_mean[idx] for idx in indices)
    n = len(indices)
    print(f"{group_name:<20} {group_imp:>12.6f} {group_imp / n:>16.6f}")

# ── 5. Marginal Gain: With vs Without xG ────────────────────────────
print("\n" + "=" * 72)
print("  5. Marginal Gain Analysis: With vs Without xG Features")
print("=" * 72)

X_with_xg = X
y_labels = y

# Remove xG features (indices 10, 11, 12, 13 → home_avg_xg, away_avg_xg, home_avg_xga, away_avg_xga)
XG_INDICES = [10, 11, 12, 13]
X_without_xg = np.delete(X_with_xg, XG_INDICES, axis=1)
features_13 = [f for i, f in enumerate(features_17) if i not in XG_INDICES]

print(f"\n  Features WITH  xG: {n_features} ({features_17[10]}, {features_17[11]}, {features_17[12]}, {features_17[13]})")
print(f"  Features WITHOUT xG: {len(features_13)} ({', '.join(features_13)})")

# --- Model WITH xG (refit from scratch for fair comparison) ---
print("\n  Fitting model WITH xG features...")
scaler_with = StandardScaler()
X_scaled_with = scaler_with.fit_transform(X_with_xg)
model_with = LogisticRegression(max_iter=2000, solver="lbfgs")
model_with.fit(X_scaled_with, y_labels)
scores_with = cross_val_score(
    LogisticRegression(max_iter=2000, solver="lbfgs"),
    X_scaled_with, y_labels,
    cv=5, scoring="accuracy",
)

# --- Model WITHOUT xG ---
print("  Fitting model WITHOUT xG features...")
scaler_without = StandardScaler()
X_scaled_without = scaler_without.fit_transform(X_without_xg)
model_without = LogisticRegression(max_iter=2000, solver="lbfgs")
model_without.fit(X_scaled_without, y_labels)
scores_without = cross_val_score(
    LogisticRegression(max_iter=2000, solver="lbfgs"),
    X_scaled_without, y_labels,
    cv=5, scoring="accuracy",
)

print(f"\n  {'Model':<25} {'Mean Accuracy':>15} {'Std Dev':>10}")
print("-" * 50)
print(f"  {'With xG (17 features)':<25} {scores_with.mean():>15.4f} {scores_with.std():>10.4f}")
print(f"  {'Without xG (13 features)':<25} {scores_without.mean():>15.4f} {scores_without.std():>10.4f}")

delta = scores_with.mean() - scores_without.mean()
print(f"\n  Accuracy delta (with - without): {delta:+.4f} ({delta*100:+.2f}%)")

# Per-class analysis: compare CV score details
print("\n  Individual fold scores:")
for fold, (s_w, s_wo) in enumerate(zip(scores_with, scores_without), 1):
    print(f"    Fold {fold}: with={s_w:.4f}  without={s_wo:.4f}  delta={s_w-s_wo:+.4f}")

# ── Final summary ────────────────────────────────────────────────────
print("\n" + "=" * 72)
print("  SUMMARY")
print("=" * 72)

top5_coef = ranked[:5]
top5_perm = perm_ranked[:5]
print("\n  Top 5 Features by |Coefficient|:")
for rank, (feat, *_, avg_abs) in enumerate(top5_coef, 1):
    group = next(g for g, fl in FEATURE_GROUPS.items() if feat in fl)
    print(f"    {rank}. {feat:<30} avg|coef|={avg_abs:.4f}  [{group}]")

print("\n  Top 5 Features by Permutation Importance:")
for rank, (feat, imp_mean, imp_std) in enumerate(top5_perm, 1):
    group = next(g for g, fl in FEATURE_GROUPS.items() if feat in fl)
    print(f"    {rank}. {feat:<30} imp={imp_mean:.6f}±{imp_std:.6f}  [{group}]")

xg_indices_group = [i for i, f in enumerate(features_17) if f in FEATURE_GROUPS["xG (NEW)"]]
xg_sum_coef = sum(abs(coef_matrix[cls, idx]) for cls in range(3) for idx in xg_indices_group)
print(f"\n  xG group sum |coef|: {xg_sum_coef:.4f}")
print(f"  xG permutation importance sum: {sum(perm_result.importances_mean[idx] for idx in XG_INDICES):.6f}")
print(f"\n  Accuracy with  xG (17 features): {scores_with.mean():.4f} ± {scores_with.std():.4f}")
print(f"  Accuracy without xG (13 features): {scores_without.mean():.4f} ± {scores_without.std():.4f}")
print(f"  Marginal gain from xG features: {delta:+.4f} ({delta*100:+.2f}%)")
print("\n✅ Analysis complete.")
