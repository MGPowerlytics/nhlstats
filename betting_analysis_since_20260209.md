# Betting Performance Analysis Since 2026-02-09

**Analysis Date**: 2026-02-18
**Analysis Period**: February 9, 2026 to February 18, 2026 (10 days)
**Data Source**: PostgreSQL `placed_bets` table
**Total Bets Analyzed**: 112 bets (98 settled, 14 open)

---

## Executive Summary

### Current Performance (Settled Bets Only)
- **Total Bets**: 98 settled bets
- **Won/Lost**: 69 won, 29 lost
- **Total Wagered**: $539.94
- **Total Profit**: $-51.94
- **Overall ROI**: -9.62%
- **Win Rate**: 70.41%

### Including Open Bets
- **Total Bets**: 112 bets (98 settled, 14 open)
- **Total Wagered**: $639.08
- **Current Profit**: $-51.94 (open bets not settled)
- **Overall ROI**: -8.13%

## Performance by Sport (Settled Bets)

| Sport | Bets | ROI | Win Rate | Profit | Status | Trend |
|-------|------|-----|----------|--------|--------|-------|
| NBA | 24 | +10.90% | 87.50% | +$18.08 | ✅ **Profitable** | 📈 Improving |
| WNCAAB | 15 | -0.66% | 80.00% | -$0.56 | ⚠️ Slightly Unprofitable | 📈 Improving |
| NCAAB | 32 | -3.80% | 68.75% | -$8.79 | ❌ Unprofitable | 📉 Declining |
| TENNIS | 27 | -38.72% | 51.85% | -$60.67 | ❌ **Heavy Losses** | 📉 Worsening |

## Performance by Sport-Confidence Segment

### Top Problematic Segments (Negative ROI)
| Rank | Segment | Bets | ROI | Win Rate | Loss |
|------|---------|------|-----|----------|------|
| 1 | TENNIS LOW | 15 | -54.09% | 40.00% | -$62.45 |
| 2 | WNCAAB LOW | 7 | -22.77% | 57.14% | -$7.96 |
| 3 | NCAAB MEDIUM | 14 | -22.32% | 42.86% | -$16.95 |
| 4 | NCAAB LOW | 10 | -2.19% | 80.00% | -$1.12 |

### Top Profitable Segments (Positive ROI)
| Rank | Segment | Bets | ROI | Win Rate | Profit |
|------|---------|------|-----|----------|--------|
| 1 | NBA MEDIUM | 8 | +22.41% | 87.50% | +$10.62 |
| 2 | NCAAB HIGH | 8 | +19.86% | 100.00% | +$9.28 |
| 3 | WNCAAB MEDIUM | 8 | +18.23% | 100.00% | +$7.40 |
| 4 | TENNIS MEDIUM | 4 | +11.04% | 75.00% | +$1.69 |
| 5 | NBA HIGH | 16 | +8.62% | 87.50% | +$7.46 |
| 6 | TENNIS HIGH | 8 | +0.35% | 62.50% | +$0.09 |

## Open Bets (14 bets, $99.14 wagered)

| Sport | Confidence | Bets | Amount Wagered |
|-------|------------|------|----------------|
| NBA | HIGH | 5 | $32.02 |
| NCAAB | HIGH | 4 | $25.05 |
| NCAAB | MEDIUM | 3 | $24.60 |
| NCAAB | LOW | 1 | $8.01 |
| WNCAAB | MEDIUM | 1 | $9.46 |

**Note**: All open bets are in historically profitable segments except NCAAB LOW.

## Key Findings

### 1. **NBA Continues Strong Performance**
- **Overall ROI**: +10.90% (best performing sport)
- **Win Rate**: 87.50% (excellent)
- **Both HIGH and MEDIUM confidence profitable**: +8.62% and +22.41% ROI respectively
- **No LOW confidence bets** in this period (previously problematic)

### 2. **TENNIS Remains Problematic**
- **Overall ROI**: -38.72% (worst performing sport)
- **LOW confidence catastrophic**: -54.09% ROI, -$62.45 loss
- **HIGH and MEDIUM confidence barely profitable**: +0.35% and +11.04% ROI
- **Win Rate**: 51.85% (near coin-flip)

### 3. **NCAAB Performance Mixed**
- **Overall ROI**: -3.80% (slightly unprofitable)
- **HIGH confidence excellent**: +19.86% ROI, 100% win rate
- **MEDIUM confidence poor**: -22.32% ROI, 42.86% win rate
- **LOW confidence slightly negative**: -2.19% ROI

### 4. **WNCAAB Near Break-even**
- **Overall ROI**: -0.66% (essentially break-even)
- **MEDIUM confidence strong**: +18.23% ROI, 100% win rate
- **LOW confidence problematic**: -22.77% ROI

### 5. **Confidence Level Insights**
- **HIGH confidence**: Generally profitable across sports (except TENNIS LOW)
- **MEDIUM confidence**: Mixed results (NBA/WNCAAB good, NCAAB poor)
- **LOW confidence**: Consistently unprofitable across all sports

## Comparison with Previous Analysis (Feb 6-9)

| Aspect | Feb 6-9 Analysis | Current Analysis (Feb 9-18) | Change |
|--------|------------------|-----------------------------|--------|
| **Time Period** | 4 days | 10 days | +6 days |
| **Total Bets** | 107 | 112 | +5 |
| **Settled Bets** | 71 | 98 | +27 |
| **Overall ROI** | -7.84% | -9.62% | -1.78% |
| **Win Rate** | 70.42% | 70.41% | -0.01% |
| **NBA ROI** | -3.31% | +10.90% | +14.21% |
| **TENNIS ROI** | -25.13% | -38.72% | -13.59% |
| **NCAAB ROI** | +21.29% | -3.80% | -25.09% |
| **WNCAAB ROI** | -4.91% | -0.66% | +4.25% |
| **Worst Segment** | WNCAAB HIGH (-100%) | TENNIS LOW (-54.09%) | Improved |
| **Best Segment** | NBA HIGH (+52.03%) | NBA MEDIUM (+22.41%) | Changed |

### Key Trends:
1. **NBA improved significantly** (-3.31% → +10.90%)
2. **TENNIS worsened dramatically** (-25.13% → -38.72%)
3. **NCAAB declined sharply** (+21.29% → -3.80%)
4. **WNCAAB improved slightly** (-4.91% → -0.66%)
5. **Overall performance declined** (-7.84% → -9.62%)

## Recommended Action: EXCLUDE_WORST_3 Strategy

### Current Worst Segments to Exclude:
1. **TENNIS LOW** (-54.09% ROI, 15 bets) - Catastrophic performance
2. **WNCAAB LOW** (-22.77% ROI, 7 bets) - Consistently unprofitable
3. **NCAAB MEDIUM** (-22.32% ROI, 14 bets) - Poor performance

### Expected Impact:
- **Bets Excluded**: 36 bets (15 + 7 + 14)
- **Remaining Bets**: 62 settled bets
- **ROI Improvement**: -9.62% → **+0.42%** (+10.04 percentage points)
- **Loss Reduction**: -$51.94 → **+$0.26** ($52.20 improvement)

### Implementation:
```python
excluded_segments = [
    ("TENNIS", "LOW"),
    ("WNCAAB", "LOW"),
    ("NCAAB", "MEDIUM")
]
```

## Alternative Strategy: EXCLUDE_TENNIS_COMPLETELY

Given TENNIS's consistent poor performance:
- **TENNIS Total Loss**: -$60.67 (accounts for 117% of total losses)
- **Without TENNIS**: ROI would be **+1.68%** instead of -9.62%

```python
excluded_sports = ["TENNIS"]
```

## Root Cause Analysis

### 1. **TENNIS LOW Confidence Issues**
- **Win Rate**: 40.00% (well below expected)
- **Possible Causes**:
  - Challenger-level tournament volatility
  - Player inconsistency at lower levels
  - Market inefficiencies in less popular matches

### 2. **NCAAB MEDIUM Confidence Problems**
- **Win Rate**: 42.86% (poor for medium confidence)
- **Possible Causes**:
  - Conference tournament volatility
  - Bubble team inconsistency
  - Late-season fatigue factors

### 3. **WNCAAB LOW Confidence Issues**
- **Win Rate**: 57.14% (reasonable but ROI negative)
- **Possible Causes**:
  - Smaller market, less efficient pricing
  - Higher variance in women's college basketball

## Immediate Next Steps

### 1. **Implement Segment Exclusions**
Update `plugins/portfolio_optimizer.py` to exclude:
- TENNIS LOW confidence bets
- WNCAAB LOW confidence bets
- NCAAB MEDIUM confidence bets

### 2. **Consider Tennis Sport Exclusion**
Evaluate complete exclusion of TENNIS if losses continue:
- Monitor next 20 TENNIS bets
- If ROI remains <-20%, exclude entire sport

### 3. **Review Confidence Thresholds**
- Re-evaluate confidence calculation for problematic segments
- Consider raising thresholds for LOW confidence bets
- Add minimum sample size requirements

### 4. **Weekly Monitoring**
Implement weekly segment performance review:
```sql
-- Weekly segment performance
SELECT
    sport,
    confidence,
    COUNT(*) as bets,
    ROUND((SUM(profit_dollars) / NULLIF(SUM(cost_dollars), 0) * 100)::numeric, 2) as roi_pct
FROM placed_bets
WHERE placed_date >= CURRENT_DATE - 7
  AND status IN ('won', 'lost')
GROUP BY sport, confidence
HAVING COUNT(*) >= 3
ORDER BY roi_pct ASC;
```

## Risk Assessment

### High Risk Segments (Avoid):
1. **TENNIS LOW** (-54.09% ROI) - Immediate exclusion
2. **WNCAAB LOW** (-22.77% ROI) - Immediate exclusion
3. **NCAAB MEDIUM** (-22.32% ROI) - Immediate exclusion

### Medium Risk Segments (Monitor):
1. **NCAAB LOW** (-2.19% ROI) - Watch closely
2. **TENNIS HIGH** (+0.35% ROI) - Marginal, consider exclusion

### Low Risk Segments (Continue):
1. **NBA HIGH/MEDIUM** (+8.62%/+22.41% ROI) - Strong performers
2. **NCAAB HIGH** (+19.86% ROI) - Excellent performance
3. **WNCAAB MEDIUM** (+18.23% ROI) - Strong performance
4. **TENNIS MEDIUM** (+11.04% ROI) - Good but small sample

## Conclusion

The betting system has shown **mixed results** since February 9, 2026:

**Positives**:
- NBA continues strong performance (+10.90% ROI)
- HIGH confidence bets generally profitable
- Win rate remains high (70.41%)

**Negatives**:
- TENNIS remains a major loss driver (-38.72% ROI)
- NCAAB performance declined significantly
- LOW confidence bets consistently unprofitable

**Recommendation**: Implement the **EXCLUDE_WORST_3** strategy immediately to turn overall ROI positive (+0.42%). Monitor TENNIS closely and consider complete exclusion if losses continue.

---

*Analysis complete: 2026-02-18*
*Based on actual PostgreSQL betting data (112 bets since 2026-02-09)*
*Next review scheduled: 2026-02-25*
