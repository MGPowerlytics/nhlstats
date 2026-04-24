# Actual Betting Data Analysis - Part 1: Overview

**Date**: February 5, 2026
**Analysis Period**: January 18, 2026 - February 5, 2026 (15 days)
**Data Source**: PostgreSQL `placed_bets` table (actual betting results)
**Purpose**: Analyze actual betting performance to identify profitable and unprofitable segments

---

## Executive Summary

Based on **407 actual bets** placed between January 18 and February 5, 2026:

- **Total Wagered**: $878.02
- **Total Profit**: -$124.97 (loss)
- **Overall ROI**: -14.23%
- **Win Rate**: 54.76%

**Key Finding**: The actual betting results show significantly different patterns than the simulated analysis from February 3, 2026.

---

## Data Overview

### Bet Count by Status
- **Total Bets**: 407
- **Won**: 213 (52.3%)
- **Lost**: 176 (43.2%)
- **Open**: 16 (3.9%)
- **Settled Bets**: 389 (95.6%)

### Date Range
- **Earliest Bet**: January 18, 2026
- **Latest Bet**: February 5, 2026
- **Unique Betting Days**: 15

### Sports with Actual Bets
The database contains bets for the following sports (in order of bet volume):

1. **TENNIS**: 157 bets (38.6% of total)
2. **NCAAB**: 104 bets (25.6% of total)
3. **NHL**: 73 bets (17.9% of total)
4. **NBA**: 56 bets (13.8% of total)
5. **UNKNOWN**: 12 bets (2.9% of total)
6. **WNCAAB**: 5 bets (1.2% of total)

**Note**: No CBA (Chinese Basketball) bets were found in the actual database, contrary to the simulated analysis.

---

## Daily Performance Summary

| Date | Bets | Wins | Losses | Open | Wagered | Profit | ROI |
|------|------|------|--------|------|---------|--------|-----|
| 2026-01-18 | 8 | 5 | 3 | 0 | $22.61 | -$2.61 | -11.54% |
| 2026-01-19 | 51 | 24 | 27 | 0 | $97.90 | -$0.90 | -0.92% |
| 2026-01-20 | 6 | 2 | 4 | 0 | $19.25 | -$5.25 | -27.27% |
| 2026-01-21 | 20 | 2 | 18 | 0 | $11.00 | -$6.00 | -54.55% |
| 2026-01-22 | 8 | 2 | 2 | 2 | $18.73 | -$2.73 | -14.58% |
| 2026-01-27 | 2 | 0 | 2 | 0 | $4.24 | -$4.24 | -100.00% |
| 2026-01-28 | 3 | 1 | 2 | 0 | $6.01 | -$3.01 | -50.08% |
| 2026-01-29 | 100 | 59 | 41 | 0 | $65.27 | -$2.27 | -3.48% |
| 2026-01-30 | 28 | 17 | 11 | 0 | $18.45 | -$1.45 | -7.86% |
| 2026-01-31 | 65 | 36 | 29 | 0 | $202.16 | -$48.16 | -23.82% |
| 2026-02-01 | 54 | 38 | 16 | 0 | $152.82 | -$3.82 | -2.50% |
| 2026-02-02 | 12 | 9 | 3 | 0 | $39.78 | $6.22 | +15.64% |
| 2026-02-03 | 16 | 7 | 9 | 0 | $84.50 | -$29.50 | -34.91% |
| 2026-02-04 | 19 | 9 | 5 | 5 | $54.10 | -$3.83 | -7.08% |
| 2026-02-05 | 15 | 2 | 4 | 9 | $81.20 | -$17.42 | -21.45% |

**Daily Insights**:
- Only **1 profitable day** out of 15 (February 2: +15.64% ROI)
- Worst day: January 27 (-100% ROI, 0-2 record)
- Largest loss day: February 3 (-$29.50, -34.91% ROI)
- Highest volume day: January 29 (100 bets)

---

## Comparison with Previous Simulated Analysis

The February 3 simulated analysis was based on **865 betting recommendations** with these key differences:

| Metric | Simulated (Feb 3) | Actual (This Analysis) |
|--------|-------------------|------------------------|
| **Total Bets** | 865 | 407 |
| **Time Period** | Jan 29 - Feb 3 (5 days) | Jan 18 - Feb 5 (15 days) |
| **Overall ROI** | -13.6% | -14.23% |
| **Sports Included** | CBA, NBA, NCAAB, NHL, TENNIS, WNCAAB | NBA, NCAAB, NHL, TENNIS, WNCAAB, UNKNOWN |
| **CBA Bets** | 11 (1.3%) | 0 |
| **Methodology** | Simulated results | Actual betting results |

**Critical Difference**: The simulated analysis identified CBA as problematic, but **no CBA bets exist in the actual database**.

---

## Next Steps

In Part 2, we will analyze:
1. Performance by sport and confidence level
2. Identification of actual problematic segments
3. Strategy optimization based on real data

---
*Analysis based on actual PostgreSQL database queries*
*Generated: 2026-02-05*
