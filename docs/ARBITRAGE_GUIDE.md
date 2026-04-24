# Multi-Platform Arbitrage System

## Overview

The multi-platform arbitrage system compares betting odds across **40+ sportsbooks** and **Kalshi prediction markets** to identify:

1. **Arbitrage Opportunities** - Risk-free profit by betting both sides on different platforms
2. **Value Bets** - When Elo predictions show better odds than the market
3. **Cross-Platform Opportunities** - Better prices on one platform vs another

## Platforms Integrated

### The Odds API (Primary Source)
- **40+ sportsbooks** including DraftKings, FanDuel, BetMGM, Bet365, Pinnacle, Bovada
- **Real-time odds** for NBA, NHL, MLB, NFL, EPL, NCAAB
- **Free tier**: 500 requests/month
- **Get API key**: https://the-odds-api.com/

### Kalshi (Prediction Markets)
- Already integrated
- Lower fees than traditional sportsbooks
- Event contracts instead of traditional bets

### Future Integrations
- **Cloudbet** - Crypto sportsbook (requires API key)
- **Polymarket** - Decentralized prediction markets (read-only)
- **Azuro Protocol** - DeFi betting pools

## Setup

### 1. Get The Odds API Key

```bash
# Sign up at https://the-odds-api.com/ (free tier: 500 requests/month)
# Set environment variable:
export ODDS_API_KEY='your-api-key-here'

# Or add to your shell profile (~/.bashrc or ~/.zshrc):
echo 'export ODDS_API_KEY="your-api-key-here"' >> ~/.bashrc
source ~/.bashrc
```

### 2. Run Arbitrage Finder

```bash
cd /mnt/data2/nhlstats

# Find arbitrage opportunities for today
python3 find_arbitrage.py
```

## Usage

### Find Arbitrage Opportunities

```python
from find_arbitrage import ArbitrageFinder
from datetime import date

finder = ArbitrageFinder(api_key='your-odds-api-key')

# Find opportunities for a sport
opportunities = finder.find_opportunities('nba', date.today().strftime('%Y-%m-%d'))

# Print results
finder.print_opportunities(opportunities)

# Save to file
finder.save_opportunities(opportunities, date.today().strftime('%Y-%m-%d'))
```

### Fetch Odds from Multiple Bookmakers

```python
from plugins.the_odds_api import TheOddsAPI

api = TheOddsAPI(api_key='your-key')

# Fetch NBA odds from all bookmakers
markets = api.fetch_markets('nba')

# Each market includes odds from 10-20+ bookmakers
for game in markets:
    print(f"{game['away_team']} @ {game['home_team']}")
    print(f"Best home odds: {game['best_home_odds']} ({game['best_home_bookmaker']})")
    print(f"Best away odds: {game['best_away_odds']} ({game['best_away_bookmaker']})")
    print(f"Available at {game['num_bookmakers']} bookmakers")
```

## Opportunity Types

### 1. Arbitrage (Risk-Free)

**What**: Bet both sides on different platforms for guaranteed profit

**Example**:
```
Lakers vs Celtics
- Bet Lakers on DraftKings: 2.10 odds (47.6% implied prob)
- Bet Celtics on FanDuel: 2.20 odds (45.5% implied prob)
- Total probability: 93.1% < 100%
- Profit margin: 6.9% RISK-FREE
```

**How to execute**:
1. Calculate stake sizes to guarantee profit
2. Place both bets simultaneously
3. Win regardless of outcome

### 2. Value Bets (Elo Edge)

**What**: Elo model predicts better odds than market offers

**Example**:
```
Lakers vs Celtics
- Elo prediction: Lakers 65% to win
- Market offers: 58% implied probability
- Edge: 7% value bet on Lakers
```

**Risk**: Elo model could be wrong, but historical edge gives long-term profit

### 3. Cross-Platform Comparison

**What**: Same bet available at better price on different platform

**Example**:
```
Lakers to win:
- Kalshi: 52 cents (52% prob)
- DraftKings: 1.85 odds (54% prob)
- Better price on Kalshi by 2%
```

## Integration with Existing System

### Updated DAG Workflow

```
For each sport:
1. Download games
2. Load to DB
3. Update Elo ratings
4. Fetch Kalshi markets (existing)
5. Fetch The Odds API markets (NEW)
6. Compare odds and find arbitrage (NEW)
7. Identify best bets across all platforms (NEW)
8. Save to database
```

### Database Schema

New table: `arbitrage_opportunities`

```sql
CREATE TABLE arbitrage_opportunities (
    opportunity_id VARCHAR PRIMARY KEY,
    opportunity_date DATE,
    sport VARCHAR,
    opportunity_type VARCHAR, -- 'arbitrage', 'value_bet', 'cross_platform'
    home_team VARCHAR,
    away_team VARCHAR,
    platform VARCHAR,
    home_platform VARCHAR,
    away_platform VARCHAR,
    edge DOUBLE,
    profit_margin DOUBLE,
    elo_prob DOUBLE,
    market_prob DOUBLE,
    num_bookmakers INTEGER,
    created_at TIMESTAMP
);
```

## Cost Analysis

### The Odds API (Recommended)

**Free Tier**:
- 500 requests/month
- ~16 requests/day
- Enough for 2-3 sports per day

**Usage**:
- 1 request = 1 sport's odds
- Efficient: Gets all bookmakers in one request

**Paid Tiers**:
- $50/month: 5,000 requests
- $100/month: 10,000 requests
- $200/month: 25,000 requests

### Alternative: Individual Sportsbook APIs

**Cloudbet**:
- Free API access
- Need to register for API key
- Crypto-based (BTC, ETH, USDT)

**Pinnacle** (if accessible):
- Industry-leading odds
- Low margins (high value)
- API available for verified accounts

## Analysis Tools

### Arbitrage Analysis

```bash
# Find all arbitrage opportunities
python3 find_arbitrage.py

# Analyze historical opportunities
python3 -c "
import duckdb
conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)
result = conn.execute('''
    SELECT
        sport,
        COUNT(*) as opportunities,
        AVG(profit_margin) as avg_profit
    FROM arbitrage_opportunities
    WHERE opportunity_type = 'arbitrage'
    GROUP BY sport
''').fetchall()
for row in result:
    print(f'{row[0]}: {row[1]} opps, avg {row[2]:.1%} profit')
"
```

### Best Platform Finder

```bash
# Which platform has best odds for each sport?
python3 analyze_platform_edges.py
```

## Example Output

```
================================================================================
FINDING OPPORTUNITIES FOR NBA
================================================================================

📊 Loading Elo predictions...
✓ Loaded Elo ratings for 30 teams

💰 Fetching Kalshi markets...
✓ Found 12 Kalshi markets

🎲 Fetching sportsbook odds from The Odds API...
📊 Requests remaining: 495
✓ Found 15 games with odds from 18 bookmakers

🔍 Analyzing 15 games...

✓ Found 23 opportunities

================================================================================
FOUND 23 OPPORTUNITIES
================================================================================

🎯 ARBITRAGE OPPORTUNITIES (2)

Lakers @ Celtics
  💰 RISK-FREE PROFIT: 2.3%
  Bet Home on draftkings: 2.15
  Bet Away on fanduel: 2.05

Heat @ Warriors
  💰 RISK-FREE PROFIT: 1.8%
  Bet Home on betmgm: 1.95
  Bet Away on pinnacle: 2.25

📈 VALUE BETS (18)

Mavericks @ Knicks
  Bet HOME: Knicks
  Platform: fanduel
  Edge: 8.2% (Elo: 72.1%, Market: 63.9%)
  Odds: 1.56

[...]
```

## Legal Considerations

- **Pennsylvania**: Traditional sportsbooks legal, crypto/offshore use at own risk
- **Kalshi**: Legal nationwide under CFTC regulation
- **The Odds API**: Aggregation service only, doesn't facilitate betting
- **Arbitrage**: Legal but sportsbooks may limit accounts
- **Always verify** local regulations before betting

## Best Practices

1. **Start with free tier** (500 requests/month)
2. **Focus on high-edge opportunities** (>5% edge or >2% arbitrage)
3. **Monitor multiple sports** to find best opportunities
4. **Act quickly** on arbitrage (odds change fast)
5. **Use Kelly Criterion** for bet sizing on value bets
6. **Track actual results** to validate Elo model accuracy

## Troubleshooting

### "No API key found"
```bash
export ODDS_API_KEY='your-key-here'
```

### "Requests remaining: 0"
- You've used your monthly quota
- Upgrade to paid tier or wait for reset
- Free tier resets monthly

### "No opportunities found"
- Markets may be efficient (no arbitrage)
- Try different sports
- Lower edge threshold in code

## Next Steps

1. ✅ **Set up The Odds API key**
2. ✅ **Run find_arbitrage.py**
3. ⏳ **Add to DAG for daily execution**
4. ⏳ **Build dashboard for visualization**
5. ⏳ **Implement automated bet placement**
6. ⏳ **Add Kelly Criterion bet sizing**
7. ⏳ **Track ROI and performance**

## Files

- `plugins/the_odds_api.py` - The Odds API integration
- `plugins/cloudbet_api.py` - Cloudbet API integration
- `plugins/polymarket_api.py` - Polymarket API integration
- `plugins/odds_comparator.py` - Multi-platform comparison engine
- `find_arbitrage.py` - Main arbitrage finder script
- `docs/ARBITRAGE_GUIDE.md` - This file
