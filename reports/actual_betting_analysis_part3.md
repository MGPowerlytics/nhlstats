# Actual Betting Data Analysis - Part 3: Strategy Optimization & Recommendations

**Date**: February 5, 2026
**Data Source**: PostgreSQL `placed_bets` table
**Analysis Focus**: Strategy optimization based on actual betting results

---

## Strategy Analysis: Impact of Segment Exclusion

Based on 317 settled bets (won/lost) with $682.94 wagered and -$111.94 profit (-16.39% ROI):

### Strategy Performance Comparison

| Strategy | Bets | Wagered | Profit | ROI | Win Rate | Excluded Segments |
|----------|------|---------|--------|-----|----------|-------------------|
| **ALL_BETS** | 317 | $682.94 | -$111.94 | -16.39% | 58.68% | None |
| **EXCLUDE_NHL_MEDIUM** | 281 | $647.64 | -$91.64 | -14.15% | 63.70% | NHL-MEDIUM |
| **EXCLUDE_NCAAB_HIGH** | 295 | $640.02 | -$90.02 | -14.07% | 60.00% | NCAAB-HIGH |
| **EXCLUDE_TENNIS_HIGH** | 267 | $525.43 | -$69.43 | -13.21% | 58.80% | TENNIS-HIGH |
| **EXCLUDE_TENNIS_LOW** | 293 | $613.61 | -$94.61 | -15.42% | 58.02% | TENNIS-LOW |
| **EXCLUDE_WORST_3** | 209 | $447.21 | -$27.21 | **-6.08%** | 67.46% | NHL-MEDIUM, NCAAB-HIGH, TENNIS-HIGH |
| **HIGH_ONLY** | 124 | $295.30 | -$51.30 | -17.37% | 58.06% | All non-HIGH confidence |
| **PROFITABLE_ONLY** | 112 | $193.55 | **+$18.45** | **+9.53%** | 67.86% | NHL-MEDIUM, NCAAB-HIGH, TENNIS-HIGH, TENNIS-LOW, NCAAB-LOW, TENNIS-MEDIUM, NBA-LOW |

---

## Strategy Evaluation

### 1. **Baseline (ALL_BETS)**
- **ROI**: -16.39%
- **Bets**: 317
- **Assessment**: Unacceptable performance

### 2. **Single Segment Exclusions**
- **NHL MEDIUM exclusion**: Improves ROI to -14.15% (+2.24% improvement)
- **NCAAB HIGH exclusion**: Improves ROI to -14.07% (+2.32% improvement)
- **TENNIS HIGH exclusion**: Best single exclusion: -13.21% ROI (+3.18% improvement)

### 3. **Multi-Segment Exclusion (EXCLUDE_WORST_3)**
- **Excludes**: NHL-MEDIUM, NCAAB-HIGH, TENNIS-HIGH
- **ROI**: -6.08% (+10.31% improvement from baseline)
- **Bets**: 209 (66% of original volume)
- **Assessment**: Significant improvement while maintaining reasonable bet volume

### 4. **Aggressive Filtering (PROFITABLE_ONLY)**
- **Excludes**: All segments with negative ROI and ≥5 settled bets
- **ROI**: +9.53% (+25.92% improvement from baseline)
- **Bets**: 112 (35% of original volume)
- **Assessment**: Profitable but dramatically reduces bet count

### 5. **HIGH_ONLY Strategy**
- **ROI**: -17.37% (worse than baseline)
- **Assessment**: Counterproductive - HIGH confidence performs poorly in actual data

---

## Recommended Strategy: EXCLUDE_WORST_3

### Rationale:
1. **Balanced Approach**: Improves ROI significantly (-16.39% → -6.08%) while keeping 66% of bet volume
2. **Targets Worst Performers**: Removes the three most problematic segments:
   - NHL MEDIUM: -57.51% ROI
   - NCAAB HIGH: -51.07% ROI
   - TENNIS HIGH: -26.99% ROI
3. **Data-Driven**: Based on actual results with sufficient sample size (≥20 bets each)
4. **Conservative**: Doesn't eliminate entire sports or confidence levels

### Expected Impact:
- **ROI Improvement**: +10.31 percentage points
- **Bet Reduction**: 34% fewer bets (317 → 209)
- **Profit Improvement**: -$111.94 → -$27.21 (reduces losses by $84.73)

---

## Alternative Strategy: PROFITABLE_ONLY

### For Consideration If:
1. Primary goal is **absolute profitability** regardless of volume
2. Willing to accept **65% reduction in bet count**
3. Can tolerate **increased variance** from smaller sample

### Segments Included (Profitable with ≥5 settled bets):
1. NBA HIGH (+33.63% ROI)
2. NBA MEDIUM (+20.57% ROI)
3. NHL HIGH (+5.29% ROI)
4. NCAAB MEDIUM (+3.03% ROI)
5. UNKNOWN MEDIUM (+2.42% ROI)

---

## Implementation Recommendations

### 1. **Immediate Changes (High Priority)**
```python
# Update PortfolioOptimizer configuration
excluded_segments = [
    ("NHL", "MEDIUM"),
    ("NCAAB", "HIGH"),
    ("TENNIS", "HIGH")
]
```

### 2. **Files to Modify**
- `plugins/portfolio_optimizer.py`: Add segment filtering logic
- `plugins/portfolio_betting.py`: Pass excluded segments parameter
- `dags/multi_sport_betting_workflow.py`: Configure excluded segments

### 3. **Monitoring Plan**
- Track performance for 7 days after implementation
- Compare ROI before/after exclusion
- Monitor bet volume reduction impact

### 4. **Additional Considerations**
- **Review TENNIS LOW**: Consider adding to exclusions if performance doesn't improve
- **NBA LOW monitoring**: Currently -7.12% ROI - monitor for deterioration
- **Sport-specific thresholds**: Consider different confidence thresholds by sport

---

## Sport-Specific Recommendations

### NBA
- **Current**: +4.06% ROI overall
- **Recommendation**: Continue current approach
- **Focus**: HIGH confidence performs exceptionally well (+33.63% ROI)

### NCAAB
- **Current**: -15.97% ROI overall
- **Recommendation**: Exclude HIGH confidence, focus on MEDIUM confidence
- **Note**: MEDIUM confidence is profitable (+3.03% ROI)

### NHL
- **Current**: -22.78% ROI overall
- **Recommendation**: Exclude MEDIUM confidence, focus on HIGH confidence
- **Note**: HIGH confidence is profitable (+5.29% ROI)

### TENNIS
- **Current**: -21.37% ROI overall
- **Recommendation**: Exclude HIGH confidence, consider excluding LOW confidence
- **Challenge**: No profitable confidence level in tennis

---

## Risk Assessment

### Risks of EXCLUDE_WORST_3 Strategy:
1. **Overfitting**: Based on limited historical data (15 days)
2. **Regime Change**: Future performance may differ from past
3. **Reduced Diversification**: Fewer bets may increase variance

### Mitigations:
1. **Gradual Implementation**: Start with exclusions, monitor closely
2. **Regular Review**: Re-evaluate segments weekly
3. **Stop-Loss**: Implement maximum daily loss limits

---

## Follow-up Analysis Plan

### 1. **Weekly Performance Review**
```sql
-- Weekly segment performance
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
ORDER BY roi_pct ASC;
```

### 2. **Before/After Comparison** (7 days post-implementation)
- Compare ROI with previous 7-day period
- Monitor bet volume impact
- Assess any new problematic segments

### 3. **Edge Analysis**
- Analyze relationship between calculated edge and actual performance
- Review confidence assignment logic

---

## Conclusion

Based on actual betting data from January 18 - February 5, 2026:

1. **Current system is unprofitable**: -16.39% ROI on settled bets
2. **Key problem segments identified**: NHL MEDIUM, NCAAB HIGH, TENNIS HIGH
3. **Recommended action**: Implement EXCLUDE_WORST_3 strategy
4. **Expected improvement**: ROI from -16.39% to -6.08% (+10.31% improvement)
5. **Monitoring required**: Weekly performance review with option to adjust

**Immediate Next Step**: Implement segment exclusions and monitor for 7 days.

---
*Analysis based on actual PostgreSQL database queries*
*Generated: 2026-02-05*
