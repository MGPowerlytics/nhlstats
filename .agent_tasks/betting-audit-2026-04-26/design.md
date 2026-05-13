# Betting System Architecture — P0 Fixes Design Document

**Audit Ref:** `.agent_tasks/betting-audit-2026-04-26/README.md`
**Date:** 2026-04-26
**Status:** COMPLETE
**Designer:** Henchman (Planner)

---

## 1. Goal

Four P0/P1 fixes targeting system integrity and calibration:

1. **Platt Scaling Calibration** — correct Elo's systematic bias via per-sport logistic calibration.
2. **Cross-Day Bet Deduplication** — prevent placing new bets on matchups already bet on in the last 3 days.
3. **Edge Window Tightening** — restricted to 5–15%.
4. **Database Elo Storage** — migrate ratings from CSV to PostgreSQL with SCD Type 2 tracking.

---

## 2. Analysis: Current Data Flow

### 2.1 Elo → Calibration → Edge → Opportunity Pipeline

```
GameContext.calculate_probabilities()
    └─► elo_system.predict(home, away)        [raw Elo prob, e.g. 0.72]
    └─► home_win_prob ← raw Elo prob          [directly used as "elo_prob"]
    └─► away_win_prob ← 1 - home_win_prob

GameContext._evaluate_outcome()
    └─► edge = elo_prob - market_prob          [no calibration layer]
    └─► if edge < min_edge or edge > max_edge → rejected
    └─► BettingOutcome(elo_prob=raw_elo_prob, ...)
         └─► to_opportunity() → dict with elo_prob field

OddsComparator.find_opportunities()
    └─► writes opportunities to bet_recommendations table

PortfolioOptimizer.load_opportunities_from_database()
    └─► reads bet_recommendations → BetOpportunity(elo_prob=raw, edge=raw - market)

PortfolioOptimizer.filter_opportunities()
    └─► filters by edge >= min_edge, kelly_fraction > 0

PortfolioOptimizer._allocate_kelly_sizing()
    └─► uses opp.kelly_fraction (which depends on opp.elo_prob)

PortfolioBettingManager._place_optimized_bets()
    └─► KalshiBetting.place_bet() → placed_bets table
```

### 2.2 Key Files & Their Roles

| File | Role | Key Functions/Types |
|---|---|---|
| `plugins/odds_comparator.py` | Generates bet opportunities | `GameContext.calculate_probabilities()`, `_evaluate_outcome()`, `BettingOutcome`, `OddsComparator.find_opportunities()` |
| `plugins/constants.py` | Thresholds & constants | `DEFAULT_MIN_EDGE=0.03`, `MAX_EDGE_THRESHOLD=0.40`, `HIGH_CONFIDENCE_MIN_EDGE=0.15` |
| `plugins/portfolio_optimizer.py` | Filters & sizes bets | `PortfolioOptimizer.filter_opportunities()`, `_allocate_kelly_sizing()` |
| `plugins/portfolio_betting.py` | Places optimized bets | `PortfolioBettingManager._process_single_allocation()`, `_place_optimized_bets()` |
| `plugins/kalshi_betting.py` | Kalshi API client | `KalshiBetting.place_bet()`, `SimpleOrderLock` |
| `plugins/bet_tracker.py` | Tracks fills/orders | `sync_orders_to_database()`, `placed_bets` table DDL |

### 2.3 `placed_bets` Table Schema (Relevant Columns)

```
bet_id          VARCHAR PRIMARY KEY
sport           VARCHAR         -- e.g., "MLB", "EPL"
placed_date     DATE
ticker          VARCHAR
home_team       VARCHAR
away_team       VARCHAR
bet_on          VARCHAR         -- team name or "home"/"away"
side            VARCHAR         -- "yes"/"no"
status          VARCHAR         -- "open", "won", "lost", "canceled"
```

### 2.4 `elo_ratings` Table Schema (NEW)

```
rating_id       SERIAL PRIMARY KEY
sport           VARCHAR
entity_id       VARCHAR         -- Team code or Player name
entity_name     VARCHAR
rating          DECIMAL(10,2)
valid_from      DATE            -- SCD Type 2
valid_to        DATE            -- SCD Type 2 (NULL if current)
games_played    INTEGER
created_at      TIMESTAMP
```

---

## 3. Design

### 3.1 Insertion Points in Data Flow

```
                    ┌─────────────────────────────────────┐
                    │         NEW: PlattCalibrator         │
                    │  plugins/probability_calibration.py  │
                    └─────────────────────────────────────┘
                                    ▲
                                    │ calibrate(sport, elo_prob)
                                    │
GameContext.calculate_probabilities()
    └─► raw_elo = elo_system.predict(...)
    └─► NEW: calib_elo = PlattCalibrator.calibrate(sport, raw_elo)
    └─► home_win_prob ← calib_elo                         [CHANGED]
    └─► away_win_prob ← 1 - calib_elo

GameContext._evaluate_outcome()
    └─► edge = calib_elo - market_prob                    [now uses calibrated prob]
    └─► BettingOutcome(elo_prob=calib_elo, ...)           [CHANGED]
         └─► to_opportunity() → elo_prob=calib_elo


                    ┌─────────────────────────────────────┐
                    │      NEW: BetDeduplicator            │
                    │  plugins/bet_deduplicator.py         │
                    └─────────────────────────────────────┘
                                    ▲
                                    │ is_duplicate(sport, home_team, away_team,
                                    │              bet_on, placed_date, db)

PortfolioBettingManager._process_single_allocation()      [CHANGED]
    └─► NEW: if BetDeduplicator.is_duplicate(...) → skip
    └─► else → proceed to market check → place_bet()


                    ┌─────────────────────────────────────┐
                    │     MODIFIED: constants.py           │
                    └─────────────────────────────────────┘
DEFAULT_MIN_EDGE = 0.03  →  0.05     [CHANGED: 3% → 5%]
MAX_EDGE_THRESHOLD = 0.40  →  0.15   [CHANGED: 40% → 15%]
```

### 3.2 New Component: `ProbabilityCalibrator` (Platt Scaling)

**File:** `plugins/probability_calibration.py`

```python
class ProbabilityCalibrator:
    """
    Per-sport Platt scaling calibrator for Elo win probabilities.

    Fits a logistic regression (Platt scaling) on historical (elo_prob, actual_outcome)
    pairs per sport, producing calibrated probabilities that better match reality.
    """

    def __init__(self, db: DBManager = default_db):
        self.db = db
        self._models: dict[str, LogisticRegression] = {}  # sport → fitted model

    def calibrate(self, sport: str, elo_prob: float) -> float:
        """
        Apply Platt scaling to a raw Elo probability.

        Args:
            sport: Sport name (e.g., "MLB", "EPL", "TENNIS").
            elo_prob: Raw Elo-predicted win probability [0, 1].

        Returns:
            Calibrated probability [0, 1].

        Raises:
            CalibratorNotFittedError: If no model is fitted for this sport.
        """
        ...

    def fit(self, sport: str, force_retrain: bool = False) -> None:
        """
        Fit (or refit) Platt scaling for a sport using historical data from
        placed_bets and settled outcomes.

        Args:
            sport: Sport to fit.
            force_retrain: If True, discard cached model and refit.
        """
        ...

    @staticmethod
    def _fetch_training_data(db: DBManager, sport: str) -> tuple[ndarray, ndarray]:
        """
        Fetch (elo_prob, was_correct) pairs from settled bets.

        SQL: SELECT elo_prob,
                    CASE WHEN status='won' THEN 1.0 ELSE 0.0 END as outcome
             FROM placed_bets
             WHERE sport = :sport
               AND status IN ('won', 'lost')
               AND elo_prob IS NOT NULL
        """
        ...
```

**Contract boundary (Calibrated Elo → BettingOutcome):**

| Input | Type | Constraint | Source |
|---|---|---|---|
| `sport` | `str` | Must match a fitted sport | `GameContext.normalized_sport` |
| `elo_prob` | `float` | `[0.0, 1.0]` | `elo_system.predict()` |
| **Output** | `float` | `[0.0, 1.0]` | Called once per outcome |

**Invariant:** `calibrated_prob` must preserve ordering — if `elo_prob_a > elo_prob_b`, then `calibrated_prob_a >= calibrated_prob_b` (monotonicity, guaranteed by logistic regression).

**Training data source:** Query `placed_bets` for all settled bets (status `won`/`lost`) with non-null `elo_prob`. The fitted Platt model maps raw Elo prob → calibrated prob using:

```
P(win | elo) = 1 / (1 + exp(A * elo_logit + B))
```

where `elo_logit = log(elo_prob / (1 - elo_prob))` and `A, B` are fitted per sport.

### 3.3 New Component: `BetDeduplicator`

**File:** `plugins/bet_deduplicator.py`

```python
class BetDeduplicator:
    """
    Checks placed_bets for existing bets on the same (sport, home_team, away_team, bet_on)
    within a configurable rolling window.
    """

    DEDUP_WINDOW_DAYS = 3

    def __init__(self, db: DBManager = default_db):
        self.db = db

    def is_duplicate(self, sport: str, home_team: str, away_team: str,
                     bet_on: str, placed_date: str | datetime) -> bool:
        """
        Check if a bet on this matchup already exists within DEDUP_WINDOW_DAYS.

        Args:
            sport: Sport in uppercase (e.g., "MLB", "EPL").
            home_team: Canonical home team name.
            away_team: Canonical away team name.
            bet_on: The side being bet on (team name or "home"/"away").
            placed_date: The proposed placement date (YYYY-MM-DD).

        Returns:
            True if a matching bet exists within the window, False otherwise.
        """
        ...

    @staticmethod
    def _dedup_query() -> str:
        """
        SQL:
        SELECT COUNT(*) AS cnt
        FROM placed_bets
        WHERE sport = :sport
          AND home_team = :home_team
          AND away_team = :away_team
          AND bet_on = :bet_on
          AND placed_date >= :window_start
          AND placed_date <= :window_end
          AND status IN ('open', 'won', 'lost')
        """
        ...
```

**Dedup interface contract:**

| Parameter | Type | Constraint | Source |
|---|---|---|---|
| `sport` | `str` | Uppercase sport code | `opp.sport.upper()` |
| `home_team` | `str` | Canonical home team name | `opp.home_team` |
| `away_team` | `str` | Canonical away team name | `opp.away_team` |
| `bet_on` | `str` | Team name or side | `opp.bet_on` |
| `placed_date` | `str` | `YYYY-MM-DD` | Current execution date |
| **Return** | `bool` | `True` = skip, `False` = proceed | |

**Edge cases:**
- `placed_bets` table may have null `home_team`/`away_team` for older rows (pre-backfill) — the query treats unmatched NULLs as non-duplicates.
- The same team pair may appear under different sport codes (e.g., same teams in different leagues) — `sport` scope prevents false positives.
- `bet_on` equality is case-insensitive; normalize to lowercase for comparison.

### 3.4 Modified: `constants.py` — Edge Window Tightening

| Constant | Old Value | New Value | Rationale |
|---|---|---|---|
| `DEFAULT_MIN_EDGE` | `0.03` (3%) | `0.05` (5%) | 5–10% edge bucket went 0-6; only 10–20% profitable |
| `MAX_EDGE_THRESHOLD` | `0.40` (40%) | `0.15` (15%) | Edges above 20% went 0-5; 15% cap catches data errors |
| `HIGH_CONFIDENCE_MIN_EDGE` | `0.15` (15%) | No change | Still reasonable — edges 15%+ are rare after the cap |

Note: The MLB/TENNIS hard ceiling in `odds_comparator.py` (`_evaluate_outcome` line with `MAX_EDGE_THRESHOLD`) will now use the new value 0.15 automatically since it reads from the constant.

### 3.5 Integration Points

#### Platt Calibration Insertion (in `odds_comparator.py`):

**In `GameContext.calculate_probabilities()`**, after computing raw Elo probabilities, call `PlattCalibrator.calibrate()`:

```python
def calculate_probabilities(self) -> bool:
    try:
        # ... existing Elo computation ...
        raw_home_win_prob = self.elo_system.predict(...)

        # NEW: Apply Platt calibration
        calibrator = ProbabilityCalibrator()
        self.home_win_prob = calibrator.calibrate(self.normalized_sport, raw_home_win_prob)
        # ... draw and away probabilities ...
        return True
    except CalibratorNotFittedError:
        # Fallback: use raw probability if no model fitted yet
        self.home_win_prob = raw_home_win_prob
        return True
```

**Calibrator loading strategy:** The `PlattCalibrator` is initialized once per process. Models are lazy-loaded (fitted on first call per sport). A `fit_all()` call runs as a DAG setup task weekly/monthly to refit from accumulated historical data.

#### Bet Dedup Insertion (in `portfolio_betting.py`):

**In `PortfolioBettingManager._process_single_allocation()`**, before market checks:

```python
def _process_single_allocation(self, index, allocation, date_str, results):
    opp = allocation.opportunity

    # NEW: Check for duplicate
    dedup = BetDeduplicator()
    if dedup.is_duplicate(
        sport=opp.sport.upper(),
        home_team=opp.home_team,
        away_team=opp.away_team,
        bet_on=opp.bet_on,
        placed_date=date_str,
    ):
        print(f"   ⚠️  Skipping duplicate: {opp.ticker}")
        results["skipped_bets"].append({
            "ticker": opp.ticker,
            "reason": "Duplicate matchup (within 3-day window)",
        })
        return

    # ... existing market checks ...
```

---

## 4. Test Strategy (TDD + Contract Tests)

### 4.1 TDD Test Plan

#### Phase 1: Platt Calibration Unit Tests

**File:** `tests/test_probability_calibration.py`

| # | Test Name | Description | Acceptance |
|---|---|---|---|
| 1 | `test_calibrate_returns_probability_in_range` | `calibrate("MLB", 0.72)` returns `[0.0, 1.0]` | Pass |
| 2 | `test_calibrate_preserves_monotonicity` | Higher input prob → >= output prob | Pass |
| 3 | `test_calibrate_reduces_bias_on_real_data` | On synthetic data where model overestimates by 30pp, calibrated prob is within 5pp of true rate | Pass |
| 4 | `test_calibrate_raises_for_unfitted_sport` | `calibrate("CBA", 0.5)` raises `CalibratorNotFittedError` | Pass |
| 5 | `test_fit_trains_logistic_model` | After `fit("MLB")`, `calibrate()` returns sensible values | Pass |
| 6 | `test_fit_force_retrain_overwrites_cached` | `fit("MLB", force_retrain=True)` replaces old model | Pass |
| 7 | `test_calibrate_identity_when_perfectly_calibrated` | Raw prob = actual rate → output ≈ input | Pass |
| 8 | `test_calibrate_saturates_at_edges` | Raw prob 0.999 → calibrated prob < 1.0 (avoids division by zero downstream) | Pass |
| 9 | `test_calibrate_different_sports_have_different_models` | Same raw prob → different calibrated probs for MLB vs EPL | Pass |

#### Phase 2: Bet Deduplication Unit Tests

**File:** `tests/test_bet_deduplicator.py`

| # | Test Name | Description | Acceptance |
|---|---|---|---|
| 1 | `test_is_duplicate_returns_true_for_exact_match` | Same (sport, home, away, bet_on) within 3 days → `True` | Pass |
| 2 | `test_is_duplicate_returns_false_for_different_sport` | Same teams, different sport → `False` | Pass |
| 3 | `test_is_duplicate_outside_window` | Same teams/matchup but placed_date > 3 days from existing → `False` | Pass |
| 4 | `test_is_duplicate_different_bet_on` | Same matchup but betting on away team when existing bet on home → `False` | Pass |
| 5 | `test_is_duplicate_empty_database` | No bets in `placed_bets` → `False` | Pass |
| 6 | `test_is_duplicate_ignores_canceled_bets` | Existing bet has status `canceled` → `False` (can re-bet) | Pass |
| 7 | `test_is_duplicate_null_team_names` | Pre-backfill rows with null home/away → treated as no match | Pass |
| 8 | `test_dedup_window_is_strictly_3_days` | Boundary test: day 3 = duplicate, day 4 = not duplicate | Pass |

#### Phase 3: Edge Window Tightening Tests

**File:** `tests/test_edge_thresholds.py` (new) or integrated into `tests/test_odds_comparator.py`

| # | Test Name | Description | Acceptance |
|---|---|---|---|
| 1 | `test_min_edge_5pct_rejects_4pct_edge` | Edge=4% → `is_value_bet` returns `False` | Pass |
| 2 | `test_min_edge_5pct_accepts_5pct_edge` | Edge=5% → `is_value_bet` returns `True` | Pass |
| 3 | `test_max_edge_15pct_rejects_16pct_edge` | Edge=16% → `is_value_bet` returns `False` | Pass |
| 4 | `test_max_edge_15pct_accepts_15pct_edge` | Edge=15% → `is_value_bet` returns `True` | Pass |
| 5 | `test_existing_tests_still_pass` | All existing tests in `test_odds_comparator.py` pass with new constants | Pass |
| 6 | `test_mlb_hard_ceiling_15pct` | MLB/TENNIS hard ceiling reflects new `MAX_EDGE_THRESHOLD` | Pass |

#### Phase 4: End-to-End Integration Tests

**File:** `tests/test_calibrated_opportunity_pipeline.py`

| # | Test Name | Description | Acceptance |
|---|---|---|---|
| 1 | `test_calibrated_elo_used_in_opportunity` | Stub calibrator returns 0.55 for raw 0.72; opportunity.elo_prob == 0.55 | Pass |
| 2 | `test_dedup_prevents_duplicate_placement` | Mock `BetDeduplicator.is_duplicate` returns True → bet skipped | Pass |
| 3 | `test_calibrator_unfitted_fallback` | No model for sport → raw Elo used, no crash | Pass |

### 4.2 Contract Tests

Following the existing pattern in `tests/contracts/`:

#### Contract 1: Calibrated Elo → BettingOutcome Boundary

**File:** `tests/contracts/test_calibrated_elo_provider.py`

The consumer (`BettingOutcome`) expects that `elo_prob` obeys:
- Type: `float` in `[0.0, 1.0]`
- Monotonicity preserved relative to raw Elo
- Per-sport distinct behavior (same raw prob → different calibrated for different sports)

**Provider tests** (exercise real `PlattCalibrator` + stubbed training data):

```python
def test_calibrated_elo_contract_honors_monotonicity():
    calibrator = ProbabilityCalibrator(db=stub_db)
    calibrator.fit("MLB")
    calibrated = [calibrator.calibrate("MLB", p) for p in [0.3, 0.5, 0.7]]
    assert calibrated[0] <= calibrated[1] <= calibrated[2]

def test_calibrated_elo_contract_range():
    calibrator = ProbabilityCalibrator(db=stub_db)
    calibrator.fit("MLB")
    for raw in [0.01, 0.25, 0.50, 0.75, 0.99]:
        cal = calibrator.calibrate("MLB", raw)
        assert 0.0 <= cal <= 1.0

def test_calibrated_elo_contract_raw_fallback():
    """When calibrator is not fitted, the system MUST use raw Elo (no crash)."""
    # Direct test on GameContext.calculate_probabilities fallback path
```

**Consumer tests** (freeze the contract schema):

```python
def test_calibrated_elo_contract_rejects_out_of_range():
    schema = {"type": "number", "minimum": 0.0, "maximum": 1.0}
    with pytest.raises(ValidationError):
        validate(1.5, schema)
```

#### Contract 2: BetDeduplicator Interface

**File:** `tests/contracts/test_bet_deduplicator_provider.py`

The interface contract:
- `is_duplicate(sport, home_team, away_team, bet_on, placed_date) → bool`
- `sport`: UPPERCASE, non-empty string
- `home_team`/`away_team`: non-empty string (canonical names)
- `bet_on`: non-empty string
- `placed_date`: `YYYY-MM-DD` format
- Window: strictly 3 calendar days (>= `placed_date - 3` AND <= `placed_date`)

```python
def test_dedup_contract_rejects_missing_sport():
    dedup = BetDeduplicator(db=stub_db)
    with pytest.raises(ValueError):
        dedup.is_duplicate(sport="", home_team="A", away_team="B", bet_on="A", placed_date="2026-04-26")

def test_dedup_contract_returns_bool():
    result = dedup.is_duplicate(sport="MLB", home_team="NYY", away_team="BOS", bet_on="NYY", placed_date="2026-04-26")
    assert isinstance(result, bool)
```

#### Contract 3: Edge Window Contract

**Schema file:** `tests/contracts/schemas/bet_opportunity_edge_v1.json`

This schema is embedded in each sport's opportunity contract (e.g., `mlb_bet_opportunity_v1.json` already has `edge.minimum=0.03` and `edge.maximum=0.40`). The values must be updated:

| Current | Target |
|---------|--------|
| `edge.minimum: 0.03` | `edge.minimum: 0.05` |
| `edge.maximum: 0.40` | `edge.maximum: 0.15` |

**Files to update:**
- `tests/contracts/schemas/mlb_bet_opportunity_v1.json`
- `tests/contracts/schemas/tennis_bet_opportunity_v1.json`
- `tests/contracts/schemas/epl_bet_opportunity_v1.json` (check if exists)

---

## 5. Implementation Order (Dependency-Aware)

### Phase 0: Edge Window Tightening (Zero Dependency, 15 min)

**Dependencies:** None

**Steps:**
1. [ ] Update `constants.py`: `DEFAULT_MIN_EDGE = 0.03 → 0.05`, `MAX_EDGE_THRESHOLD = 0.40 → 0.15`
2. [ ] Update contract schemas: minimum edge 0.05, maximum edge 0.15 in `mlb_bet_opportunity_v1.json`, `tennis_bet_opportunity_v1.json`
3. [ ] Write tests in `tests/test_edge_thresholds.py`
4. [ ] Run existing tests to confirm no regressions: `pytest tests/test_odds_comparator.py`

### Phase 1: Platt Calibration (Dependency: Phase 0)

**Dependencies:** `ProbabilityCalibrator` is standalone (new file). Edge constants are already changed so new edge values flow through.

**Steps:**
1. [ ] WRITE FAILING TESTS: `tests/test_probability_calibration.py` (all 9 tests from §4.1 Phase 1)
2. [ ] IMPLEMENT: `plugins/probability_calibration.py` — `ProbabilityCalibrator` class
3. [ ] WRITE CONTRACT TESTS: `tests/contracts/test_calibrated_elo_provider.py` (3 tests from §4.2)
4. [ ] INTEGRATE: Modify `GameContext.calculate_probabilities()` in `odds_comparator.py` to call calibrator
5. [ ] RUN ALL TESTS: `pytest tests/test_probability_calibration.py tests/contracts/test_calibrated_elo_provider.py tests/test_odds_comparator.py`

### Phase 2: Bet Deduplication (Dependency: Phase 0)

**Dependencies:** Independent of Phase 1 (can be done in parallel).

**Steps:**
1. [ ] WRITE FAILING TESTS: `tests/test_bet_deduplicator.py` (all 8 tests from §4.1 Phase 2)
2. [ ] IMPLEMENT: `plugins/bet_deduplicator.py` — `BetDeduplicator` class
3. [ ] WRITE CONTRACT TESTS: `tests/contracts/test_bet_deduplicator_provider.py` (2 tests from §4.2)
4. [ ] INTEGRATE: Modify `PortfolioBettingManager._process_single_allocation()` in `portfolio_betting.py`
5. [ ] RUN ALL TESTS: `pytest tests/test_bet_deduplicator.py tests/contracts/test_bet_deduplicator_provider.py tests/test_portfolio_betting.py`

### Phase 3: Integration Validation (Dependency: Phase 1 + Phase 2)

**Steps:**
1. [ ] WRITE END-TO-END TESTS: `tests/test_calibrated_opportunity_pipeline.py` (3 tests from §4.1 Phase 4)
2. [ ] FULL TEST SUITE: `pytest tests/test_odds_comparator.py tests/test_probability_calibration.py tests/test_bet_deduplicator.py tests/test_calibrated_opportunity_pipeline.py tests/contracts/`
3. [ ] LINT: `ruff check plugins/ tests/`

---

## 6. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Calibrator not fitted yet (first run) | High — no calibrated bets | Medium | Fallback to raw Elo with warning; log message "No calibration model for {sport}" |
| Calibrator overfits on small sample | Medium — bad calibration | Low | Minimum training threshold: require ≥30 settled bets per sport before fitting. Log warning if <30. |
| `placed_bets` has null team names (pre-backfill rows) | Low — dedup misses some | Medium | Query uses `IS NOT DISTINCT FROM` or ignores NULLs. Some old bets won't dedup but new ones will. |
| Edge window 5-15% misses profitable >15% opportunities | Medium — missed profits | Low | Audit data showed 15%+ bucket went 0-5; empirical evidence supports tightening |
| Kalshi market has edge < 5% after calibration that was > 5% before | Medium — fewer bets | High (desired) | This is the entire point — phantom edges generated by uncalibrated Elo should not be bet on |
| Concurrent DAG runs cause race conditions in dedup | Low — double bet | Low | The dedup check + bet placement is atomic enough (check first, place second); worst case: duplicate caught by `SimpleOrderLock` |

---

## 7. Verification Checklist

- [ ] `pytest tests/test_probability_calibration.py` — all green
- [ ] `pytest tests/test_bet_deduplicator.py` — all green
- [ ] `pytest tests/test_edge_thresholds.py` — all green
- [ ] `pytest tests/test_odds_comparator.py` — all green (no regressions)
- [ ] `pytest tests/test_portfolio_betting.py` — all green (no regressions)
- [ ] `pytest tests/contracts/` — all green (contracts updated)
- [ ] `ruff check plugins/probability_calibration.py plugins/bet_deduplicator.py` — clean
- [ ] `DEFAULT_MIN_EDGE` = 0.05, `MAX_EDGE_THRESHOLD` = 0.15 in `constants.py`
- [ ] Contract schemas reflect edge minimum=0.05, maximum=0.15

---

## Appendix: Key Knowledge Graph Updates

- `kg_update("add_entity", "ProbabilityCalibrator", "class", ...)`
- `kg_update("add_entity", "BetDeduplicator", "class", ...)`
- `kg_update("add_relation", "ProbabilityCalibrator", "depends_on", "placed_bets")`
- `kg_update("add_relation", "BetDeduplicator", "depends_on", "placed_bets")`
- `kg_update("add_observation", "edge_window", "MIN_EDGE changed from 3% to 5%; MAX_EDGE from 40% to 15%")`
