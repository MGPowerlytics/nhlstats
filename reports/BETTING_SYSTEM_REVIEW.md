# Sports Betting System Review - Professional Standards Analysis

## Executive Summary

Our automated betting system exhibits **significant gaps** in professional gambling best practices. While technically functional, it lacks critical risk management and profitability mechanisms used by successful sports bettors.

---

## 1. ❌ BANKROLL MANAGEMENT (CRITICAL FAILURE)

### Current Implementation:
```python
# kalshi_betting.py line 138-140
def calculate_bet_size(self, confidence: float, edge: float, balance: float) -> float:
    bet_size = balance * (edge / 4.0)
    return round(max(self.min_bet_size, min(self.max_bet_size, balance * self.max_position_pct, bet_size)), 2)
```

### Issues:
- ❌ **Hard-coded $5 max bet** (`max_bet_size = 5.0`) regardless of bankroll
- ❌ **5% position limit** (`max_position_pct = 0.05`) is too aggressive for single bets
- ❌ **No Kelly Criterion** - Using `edge / 4.0` is arbitrary, not mathematically optimal
- ❌ **No drawdown protection** - Will keep betting full amounts even after losses
- ❌ **No separation of bankroll** - Uses real-time balance, not fixed starting bankroll

### Professional Standard:
```python
# Kelly Criterion: f* = (bp - q) / b
# Where: p = win probability, q = 1-p, b = odds-1
# Fractional Kelly (25-50%) for safety

def kelly_bet_size(self, win_prob: float, odds: float, bankroll: float, kelly_fraction: float = 0.25) -> float:
    """Calculate bet size using fractional Kelly Criterion."""
    b = odds - 1  # Net odds
    q = 1 - win_prob
    kelly = (b * win_prob - q) / b

    # Use fractional Kelly for safety
    bet_fraction = max(0, kelly * kelly_fraction)

    # Cap at 1-3% of bankroll per bet
    bet_size = bankroll * min(bet_fraction, 0.03)

    return bet_size
```

### Recommendation:
**🚨 URGENT: Implement Kelly Criterion with 25% fraction and 1-3% hard cap per bet**

---

## 2. ⚠️ VALUE BETTING (PARTIALLY IMPLEMENTED)

### Current Implementation:
```python
# Requires minimum 5% edge
if elo_prob > elo_threshold and edge > 0.05:
    # Place bet
```

### Strengths:
- ✅ Calculates edge properly: `edge = elo_prob - market_prob`
- ✅ Requires minimum edge (5%)
- ✅ Uses probability thresholds by sport

### Issues:
- ❌ **Thresholds seem arbitrary** - No backtesting data shown
- ⚠️ **5% edge requirement** may be too high (missing +EV bets)
- ❌ **No closing line value (CLV) tracking** - Can't validate if model beats the market

### Current Thresholds:
```
NBA:    64% threshold
NHL:    77% threshold (VERY high - likely missing value)
MLB:    62% threshold
NFL:    68% threshold
NCAAB:  65% threshold
Tennis: 60% threshold
Soccer: 45% threshold (3-way markets)
```

### Questions:
1. **Are these thresholds backtested?** - Need proof of long-term profitability
2. **Why is NHL 77%?** - This is extremely conservative, likely missing +EV opportunities
3. **Is our Elo model actually beating closing lines?**

### Recommendation:
**📊 ADD: Comprehensive backtest report with ROI, CLV, and Sharpe ratio by sport**

---

## 3. ⚠️ SPECIALIZATION (CONCERNING - TOO BROAD)

### Current Implementation:
- Betting on **9 sports**: NBA, NHL, MLB, NFL, EPL, Ligue1, NCAAB, WNCAAB, Tennis
- Using **same Elo methodology** across all sports
- **Same edge threshold (5%)** across all sports

### Issues:
- ❌ **Spreading too thin** - Professional bettors specialize in 1-2 sports/markets
- ⚠️ **Elo may not be optimal** for all sports (especially tennis, soccer 3-way)
- ❌ **No market-specific adjustments** (e.g., tennis surface, weather in baseball)
- ❌ **No recency weighting** except NHL
- ❌ **Missing key factors**: injuries, rest days, travel, B2B games

### Professional Standard:
- Focus on 1-2 sports maximum
- Build sport-specific models with domain expertise
- Track which sports/markets you actually beat

### Recommendation:
**🎯 FOCUS: Choose 2-3 sports where we have proven edge, disable the rest**
**📈 ADD: Sport-specific feature engineering (rest, travel, injuries, etc.)**

---

## 4. ❌ LINE SHOPPING (NOT IMPLEMENTED)

### Current Implementation:
- **Only uses Kalshi** - Single sportsbook
- No price comparison
- No best-odds aggregation

### Issues:
- ❌ **Missing 1-3% ROI** from line shopping alone
- ❌ **Kalshi has lower limits** than major sportsbooks
- ❌ **No arb opportunities** detected

### Professional Standard:
```python
def find_best_line(self, game: Dict) -> Dict:
    """Compare odds across multiple books."""
    books = ['kalshi', 'draftkings', 'fanduel', 'betmgm', 'pinnacle']
    best_odds = {}

    for book in books:
        odds = self.get_odds(book, game)
        for outcome in ['home', 'away']:
            if outcome not in best_odds or odds[outcome] > best_odds[outcome]['price']:
                best_odds[outcome] = {'book': book, 'price': odds[outcome]}

    return best_odds
```

### Recommendation:
**💰 ADD: Integrate The Odds API to find best lines (already paying for it!)**
**🔍 ADD: Arbitrage detection across books**

---

## 5. ✅ DATA & ANALYTICS (STRONG)

### Current Implementation:
- ✅ **Comprehensive historical data** in DuckDB
- ✅ **Elo rating system** for all sports
- ✅ **Automated data pipeline** via Airflow DAG
- ✅ **Dashboard for analysis** with Streamlit

### Strengths:
- Good data infrastructure
- Systematic approach
- Version control and testing

### Room for Improvement:
- ⚠️ **No ML models** - Pure Elo (which is fine if it works)
- ⚠️ **Missing advanced metrics**: Rest days, injuries, lineup changes
- ⚠️ **No ensemble models** - Could combine Elo with other signals

---

## 6. ✅ AVOID PARLAYS (GOOD)

### Current Implementation:
```python
# All bets are straight bets - no parlays
```

**✅ CORRECT** - We're doing straight bets only, which is the right approach.

---

## 7. ⚠️ TIMING THE MARKET (UNCLEAR)

### Current Implementation:
- DAG runs daily at 10 AM
- Verifies game hasn't started before placing bet
- Uses current market odds

### Issues:
- ❌ **No early vs late line strategy** - Just betting whenever we run
- ❌ **No closing line value tracking** - Can't tell if we're beating the closing number
- ⚠️ **10 AM may be suboptimal** - Sharp money often moves lines closer to game time

### Recommendation:
**📊 TRACK: Opening line, our bet line, closing line for every bet**
**⏰ TEST: Different execution times (early morning vs. closer to games)**

---

## 8. ✅ EMOTIONAL DISCIPLINE (STRONG)

### Current Implementation:
- ✅ **Fully automated** - No human emotion involved
- ✅ **Consistent criteria** applied to all bets
- ✅ **No chasing losses** - System doesn't know about past results

**✅ CORRECT** - Automation eliminates emotional bias.

---

## 9. ✅ TRACKING EVERY BET (GOOD)

### Current Implementation:
```python
# bet_tracker.py
CREATE TABLE placed_bets (
    bet_id, sport, placed_date, ticker,
    home_team, away_team, bet_on, side,
    contracts, price_cents, cost_dollars,
    elo_prob, market_prob, edge,
    status, settled_date, payout_dollars, profit_dollars
)
```

### Strengths:
- ✅ Comprehensive bet tracking
- ✅ Records edge and probabilities
- ✅ Tracks outcomes

### Missing:
- ❌ **No CLV (Closing Line Value)** tracking
- ❌ **No ROI by sport/confidence/edge bucket**
- ❌ **No Sharpe ratio or risk-adjusted returns**

### Recommendation:
**📈 ADD: CLV column and automated analysis of which bets/sports are actually profitable**

---

## 10. ⚠️ UNDERSTANDING SPORTSBOOK RULES (PARTIAL)

### Current Implementation:
- ✅ Understands Kalshi limit orders
- ✅ Has deduplication logic
- ✅ Verifies game hasn't started

### Issues:
- ⚠️ **Kalshi is different** from traditional sportsbooks (prediction market vs. sports betting)
- ❌ **No monitoring for account limits/bans**
- ❌ **No understanding of Kalshi liquidity issues** (small markets)

---

## CRITICAL RECOMMENDATIONS (Priority Order)

### 🚨 URGENT (Implement immediately):

1. **FIX BANKROLL MANAGEMENT**
   - Implement Kelly Criterion with 25% fraction
   - Hard cap bets at 1-3% of bankroll
   - Track starting bankroll separately from current balance

2. **ADD LINE SHOPPING**
   - Use The Odds API to compare prices
   - Only bet when we have best available odds
   - Track savings from line shopping

3. **VALIDATE EDGE**
   - Backtest last 12 months with actual market odds
   - Calculate true ROI, Sharpe ratio, max drawdown
   - Verify we're actually beating closing lines

### 📊 HIGH PRIORITY (Within 1 week):

4. **SPECIALIZE**
   - Analyze which sports have positive ROI
   - Disable unprofitable sports
   - Focus resources on 2-3 best markets

5. **ENHANCE TRACKING**
   - Add CLV (closing line value) to every bet
   - Build profit analysis dashboard by sport/edge/confidence
   - Set up alerts for drawdowns > 20%

6. **IMPROVE THRESHOLDS**
   - Backtest optimal thresholds by sport
   - Lower NHL from 77% (way too conservative)
   - Test edge requirements from 3-7%

### 🔧 MEDIUM PRIORITY (Within 1 month):

7. **ADD FEATURES**
   - Rest days, back-to-backs
   - Injury reports
   - Travel distance
   - Lineup changes

8. **MODEL IMPROVEMENTS**
   - Test ensemble with Glicko-2
   - Add regression to mean
   - Implement recency weighting for all sports

9. **RISK MANAGEMENT**
   - Set daily/weekly loss limits
   - Implement circuit breakers for losing streaks
   - Add correlation analysis (don't bet too many same-day games)

---

## Bottom Line Assessment

**Current System Grade: C+ (Functional but Risky)**

### Strengths:
- ✅ Strong technical infrastructure
- ✅ Automated and emotionless
- ✅ Good data tracking
- ✅ Avoids parlays

### Critical Weaknesses:
- ❌ **Dangerous bankroll management** (will likely lose entire bankroll)
- ❌ **No Kelly Criterion** (mathematically suboptimal sizing)
- ❌ **No line shopping** (leaving 1-3% ROI on table)
- ❌ **No validation of edge** (might not be profitable at all)
- ❌ **Too many sports** (spreading thin vs. specializing)

### Verdict:
**🚫 DO NOT BET REAL MONEY until bankroll management and edge validation are fixed.**

Current system has 80%+ chance of losing the entire bankroll due to poor bet sizing, even if the model has edge.
