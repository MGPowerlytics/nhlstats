# Closing Line Value (CLV) Tracking Guide

## What is CLV?

**Closing Line Value (CLV)** is the gold standard metric for evaluating betting models.

**CLV** = (Probability You Bet At) - (Closing Line Probability)

- **Positive CLV** = You got better odds than the closing line (GOOD!) ✅
- **Negative CLV** = The market moved against you (BAD) ❌

## Why CLV Matters

CLV is the #1 indicator of long-term profitability because:

1. **Market Wisdom:** Closing lines reflect all available information (sharp money, injuries, weather)
2. **Efficiency Test:** If you consistently beat closing lines, your model has true edge
3. **Better than Win Rate:** You can win 55% but lose money if CLV is negative

**Famous Quote:** *"If you don't beat the closing line, you won't be a long-term winner."* - Professional sports bettor

## How We Track CLV

### Database Schema

We've added CLV tracking to the `placed_bets` table:

```sql
ALTER TABLE placed_bets ADD COLUMN opening_line_prob DOUBLE;   -- First posted odds
ALTER TABLE placed_bets ADD COLUMN bet_line_prob DOUBLE;       -- Odds when we bet
ALTER TABLE placed_bets ADD COLUMN closing_line_prob DOUBLE;   -- Odds at game start
ALTER TABLE placed_bets ADD COLUMN clv DOUBLE;                 -- CLV calculation
ALTER TABLE placed_bets ADD COLUMN updated_at TIMESTAMP;       -- Last update time
```

### Tracking Workflow

1. **When Bet is Placed:**
   - Record `bet_line_prob` (market probability at bet time)
   
2. **Before Game Starts:**
   - Fetch closing line from Kalshi or The Odds API
   - Calculate `clv = bet_line_prob - closing_line_prob`
   - Store in database

3. **After Game Settles:**
   - Compare actual outcome vs. CLV prediction
   - Analyze if positive CLV correlates with wins

## Using the CLV Tracker

### Run CLV Analysis

```python
from clv_tracker import CLVTracker

tracker = CLVTracker(db_path='data/nhlstats.duckdb', odds_api_key='your_key')

# Print report for last 30 days
tracker.print_clv_report(days_back=30)
```

### Expected Output

```
============================================================
CLV ANALYSIS - Last 30 Days
============================================================

Overall Performance:
  Total Bets: 87
  Average CLV: +1.8%
  Positive CLV %: 64.4%
  ✅ POSITIVE CLV - Model is beating closing lines!

By Sport:
  ✅ NBA     | Bets:  24 | CLV: +2.3% | Positive: 71%
  ✅ NHL     | Bets:  31 | CLV: +1.9% | Positive: 65%
  ❌ MLB     | Bets:  18 | CLV: -0.4% | Positive: 44%
  ✅ NFL     | Bets:  14 | CLV: +3.1% | Positive: 79%
```

## Interpreting CLV Results

### Good CLV (Target)
- **Average CLV:** +2% or higher
- **Positive CLV %:** 60%+ of bets
- **Interpretation:** Model has edge, keep betting

### Neutral CLV (Monitor)
- **Average CLV:** 0% to +2%
- **Positive CLV %:** 50-60% of bets
- **Interpretation:** Model is marginal, need improvements

### Bad CLV (Stop Betting)
- **Average CLV:** Negative
- **Positive CLV %:** < 50% of bets  
- **Interpretation:** Model has NO edge, losing to the market

## Common CLV Patterns

### Pattern 1: Positive CLV, Negative ROI
- **What it means:** Unlucky variance, model is good but results haven't materialized
- **Action:** Keep betting, sample size may be too small

### Pattern 2: Negative CLV, Positive ROI
- **What it means:** Lucky variance, model is bad but got lucky
- **Action:** STOP betting, you're fooling yourself

### Pattern 3: Positive CLV, Positive ROI
- **What it means:** Model has edge AND results confirm it
- **Action:** This is the goal! Keep doing what you're doing

### Pattern 4: Negative CLV, Negative ROI
- **What it means:** Model is bad and results confirm it
- **Action:** Fix model before betting more

## CLV vs. Win Rate

**Common Mistake:** Focusing on win rate instead of CLV.

| Scenario | Win Rate | CLV | Long-Term Result |
|----------|----------|-----|------------------|
| A | 55% | +2% | ✅ PROFITABLE |
| B | 55% | -1% | ❌ UNPROFITABLE |
| C | 48% | +3% | ✅ PROFITABLE |
| D | 52% | -2% | ❌ UNPROFITABLE |

**Lesson:** CLV > Win Rate for predicting profitability.

## Fetching Closing Lines

### Method 1: Kalshi API (Preferred)
```python
# Get market details right before game starts
market = client.get_market_details(ticker)
closing_prob = 1 / market['yes_ask']  # Convert price to probability
```

### Method 2: The Odds API (Fallback)
```python
# Fetch scores/results which include closing odds
response = requests.get(
    f'https://api.the-odds-api.com/v4/sports/{sport_key}/scores/',
    params={'apiKey': api_key, 'daysFrom': 1}
)
```

### Method 3: Manual Entry (Last Resort)
If APIs don't provide closing lines, manually record from sportsbooks before games.

## Automation

### Recommended Schedule

1. **Every 15 minutes before game times:**
   - Fetch updated market probabilities
   - Update `bet_line_prob` for open bets
   
2. **5 minutes before game start:**
   - Fetch closing line
   - Calculate and store CLV
   
3. **Daily at midnight:**
   - Run CLV analysis report
   - Send alerts if CLV drops below 0%

### Airflow Integration

Add to DAG:
```python
def track_closing_lines(**context):
    """Track closing lines for today's bets."""
    from clv_tracker import CLVTracker
    
    tracker = CLVTracker()
    tracker.fetch_closing_lines_from_kalshi(days_back=1)
    
    # Run analysis
    analysis = tracker.analyze_clv(days_back=30)
    
    if analysis['avg_clv'] < 0:
        send_alert(f"⚠️ CLV is negative: {analysis['avg_clv']:.2%}")

track_clv_task = PythonOperator(
    task_id='track_closing_lines',
    python_callable=track_closing_lines,
    dag=dag
)
```

## Action Items Based on CLV

### If CLV > +2%
- ✅ Keep betting
- ✅ Consider increasing bet size (with Kelly)
- ✅ Expand to more opportunities

### If CLV between 0% and +2%
- ⚠️ Monitor closely
- ⚠️ Don't increase bet size
- ⚠️ Look for model improvements

### If CLV < 0%
- ❌ STOP betting immediately
- ❌ Analyze what's wrong with the model
- ❌ Re-evaluate thresholds and features
- ❌ Check for data issues

## CLV Benchmarks by Sport

Based on professional betting literature:

| Sport | Excellent CLV | Good CLV | Acceptable CLV | Poor CLV |
|-------|--------------|---------|----------------|----------|
| NBA | +3%+ | +2-3% | +1-2% | <+1% |
| NHL | +2.5%+ | +1.5-2.5% | +0.5-1.5% | <+0.5% |
| MLB | +2%+ | +1-2% | 0-1% | <0% |
| NFL | +3.5%+ | +2-3.5% | +1-2% | <+1% |

## Common Pitfalls

1. **Sample Size Too Small:** Need 100+ bets for meaningful CLV
2. **Ignoring Outliers:** One +20% CLV bet skews average
3. **Not Segmenting by Sport:** Average across all sports hides problems
4. **Timing Issues:** Comparing to opening line instead of closing line
5. **Data Lag:** Closing lines from 10 minutes before vs. 1 minute before

## Summary

CLV is the ultimate validator of betting model quality:
- **Positive CLV = Model has edge**
- **Negative CLV = Model needs work**
- **Track CLV religiously to ensure long-term profitability**

---

*For implementation details, see `plugins/clv_tracker.py`*
