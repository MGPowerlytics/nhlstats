# Elo Predictiveness Analysis - Part 1: Current Performance Assessment

**Date**: February 5, 2026
**Data Source**: 317 settled bets from PostgreSQL database
**Analysis Focus**: Evaluate current Elo system predictiveness and identify improvement opportunities

---

## Executive Summary

The current Elo rating system shows **significant calibration issues** and **poor predictive performance**:

- **Overall Accuracy**: 59.31% (Elo > 0.5 threshold)
- **Brier Score**: 0.2493 (poor calibration)
- **Mean Edge**: -0.0169 (negative, indicating systematic bias)
- **Correlation (edge vs true edge)**: 0.0076 (essentially random)

**Critical Issues Identified**:
1. **Severe miscalibration**: Elo overestimates probabilities, especially for NHL
2. **Negative edge**: Elo probabilities are systematically lower than market probabilities
3. **Poor sport-specific performance**: NHL accuracy only 41.10%
4. **Confidence levels don't correlate with profitability**: HIGH confidence has worst ROI (-18.92%)

---

## Current Performance Metrics

### Overall Statistics
| Metric | Value | Assessment |
|--------|-------|------------|
| **Total Bets Analyzed** | 317 | Sufficient sample |
| **Elo Accuracy (>0.5)** | 59.31% | Below target (60%+) |
| **Brier Score** | 0.2493 | Poor (0.25 = random) |
| **Mean Elo Probability** | 0.6599 | Slightly overconfident |
| **Mean Market Probability** | 0.6768 | Market more confident |
| **Mean Edge (Elo - Market)** | -0.0169 | **Negative - systematic issue** |

### Calibration Analysis
| Probability Bin | Mean Elo | Actual Win Rate | Calibration Error | Bets |
|----------------|----------|-----------------|-------------------|------|
| 0.50-0.55 | 0.524 | 0.550 | +0.026 | 20 |
| 0.55-0.60 | 0.577 | 0.600 | +0.023 | 25 |
| 0.60-0.65 | 0.640 | 0.563 | **-0.077** | 174 |
| 0.65-0.70 | 0.678 | 0.615 | -0.062 | 39 |
| 0.70-0.75 | 0.720 | 0.667 | -0.053 | 21 |
| 0.75-0.80 | 0.777 | 0.500 | **-0.277** | 16 |
| 0.80-0.85 | 0.822 | 0.750 | -0.072 | 8 |
| 0.85-0.90 | 0.874 | 0.900 | +0.026 | 10 |
| 0.90-0.95 | 0.919 | 0.250 | **-0.669** | 4 |

**Key Calibration Issues**:
1. **Severe overestimation** in 0.60-0.80 range
2. **Extreme miscalibration** at high probabilities (0.75-0.80: -0.277 error)
3. **Inconsistent** - both over and underestimation in different ranges

---

## Sport-Specific Performance

### Performance by Sport
| Sport | Bets | Elo Mean | Market Mean | Bias | Actual Win Rate | Accuracy | Calibration Error |
|-------|------|----------|-------------|------|-----------------|----------|-------------------|
| **TENNIS** | 116 | 0.657 | 0.704 | -0.047 | 0.595 | 61.21% | -6.21% |
| **NCAAB** | 89 | 0.681 | 0.673 | +0.008 | 0.663 | 66.29% | -1.79% |
| **NHL** | 73 | 0.641 | 0.605 | +0.036 | 0.411 | 41.10% | **-23.03%** |
| **NBA** | 32 | 0.645 | 0.749 | -0.104 | 0.750 | 75.00% | +10.48% |
| **UNKNOWN** | 7 | 0.660 | 0.643 | +0.017 | 0.571 | 57.14% | -8.86% |

**Sport-Specific Insights**:
1. **NHL**: Catastrophic performance - 41.10% accuracy, -23.03% calibration error
2. **NBA**: Good accuracy (75.00%) but Elo underestimates (+10.48% calibration error)
3. **TENNIS**: Moderate accuracy (61.21%), Elo underestimates (-6.21% error)
4. **NCAAB**: Best balanced performance (66.29% accuracy, -1.79% error)

---

## Edge Analysis

### Edge Distribution
| Statistic | Value |
|-----------|-------|
| Mean Edge | -0.0169 |
| Median Edge | -0.0024 |
| Std Dev Edge | 0.1292 |
| Min Edge | -0.4294 |
| Max Edge | +0.5477 |

### Edge vs Performance
| Edge Bin | Bets | Mean Edge | Mean True Edge | ROI |
|----------|------|-----------|----------------|-----|
| (-0.3, -0.25] | 6 | -0.278 | -0.178 | -19.14% |
| (-0.25, -0.2] | 19 | -0.229 | -0.181 | -23.71% |
| (-0.2, -0.15] | 11 | -0.173 | +0.007 | -8.31% |
| (-0.15, -0.1] | 21 | -0.125 | -0.098 | -18.78% |
| (-0.1, -0.05] | 21 | -0.075 | +0.087 | +11.82% |
| (-0.05, 0.0] | 52 | -0.021 | -0.065 | -20.95% |
| (0.0, 0.05] | 37 | +0.023 | -0.104 | -18.06% |
| (0.05, 0.1] | 31 | +0.070 | -0.154 | -20.59% |
| (0.1, 0.15] | 14 | +0.133 | -0.138 | -6.54% |
| (0.15, 0.2] | 2 | +0.186 | -0.533 | -100.00% |
| (0.2, 0.25] | 2 | +0.215 | +0.340 | +51.52% |

**Critical Finding**: **Edge calculation is essentially random** (correlation = 0.0076)

---

## Confidence Level Analysis

### Performance by Confidence
| Confidence | Bets | Mean Elo | Mean Edge | Win Rate | ROI |
|------------|------|----------|-----------|----------|-----|
| **HIGH** | 118 | 0.671 | +0.006 | 58.47% | -18.92% |
| **MEDIUM** | 144 | 0.655 | +0.025 | 52.78% | -12.70% |
| **LOW** | 55 | 0.649 | -0.177 | 74.55% | -18.22% |

**Confidence Issues**:
1. **HIGH confidence has worst ROI** (-18.92%)
2. **LOW confidence has highest win rate** (74.55%) but negative ROI
3. **Confidence assignment doesn't correlate with profitability**

---

## Key Problems Identified

### 1. **Systematic Negative Edge**
- Elo probabilities are systematically lower than market probabilities
- Mean edge: -0.0169 (negative)
- This suggests either:
  - Elo is underestimating true probabilities
  - Market is overestimating probabilities
  - Both

### 2. **Severe Calibration Issues**
- Elo overestimates in 0.60-0.80 probability range
- Extreme errors at high probabilities (0.75-0.80: -0.277 error)
- Poor Brier score (0.2493 ≈ random)

### 3. **Sport-Specific Problems**
- **NHL**: Catastrophic - 41.10% accuracy, -23.03% calibration error
- **TENNIS**: Elo systematically underestimates (-0.047 bias)
- **NBA**: Elo underestimates successful teams (-0.104 bias)

### 4. **Edge Calculation Useless**
- Correlation between predicted edge and true edge: 0.0076 (random)
- Positive edge bets perform worse than negative edge bets
- Edge magnitude doesn't predict ROI

### 5. **Confidence System Broken**
- HIGH confidence has worst performance
- Confidence levels don't align with actual predictability

---

## Root Cause Hypotheses

### Hypothesis 1: **Parameter Mismatch**
- Current parameters (K=20, HA=100) may be wrong for some sports
- NHL previously optimized to K=10, HA=50 - are we using correct values?

### Hypothesis 2: **Data Quality Issues**
- Elo ratings may not be properly initialized or updated
- Missing historical data affecting rating accuracy
- Incorrect game result processing

### Hypothesis 3: **Market Efficiency**
- Kalshi markets may be more efficient than expected
- Elo can't beat market prices consistently
- Need more sophisticated models

### Hypothesis 4: **Implementation Bugs**
- Edge calculation may have bugs
- Confidence assignment logic flawed
- Probability scaling issues

---

## Next Steps for Part 2

In Part 2, we will investigate:
1. **Parameter optimization analysis** - Check if current parameters are optimal
2. **Data quality audit** - Verify Elo rating initialization and updates
3. **Market efficiency test** - Compare Elo vs market predictive power
4. **Implementation review** - Check for bugs in edge/confidence calculations

---
*Analysis based on actual betting data from PostgreSQL*
*Generated: 2026-02-05*
