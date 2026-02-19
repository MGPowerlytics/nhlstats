# Elo Predictiveness Analysis: Final Summary & Next Steps

**Date**: February 5, 2026
**Status**: CRITICAL DATA ISSUE FIXED, READY FOR ELO RE-EVALUATION

---

## Executive Summary

We have **successfully fixed the critical data issue** that was preventing meaningful Elo analysis:

### ✅ **ACCOMPLISHED:**
1. **Team data is now 100% complete** in `placed_bets` table
2. **Fixed backfill functions** to include team data
3. **Created ticker parsing** for missing recommendations
4. **Verified data pipeline** is working (`bet_recommendations` has 2760 entries)

### ⚠️ **REMAINING ISSUE:**
**Elo probabilities in database are based on placeholder values** (calculated when team data was missing).

### 📊 **Current State:**
- **Team Data**: 100% complete (389/389 bets)
- **Elo Variance**: Poor (non-tennis sports have <15% unique probabilities)
- **Calibration**: Poor (NHL: -23% error, NBA: +10% error)
- **Recommendations**: Working (2760 entries, Jan 22-Feb 5)

---

## Root Cause Analysis: Complete

### Problem Timeline:
1. **Jan 18-21**: Bets placed without team data in database
2. **Jan 22 onward**: `bet_recommendations` pipeline starts working
3. **Backfill ran**: Added Elo probabilities but **not team data**
4. **Result**: Elo probabilities calculated with `home_team='None'`, `away_team='None'`

### Impact:
- **NHL**: Only 6 unique probabilities for 73 bets
- **NBA**: Only 3 unique probabilities for 32 bets
- **NCAAB**: 11 unique probabilities for 89 bets
- **TENNIS**: 94 unique probabilities for 116 bets (better due to different calculation)

**Conclusion**: Non-tennis Elo probabilities are **essentially random placeholders**.

---

## Immediate Next Step: Recalculate Elo Probabilities

### Action Required:
**Recalculate ALL Elo probabilities using actual team data.**

### Implementation Options:

#### Option 1: **Backfill Recalculation Script**
```python
def recalculate_elo_probabilities():
    """Recalculate Elo probabilities for all bets using actual team data."""

    # For each bet in placed_bets:
    # 1. Get home_team, away_team, sport, game_date
    # 2. Load appropriate Elo ratings for that date
    # 3. Calculate proper Elo probability
    # 4. Update database

    # This requires historical Elo rating snapshots
```

#### Option 2: **Regenerate from bet_recommendations**
```python
def sync_elo_from_recommendations():
    """Sync Elo probabilities from bet_recommendations."""

    # bet_recommendations has correct Elo probabilities
    # (calculated with team data)
    # Sync these to placed_bets

    query = """
        UPDATE placed_bets pb
        SET elo_prob = (
            SELECT br.elo_prob
            FROM bet_recommendations br
            WHERE br.ticker = pb.ticker
            ORDER BY br.created_at DESC
            LIMIT 1
        )
        WHERE pb.elo_prob IS NOT NULL
          AND EXISTS (
            SELECT 1 FROM bet_recommendations br2
            WHERE br2.ticker = pb.ticker
          )
    """
```

#### Option 3: **Historical Replay**
```python
def replay_historical_elo():
    """Replay historical games to regenerate Elo ratings."""

    # 1. Load all historical games
    # 2. Initialize Elo ratings
    # 3. Process games chronologically
    # 4. Calculate probabilities at time of each bet
    # 5. Update placed_bets

    # Most accurate but most complex
```

---

## Expected Improvements After Recalculation

### With Proper Team-Based Elo Probabilities:

| Metric | Current (Placeholder) | Expected (Team-Based) | Improvement |
|--------|----------------------|----------------------|-------------|
| **NHL Accuracy** | 41.1% | ~54.0% | +12.9% |
| **NHL Calibration Error** | -23.0% | <5.0% | +18.0% |
| **Elo Variance (NHL)** | 0.0053 std dev | >0.05 std dev | 10x |
| **Edge Correlation** | 0.0076 (random) | >0.20 | Meaningful |
| **Brier Score** | 0.2493 (≈random) | <0.240 | Better |

### Sport-Specific Expectations:
1. **NHL**: Should match tuning results (54% accuracy with K=10, HA=50)
2. **NBA**: Should improve from current 75% accuracy (likely overfitted)
3. **NCAAB**: Should maintain ~66% accuracy with better calibration
4. **TENNIS**: Should maintain ~61% accuracy with better calibration

---

## Implementation Plan

### Phase 1: Data Validation (COMPLETE)
- [x] Identify missing team data issue
- [x] Fix backfill functions
- [x] Parse teams from tickers
- [x] Achieve 100% team data completeness

### Phase 2: Elo Recalculation (NEXT)
- [ ] Choose recalculation method
- [ ] Implement script
- [ ] Run recalculation
- [ ] Verify new probabilities have proper variance

### Phase 3: Performance Evaluation
- [ ] Re-run predictiveness analysis
- [ ] Evaluate calibration
- [ ] Check edge calculation correlation
- [ ] Update confidence thresholds

### Phase 4: Optimization
- [ ] Parameter tuning with real data
- [ ] Model improvements
- [ ] Validation framework
- [ ] Monitoring system

---

## Risk Assessment

### Low Risk (Controlled):
- **Data completeness**: Now 100%
- **Pipeline functionality**: Working
- **Team parsing**: Tested and working

### Medium Risk (Manageable):
- **Historical Elo recalculation**: Complex but doable
- **Performance validation**: Need sufficient sample size
- **Model tuning**: Iterative process

### High Risk (Mitigated):
- **Missing team data**: **FIXED**
- **Placeholder probabilities**: Next to fix
- **Broken pipeline**: Working

---

## Success Metrics

### Already Achieved:
1. ✅ **Team data completeness**: 100% (389/389 bets)
2. ✅ **bet_recommendations pipeline**: Working (2760 entries)
3. ✅ **Ticker parsing**: Working for all sports

### To Achieve (After Recalculation):
1. **Elo probability variance**: >30% uniqueness for team sports
2. **Calibration error**: <5% for all sports
3. **Accuracy improvement**: NHL >54%, maintain other sports
4. **Edge correlation**: >0.20 with true edge

---

## Technical Recommendations

### 1. **Implement Elo Rating Persistence**
```python
# Save daily Elo rating snapshots
def save_elo_snapshot(sport: str, date: date):
    """Save Elo ratings for historical recalculation."""
    ratings = elo.get_all_ratings()
    save_to_database(sport, date, ratings)
```

### 2. **Add Data Quality Monitoring**
```python
# Daily check
def daily_data_quality_check():
    checks = [
        check_team_data_completeness(),
        check_elo_probability_variance(),
        check_recommendations_count(),
        check_calibration_errors()
    ]

    if any(check.failed for check in checks):
        send_alert()
```

### 3. **Improve bet_tracker Integration**
```python
# When syncing new bets
def sync_bets_to_database():
    # ... existing code ...

    # Always try to get team data
    if not home_team or home_team == 'None':
        home_team, away_team = parse_teams_from_ticker(ticker, market_title)

    # Recalculate Elo probability if needed
    if home_team and away_team and (not elo_prob or elo_prob == 0.64):
        elo_prob = calculate_elo_probability(sport, home_team, away_team, game_date)
```

---

## Conclusion

**The critical path forward is clear:**

1. **We have fixed the data issue** (100% team data completeness)
2. **Now we need to recalculate Elo probabilities** with actual team data
3. **Then we can properly evaluate** Elo predictiveness
4. **Finally, we can optimize** the system based on real performance

**Next immediate action**: Implement Option 2 (sync from bet_recommendations) as it's the simplest and `bet_recommendations` already has correct Elo probabilities calculated with team data.

Once Elo probabilities are recalculated, we'll have a meaningful baseline to analyze and improve predictiveness.

---
*Analysis complete: 2026-02-05*
*Next: Recalculate Elo probabilities with team data*
