# Betting Threshold Optimization Report
Generated: 2026-01-19 19:54:06

## Executive Summary

This report documents the selection of optimal betting thresholds for each sport based on:
1. **Lift/Gain Analysis** - Validating that Elo predictions are calibrated
2. **Historical Backtesting** - Testing various threshold combinations
3. **Risk-Adjusted Returns** - Optimizing for Sharpe ratio

## Methodology

### Approach
- Analyzed 0 total games across 0 sports
- Generated out-of-sample Elo predictions for each game
- Calculated lift/gain by probability decile
- Backtested combinations of probability thresholds (52%-78%) and edge thresholds (2%-11%)
- Optimized for Sharpe ratio (risk-adjusted returns)

### Key Findings: High/Low Decile Predictiveness

**Two-outcome sports (NBA, NHL, MLB, NFL, NCAAB, WNCAAB) show strong predictiveness in extreme deciles:**


## Implementation Recommendations

### Conservative Thresholds (Risk-Averse)
Use thresholds on the higher end to focus on only the strongest opportunities:
- Increases win rate
- Decreases bet volume
- Lower variance, more stable returns

### Aggressive Thresholds (Volume-Seeking)
Use thresholds on the lower end to capture more opportunities:
- More bets for diversification
- Lower win rate but more edge capture
- Higher variance

### Current Recommendation: **Sharpe-Optimized Thresholds**
The thresholds above represent the optimal balance between:
- Risk (variance of returns)
- Reward (expected profit)
- Volume (number of betting opportunities)

## Closing Line Value (CLV) Tracking

CLV tracking has been added to the betting system:
- Records the line we bet at
- Compares to closing line before game starts
- Validates if our model beats the market

**If CLV is consistently positive, our model has true edge.**
**If CLV is negative, we need to improve our timing or model.**

## Next Steps

1. **Monitor CLV** - Track if we're beating closing lines
2. **Validate Thresholds** - Confirm these work in live betting
3. **Adjust Based on Results** - Update thresholds quarterly based on actual performance
4. **Consider Sport-Specific Factors** - Add injury, rest, travel features to improve edge

---

*This analysis was generated automatically. Review and validate before deploying to production betting.*
