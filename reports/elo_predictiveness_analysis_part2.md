# Elo Predictiveness Analysis - Part 2: Root Cause Analysis & Solutions

**Date**: February 5, 2026
**Analysis Focus**: Identify root causes of poor Elo predictiveness and propose solutions

---

## Executive Summary

**Root Cause Identified**: **Team data is completely missing** from the betting pipeline, making Elo predictions meaningless.

**Critical Findings**:
1. **No team data in `placed_bets`**: All `home_team` and `away_team` fields are `'None'`
2. **Empty `bet_recommendations` table**: No recent bet recommendations exist
3. **Elo probabilities are generic**: NHL has only 6 unique probabilities for 73 bets
4. **Broken data pipeline**: Bets bypass the recommendation system entirely

**Immediate Impact**: Elo predictions are **essentially random** because they can't be team-specific.

---

## Detailed Root Cause Analysis

### 1. **Missing Team Data in placed_bets**
```sql
-- All sports have missing team data
SELECT sport, COUNT(*) as bets_without_teams
FROM placed_bets
WHERE (home_team IS NULL OR home_team = 'None')
  AND (away_team IS NULL OR away_team = 'None')
GROUP BY sport;

-- Result: ALL 407 bets have missing team data
```

**Impact**: Elo probabilities cannot be calculated based on actual team ratings.

### 2. **Empty bet_recommendations Table**
```sql
-- No recent bet recommendations
SELECT COUNT(*) FROM bet_recommendations
WHERE created_at >= CURRENT_DATE - 7;
-- Result: 0
```

**Impact**: The recommendation pipeline is not producing outputs.

### 3. **Generic Elo Probabilities**
- **NHL**: Only 6 unique probabilities for 73 bets
- **NBA**: Only 3 unique probabilities for 32 bets
- **NCAAB**: 11 unique probabilities for 89 bets
- **TENNIS**: 94 unique probabilities for 116 bets (better but still problematic)

**Analysis**: Non-tennis sports show extreme probability quantization, suggesting placeholder/default values.

### 4. **Broken Data Pipeline**
Based on DAG_TASK_DATA_FLOW.md, the correct flow should be:
```
download_games → load_db → identify_bets → load_bets_db → portfolio_betting
      ↓              ↓           ↓             ↓              ↓
  Team data → Team data → Team data → Team data → Team data
```

**Actual flow observed**:
```
sync_bets_from_kalshi → placed_bets (NO TEAM DATA)
```

---

## Technical Investigation

### 1. **Backfill Function Analysis**
The `backfill_bet_metrics()` function in `bet_tracker.py` only copies:
- `elo_prob`, `market_prob`, `edge`
- `expected_value`, `kelly_fraction`, `confidence`

**Missing**: `home_team`, `away_team`, `bet_on`

**Problem**: Even if `bet_recommendations` had data, team information wouldn't be transferred.

### 2. **NHL Elo Probability Analysis**
```
Unique NHL Elo probabilities (73 bets):
- 0.6247722833142699
- 0.6343623968163071
- 0.6400649998028851  ← Most common (30 bets = 41%)
- 0.6457283331670828
- 0.647608217241493
- 0.651351096099538
```

**Observation**: These look like default/placeholder values, not actual Elo calculations.

### 3. **Probability Distribution Evidence**
```
Sport    | Bets | Unique Probs | Uniqueness | Std Dev
---------|------|--------------|------------|---------
TENNIS   | 116  | 94           | 81.03%     | 0.1006
NCAAB    | 89   | 11           | 12.36%     | 0.0849
NHL      | 73   | 6            | 8.22%      | 0.0053  ← EXTREMELY LOW
NBA      | 32   | 3            | 9.38%      | 0.0110
```

**Conclusion**: Non-tennis sports show clear evidence of placeholder probabilities.

---

## Root Causes Hierarchy

### Primary Root Cause: **Missing Team Data**
- **Effect**: Elo can't calculate team-specific probabilities
- **Evidence**: All `home_team`/`away_team` fields are `'None'`
- **Impact**: Predictions are generic/placeholder

### Secondary Root Cause: **Empty bet_recommendations**
- **Effect**: No source for team data or validated probabilities
- **Evidence**: Table is empty for last 7 days
- **Impact**: Backfill has nothing to work with

### Tertiary Root Cause: **Broken Pipeline Integration**
- **Effect**: Bets placed directly from Kalshi sync
- **Evidence**: No linkage between `bet_recommendations` and `placed_bets`
- **Impact**: Bypasses entire recommendation system

---

## Impact on Predictiveness

### 1. **Elo Accuracy is Meaningless**
- Current "accuracy" of 59.31% is based on **placeholder probabilities**
- Without team data, Elo can't make meaningful predictions
- The system is essentially making random guesses

### 2. **Calibration Issues Explained**
- Severe miscalibration (e.g., NHL -23.03% error) makes sense
- Placeholder probabilities won't calibrate to actual outcomes
- Brier score of 0.2493 ≈ random predictions

### 3. **Edge Calculation Useless**
- Correlation between predicted edge and true edge: 0.0076 (random)
- Without proper Elo probabilities, edge calculation is meaningless
- Confidence levels assigned arbitrarily

---

## Solutions

### Solution 1: **Fix Team Data Pipeline** (HIGHEST PRIORITY)

#### 1.1 Update `backfill_bet_metrics()` function
```python
# Add team data to backfill
def backfill_bet_metrics(db: DBManager = default_db) -> None:
    """Backfill missing metrics INCLUDING team data."""
    try:
        query = """
            UPDATE placed_bets
            SET elo_prob = (...),
                market_prob = (...),
                edge = (...),
                expected_value = (...),
                kelly_fraction = (...),
                confidence = (...),
                home_team = (  -- NEW
                    SELECT home_team FROM bet_recommendations
                    WHERE placed_bets.ticker = bet_recommendations.ticker
                    AND ticker IS NOT NULL
                    ORDER BY created_at DESC LIMIT 1
                ),
                away_team = (  -- NEW
                    SELECT away_team FROM bet_recommendations
                    WHERE placed_bets.ticker = bet_recommendations.ticker
                    AND ticker IS NOT NULL
                    ORDER BY created_at DESC LIMIT 1
                ),
                bet_on = (  -- NEW
                    SELECT bet_on FROM bet_recommendations
                    WHERE placed_bets.ticker = bet_recommendations.ticker
                    AND ticker IS NOT NULL
                    ORDER BY created_at DESC LIMIT 1
                )
            WHERE elo_prob IS NULL
               OR home_team IS NULL
               OR home_team = 'None'
        """
        db.execute(query)
        print("✓ Backfilled missing bet metrics INCLUDING team data")
    except Exception as e:
        print(f"⚠️ Error backfilling metrics: {e}")
```

#### 1.2 Fix `sync_bets_to_database()` function
```python
# In sync_bets_to_database(), add team data lookup
def sync_bets_to_database(...):
    # ... existing code ...
    for fill in fills:
        # ... existing processing ...

        # Look up team data from bet_recommendations or unified_games
        team_query = """
            SELECT home_team, away_team, bet_on
            FROM bet_recommendations
            WHERE ticker = %s
            ORDER BY created_at DESC
            LIMIT 1
        """
        team_data = db.fetch_df(team_query, params=[ticker])

        if not team_data.empty:
            home_team = team_data.iloc[0]['home_team']
            away_team = team_data.iloc[0]['away_team']
            bet_on = team_data.iloc[0]['bet_on']
        else:
            # Fallback: Parse from ticker or market_title
            home_team, away_team = parse_teams_from_ticker(ticker, market_title)
            bet_on = determine_bet_on(side, home_team, away_team)

        # Use team data in INSERT/UPDATE
        # ... rest of processing ...
```

### Solution 2: **Fix bet_recommendations Pipeline** (MEDIUM PRIORITY)

#### 2.1 Verify `{sport}_identify_bets` tasks are running
- Check DAG runs for January 29-February 5
- Verify `bet_recommendations` table is being populated
- Ensure `load_bets_db` tasks are successful

#### 2.2 Add monitoring for empty recommendations
```python
# Add validation to portfolio_optimized_betting task
def load_opportunities_from_database():
    opportunities = db.fetch_df("""
        SELECT * FROM bet_recommendations
        WHERE recommendation_date = CURRENT_DATE
    """)

    if opportunities.empty:
        raise ValueError("No bet recommendations found for today!")

    return opportunities
```

### Solution 3: **Implement Data Quality Checks** (LOW PRIORITY)

#### 3.1 Add team data validation
```python
def validate_team_data(db: DBManager = default_db):
    """Check for bets missing team data."""
    query = """
        SELECT
            sport,
            COUNT(*) as total_bets,
            SUM(CASE WHEN home_team IS NULL OR home_team = 'None' THEN 1 ELSE 0 END) as missing_home,
            SUM(CASE WHEN away_team IS NULL OR away_team = 'None' THEN 1 ELSE 0 END) as missing_away
        FROM placed_bets
        WHERE status IN ('won', 'lost')
        GROUP BY sport
        HAVING SUM(CASE WHEN home_team IS NULL OR home_team = 'None' THEN 1 ELSE 0 END) > 0
    """

    results = db.fetch_df(query)
    if not results.empty:
        raise ValueError(f"Missing team data found: {results.to_dict('records')}")
```

#### 3.2 Add Elo probability validation
```python
def validate_elo_probabilities(db: DBManager = default_db):
    """Check for suspicious Elo probability patterns."""
    query = """
        SELECT
            sport,
            COUNT(DISTINCT elo_prob) as unique_probs,
            COUNT(*) as total_bets,
            STDDEV(elo_prob) as std_dev
        FROM placed_bets
        WHERE status IN ('won', 'lost')
          AND elo_prob IS NOT NULL
        GROUP BY sport
        HAVING COUNT(DISTINCT elo_prob) / COUNT(*)::float < 0.3
           OR STDDEV(elo_prob) < 0.01
    """

    results = db.fetch_df(query)
    if not results.empty:
        raise ValueError(f"Suspicious Elo probability patterns: {results.to_dict('records')}")
```

---

## Implementation Plan

### Phase 1: Immediate Fixes (This Week)
1. **Update `backfill_bet_metrics()`** to include team data
2. **Run backfill** on existing `placed_bets`
3. **Verify team data** now exists in `placed_bets`

### Phase 2: Pipeline Fixes (Next Week)
1. **Fix `sync_bets_to_database()`** to include team data lookup
2. **Verify `bet_recommendations` pipeline** is working
3. **Add data quality checks** to DAG tasks

### Phase 3: Validation & Monitoring (Ongoing)
1. **Implement validation tasks** for team data
2. **Add alerts** for empty recommendations
3. **Monitor Elo probability distribution** for anomalies

---

## Expected Improvements

### After Fixing Team Data:
1. **Meaningful Elo probabilities**: Based on actual team ratings
2. **Improved accuracy**: Expected 54-58% for NHL (based on tuning results)
3. **Better calibration**: Probabilities should match actual win rates
4. **Useful edge calculation**: Should correlate with actual performance

### After Fixing Pipeline:
1. **Consistent data flow**: Team data flows through entire pipeline
2. **Reliable recommendations**: `bet_recommendations` populated daily
3. **Proper integration**: All bets go through recommendation system

---

## Verification Steps

### Step 1: Check Team Data
```sql
-- After fixes, this should return 0
SELECT COUNT(*)
FROM placed_bets
WHERE (home_team IS NULL OR home_team = 'None')
  AND status IN ('won', 'lost');
```

### Step 2: Check Elo Probability Distribution
```sql
-- Should show reasonable variance
SELECT
    sport,
    COUNT(DISTINCT elo_prob) as unique_probs,
    COUNT(*) as total_bets,
    STDDEV(elo_prob) as std_dev
FROM placed_bets
WHERE status IN ('won', 'lost')
GROUP BY sport;
```

### Step 3: Check bet_recommendations
```sql
-- Should have daily recommendations
SELECT
    recommendation_date,
    COUNT(*) as recommendations
FROM bet_recommendations
WHERE recommendation_date >= CURRENT_DATE - 7
GROUP BY recommendation_date
ORDER BY recommendation_date DESC;
```

---

## Conclusion

The poor Elo predictiveness is **not a model problem** - it's a **data pipeline problem**. The Elo system cannot function without team data.

**Primary action required**: Fix the team data pipeline immediately. Without this fix, any further Elo tuning or optimization is meaningless.

**Secondary action**: Ensure the `bet_recommendations` pipeline is working and integrated with the betting system.

Once team data is flowing correctly, we can then properly evaluate and optimize the Elo system's predictiveness.

---
*Analysis complete: 2026-02-05*
*Next step: Implement Phase 1 fixes*
