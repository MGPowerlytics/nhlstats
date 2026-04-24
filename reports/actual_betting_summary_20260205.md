# Actual Betting Analysis Summary

**Date**: February 5, 2026
**Analysis Period**: January 18 - February 5, 2026 (15 days)
**Data Source**: PostgreSQL `placed_bets` table (407 actual bets)

---

## Executive Summary

### Current Performance
- **Total Bets**: 407 (213 won, 176 lost, 16 open)
- **Total Wagered**: $878.02
- **Total Profit**: -$124.97
- **Overall ROI**: -14.23%
- **Win Rate**: 54.76%

### Key Findings
1. **NBA is the only profitable major sport** (+4.06% ROI)
2. **TENNIS has largest losses** (-$82.52, -21.37% ROI)
3. **NHL MEDIUM is worst segment** (-57.51% ROI)
4. **NCAAB HIGH performs poorly** (-51.07% ROI)
5. **No CBA bets exist** in actual database (contrary to simulated analysis)

---

## Recommended Action: EXCLUDE_WORST_3 Strategy

### Segments to Exclude:
1. **NHL MEDIUM** (-57.51% ROI, 36 bets)
2. **NCAAB HIGH** (-51.07% ROI, 22 bets)
3. **TENNIS HIGH** (-26.99% ROI, 50 bets)

### Expected Impact:
- **ROI Improvement**: -16.39% → -6.08% (+10.31 percentage points)
- **Bet Reduction**: 317 → 209 settled bets (34% reduction)
- **Loss Reduction**: -$111.94 → -$27.21 ($84.73 improvement)

### Implementation:
```python
excluded_segments = [
    ("NHL", "MEDIUM"),
    ("NCAAB", "HIGH"),
    ("TENNIS", "HIGH")
]
```

---

## Performance by Sport

| Sport | Bets | ROI | Win Rate | Status |
|-------|------|-----|----------|--------|
| NBA | 56 | +4.06% | 66.67% | ✅ Profitable |
| UNKNOWN | 12 | +4.16% | 57.14% | ✅ Profitable |
| WNCAAB | 5 | -20.63% | 40.00% | ⚠️ Small sample |
| NCAAB | 104 | -15.97% | 65.05% | ❌ Unprofitable |
| NHL | 73 | -22.78% | 41.10% | ❌ Unprofitable |
| TENNIS | 157 | -21.37% | 50.98% | ❌ Unprofitable |

---

## Top Problematic Segments

| Rank | Segment | Bets | ROI | Win Rate | Loss |
|------|---------|------|-----|----------|------|
| 1 | NHL MEDIUM | 36 | -57.51% | 19.44% | -$20.30 |
| 2 | NCAAB HIGH | 22 | -51.07% | 40.91% | -$21.92 |
| 3 | TENNIS HIGH | 50 | -26.99% | 58.00% | -$42.51 |
| 4 | TENNIS LOW | 24 | -25.00% | 66.67% | -$17.33 |
| 5 | NCAAB LOW | 15 | -22.08% | 80.00% | -$5.95 |

---

## Top Profitable Segments

| Rank | Segment | Bets | ROI | Win Rate | Profit |
|------|---------|------|-----|----------|--------|
| 1 | NBA HIGH | 8 | +33.63% | 87.50% | +$9.06 |
| 2 | NBA MEDIUM | 8 | +20.57% | 50.00% | +$2.73 |
| 3 | NHL HIGH | 37 | +5.29% | 62.16% | +$2.31 |
| 4 | NCAAB MEDIUM | 52 | +3.03% | 73.08% | +$2.59 |
| 5 | UNKNOWN MEDIUM | 6 | +2.42% | 50.00% | +$0.52 |

---

## Comparison with Previous Simulated Analysis (Feb 3)

| Aspect | Simulated Analysis | Actual Analysis |
|--------|-------------------|-----------------|
| **Data Source** | 865 simulated bets | 407 actual bets |
| **Time Period** | Jan 29 - Feb 3 (5d) | Jan 18 - Feb 5 (15d) |
| **CBA Bets** | 11 bets identified | 0 bets found |
| **WNCAAB LOW** | Flagged as problematic | No bets found |
| **TENNIS HIGH ROI** | +2.0% (profitable) | -26.99% (unprofitable) |
| **NHL MEDIUM** | Not identified | -57.51% ROI (worst) |
| **Recommended Exclusions** | CBA-LOW/MED, WNCAAB-LOW, TENNIS-LOW | NHL-MEDIUM, NCAAB-HIGH, TENNIS-HIGH |

---

## Immediate Next Steps

1. **Implement EXCLUDE_WORST_3 strategy** in portfolio optimizer
2. **Monitor for 7 days** with daily performance tracking
3. **Review TENNIS LOW** for potential additional exclusion
4. **Weekly segment analysis** to identify new patterns

---

## Files to Update

1. `plugins/portfolio_optimizer.py` - Add segment filtering
2. `plugins/portfolio_betting.py` - Pass excluded segments
3. `dags/multi_sport_betting_workflow.py` - Configure exclusions

---

## Monitoring Query

```sql
-- Weekly segment performance monitoring
SELECT
    sport,
    confidence,
    COUNT(*) as bets,
    SUM(profit_dollars) as profit,
    ROUND((SUM(profit_dollars) / NULLIF(SUM(cost_dollars), 0) * 100)::numeric, 2) as roi_pct
FROM placed_bets
WHERE placed_date >= CURRENT_DATE - 7
  AND status IN ('won', 'lost')
GROUP BY sport, confidence
HAVING COUNT(*) >= 5
ORDER BY roi_pct ASC;
```

---
*Analysis complete: 2026-02-05*
*Based on actual PostgreSQL betting data*
