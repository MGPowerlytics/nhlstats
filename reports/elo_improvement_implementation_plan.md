# Elo Predictiveness Improvement: Implementation Plan

**Date**: February 5, 2026
**Priority**: CRITICAL - System cannot function without team data

---

## Problem Summary

The Elo rating system shows poor predictiveness because **team data is completely missing** from the betting pipeline:

1. **All 407 bets** have `home_team = 'None'` and `away_team = 'None'`
2. **Elo probabilities are generic placeholders** (NHL: only 6 unique values for 73 bets)
3. **bet_recommendations table is empty** (no recent recommendations)
4. **Data pipeline is broken** - bets bypass the recommendation system

**Impact**: Elo predictions are essentially random without team data.

---

## Immediate Action Required (Phase 1)

### 1.1 Fix `backfill_bet_metrics()` Function
**File**: `/mnt/data2/nhlstats/plugins/bet_tracker.py`
**Line**: ~151

**Current function only backfills**:
- `elo_prob`, `market_prob`, `edge`
- `expected_value`, `kelly_fraction`, `confidence`

**Need to add**:
- `home_team`, `away_team`, `bet_on`

**Implementation**:
```python
def backfill_bet_metrics(db: DBManager = default_db) -> None:
    """Backfill missing metrics INCLUDING team data."""
    try:
        query = """
            UPDATE placed_bets
            SET elo_prob = (
                SELECT elo_prob FROM bet_recommendations
                WHERE placed_bets.ticker = bet_recommendations.ticker
                AND ticker IS NOT NULL
                ORDER BY created_at DESC LIMIT 1
            ),
            -- ... existing fields ...
            home_team = (  -- NEW: Add team data
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

### 1.2 Run Backfill on Existing Data
```bash
cd /mnt/data2/nhlstats
POSTGRES_HOST=localhost python -c "
import sys
sys.path.insert(0, 'plugins')
from bet_tracker import backfill_bet_metrics
backfill_bet_metrics()
print('Backfill complete')
"
```

### 1.3 Verify Team Data Now Exists
```sql
-- Should return 0 after backfill
SELECT COUNT(*)
FROM placed_bets
WHERE (home_team IS NULL OR home_team = 'None')
  AND status IN ('won', 'lost');
```

---

## Medium-Term Actions (Phase 2)

### 2.1 Fix `sync_bets_to_database()` Function
**File**: `/mnt/data2/nhlstats/plugins/bet_tracker.py`
**Line**: ~230

**Problem**: Function doesn't look up team data when syncing bets from Kalshi.

**Solution**: Add team data lookup from `bet_recommendations` or parse from ticker.

### 2.2 Verify bet_recommendations Pipeline
**Check DAG tasks**:
1. `{sport}_identify_bets` - Should create recommendations
2. `{sport}_load_bets_db` - Should load to database
3. `portfolio_optimized_betting` - Should read from database

**Debug steps**:
```bash
# Check recent DAG runs
cd /mnt/data2/nhlstats
POSTGRES_HOST=localhost python -c "
import sys
sys.path.insert(0, 'plugins')
from db_manager import default_db

# Check if bet_recommendations is being populated
query = '''
SELECT
    MIN(created_at) as earliest,
    MAX(created_at) as latest,
    COUNT(*) as total,
    COUNT(DISTINCT recommendation_date) as dates
FROM bet_recommendations
'''

result = default_db.fetch_df(query)
print('bet_recommendations status:')
print(result.to_string(index=False))
"
```

### 2.3 Add Data Quality Checks to DAG
**Add validation tasks**:
1. Check `bet_recommendations` has data for today
2. Check `placed_bets` has team data
3. Check Elo probabilities have reasonable variance

---

## Long-Term Improvements (Phase 3)

### 3.1 Implement Team Data Parsing
Create utility function to parse team names from Kalshi tickers:
```python
def parse_teams_from_ticker(ticker: str, market_title: str = None) -> Tuple[str, str]:
    """Parse home and away teams from Kalshi ticker or market title."""
    # Examples:
    # - "KXNHLGAME-26FEB05BOSNYR-BOS" → "Boston Bruins", "New York Rangers"
    # - "KXNBAGAME-26FEB05LALGSW-LAL" → "Los Angeles Lakers", "Golden State Warriors"

    # Implementation logic...
    return home_team, away_team
```

### 3.2 Add Monitoring and Alerts
1. **Daily check**: Team data completeness
2. **Daily check**: bet_recommendations count
3. **Weekly check**: Elo probability distribution
4. **Alert**: When team data is missing

### 3.3 Improve Error Handling
1. **Graceful degradation**: When team data unavailable
2. **Fallback mechanisms**: Multiple sources for team data
3. **Data validation**: At each pipeline stage

---

## Expected Timeline

### Week 1 (Immediate)
- [ ] Fix `backfill_bet_metrics()` function
- [ ] Run backfill on existing data
- [ ] Verify team data now exists
- [ ] Re-run Elo predictiveness analysis

### Week 2 (Pipeline Fixes)
- [ ] Fix `sync_bets_to_database()` function
- [ ] Verify bet_recommendations pipeline
- [ ] Add data quality checks
- [ ] Monitor for 7 days

### Week 3+ (Optimization)
- [ ] Re-evaluate Elo parameters with real data
- [ ] Implement team data parsing
- [ ] Add comprehensive monitoring
- [ ] Optimize Elo predictiveness

---

## Success Metrics

### Primary Metrics (After Phase 1)
1. **Team data completeness**: 100% of bets have `home_team` and `away_team`
2. **Elo probability variance**: Reasonable std dev (>0.05 for team sports)
3. **bet_recommendations count**: >0 daily recommendations

### Secondary Metrics (After Phase 2)
1. **Elo accuracy**: >54% for NHL, >60% for other sports
2. **Calibration error**: <5% for all probability bins
3. **Edge correlation**: >0.2 correlation with true edge

### Tertiary Metrics (After Phase 3)
1. **Model performance**: Comparable to historical tuning results
2. **Betting performance**: Positive ROI with proper team data
3. **System reliability**: No missing team data incidents

---

## Risk Assessment

### High Risk: Team Data Unavailable
- **Probability**: High (currently 100%)
- **Impact**: Critical (system unusable)
- **Mitigation**: Phase 1 fixes

### Medium Risk: bet_recommendations Empty
- **Probability**: High (currently 100%)
- **Impact**: High (pipeline broken)
- **Mitigation**: Phase 2 fixes

### Low Risk: Elo Model Issues
- **Probability**: Medium
- **Impact**: Medium (predictiveness suboptimal)
- **Mitigation**: Can be tuned after data fixed

---

## Verification Script

Create verification script to check implementation:

```python
#!/usr/bin/env python3
"""
Verify Elo system data quality after fixes.
"""

import sys
sys.path.insert(0, '/mnt/data2/nhlstats/plugins')
from db_manager import default_db

def verify_team_data():
    """Verify team data exists in placed_bets."""
    query = """
        SELECT
            COUNT(*) as total_bets,
            SUM(CASE WHEN home_team IS NULL OR home_team = 'None' THEN 1 ELSE 0 END) as missing_home,
            SUM(CASE WHEN away_team IS NULL OR away_team = 'None' THEN 1 ELSE 0 END) as missing_away
        FROM placed_bets
        WHERE status IN ('won', 'lost')
    """

    result = default_db.fetch_df(query)
    missing_pct = (result.iloc[0]['missing_home'] / result.iloc[0]['total_bets']) * 100

    if missing_pct > 5:
        print(f"❌ FAIL: {missing_pct:.1f}% of bets missing team data")
        return False
    else:
        print(f"✅ PASS: Team data complete ({missing_pct:.1f}% missing)")
        return True

def verify_elo_variance():
    """Verify Elo probabilities have reasonable variance."""
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
    """

    results = default_db.fetch_df(query)
    all_ok = True

    for _, row in results.iterrows():
        sport = row['sport']
        uniqueness = row['unique_probs'] / row['total_bets']
        std_dev = row['std_dev']

        if sport != 'TENNIS':  # Tennis has different characteristics
            if uniqueness < 0.3 or std_dev < 0.02:
                print(f"❌ {sport}: Low variance (uniqueness={uniqueness:.1%}, std={std_dev:.4f})")
                all_ok = False
            else:
                print(f"✅ {sport}: Good variance (uniqueness={uniqueness:.1%}, std={std_dev:.4f})")

    return all_ok

def verify_recommendations():
    """Verify bet_recommendations has data."""
    query = """
        SELECT
            COUNT(*) as total,
            COUNT(DISTINCT recommendation_date) as dates
        FROM bet_recommendations
        WHERE recommendation_date >= CURRENT_DATE - 7
    """

    result = default_db.fetch_df(query)

    if result.iloc[0]['total'] == 0:
        print("❌ FAIL: No bet recommendations in last 7 days")
        return False
    else:
        print(f"✅ PASS: {result.iloc[0]['total']} recommendations across {result.iloc[0]['dates']} days")
        return True

if __name__ == "__main__":
    print("=== ELO SYSTEM DATA QUALITY VERIFICATION ===\n")

    team_ok = verify_team_data()
    variance_ok = verify_elo_variance()
    recommendations_ok = verify_recommendations()

    print("\n=== SUMMARY ===")
    if team_ok and variance_ok and recommendations_ok:
        print("✅ ALL CHECKS PASSED - Elo system data quality is good")
    else:
        print("❌ SOME CHECKS FAILED - See issues above")
        sys.exit(1)
```

---

## Conclusion

**The Elo system cannot be improved until team data is fixed.** All tuning, optimization, or model changes are meaningless without proper team data.

**Immediate priority**: Implement Phase 1 fixes to get team data into the system.

**Once team data is fixed**, we can properly evaluate Elo predictiveness and make meaningful improvements.

---
*Implementation plan created: 2026-02-05*
*Next: Execute Phase 1 immediately*
