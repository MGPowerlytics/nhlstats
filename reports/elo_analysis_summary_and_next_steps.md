# Elo Predictiveness Analysis: Summary & Next Steps

**Date**: February 5, 2026
**Status**: Phase 1 partially complete, Phase 2 needed

---

## Executive Summary

We've identified and **partially fixed** the root cause of poor Elo predictiveness: **missing team data**.

### What Was Fixed:
1. **Updated `backfill_bet_metrics()`** to include team data backfill
2. **Ran backfill** - reduced missing team data from 100% to 18.5%
3. **NHL now has 100% team data** (73/73 bets)

### What Remains:
1. **TENNIS**: 24.2% missing team data (37/153 bets)
2. **NBA**: 33.3% missing team data (16/48 bets)
3. **WNCAAB**: 100% missing team data (5/5 bets)
4. **Early bets** (Jan 18-20) lack matching recommendations

---

## Current State Analysis

### Team Data Completeness (After Phase 1)
| Sport | Total Bets | Missing Team Data | % Missing | Status |
|-------|------------|-------------------|-----------|--------|
| NHL | 73 | 0 | 0.0% | ✅ **FIXED** |
| NCAAB | 103 | 14 | 13.6% | ⚠️ Partial |
| TENNIS | 153 | 37 | 24.2% | ⚠️ Needs work |
| NBA | 48 | 16 | 33.3% | ⚠️ Needs work |
| UNKNOWN | 7 | 0 | 0.0% | ✅ **FIXED** |
| WNCAAB | 5 | 5 | 100.0% | ❌ Critical |

**Overall**: 18.5% missing team data (72/389 bets)

### Root Cause of Remaining Issues
1. **Early bets (Jan 18-20)**: No matching recommendations in `bet_recommendations`
2. **Ticker parsing needed**: Need to parse team names from tickers when recommendations unavailable
3. **WNCAAB**: Possibly no recommendations at all for women's college basketball

---

## Phase 2: Complete Team Data Fix

### 2.1 Create Ticker Parsing Backfill Script
```python
#!/usr/bin/env python3
"""
Backfill team data by parsing from tickers when recommendations unavailable.
"""

import sys
sys.path.insert(0, '/mnt/data2/nhlstats/plugins')
from db_manager import default_db
from parse_teams_from_ticker_fixed import parse_teams_from_ticker, determine_bet_on

def backfill_teams_from_tickers():
    """Backfill missing team data by parsing from tickers."""

    # Get bets still missing team data
    query = """
        SELECT
            bet_id, ticker, sport, side, market_title,
            home_team, away_team, bet_on
        FROM placed_bets
        WHERE (home_team IS NULL OR home_team = 'None')
          AND status IN ('won', 'lost')
          AND ticker IS NOT NULL
    """

    bets = default_db.fetch_df(query)

    if bets.empty:
        print("No bets missing team data")
        return

    print(f"Found {len(bets)} bets missing team data")

    updated = 0
    for _, bet in bets.iterrows():
        ticker = bet['ticker']
        sport = bet['sport']
        side = bet['side']
        market_title = bet['market_title']

        # Parse teams from ticker
        home_team, away_team = parse_teams_from_ticker(ticker, market_title)

        if home_team and away_team:
            # Determine which team bet is on
            bet_on = determine_bet_on(side, home_team, away_team, ticker)

            # Update database
            update_query = """
                UPDATE placed_bets
                SET home_team = %s,
                    away_team = %s,
                    bet_on = %s
                WHERE bet_id = %s
            """

            default_db.execute(update_query, params=[
                home_team, away_team, bet_on, bet['bet_id']
            ])

            updated += 1

    print(f"Updated {updated} bets with team data from ticker parsing")
```

### 2.2 Update `sync_bets_to_database()` Function
**File**: `plugins/bet_tracker.py`

Add team parsing logic when inserting new bets:
```python
def sync_bets_to_database(...):
    # ... existing code ...

    for fill in fills:
        # ... existing processing ...

        # Parse teams from ticker if not in recommendations
        home_team, away_team = parse_teams_from_ticker(ticker, market_title)
        bet_on = determine_bet_on(side, home_team, away_team, ticker)

        # Use parsed teams if available
        # ... rest of processing ...
```

### 2.3 Create Data Quality Monitoring
Add to DAG or run daily:
```python
def monitor_team_data_quality():
    """Daily check for team data completeness."""
    query = """
        SELECT
            sport,
            COUNT(*) as total_bets,
            SUM(CASE WHEN home_team IS NULL OR home_team = 'None' THEN 1 ELSE 0 END) as missing
        FROM placed_bets
        WHERE placed_date >= CURRENT_DATE - 7
        GROUP BY sport
        HAVING SUM(CASE WHEN home_team IS NULL OR home_team = 'None' THEN 1 ELSE 0 END) > 0
    """

    results = default_db.fetch_df(query)

    if not results.empty:
        # Send alert
        send_alert(f"Missing team data: {results.to_dict('records')}")
```

---

## Phase 3: Elo System Re-evaluation

### Once team data is 95%+ complete:
1. **Re-run Elo predictiveness analysis** with real team-based probabilities
2. **Evaluate calibration** - should improve significantly
3. **Check edge calculation** - should show meaningful correlation
4. **Review confidence levels** - should align with actual performance

### Expected Improvements:
1. **NHL accuracy**: Should improve from 41.1% to ~54% (based on tuning results)
2. **Calibration error**: Should reduce from -23% to <5%
3. **Edge correlation**: Should increase from 0.0076 to >0.2
4. **Brier score**: Should improve from 0.2493 to <0.24

---

## Immediate Next Actions

### 1. Create and Run Ticker Parsing Backfill
```bash
cd /mnt/data2/nhlstats
POSTGRES_HOST=localhost python scripts/backfill_teams_from_tickers.py
```

### 2. Verify Team Data Completeness
```bash
cd /mnt/data2/nhlstats
POSTGRES_HOST=localhost python scripts/verify_elo_data_quality.py
```

### 3. Update sync_bets_to_database() Function
Edit `plugins/bet_tracker.py` to include team parsing for new bets.

### 4. Add Daily Monitoring
Create a daily DAG task to check team data quality.

---

## Long-term Elo Improvements (After Data Fix)

Once team data is complete, we can focus on actual Elo model improvements:

### 1. **Parameter Optimization**
- Re-tune K-factor, home advantage for each sport
- Implement sport-specific optimizations
- Add recency weighting where beneficial

### 2. **Model Enhancements**
- Consider margin of victory adjustments
- Add fatigue/travel factors
- Implement uncertainty estimation

### 3. **Validation Framework**
- Cross-validation by season
- Out-of-sample testing
- Real-time performance tracking

### 4. **Alternative Models**
- Test Glicko-2 for high-variance sports
- Consider ensemble approaches
- Evaluate machine learning alternatives

---

## Risk Assessment

### Low Risk (Controlled):
- **Ticker parsing errors**: Can be manually corrected
- **Partial team data**: 80% complete is usable for analysis
- **Model tuning**: Can be iterative

### Medium Risk (Manageable):
- **bet_recommendations pipeline**: Needs monitoring
- **Data synchronization**: Between Kalshi and database
- **Performance validation**: Need sufficient sample size

### High Risk (Mitigation Needed):
- **Complete pipeline failure**: Would stop all betting
- **Data corruption**: Need backup/restore procedures
- **Regulatory changes**: Could affect market access

---

## Success Metrics Timeline

### Week 1 (Complete):
- [x] Identify team data issue
- [x] Update backfill function
- [ ] **Achieve 95%+ team data completeness**

### Week 2 (Evaluation):
- [ ] Re-run Elo predictiveness analysis
- [ ] Verify calibration improvement
- [ ] **Achieve >54% NHL accuracy**

### Week 3 (Optimization):
- [ ] Parameter tuning with real data
- [ ] Implement model improvements
- [ ] **Achieve positive ROI with Elo-based bets**

### Ongoing (Monitoring):
- [ ] Daily data quality checks
- [ ] Weekly performance reviews
- [ ] Monthly model re-evaluation

---

## Conclusion

**The critical path is clear**: Fix team data completeness first, then evaluate and optimize Elo.

**Current priority**: Complete Phase 2 (ticker parsing backfill) to get to 95%+ team data completeness.

**Once team data is fixed**, we'll have a meaningful baseline to evaluate Elo predictiveness and make data-driven improvements.

---
*Analysis and plan created: 2026-02-05*
*Next: Execute Phase 2 immediately*
