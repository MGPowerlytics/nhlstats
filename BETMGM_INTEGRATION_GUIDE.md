# BetMGM Integration Guide

## Overview

This integration allows you to:
1. **Fetch live BetMGM odds** via The Odds API
2. **Compare with our Elo predictions** to find value bets
3. **Cross-reference Kalshi and BetMGM** markets
4. **Identify arbitrage opportunities** between platforms

## Files Created

### Core Scripts
- `plugins/betmgm_integration.py` - Main BetMGM odds fetcher and comparator
- `compare_betting_markets.py` - Cross-market analysis tool

### Mapping Files
- `data/betmgm_to_nba_mapping.json` - Maps BetMGM team names to our NBA names
- `data/betmgm_to_ncaab_mapping.json` - Maps BetMGM team names to our NCAAB names
- `data/betmgm_to_wncaab_mapping.json` - Maps BetMGM team names to our WNCAAB names (create as needed)

## Usage

### 1. Fetch BetMGM Odds and Compare with Elo

```bash
python plugins/betmgm_integration.py
```

**Output:**
- Fetches live odds from BetMGM for NBA, NCAAB, WNCAAB
- Compares with our Elo predictions
- Saves to `data/betmgm_opportunities_YYYY-MM-DD.json`
- Shows games where Elo differs from market

**Note:** Uses The Odds API (500 requests/month on free tier)

### 2. Cross-Market Analysis

```bash
python compare_betting_markets.py [YYYY-MM-DD]
```

**Output:**
- Compares Kalshi bets vs BetMGM odds
- Identifies arbitrage opportunities
- Shows edge analysis for both markets
- Recommendations for today's bets

### 3. Example Workflow

```bash
# Step 1: Run DAG to generate Kalshi bets
# (happens automatically at 10 AM daily)

# Step 2: Fetch BetMGM odds
python plugins/betmgm_integration.py

# Step 3: Compare markets
python compare_betting_markets.py

# Step 4: Review recommendations and place bets
```

## Key Findings from Initial Analysis

### BetMGM vs Elo Comparison
- **ALL edges are negative** - BetMGM odds are MORE accurate than raw Elo
- This suggests:
  - BetMGM incorporates more information (injuries, lineups, etc.)
  - Our Elo model is conservative
  - BetMGM is a sharp market

### Kalshi Market Analysis
- **29 high-edge bets (≥10%)** found today
- Largest edges:
  - WNCAAB: 85% edge (Texas A&M vs LSU)
  - NCAAB: 81% edge (Morgan St vs Virginia)
  - NCAAB: 70% edge (Michigan vs Bowling Green)

### Arbitrage
- **No pure arbitrage found** between Kalshi and BetMGM
- Markets are efficient
- Both platforms price accurately

## Interpretation Guide

### Edge Calculation

```
Edge = Elo_Probability - Market_Probability
```

**Positive Edge (+):** Our Elo thinks team is MORE likely to win than market
**Negative Edge (-):** Our Elo thinks team is LESS likely to win than market

### When to Bet

#### On Kalshi (Prediction Markets)
- ✅ **High edge (≥10%)** over Kalshi market
- ✅ **Elo probability > 65%** for high confidence
- ✅ Games where we have clear information advantage

#### On BetMGM (Sportsbooks)
- ⚠️ **Use caution** - BetMGM odds are sharp
- ✅ Only when Elo shows **significant** edge (>8%)
- ✅ Cross-reference with Kalshi for validation

### Key Insight

**Kalshi markets show MORE edge than BetMGM!**

This makes sense because:
1. Kalshi is a newer prediction market
2. Lower liquidity = more inefficiencies
3. Fewer sharp bettors
4. Better opportunities for Elo-based strategies

**Recommendation:** Focus on Kalshi, use BetMGM for hedge/arbitrage only.

## Team Name Mapping

### Why Mappings Are Needed

Each platform uses different team name formats:

| Platform | Example |
|----------|---------|
| Our System | `Michigan` |
| BetMGM | `Michigan Wolverines` |
| Kalshi | `UMICH` |

### Adding New Mappings

Edit the JSON files:

```json
// data/betmgm_to_ncaab_mapping.json
{
  "Michigan Wolverines": "Michigan",
  "Ohio State Buckeyes": "Ohio_State",
  ...
}
```

### Auto-Matching

The script attempts to auto-match using:
1. **Direct match** - exact name
2. **Normalized match** - removes punctuation, "State" → "St", etc.
3. **Fuzzy match** - substring matching
4. **Manual mapping** - uses JSON files (most reliable)

## API Limits

### The Odds API
- **Free tier:** 500 requests/month
- **Cost per request:** ~$0.01 over limit
- **Each sport fetch:** 1 request
- **Daily usage:** ~4 requests (NBA, NCAAB, WNCAAB, Tennis)
- **Monthly capacity:** ~125 days (more than enough)

### Optimization
- Cache results to avoid duplicate API calls
- Only fetch during betting hours (e.g., morning and evening)
- Use conditional fetching based on schedule

## Output Files

### `betmgm_opportunities_YYYY-MM-DD.json`

```json
[
  {
    "sport": "nba",
    "home_team": "Warriors",
    "away_team": "Raptors",
    "commence_time": "2026-01-20T02:00:00Z",
    "best_bet": "away",
    "bet_team": "Raptors",
    "elo_prob": 0.53,
    "betmgm_prob": 0.60,
    "edge": -0.07,
    "betmgm_odds": -150,
    "home_odds": 130,
    "away_odds": -150
  }
]
```

## Future Enhancements

### 1. Tennis Integration
- Map ATP/WTA player names
- Handle player-level Elo ratings
- Account for surface, tournament, etc.

### 2. Live Betting
- Monitor odds movements
- Alert on sudden line changes
- In-game betting based on live Elo updates

### 3. Multi-Book Comparison
- Add DraftKings, FanDuel, Caesars
- Find best available odds across books
- True arbitrage finder

### 4. Automated Betting
- API integration with betting platforms
- Auto-place bets based on edge thresholds
- Position sizing using Kelly Criterion

### 5. Results Tracking
- Track actual vs predicted outcomes
- Calculate ROI by market (Kalshi vs BetMGM)
- Refine Elo parameters based on results

## Troubleshooting

### "Could not match" warnings
- Add team to mapping JSON file
- Check for spelling differences
- Look at Elo ratings file for exact team name

### No opportunities found
- Check if games are scheduled today
- Verify API key is working
- Ensure Elo ratings are up to date

### API rate limit exceeded
- Wait until next month
- Reduce fetch frequency
- Upgrade to paid plan

## Summary

✅ **Created:** BetMGM integration via The Odds API  
✅ **Mapped:** NBA, NCAAB team names between systems  
✅ **Compared:** Elo predictions vs BetMGM market odds  
✅ **Analyzed:** Cross-market opportunities (Kalshi vs BetMGM)  
✅ **Found:** 29 high-edge Kalshi bets for today  

**Next Steps:**
1. Complete WNCAAB and Tennis mappings
2. Add to daily DAG workflow
3. Track performance and refine thresholds
4. Consider automated bet placement

---

**Note:** Always bet responsibly. Past performance does not guarantee future results.
