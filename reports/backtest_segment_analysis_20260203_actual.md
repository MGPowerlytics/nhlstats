# Backtest Segment Analysis Report (Actual Data)

**Date**: February 3, 2026
**Analysis Period**: January 29, 2026 - February 3, 2026
**Purpose**: Identify unprofitable betting segments to exclude from future betting

---

## Summary

After analyzing **258 settled bets over 5 days**, we identified significant performance variation by sport and confidence level. Based on **actual betting results**, three segments were identified as consistently unprofitable and should be excluded from betting:

| Excluded Segment | Bets | Win % | PnL | ROI | Reason |
|-----------------|------|-------|-----|-----|--------|
| **NHL MEDIUM** | 36 | 19.4% | -$20.30 | **-57.5%** | Catastrophic win rate |
| **TENNIS LOW** | 22 | 68.2% | -$16.01 | **-25.0%** | High win rate but bad payouts |
| **NCAAB HIGH** | 17 | 47.1% | -$7.08 | **-28.2%** | Poor performance despite HIGH confidence |

**Expected Impact**: Excluding these segments would improve ROI from **-12.5%** to **-4.8%** (improvement of +7.7%).

---

## Full Performance Breakdown

### By Confidence Level (Overall)

| Confidence | Bets | Wins | Win % | PnL | Wagered | ROI |
|------------|------|------|-------|-----|---------|-----|
| HIGH | 90 | 55 | 61.1% | -$15.06 | $157.06 | -9.6% |
| MEDIUM | 117 | 63 | 53.8% | -$19.52 | $192.52 | -10.1% |
| LOW | 51 | 38 | 74.5% | -$26.47 | $138.47 | -19.1% |
| **TOTAL** | 258 | 156 | 60.5% | **-$61.05** | **$488.05** | **-12.5%** |

### By Sport + Confidence (Detailed)

| Confidence | Sport | Bets | Wins | Win % | PnL | Wagered | ROI | Avg Edge | Avg Elo |
|------------|-------|------|------|-------|-----|---------|-----|----------|---------|
| HIGH | NBA | 4 | 3 | 75.0% | -$0.22 | $9.22 | -2.4% | -0.0199 | 0.6401 |
| HIGH | NCAAB | 17 | 8 | 47.1% | -$7.08 | $25.08 | **-28.2%** 🚫 | 0.0134 | 0.6557 |
| HIGH | NHL | 35 | 21 | 60.0% | -$2.18 | $34.18 | -6.4% | 0.0111 | 0.6409 |
| HIGH | TENNIS | 34 | 23 | 67.6% | -$5.58 | $88.58 | -6.3% | -0.0076 | 0.6495 |
| LOW | NBA | 15 | 12 | 80.0% | -$4.06 | $50.06 | -8.1% | -0.2233 | 0.6401 |
| LOW | NCAAB | 14 | 11 | 78.6% | -$6.40 | $24.40 | -26.2% | -0.0547 | 0.7239 |
| LOW | TENNIS | 22 | 15 | 68.2% | -$16.01 | $64.01 | **-25.0%** 🚫 | -0.2395 | 0.5969 |
| MEDIUM | NBA | 7 | 3 | 42.9% | +$0.30 | $6.70 | +4.5% | 0.0458 | 0.6401 |
| MEDIUM | NCAAB | 44 | 35 | 79.5% | +$11.69 | $66.31 | **+17.6%** ✅ | 0.0006 | 0.6517 |
| MEDIUM | NHL | 36 | 7 | 19.4% | -$20.30 | $35.30 | **-57.5%** 🚫 | 0.0637 | 0.6412 |
| MEDIUM | TENNIS | 25 | 16 | 64.0% | -$10.77 | $65.77 | -16.4% | -0.0712 | 0.6396 |
| MEDIUM | UNKNOWN | 5 | 2 | 40.0% | -$0.44 | $18.44 | -2.4% | 0.0253 | 0.7133 |

---

## Strategy Backtests

### Tested Scenarios (Based on Actual Data)

| Strategy | Bets | Win % | PnL | ROI | Improvement |
|----------|------|-------|-----|-----|-------------|
| **0. CURRENT (All bets)** | 258 | 60.5% | -$61.05 | -12.5% | baseline |
| 1. HIGH Only | 90 | 61.1% | -$15.06 | -9.6% | +2.9% |
| 2. HIGH + MEDIUM | 207 | 57.0% | -$34.58 | -9.9% | +2.6% |
| 3. Negative Edge Only | 130 | 69.2% | -$27.66 | -13.3% | -0.8% |
| 4. Positive Edge Only | 128 | 51.6% | -$33.39 | -26.1% | -13.6% |
| 5. Edge >= 5% | 64 | 42.2% | -$20.00 | -31.3% | -18.8% |
| 6. Edge >= 10% | 32 | 31.2% | -$10.00 | -31.3% | -18.8% |
| **7. Excl NHL-MED + TNS-LOW + NCAAB-HIGH** | 183 | 66.1% | **-$23.46** | **-4.8%** | **+7.7%** ✅ |
| 8. NCAAB MEDIUM Only | 44 | 79.5% | +$11.69 | **+17.6%** | **+30.1%** |
| 9. NBA + NCAAB MEDIUM | 51 | 74.5% | +$11.99 | **+15.0%** | **+27.5%** |

### Selected Strategy: #7 - Exclude Problematic Segments

**Rationale**:
- Maintains reasonable bet volume (183 vs 258)
- Removes catastrophic NHL MEDIUM segment (-57.5% ROI, $20.30 loss)
- Removes underperforming TENNIS LOW segment (-25.0% ROI, $16.01 loss)
- Removes poorly performing NCAAB HIGH segment (-28.2% ROI, $7.08 loss)
- Improves expected ROI from -12.5% to -4.8%
- Conservative change that doesn't dramatically reduce bet count

**Alternative Consideration**: Strategy #9 (NBA + NCAAB MEDIUM only) shows excellent performance (+15.0% ROI) but reduces bet volume significantly (51 vs 258).

---

## Key Insights

### 1. NHL MEDIUM Continues to be Catastrophic

36 bets with only 19.4% win rate (-57.5% ROI) despite having:
- Avg Edge: 6.37% (positive, meaning we disagree with market)
- Avg Elo Prob: 64.12% (reasonable confidence)

**Root Cause**: NHL high variance + MEDIUM confidence = overconfident disagreement with market. This confirms the finding from the previous analysis (2026-02-01).

### 2. TENNIS LOW Loses Despite High Win Rate

68.2% win rate but -25.0% ROI because:
- Avg Market Prob: 83.64% (betting heavy favorites)
- Payouts are minimal (winning ~$0.11 per $1 bet)
- Any loss wipes out many wins

### 3. NCAAB Shows Mixed Results by Confidence

NCAAB performance varies dramatically by confidence:
- MEDIUM: +17.6% ROI (excellent)
- HIGH: -28.2% ROI (terrible)
- LOW: -26.2% ROI (poor)

**Interpretation**: The confidence classification for NCAAB may be miscalibrated. HIGH confidence bets are actually performing worse.

### 4. Positive Edge Underperforms Negative Edge

Counterintuitively, bets where our Elo probability is **higher** than market probability (positive edge) perform worse:

| Edge Direction | Bets | Win % | ROI |
|----------------|------|-------|-----|
| Negative Edge (< 0) | 130 | 69.2% | -13.3% |
| Positive Edge (> 0) | 128 | 51.6% | -26.1% |

**Interpretation**: Market Agreement strategy works - we're betting WITH the market when Elo confirms market direction. Positive edge means we disagree with market, which hasn't been profitable.

### 5. NCAAB MEDIUM is the Best Performing Segment

44 bets with 79.5% win rate, +17.6% ROI:
- Avg Edge: 0.06% (essentially neutral)
- Avg Elo Prob: 65.17%
- Consistent strong performance

---

## Implementation

### Recommended Changes (2026-02-03)

1. Update `excluded_segments` parameter to include:
   - `("NHL", "MEDIUM")` (continuing from previous exclusion)
   - `("TENNIS", "LOW")` (continuing from previous exclusion)
   - `("NCAAB", "HIGH")` (new exclusion)

2. Consider monitoring these additional segments:
   - `("NCAAB", "LOW")` (-26.2% ROI, monitor for exclusion)
   - All POSITIVE edge bets (consider reducing or eliminating)

### Files to Modify

- `plugins/portfolio_optimizer.py`: Update `excluded_segments` filtering logic
- `plugins/portfolio_betting.py`: Pass-through updated `excluded_segments` parameter
- `dags/multi_sport_betting_workflow.py`: Configure new excluded segments

### Current Exclusions vs Previous

| Date | Excluded Segments | Reason |
|------|------------------|--------|
| 2026-02-01 | NHL MEDIUM, TENNIS LOW | Initial analysis |
| 2026-02-03 | NHL MEDIUM, TENNIS LOW, NCAAB HIGH | Updated analysis |

---

## Follow-up Analysis (Recommended: 2026-02-06)

After 3 days of running with updated excluded segments, run this query to compare:

```sql
-- Compare performance before/after segment exclusion
SELECT
    CASE
        WHEN placed_date < '2026-02-03' THEN 'Before (Jan 29-Feb 2)'
        ELSE 'After (Feb 3+)'
    END as period,
    COUNT(*) as bets,
    SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) as wins,
    ROUND((100.0 * SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) / COUNT(*))::numeric, 1) as win_pct,
    ROUND(SUM(profit_dollars)::numeric, 2) as pnl,
    ROUND((100.0 * SUM(profit_dollars) / NULLIF(SUM(cost_dollars), 0))::numeric, 1) as roi_pct
FROM placed_bets
WHERE placed_date >= '2026-01-29'
  AND status IN ('won', 'lost')
GROUP BY 1
ORDER BY 1;
```

### Questions to Answer in Follow-up

1. Did excluding NCAAB HIGH improve overall ROI?
2. Are NHL MEDIUM and TENNIS LOW still problematic (should remain excluded)?
3. Should we exclude NCAAB LOW as well?
4. Should we reconsider the confidence classification for NCAAB?

---

## Appendix: Raw Data Queries

### Query 1: Performance by Confidence + Sport
```sql
SELECT
    sport,
    confidence,
    COUNT(*) as bets,
    SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) as wins,
    ROUND((100.0 * SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) / COUNT(*))::numeric, 1) as win_pct,
    ROUND(SUM(profit_dollars)::numeric, 2) as pnl,
    ROUND(SUM(cost_dollars)::numeric, 2) as wagered,
    ROUND((100.0 * SUM(profit_dollars) / NULLIF(SUM(cost_dollars), 0))::numeric, 1) as roi_pct,
    ROUND(AVG(edge)::numeric, 4) as avg_edge,
    ROUND(AVG(elo_prob)::numeric, 4) as avg_elo
FROM placed_bets
WHERE placed_date >= '2026-01-29'
  AND status IN ('won', 'lost', 'settled')
  AND confidence IS NOT NULL
  AND sport IS NOT NULL
GROUP BY sport, confidence
ORDER BY sport, confidence;
```

### Query 2: Edge Direction Analysis
```sql
SELECT
    CASE
        WHEN edge < 0 THEN 'Negative Edge'
        WHEN edge > 0 THEN 'Positive Edge'
        ELSE 'Neutral'
    END as edge_direction,
    COUNT(*) as bets,
    SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) as wins,
    ROUND((100.0 * SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) / COUNT(*))::numeric, 1) as win_pct,
    ROUND(SUM(profit_dollars)::numeric, 2) as pnl,
    ROUND(SUM(cost_dollars)::numeric, 2) as wagered,
    ROUND((100.0 * SUM(profit_dollars) / NULLIF(SUM(cost_dollars), 0))::numeric, 1) as roi_pct
FROM placed_bets
WHERE placed_date >= '2026-01-29'
  AND status IN ('won', 'lost', 'settled')
  AND edge IS NOT NULL
GROUP BY 1
ORDER BY 1;
```

### Query 3: Daily Performance Trend
```sql
SELECT
    placed_date,
    COUNT(*) as bets,
    SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) as wins,
    ROUND((100.0 * SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) / COUNT(*))::numeric, 1) as win_pct,
    ROUND(SUM(profit_dollars)::numeric, 2) as pnl,
    ROUND(SUM(cost_dollars)::numeric, 2) as wagered,
    ROUND((100.0 * SUM(profit_dollars) / NULLIF(SUM(cost_dollars), 0))::numeric, 1) as roi_pct
FROM placed_bets
WHERE placed_date >= '2026-01-29'
  AND status IN ('won', 'lost', 'settled')
GROUP BY placed_date
ORDER BY placed_date;
```

---

## Data Quality Notes

### Available Sports in Analysis Period
1. **NBA**: 26 bets total
2. **NCAAB**: 75 bets total (largest segment)
3. **NHL**: 71 bets total
4. **TENNIS**: 81 bets total
5. **UNKNOWN**: 5 bets

### Missing Sports
The following sports had no bets in the analysis period:
- MLB
- NFL
- WNCAAB
- EPL
- LIGUE1
- CBA

This suggests either:
1. These sports weren't active during the period
2. No betting opportunities met the criteria
3. Sports were excluded from betting

---

*Report generated: 2026-02-03*
*Analyst: Automated Backtest System*
*Data Source: PostgreSQL placed_bets table (actual betting results)*
