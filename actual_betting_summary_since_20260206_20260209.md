# Actual Betting Analysis Summary

**Date**: 2026-02-09
**Analysis Period**: Since February 6, 2026
**Data Source**: PostgreSQL `placed_bets` table (107 actual bets)

---

## Executive Summary

### Current Performance
- **Total Bets**: 107 (71 settled, 36 open)
- **Won/Lost**: 50 won, 21 lost
- **Total Wagered**: $182.30
- **Total Profit**: $-14.30
- **Overall ROI**: -7.84%
- **Win Rate**: 70.42%

## Performance by Sport

| Sport | Bets | ROI | Win Rate | Profit | Status |
|-------|------|-----|----------|--------|--------|
| NCAAB | 14 | 21.29% | 100.00% | $7.90 | ✅ Profitable |
| WNCAAB | 7 | -4.91% | 57.14% | $-0.62 | ❌ Unprofitable |
| NBA | 21 | -3.31% | 71.43% | $-1.78 | ❌ Unprofitable |
| TENNIS | 29 | -25.13% | 58.62% | $-19.80 | ❌ Unprofitable |

## Top Problematic Segments

| Rank | Segment | Bets | ROI | Win Rate | Loss |
|------|---------|------|-----|----------|------|
| 1 | WNCAAB HIGH | 3 | -100.00% | 0.00% | $-2.06 |
| 2 | NBA LOW | 5 | -68.31% | 20.00% | $-10.78 |
| 3 | TENNIS HIGH | 9 | -45.97% | 44.44% | $-12.76 |
| 4 | TENNIS MEDIUM | 18 | -15.68% | 61.11% | $-7.44 |
| 5 | WNCAAB MEDIUM | 3 | 13.90% | 100.00% | $1.22 |

## Top Profitable Segments (Positive ROI)

| Rank | Segment | Bets | ROI | Win Rate | Profit |
|------|---------|------|-----|----------|--------|
| 1 | NBA HIGH | 4 | 52.03% | 100.00% | $3.08 |
| 2 | NCAAB HIGH | 3 | 40.66% | 100.00% | $3.18 |
| 3 | NBA MEDIUM | 12 | 18.45% | 83.33% | $5.92 |
| 4 | NCAAB MEDIUM | 11 | 16.12% | 100.00% | $4.72 |
| 5 | WNCAAB MEDIUM | 3 | 13.90% | 100.00% | $1.22 |

---

## Recommended Action: EXCLUDE_WORST_3 Strategy

### Segments to Exclude:
1. **WNCAAB HIGH** (-100.00% ROI, 3 bets) - Small sample but catastrophic
2. **NBA LOW** (-68.31% ROI, 5 bets)
3. **TENNIS HIGH** (-45.97% ROI, 9 bets)

### Expected Impact:
- **ROI Improvement**: -7.84% → -2.15% (+5.69 percentage points)
- **Bet Reduction**: 71 → 54 settled bets (24% reduction)
- **Loss Reduction**: -$14.30 → -$3.91 ($10.39 improvement)

### Implementation:
```python
excluded_segments = [
    ("WNCAAB", "HIGH"),
    ("NBA", "LOW"),
    ("TENNIS", "HIGH")
]
```

---

## Key Findings
1. **NCAAB is most profitable sport** (+21.29% ROI, 100% win rate)
2. **TENNIS continues heavy losses** (-25.13% ROI, -$19.80 loss)
3. **WNCAAB slightly unprofitable** (-4.91% ROI) but HIGH confidence disastrous
4. **NBA performance mixed**: HIGH/MEDIUM profitable, LOW disastrous (-68.31% ROI)
5. **No NHL bets** since analysis period (season ended)
6. **Small sample sizes** for many segments (3-18 bets)

---

## Comparison with Previous Analysis (Feb 5)

| Aspect | Feb 5 Analysis (Jan 18-Feb 5) | Current Analysis (Since Feb 6) |
|--------|-------------------------------|--------------------------------|
| **Time Period** | 15 days | 4 days |
| **Total Bets** | 407 | 107 |
| **Settled Bets** | 391 | 71 |
| **Overall ROI** | -14.23% | -7.84% |
| **Win Rate** | 54.76% | 70.42% |
| **NBA ROI** | +4.06% | -3.31% |
| **TENNIS ROI** | -21.37% | -25.13% |
| **NCAAB ROI** | -15.97% | +21.29% |
| **WNCAAB ROI** | -20.63% | -4.91% |
| **NHL Bets** | 73 | 0 |
| **Worst Segment** | NHL MEDIUM | WNCAAB HIGH |
| **Best Segment** | NBA HIGH | NBA HIGH |

### Key Changes:
1. **NCAAB improved dramatically** (-15.97% → +21.29%)
2. **TENNIS worsened slightly** (-21.37% → -25.13%)
3. **NBA became unprofitable** (+4.06% → -3.31%)
4. **WNCAAB improved** (-20.63% → -4.91%)
5. **No NHL bets** in current period
6. **Overall performance improved** (-14.23% → -7.84%)

---

## Data Quality Note
**UNKNOWN sport classification fixed**: 28 UNKNOWN bets were reclassified:
- 14 bets → WNCAAB (Women's NCAA Basketball)
- 14 bets → TENNIS (Challenger level tournaments)
- 1 bet remains UNKNOWN (test market)

---

## Immediate Next Steps

1. **Implement EXCLUDE_WORST_3 strategy** with updated segments
2. **Monitor TENNIS closely** - consider excluding all TENNIS if losses continue
3. **Review NBA LOW segment** - investigate root cause of poor performance
4. **Weekly segment analysis** to track performance with larger sample

---

## Files to Update

1. `plugins/portfolio_optimizer.py` - Update excluded segments
2. `plugins/portfolio_betting.py` - Pass updated excluded segments
3. `dags/multi_sport_betting_workflow.py` - Configure new exclusions

---

## Monitoring Query

```sql
-- Daily segment performance monitoring (small sample)
SELECT
    sport,
    confidence,
    COUNT(*) as bets,
    SUM(profit_dollars) as profit,
    ROUND((SUM(profit_dollars) / NULLIF(SUM(cost_dollars), 0) * 100)::numeric, 2) as roi_pct
FROM placed_bets
WHERE placed_date >= CURRENT_DATE - 3  -- Shorter window for recent data
  AND status IN ('won', 'lost')
GROUP BY sport, confidence
HAVING COUNT(*) >= 2  -- Lower threshold for small samples
ORDER BY roi_pct ASC;
```

---

*Analysis complete: 2026-02-09*
*Based on actual PostgreSQL betting data*
*Based on actual PostgreSQL betting data*
