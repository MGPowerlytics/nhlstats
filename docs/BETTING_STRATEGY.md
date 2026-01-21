# Multi-Sport Betting Strategy Overview

**Date:** January 20, 2026
**System Architecture:** PostgreSQL-backed, Airflow-automated, Kelly-optimized portfolio betting.

---

## 1. Core Methodology: Elo-Based Value Betting

The fundamental strategy across all sports is **Value Betting**. We identify discrepancies between our internal **Elo-based probabilities** and the **market probabilities** offered by Kalshi.

*   **Elo Probability**: Calculated using historical game data (55,000+ games) and updated daily.
*   **Market Probability**: Implied from Kalshi's `yes_ask` or `no_ask` prices.
*   **Edge**: `Elo Probability - Market Probability`.
*   **Threshold**: A minimum edge (typically 5%) and a minimum Elo confidence are required to place a bet.

---

## 2. General Portfolio Strategy

Instead of treating each sport in isolation, the system uses a **Unified Portfolio Manager** to allocate capital efficiently across all active markets.

### Kelly Criterion Allocation
- **Fractional Kelly (25%)**: We use a "Quarter Kelly" approach to maximize long-term growth while significantly reducing the variance and risk of ruin.
- **Dynamic Sizing**: Bet sizes scale with our calculated edge and current bankroll.
- **Constraints**:
    - **Min Bet**: $2.00 (to avoid noise)
    - **Max Bet**: $50.00 (to prevent overexposure)
    - **Max Daily Risk**: 25% of total bankroll.
    - **Max Position**: 5% of bankroll per single match.

### Match-Level Locking
- **Live API Checking**: Before placing a bet, the system queries the Kalshi API for current open positions.
- **Event Conflict Prevention**: We never bet on both sides of the same match (e.g., Alcaraz and his opponent). If we have an open position on *any* ticker associated with a match, further betting on that match is locked.

---

## 3. Sport-Specific Strategies

### 🏀 NBA & College Basketball (NCAAB/WNCAAB)
- **Strategy**: Focus on Extreme Confidence.
- **Thresholds**:
    - **NBA**: 73% Elo Prob
    - **NCAAB/WNCAAB**: 72% Elo Prob
- **Rationale**: Basketball shows the strongest "lift" in the top 20% of predictions (1.39x). We ignore middle-of-the-road games where the market is most efficient.

### 🎾 Tennis, 🏒 NHL & ⚽ Ligue 1
- **Strategy**: **Sharp Odds Confirmation**.
- **Execution**: We only bet on Kalshi if our Elo edge is confirmed by "Sharp" bookmakers (Pinnacle/BetMGM).
- **Rationale**: These markets are highly efficient. Our analysis showed massive ROI potential (+26% for NHL, high potential for Ligue 1) when filtering for "Market Laggards"—cases where Kalshi hasn't moved their price yet despite a consensus shift in the professional betting world.
- **Status**: **Automated Betting Active**.

### 🏀 Basketball, ⚾ MLB, 🏈 NFL
- **Strategy**: **Standard Elo Value Betting**.
- **Methodology**: These sports currently rely on our optimized Elo models and optimized thresholds derived from 55,000+ historical games.
- **Status**: **Automated Betting Active** (Basketball), **Inactive** (MLB/NFL - Offseason/Awaiting setup).

### ⚽ Soccer (EPL/Ligue 1)
- **Strategy**: 3-Way Market Normalization.
- **Threshold**: 45% Elo Prob.
- **Rationale**: Adjusted for the 3rd outcome (Draw). A 45% probability in a 3-way market represents a significant outlier compared to the ~33% baseline.

---

## 4. Operational Execution

### Automated Workflow (Airflow)
1.  **05:00 ET**: Daily DAG trigger.
2.  **Data Ingest**: Download latest results and update PostgreSQL.
3.  **Elo Refresh**: Recalculate ratings for 1,000+ athletes and teams.
4.  **Market Fetch**: Scan Kalshi for hundreds of open contracts.
5.  **Identification**: Compare internal models vs. Kalshi vs. Sharp Odds.
6.  **Optimization**: Run Kelly Criterion across all identified edges.
7.  **Betting**: Execute limit orders on Kalshi with live position verification.
8.  **Reporting**: Log all bets to `placed_bets` and send summary via SMS.

### Data Integrity & Tracking
- **PostgreSQL**: All bets, odds, and game results are stored in a centralized database to prevent concurrency issues.
- **CLV Tracking**: Every bet tracks **Closing Line Value** to ensure our model consistently beats the market before game time.

---

## 5. Risk Summary

| Category | Risk Level | Mitigation |
| :--- | :--- | :--- |
| **Market Risk** | Medium | Fractional Kelly + Max Position Caps |
| **Execution Risk**| Low | Match-level locking + Position deduplication |
| **Model Risk** | Medium | Continuous lift/gain monitoring + Sharp confirmation |
| **Connectivity** | Low | Fallback auth methods + PostgreSQL persistence |
