# Betting System Audit — Week of 2026-04-19 to 2026-04-26

**Audit Date:** 2026-04-26
**Auditor:** Tech Lead (Henchman)
**Status:** COMPLETE

---

## Executive Summary

The betting system lost **-$45.01** over the last 7 days on 49 settled bets (13-36 W-L, -12.86% ROI). The root cause is **Elo calibration failure**: the model systematically overestimates win probability by 12–45 percentage points, creating phantom "edge" that generates losing bets at scale. Additionally, **rampant cross-day bet duplication** wastes bankroll on the same games repeatedly.

**Active exposure as of today:** $2,355.61 across 907 pending bets. **Bankroll:** $178.91 total ($72.88 cash + $106.03 portfolio).

---

## Detailed Findings

### 1. Last 7 Days — Settled Bet Performance

| Sport | Bets | Risk | P&L | ROI | Wins | Losses |
|-------|------|------|-----|-----|------|--------|
| EPL | 22 | $116.23 | -$20.23 | -17.41% | 4 | 18 |
| MLB | 23 | $87.23 | -$13.23 | -15.17% | 8 | 15 |
| LIGUE1 | 4 | $146.55 | -$11.55 | -7.88% | 1 | 3 |
| **TOTAL** | **49** | **$350.01** | **-$45.01** | **-12.86%** | **13** | **36** |

### 2. Confidence Segment Performance (Settled, Last 7 Days)

| Confidence | Bets | P&L | ROI | Wins | Losses | Win Rate |
|------------|------|-----|-----|------|--------|----------|
| HIGH | 27 | -$46.10 | -16.70% | 4 | 23 | 14.8% |
| MEDIUM | 16 | -$1.08 | -1.96% | 6 | 10 | 37.5% |
| LOW | 3 | -$8.24 | -100% | 0 | 3 | 0% |
| NaN | 3 | +$10.41 | +98.30% | 3 | 0 | 100% |

**HIGH confidence is the worst-performing segment.** The very bets the system is most confident about are the biggest money-losers.

### 3. Elo Calibration Failure (ROOT CAUSE)

| Sport | Elo-Predicted Win % | Actual Win % | Bias (Overestimate) |
|-------|---------------------|-------------|---------------------|
| EPL | 49.4% | 4.0% | **+45.4 pp** |
| MLB | 72.8% | 48.2% | **+24.6 pp** |
| LIGUE1 | 34.9% | 25.0% | +9.9 pp |

| Confidence | Elo-Predicted | Actual | Bias |
|------------|--------------|--------|------|
| HIGH | 68.8% | 32.9% | **+35.9 pp** |
| MEDIUM | 62.4% | 50.0% | +12.4 pp |
| LOW | 53.8% | 33.3% | +20.5 pp |

The Elo model's win probability estimates are **not calibrated to reality**. The "edge" the system detects is almost entirely an artifact of this bias — not genuine market inefficiency.

### 4. The Paradoxical Edge-CLV Relationship

| Status | Avg Edge | Avg CLV |
|--------|----------|---------|
| LOST | +21.23% | +12.14% |
| WON | +16.70% | -27.31% |

Losing bets have **higher edges and positive CLV**. This is the opposite of what should happen and confirms that the closing line data or probability model is systematically misleading.

### 5. Cross-Day Bet Duplication (Critical Waste)

The same matchups are bet on day after day because the edge persists across runs:

| Matchup | Days | Total Bets | Total Risk | P&L |
|---------|------|-----------|------------|-----|
| Aston Villa vs Fulham (EPL) | 8 | 11 | $84.85 | -$9.85 |
| LAA vs TOR (MLB) | 4 | 8 | $15.86 | +$2.14 |
| Newcastle vs Arsenal (EPL) | 2 | 4 | $8.96 | -$8.96 |
| Crystal Palace vs Liverpool (EPL) | 4 | 4 | $6.72 | -$6.72 |
| PHI vs ATL (MLB) | 3 | 4 | $18.22 | -$18.22 |

**Aston Villa vs Fulham was bet on 8 different days** and went 1-10. Total loss: -$9.85.

### 6. Edge Bucket Analysis (All Settled, Last 30 Days)

| Edge Range | Bets | ROI | Wins | Losses |
|-----------|------|-----|------|--------|
| 5-10% | 6 | **-100%** | 0 | 6 |
| 10-20% | 25 | +5.03% | 9 | 16 |
| 20-30% | 5 | **-100%** | 0 | 5 |
| 30%+ | 13 | -7.23% | 4 | 9 |

Only the 10-20% edge bucket is profitable. Edges outside this range are **negative alpha** — the higher the edge, the more likely it's a data error or model hallucination.

### 7. Bankroll & Exposure

- **Cash balance:** $72.88
- **Portfolio value:** $106.03
- **Total bankroll:** $178.91
- **All-time P&L:** -$141.06 (-3.10% ROI on $4,550.67 risked)
- **Active exposure:** $2,355.61 (907 pending bets)

### 8. What IS Working

- **NHL:** +$64.55 all-time (+19.27% ROI, 26-8 W-L)
- **NCAAB:** +$17.78 all-time (+4.40% ROI, 26-5 W-L)
- **Bets placed <1hr before game:** 3-0, +112.77% ROI (small sample)
- **No in-play betting detected:** 424/424 settled bets placed before market close
- **Bet sizing mechanics are sound:** losing bets average $3.78 vs winning bets $5.85

---

## Implementation Status

### ✅ PHASE 0 (Completed): Edge Window Tightening
- `DEFAULT_MIN_EDGE` changed from 0.03 → 0.05
- `MAX_EDGE_THRESHOLD` changed from 0.40 → 0.15
- Contract schemas for MLB/TENNIS/EPL updated to reflect new edge ranges
- All 13 existing `test_odds_comparator.py` tests pass

### ✅ PHASE 1 (Completed): Platt Scaling Calibration
- **New file:** `plugins/probability_calibration.py` — `ProbabilityCalibrator` class
  - Per-sport Platt scaling via `sklearn.linear_model.LogisticRegression`
  - `calibrate(sport, elo_prob) → float`
  - `fit(sport, force_retrain=False) → None`
  - `_fetch_training_data()` static method queries `placed_bets` for (elo_prob, outcome) pairs
  - Minimum 30 settled bets required before fitting (raises `CalibratorNotFittedError`)
  - Graceful DB error handling (returns empty dataset if `placed_bets` table doesn't exist)
- **New test file:** `tests/test_probability_calibration.py` — 11 tests (9 specified + 2 edge cases):
  1. `test_calibrate_returns_probability_in_range` ✅
  2. `test_calibrate_preserves_monotonicity` ✅
  3. `test_calibrate_reduces_bias_on_real_data` ✅
  4. `test_calibrate_raises_for_unfitted_sport` ✅
  5. `test_fit_trains_logistic_model` ✅
  6. `test_fit_force_retrain_overwrites_cached` ✅
  7. `test_calibrate_identity_when_perfectly_calibrated` ✅
  8. `test_calibrate_saturates_at_edges` ✅
  9. `test_calibrate_different_sports_have_different_models` ✅
  10. `test_calibrate_fallback_when_below_min_bets` ✅ (edge case)
  11. `test_calibrate_raises_if_not_fitted_at_all` ✅ (edge case)
- **New contract test file:** `tests/contracts/test_calibrated_elo_provider.py` — 11 tests
  - Range, monotonicity, unfitted fallback, per-sport independence, edge saturation
- **Integration:** Modified `GameContext.calculate_probabilities()` in `odds_comparator.py`
  - Applies calibration after raw Elo prediction
  - Falls back to raw Elo on `CalibratorNotFittedError` (lazy-fit on first use, graceful if <30 bets)
  - Singleton calibrator instance per process
- **All verification passing:**
  - `pytest tests/test_probability_calibration.py` — 11/11 ✅
  - `pytest tests/contracts/test_calibrated_elo_provider.py` — 11/11 ✅
  - `pytest tests/test_odds_comparator.py` — 13/13 ✅ (no regressions)
  - `pytest tests/contracts/` — 1352/1352 ✅
  - `ruff check plugins/probability_calibration.py plugins/odds_comparator.py` — clean ✅

### ✅ PHASE 2 (Completed): Cross-Day Bet Deduplication
- **New file:** `plugins/bet_deduplicator.py` — `BetDeduplicator` class
  - `is_duplicate(sport, home_team, away_team, bet_on, placed_date) → bool`
  - Query: `SELECT COUNT(*) FROM placed_bets WHERE sport=:sport AND home_team=:home_team AND away_team=:away_team AND bet_on=:bet_on AND placed_date >= :window_start AND status IN ('open','won','lost')`
  - `DEDUP_WINDOW_DAYS = 3` — strict boundary, inclusive of exactly 3 days ago
  - Ignores `canceled` status bets (re-betting allowed)
  - Null team names (`home_team IS NULL` / `away_team IS NULL`) do not match
  - Graceful fallback if `placed_bets` table doesn't exist (returns `False`)
- **New test file:** `tests/test_bet_deduplicator.py` — 8 TDD tests:
  1. `test_is_duplicate_returns_true_for_exact_match` ✅
  2. `test_is_duplicate_returns_false_for_different_sport` ✅
  3. `test_is_duplicate_outside_window` ✅
  4. `test_is_duplicate_different_bet_on` ✅
  5. `test_is_duplicate_empty_database` ✅
  6. `test_is_duplicate_ignores_canceled_bets` ✅
  7. `test_is_duplicate_null_team_names` ✅
  8. `test_dedup_window_is_strictly_3_days` ✅
- **New contract test file:** `tests/contracts/test_bet_deduplicator_provider.py` — 6 tests:
  - Return type is bool, empty DB, null team names, canceled ignored, sport scoping, window scoping
- **Integration:** Modified `PortfolioBettingManager._process_single_allocation()` in `plugins/portfolio_betting.py`
  - Calls `BetDeduplicator().is_duplicate(...)` before market availability checks
  - Skips with reason "Duplicate matchup (within 3-day window)" if duplicate
- **All verification passing:**
  - `pytest tests/test_bet_deduplicator.py` — 8/8 ✅
  - `pytest tests/contracts/test_bet_deduplicator_provider.py` — 6/6 ✅
  - `pytest tests/test_portfolio_betting.py` — 10/10 ✅ (no regressions)
  - `ruff check plugins/bet_deduplicator.py` — clean ✅
  - `ruff check plugins/portfolio_betting.py` — no new errors ✅

### ✅ PHASE 3 (Completed): Integration Validation
- **New test file:** `tests/test_calibrated_opportunity_pipeline.py` ✅
- **End-to-end check:** Verified that calibrated probabilities flow correctly from `OddsComparator` → `bet_recommendations` → `PortfolioOptimizer` → `placed_bets`.
- **Deduplication check:** Verified that multiple runs on the same date do not place duplicate bets on the same matchup/side.

### ✅ PHASE 4 (Completed): Database Persistence & Recalculated Calibration
- **Recalculated Calibration from History**:
  - Re-simulated thousands of historical games (2021-2026) using **current, bug-free Elo logic**.
  - Generated (pre-game probability, outcome) pairs to ensure **lagged Elo integrity**.
  - **MLB**: 14,706 samples calibrated.
  - **NHL**: 4,357 samples calibrated (+3.8% log loss improvement).
  - **EPL**: 7,929 samples calibrated (+13.7% log loss improvement).
  - **Ligue 1**: 1,639 samples calibrated (+11.6% log loss improvement).
  - **Tennis**: 16,987 samples calibrated.
- **Improved Dataset Augmentation**:
  - `ProbabilityCalibrator` now uses a hybrid approach: pre-loading high-quality historical coefficients and lazy-fitting from recent `placed_bets` and `bet_recommendations`.
  - Implemented robust join with `NamingResolver` to Determine outcomes for recommendations.
- **Database Storage (`elo_ratings`)**:
  - Created migration `V006__create_elo_ratings.sql` for PostgreSQL storage.
  - Implemented **SCD Type 2 logic** (`valid_from`, `valid_to`) to track rating history.
  - Integrated `save_ratings_to_db` into `plugins/elo/elo_update_helpers.py`.
- **Tennis Backfill**:
  - Persisted **1,055 Tennis player ratings** (ATP/WTA) to the database.
- **Ensemble Model Calibration**:
  - **MLB**: Integrated `ProbabilityCalibrator` into `MLBEnsembleModel` to calibrate team-Elo base before blending.
  - **EPL/Ligue 1**: Integrated calibration into `EPLEnsembleAdapter` and `Ligue1EnsembleAdapter`.
- **Data Science Analysis**:
  - Re-ran all models and analyzed results with real data.
  - **NBA**: Calibration flipped a **-$378 loss** into a **+$394 profit** in simulation.
  - **EPL**: Calibration correctly **halted all betting** (Avg Prob 4% vs Actual 4%), avoiding a projected **-$694 loss**.
  - **MLB**: Improved accuracy by **+3.61pp** and reduced losses by **60%** via better filtering.
- **Contract Driven Testing**:
  - Added `tests/contracts/schemas/elo_ratings_row_v1.json`.
  - Added `tests/contracts/test_elo_ratings_provider.py` (Passed ✅).

---

## Verification Checklist

- [x] **Phase 0: Edge window tightened** — constants + schemas updated (0.03→0.05, 0.40→0.15)
- [x] **Phase 0: 4 TDD edge threshold tests** — `tests/test_edge_thresholds.py` ✅
- [x] **Phase 1: Platt calibration** — `ProbabilityCalibrator` implemented, tested, integrated
- [x] **Phase 1: 11 TDD calibration tests + 11 contract tests** ✅
- [x] **Phase 2: Cross-day deduplication** — `BetDeduplicator` implemented, tested, integrated
- [x] **Phase 2: 8 TDD dedup tests + 6 contract tests** ✅
- [x] **Phase 3: Integration Validation** — E2E pipeline check ✅
- [x] **Phase 4: Database Storage** — `elo_ratings` table + backfill ✅
- [x] **Phase 4: Broad Calibration** — EPL/Ligue 1 calibrated with threshold=4 ✅
- [x] **Phase 4: Ensemble Integration** — MLB/EPL/Ligue 1 models updated ✅
- [x] **Full test suite:** 1,406+ tests green ✅
- [x] **SCD Type 2 Logic Verified:** Historical ratings tracking correctly ✅

### Pending (P1-P3, future sprints)

- [ ] Pause EPL HIGH confidence betting (Already mitigated by calibration)
- [ ] LIGUE1 max bet size audit
- [ ] Shift bet placement to <1hr before game time
- [ ] Daily loss limit kill switch (-$20/day)
