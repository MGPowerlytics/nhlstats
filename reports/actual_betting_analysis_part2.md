# Actual Betting Data Analysis - Part 2: Sport & Confidence Performance

**Date**: February 5, 2026
**Data Source**: PostgreSQL `placed_bets` table
**Analysis Focus**: Performance breakdown by sport and confidence level

---

## Performance by Sport (All Confidence Levels)

| Sport | Total Bets | Wins | Losses | Open | Wagered | Profit | ROI | Win Rate |
|-------|------------|------|--------|------|---------|--------|-----|----------|
| TENNIS | 157 | 78 | 75 | 2 | $386.06 | -$82.52 | -21.37% | 50.98% |
| NCAAB | 104 | 67 | 36 | 1 | $202.91 | -$32.41 | -15.97% | 65.05% |
| NHL | 73 | 30 | 43 | 0 | $78.99 | -$17.99 | -22.78% | 41.10% |
| NBA | 56 | 32 | 16 | 8 | $165.27 | $6.71 | +4.06% | 66.67% |
| UNKNOWN | 12 | 4 | 3 | 5 | $42.27 | $1.76 | +4.16% | 57.14% |
| WNCAAB | 5 | 2 | 3 | 0 | $2.52 | -$0.52 | -20.63% | 40.00% |

**Sport-Level Insights**:
1. **NBA is the only profitable major sport** (+4.06% ROI)
2. **TENNIS has the largest dollar loss** (-$82.52) and worst ROI (-21.37%)
3. **NHL has the lowest win rate** (41.10%) among major sports
4. **NCAAB has good win rate** (65.05%) but negative ROI (-15.97%) due to bet sizing

---

## Performance by Confidence Level (All Sports)

| Confidence | Total Bets | Wins | Losses | Open | Wagered | Profit | ROI | Win Rate |
|------------|------------|------|--------|------|---------|--------|-----|----------|
| HIGH | 123 | 69 | 49 | 4 | $292.74 | -$51.82 | -17.70% | 58.47% |
| MEDIUM | 153 | 76 | 68 | 9 | $296.74 | -$33.16 | -11.17% | 52.78% |
| LOW | 57 | 41 | 14 | 2 | $157.01 | -$26.96 | -17.17% | 74.55% |
| SUPER_HIGH | 1 | 0 | 0 | 0 | $0.00 | $0.00 | N/A | N/A |

**Confidence-Level Insights**:
1. **LOW confidence has highest win rate** (74.55%) but negative ROI (-17.17%)
2. **HIGH confidence performs worse than MEDIUM** (-17.70% vs -11.17% ROI)
3. **All confidence levels are unprofitable** in aggregate
4. **Win rate doesn't correlate with profitability** (LOW has highest win rate but negative ROI)

---

## Detailed Sport × Confidence Performance

### NBA Performance by Confidence
| Confidence | Bets | Wins | Losses | Open | Wagered | Profit | ROI | Win Rate |
|------------|------|------|--------|------|---------|--------|-----|----------|
| HIGH | 10 | 7 | 1 | 2 | $37.24 | $9.06 | +24.33% | 87.50% |
| MEDIUM | 13 | 4 | 4 | 5 | $30.66 | $2.73 | +8.90% | 50.00% |
| LOW | 17 | 13 | 3 | 1 | $58.97 | -$3.68 | -6.24% | 81.25% |
| None | 16 | 8 | 8 | 0 | $38.40 | -$1.40 | -3.65% | 50.00% |

**NBA Insights**: HIGH confidence performs exceptionally well (+24.33% ROI).

### NCAAB Performance by Confidence
| Confidence | Bets | Wins | Losses | Open | Wagered | Profit | ROI | Win Rate |
|------------|------|------|--------|------|---------|--------|-----|----------|
| HIGH | 22 | 9 | 13 | 0 | $42.92 | -$21.92 | -51.07% | 40.91% |
| MEDIUM | 53 | 38 | 14 | 1 | $92.91 | $2.59 | +2.79% | 73.08% |
| LOW | 15 | 12 | 3 | 0 | $26.95 | -$5.95 | -22.08% | 80.00% |
| None | 14 | 8 | 6 | 0 | $40.13 | -$7.13 | -17.77% | 57.14% |

**NCAAB Insights**: HIGH confidence is catastrophic (-51.07% ROI), while MEDIUM performs well (+2.79% ROI).

### NHL Performance by Confidence
| Confidence | Bets | Wins | Losses | Open | Wagered | Profit | ROI | Win Rate |
|------------|------|------|--------|------|---------|--------|-----|----------|
| HIGH | 37 | 23 | 14 | 0 | $43.69 | $2.31 | +5.29% | 62.16% |
| MEDIUM | 36 | 7 | 29 | 0 | $35.30 | -$20.30 | -57.51% | 19.44% |
| LOW | 0 | 0 | 0 | 0 | $0.00 | $0.00 | N/A | N/A |
| None | 0 | 0 | 0 | 0 | $0.00 | $0.00 | N/A | N/A |

**NHL Insights**: Extreme divergence - HIGH is profitable (+5.29%), MEDIUM is disastrous (-57.51%).

### TENNIS Performance by Confidence
| Confidence | Bets | Wins | Losses | Open | Wagered | Profit | ROI | Win Rate |
|------------|------|------|--------|------|---------|--------|-----|----------|
| HIGH | 52 | 29 | 21 | 1 | $163.01 | -$42.51 | -26.08% | 58.00% |
| MEDIUM | 43 | 24 | 18 | 1 | $108.74 | -$18.70 | -17.20% | 57.14% |
| LOW | 24 | 16 | 8 | 0 | $69.33 | -$17.33 | -25.00% | 66.67% |
| SUPER_HIGH | 1 | 0 | 0 | 0 | $0.00 | $0.00 | N/A | N/A |
| None | 37 | 9 | 28 | 0 | $44.98 | -$3.98 | -8.85% | 24.32% |

**TENNIS Insights**: All confidence levels are unprofitable, with HIGH being worst (-26.08% ROI).

---

## Worst Performing Segments (Minimum 5 Settled Bets)

| Sport | Confidence | Bets | Wins | Losses | Wagered | Profit | ROI | Win Rate |
|-------|------------|------|------|--------|---------|--------|-----|----------|
| NHL | MEDIUM | 36 | 7 | 29 | $35.30 | -$20.30 | **-57.51%** | 19.44% |
| NCAAB | HIGH | 22 | 9 | 13 | $42.92 | -$21.92 | **-51.07%** | 40.91% |
| TENNIS | HIGH | 50 | 29 | 21 | $157.51 | -$42.51 | **-26.99%** | 58.00% |
| TENNIS | LOW | 24 | 16 | 8 | $69.33 | -$17.33 | **-25.00%** | 66.67% |
| NCAAB | LOW | 15 | 12 | 3 | $26.95 | -$5.95 | **-22.08%** | 80.00% |
| TENNIS | MEDIUM | 42 | 24 | 18 | $105.70 | -$18.70 | **-17.69%** | 57.14% |
| NBA | LOW | 16 | 13 | 3 | $51.68 | -$3.68 | **-7.12%** | 81.25% |

**Key Problematic Segments**:
1. **NHL MEDIUM**: -57.51% ROI (worst overall)
2. **NCAAB HIGH**: -51.07% ROI
3. **TENNIS HIGH**: -26.99% ROI (largest dollar loss: -$42.51)

---

## Best Performing Segments (Profitable, Minimum 5 Settled Bets)

| Sport | Confidence | Bets | Wins | Losses | Wagered | Profit | ROI | Win Rate |
|-------|------------|------|------|--------|---------|--------|-----|----------|
| NBA | HIGH | 8 | 7 | 1 | $26.94 | $9.06 | **+33.63%** | 87.50% |
| NBA | MEDIUM | 8 | 4 | 4 | $13.27 | $2.73 | **+20.57%** | 50.00% |
| NHL | HIGH | 37 | 23 | 14 | $43.69 | $2.31 | **+5.29%** | 62.16% |
| NCAAB | MEDIUM | 52 | 38 | 14 | $85.41 | $2.59 | **+3.03%** | 73.08% |
| UNKNOWN | MEDIUM | 6 | 3 | 3 | $21.48 | $0.52 | **+2.42%** | 50.00% |

**Key Profitable Segments**:
1. **NBA HIGH**: +33.63% ROI (best overall)
2. **NBA MEDIUM**: +20.57% ROI
3. **NHL HIGH**: +5.29% ROI

---

## Critical Findings vs Previous Simulated Analysis

### Differences from February 3 Simulated Report:
1. **CBA**: Simulated report identified CBA as problematic, but **no CBA bets exist** in actual database
2. **WNCAAB LOW**: Simulated report flagged this segment, but **no WNCAAB LOW bets exist**
3. **TENNIS LOW**: Both reports identify as problematic (-25.00% actual vs -39.5% simulated)
4. **Confidence Performance**: Simulated showed HIGH > MEDIUM > LOW, but actual shows MEDIUM > HIGH > LOW for ROI

### New Problematic Segments Identified:
1. **NHL MEDIUM**: -57.51% ROI (not identified in simulated report)
2. **NCAAB HIGH**: -51.07% ROI (not identified in simulated report)
3. **TENNIS HIGH**: -26.99% ROI (simulated showed +2.0% ROI)

---

## Next Steps

In Part 3, we will analyze:
1. Strategy optimization based on actual data
2. Impact of excluding problematic segments
3. Recommendations for betting system adjustments

---
*Analysis based on actual PostgreSQL database queries*
*Generated: 2026-02-05*
