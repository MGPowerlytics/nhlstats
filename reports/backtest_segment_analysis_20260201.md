# Backtest Segment Analysis Report

**Date**: February 1, 2026
**Analysis Period**: January 28, 2026 - February 1, 2026
**Purpose**: Identify unprofitable betting segments to exclude from future betting

---

## Summary

After analyzing 187 settled bets over 4 days, we identified significant performance variation by sport and confidence level. Two segments were identified as consistently unprofitable and have been excluded from betting:

| Excluded Segment | Bets | Win % | PnL | ROI | Reason |
|-----------------|------|-------|-----|-----|--------|
| **NHL MEDIUM** | 34 | 14.7% | -$24.45 | **-83.0%** | Catastrophic win rate |
| **TENNIS LOW** | 12 | 66.7% | -$11.09 | **-26.3%** | High win rate but bad payouts |

**Expected Impact**: Excluding these segments would have improved ROI from **-14.1%** to **-1.2%** (saving $35.54).

---

## Full Performance Breakdown

### By Confidence Level (Overall)

| Confidence | Bets | Wins | Win % | PnL | Wagered | ROI |
|------------|------|------|-------|-----|---------|-----|
| HIGH | 71 | 44 | 62.0% | -$4.17 | $89.17 | -4.7% |
| MEDIUM | 90 | 46 | 51.1% | -$23.74 | $144.74 | -16.4% |
| LOW | 26 | 21 | 80.8% | -$9.96 | $34.96 | -28.5% |
| **TOTAL** | 187 | 111 | 59.4% | -$37.87 | $268.87 | **-14.1%** |

### By Sport + Confidence (Detailed)

| Confidence | Sport | Bets | Wins | Win % | PnL | Wagered | ROI | Avg Edge | Avg Elo |
|------------|-------|------|------|-------|-----|---------|-----|----------|---------|
| HIGH | NBA | 1 | 0 | 0.0% | -$3.30 | $3.30 | -100.0% | -0.0199 | 0.6401 |
| HIGH | NCAAB | 17 | 9 | 52.9% | -$5.45 | $26.45 | -20.6% | 0.0242 | 0.6695 |
| HIGH | NHL | 32 | 19 | 59.4% | -$2.02 | $25.02 | -8.1% | 0.0142 | 0.6414 |
| HIGH | TENNIS | 9 | 7 | 77.8% | +$3.02 | $24.98 | **+12.1%** ✅ | -0.0142 | 0.6680 |
| HIGH | UNKNOWN | 12 | 9 | 75.0% | +$3.58 | $9.42 | **+38.0%** ✅ | -0.0125 | 0.5833 |
| LOW | NBA | 2 | 2 | 100.0% | +$1.24 | $6.76 | **+18.3%** ✅ | -0.2049 | 0.6401 |
| LOW | NCAAB | 10 | 9 | 90.0% | -$0.49 | $15.49 | -3.2% | 0.0204 | 0.7574 |
| LOW | TENNIS | 12 | 8 | 66.7% | -$11.09 | $42.09 | **-26.3%** 🚫 | -0.2848 | 0.6077 |
| LOW | UNKNOWN | 2 | 2 | 100.0% | +$0.38 | $1.62 | **+23.5%** ✅ | -0.1790 | 0.6310 |
| MEDIUM | NBA | 6 | 2 | 33.3% | -$1.75 | $3.75 | -46.7% | 0.0451 | 0.6401 |
| MEDIUM | NCAAB | 33 | 28 | 84.8% | +$8.24 | $37.76 | **+21.8%** ✅ | 0.0267 | 0.6612 |
| MEDIUM | NHL | 34 | 5 | 14.7% | -$24.45 | $29.45 | **-83.0%** 🚫 | 0.0642 | 0.6412 |
| MEDIUM | TENNIS | 11 | 6 | 54.5% | -$5.20 | $33.20 | -15.7% | -0.0687 | 0.6431 |
| MEDIUM | UNKNOWN | 6 | 5 | 83.3% | -$0.58 | $9.58 | -6.1% | -0.0850 | 0.5866 |

---

## Strategy Backtests

### Tested Scenarios

| Strategy | Bets | Win % | PnL | ROI | Improvement |
|----------|------|-------|-----|-----|-------------|
| **0. CURRENT (All bets)** | 187 | 59.4% | -$37.87 | -14.1% | baseline |
| 1. HIGH Only | 71 | 62.0% | -$4.17 | -4.7% | +9.4% |
| 2. HIGH + MEDIUM | 161 | 55.9% | -$27.91 | -13.8% | +0.3% |
| 3. Negative Edge Only | 87 | 72.4% | -$10.17 | -6.0% | +8.1% |
| 4. Positive Edge Only | 100 | 48.0% | -$27.70 | -28.1% | -14.0% |
| 5. Edge >= 5% | 68 | 45.6% | -$17.80 | -26.3% | -12.2% |
| 6. Edge >= 10% | 9 | 77.8% | +$0.20 | +1.9% | +16.0% |
| **7. Excl NHL-MED + TNS-LOW** | 141 | 69.5% | **-$2.33** | **-1.2%** | **+12.9%** ✅ |
| 8. HIGH + Neg Edge | 37 | 67.6% | +$3.51 | +6.4% | +20.5% |
| 9. NCAAB Only | 60 | 76.7% | +$2.30 | +2.9% | +17.0% |

### Selected Strategy: #7 - Exclude NHL MEDIUM + TENNIS LOW

**Rationale**:
- Maintains high bet volume (141 vs 187)
- Removes catastrophic NHL MEDIUM segment (-83% ROI, $24.45 loss)
- Removes underperforming TENNIS LOW segment (-26.3% ROI, $11.09 loss)
- Improves expected ROI from -14.1% to -1.2%
- Conservative change that doesn't dramatically reduce bet count

---

## Key Insights

### 1. Negative Edge Outperforms Positive Edge

Counterintuitively, bets where our Elo probability is **lower** than market probability (negative edge) perform better:

| Edge Direction | Bets | Win % | ROI |
|----------------|------|-------|-----|
| Negative Edge (< 0) | 87 | 72.4% | -6.0% |
| Positive Edge (> 0) | 100 | 48.0% | -28.1% |

**Interpretation**: Market Agreement strategy works - we're betting WITH the market when Elo confirms market direction. Positive edge means we disagree with market, which hasn't been profitable.

### 2. NHL MEDIUM is Catastrophic

34 bets with only 14.7% win rate (-83% ROI) despite having:
- Avg Edge: 6.42% (positive, meaning we disagree with market)
- Avg Elo Prob: 64.12% (reasonable confidence)

**Root Cause**: NHL high variance + MEDIUM confidence = overconfident disagreement with market.

### 3. TENNIS LOW Loses Despite High Win Rate

66.7% win rate but -26.3% ROI because:
- Avg Market Prob: 89.25% (betting heavy favorites)
- Payouts are minimal (winning ~$0.11 per $1 bet)
- Any loss wipes out many wins

### 4. NCAAB MEDIUM is Profitable

Best performing segment with 84.8% win rate, +21.8% ROI:
- Avg Edge: 2.67% (small positive edge)
- Avg Elo Prob: 66.12%
- Consistent performance

---

## Implementation

### Changes Made (2026-02-01)

1. Added `excluded_segments` parameter to `PortfolioOptimizer`
2. Added `excluded_segments` parameter to `PortfolioBettingManager`
3. Updated DAG to exclude:
   - `("NHL", "MEDIUM")`
   - `("TENNIS", "LOW")`

### Files Modified

- `plugins/portfolio_optimizer.py`: Added `excluded_segments` filtering
- `plugins/portfolio_betting.py`: Pass-through `excluded_segments` parameter
- `dags/multi_sport_betting_workflow.py`: Configure excluded segments

---

## Follow-up Analysis (Recommended: 2026-02-03)

After 2 days of running with excluded segments, run this query to compare:

```sql
-- Compare performance before/after segment exclusion
SELECT
    CASE
        WHEN placed_date < '2026-02-01' THEN 'Before (Jan 28-31)'
        ELSE 'After (Feb 1+)'
    END as period,
    COUNT(*) as bets,
    SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) as wins,
    ROUND((100.0 * SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) / COUNT(*))::numeric, 1) as win_pct,
    ROUND(SUM(profit_dollars)::numeric, 2) as pnl,
    ROUND((100.0 * SUM(profit_dollars) / NULLIF(SUM(cost_dollars), 0))::numeric, 1) as roi_pct
FROM placed_bets
WHERE placed_date >= '2026-01-28'
  AND status IN ('won', 'lost')
GROUP BY 1
ORDER BY 1;
```

### Questions to Answer in Follow-up

1. Did excluding NHL MEDIUM and TENNIS LOW improve ROI?
2. Are there other segments emerging as problematic?
3. Should we consider more aggressive filtering (e.g., HIGH + Negative Edge only)?
4. Is NCAAB continuing to outperform?

---

## Appendix: Raw Data Queries

### Query 1: Performance by Confidence + Sport
```sql
SELECT confidence, sport, COUNT(*), SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) as wins,
       ROUND((100.0 * SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) / COUNT(*))::numeric, 1) as win_pct,
       ROUND(SUM(profit_dollars)::numeric, 2) as pnl
FROM placed_bets
WHERE placed_date >= '2026-01-28' AND status IN ('won','lost')
GROUP BY confidence, sport ORDER BY confidence, sport;
```

### Query 2: Backtest Scenario Comparison
```sql
-- See strategy backtest section above for full queries
```

---

*Report generated: 2026-02-01*
*Analyst: Automated Backtest System*
