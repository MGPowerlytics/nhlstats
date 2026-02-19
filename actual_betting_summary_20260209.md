# Actual Betting Analysis Summary

**Date**: 2026-02-09
**Analysis Period**: Since February 6, 2025
**Data Source**: PostgreSQL `placed_bets` table (537 actual bets)

---

## Executive Summary

### Current Performance
- **Total Bets**: 537 (497 settled, 40 open)
- **Won/Lost**: 290 won, 207 lost
- **Total Wagered**: $1065.22
- **Total Profit**: $-132.22
- **Overall ROI**: -12.41%
- **Win Rate**: 58.35%

## Performance by Sport

| Sport | Bets | ROI | Win Rate | Profit | Status |
|-------|------|-----|----------|--------|--------|
| UNKNOWN | 25 | 14.89% | 76.00% | $8.94 | ✅ Profitable |
| NBA | 84 | 3.64% | 70.24% | $8.14 | ✅ Profitable |
| WNCAAB | 5 | -20.63% | 40.00% | $-0.52 | ❌ Unprofitable |
| NHL | 73 | -22.78% | 41.10% | $-17.99 | ❌ Unprofitable |
| NCAAB | 121 | -9.51% | 68.60% | $-23.02 | ❌ Unprofitable |
| TENNIS | 189 | -23.54% | 51.32% | $-107.77 | ❌ Unprofitable |

## Top Problematic Segments

| Rank | Segment | Bets | ROI | Win Rate | Loss |
|------|---------|------|-----|----------|------|
| 1 | NHL MEDIUM | 47 | -54.45% | 19.15% | $-23.91 |
| 2 | NCAAB HIGH | 21 | -37.48% | 42.86% | $-14.99 |
| 3 | NBA LOW | 21 | -36.65% | 57.14% | $-23.72 |
| 4 | TENNIS HIGH | 60 | -33.55% | 55.00% | $-58.57 |
| 5 | TENNIS LOW | 26 | -23.21% | 69.23% | $-16.93 |

## Top Profitable Segments

| Rank | Segment | Bets | ROI | Win Rate | Profit |
|------|---------|------|-----|----------|--------|
| 1 | NBA HIGH | 18 | 34.80% | 94.44% | $17.04 |
| 2 | NBA MEDIUM | 29 | 22.60% | 75.86% | $16.22 |
| 3 | UNKNOWN MEDIUM | 18 | 17.99% | 83.33% | $9.15 |
| 4 | NHL HIGH | 26 | 16.88% | 80.77% | $5.92 |
| 5 | NCAAB MEDIUM | 68 | 2.67% | 76.47% | $3.49 |

---

## Recommended Action: EXCLUDE_WORST_3 Strategy

### Segments to Exclude:
1. **NHL MEDIUM** (-54.45% ROI, 47 bets)
2. **NCAAB HIGH** (-37.48% ROI, 21 bets)
3. **NBA LOW** (-36.65% ROI, 21 bets)

### Expected Impact:
- **ROI Improvement**: -12.41% → -5.21% (+7.20 percentage points)
- **Bet Reduction**: 497 → 408 settled bets (18% reduction)
- **Loss Reduction**: -$132.22 → -$55.58 ($76.64 improvement)

### Implementation:
```python
excluded_segments = [
    ("NHL", "MEDIUM"),
    ("NCAAB", "HIGH"),
    ("NBA", "LOW")
]
```

---

## Strategy Comparison

| Strategy | Bets | Wagered | Profit | ROI | Win Rate |
|----------|------|---------|--------|-----|----------|
| ALL_BETS | 497 | $1065.22 | $-132.22 | -12.41% | 58.35% |
| EXCLUDE_WORST_3 | 408 | $914.59 | $-55.58 | -5.21% | 61.27% |

---

## Key Findings
1. **NBA remains profitable** (+3.64% ROI) but NBA LOW segment is problematic (-36.65%)
2. **TENNIS continues heavy losses** (-23.54% ROI, -$107.77 loss)
3. **NHL MEDIUM is worst segment** (-54.45% ROI)
4. **NCAAB HIGH performs poorly** (-37.48% ROI)
5. **UNKNOWN segment performs well** (+14.89% ROI) but small sample size

---

## Comparison with Previous Analysis (Feb 5)

| Aspect | Feb 5 Analysis (Jan 18-Feb 5) | Current Analysis (Since Feb 6) |
|--------|-------------------------------|--------------------------------|
| **Total Bets** | 407 | 537 |
| **Settled Bets** | 391 | 497 |
| **Total Wagered** | $878.02 | $1065.22 |
| **Total Profit** | -$124.97 | -$132.22 |
| **Overall ROI** | -14.23% | -12.41% |
| **Win Rate** | 54.76% | 58.35% |
| **NBA ROI** | +4.06% | +3.64% |
| **TENNIS ROI** | -21.37% | -23.54% |
| **NHL MEDIUM ROI** | -57.51% | -54.45% |
| **NCAAB HIGH ROI** | -51.07% | -37.48% |
| **Worst Segment** | NHL MEDIUM | NHL MEDIUM |
| **Best Segment** | NBA HIGH | NBA HIGH |
| **Recommended Exclusions** | NHL-MEDIUM, NCAAB-HIGH, TENNIS-HIGH | NHL-MEDIUM, NCAAB-HIGH, NBA-LOW |

### Key Changes:
1. **NBA LOW emerged as problematic** (-36.65% ROI) replacing TENNIS HIGH in worst segments
2. **Overall performance improved slightly** (ROI: -14.23% → -12.41%)
3. **Win rate increased** (54.76% → 58.35%)
4. **NCAAB HIGH improved** (-51.07% → -37.48%) but still unprofitable
5. **TENNIS performance worsened** (-21.37% → -23.54%)

---

## Immediate Next Steps

1. **Implement EXCLUDE_WORST_3 strategy** in portfolio optimizer
2. **Monitor TENNIS performance** - consider additional exclusions if losses continue
3. **Review NBA LOW segment** - investigate why low confidence NBA bets underperform
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

*Analysis complete: 2026-02-09*
*Based on actual PostgreSQL betting data*
