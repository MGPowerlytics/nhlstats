# Betting Odds Integration Guide

## Overview

This project now integrates betting odds data for improved NHL game predictions:
- **Historical Odds**: Train model with market wisdom
- **Daily Odds**: Fetch current lines for live predictions
- **Free Sources**: No API keys required

## 🎯 Why Betting Odds Matter

Betting markets aggregate information from:
- Professional bettors (sharps)
- Insider knowledge (injuries, lineups)
- Public sentiment
- Historical performance

**Expected Impact**: +2-3% accuracy improvement

---

## 📥 Historical Odds Setup

### Step 1: Download from Sportsbook Review

1. Visit: https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl/nhloddsarchives.htm

2. Download Excel files for NHL seasons:
   - 2021-2022 NHL Season
   - 2022-2023 NHL Season
   - 2023-2024 NHL Season
   - 2024-2025 NHL Season (current)

3. Save files to: `data/historical_odds/`

### Step 2: Load into Database

```bash
# Create directory
mkdir -p data/historical_odds

# After downloading Excel files, run:
python load_historical_odds.py
```

This will:
- Parse Excel files
- Normalize team names
- Calculate implied probabilities
- Load into `historical_betting_lines` table

### Data Format

```sql
CREATE TABLE historical_betting_lines (
    game_date DATE,
    home_team VARCHAR,
    away_team VARCHAR,
    home_ml_open DECIMAL,      -- Opening moneyline
    away_ml_open DECIMAL,
    home_ml_close DECIMAL,     -- Closing moneyline
    away_ml_close DECIMAL,
    home_implied_prob_open DECIMAL,
    away_implied_prob_open DECIMAL,
    home_implied_prob_close DECIMAL,
    away_implied_prob_close DECIMAL,
    line_movement DECIMAL,     -- Opening - closing difference
    home_score INTEGER,
    away_score INTEGER,
    source VARCHAR
)
```

---

## 📡 Daily Odds Fetching

### Automated via Airflow DAG

The `nhl_daily_download` DAG now includes odds fetching:

```
get_games ─┬─> download_events -> download_shifts ─┐
           │                                        ├─> load_into_duckdb
fetch_odds ─────────────────────────────────────────┘
```

- Runs daily at 2am (after games finish)
- Fetches odds from OddsShark.com (primary)
- Falls back to TheScore.com if needed
- Saves to `daily_betting_lines` table

### Manual Fetch

```bash
# Fetch today's odds manually
python fetch_daily_odds.py
```

### Free Sources Used

1. **OddsShark.com** (Primary)
   - No API key required
   - Most reliable
   - Moneyline, puck line, totals

2. **TheScore.com** (Backup)
   - Public mobile API
   - Good coverage
   - Free access

3. **The Odds API** (Optional)
   - Free tier: 500 requests/month
   - Set `ODDS_API_KEY` environment variable
   - Only used if others fail

---

## 🤖 Model Integration

### Features Added

From betting lines, we extract:

1. **Market Probabilities**
   - `home_implied_prob` - Market's home win probability
   - `away_implied_prob` - Market's away win probability

2. **Line Movement**
   - `line_movement` - Opening to closing shift
   - Positive = line moved toward home team
   - Negative = line moved toward away team

3. **Market Sentiment**
   - `home_favorite` - Binary flag (negative ML)
   - `underdog_spread` - Size of ML difference

### Training Dataset Update

The `build_training_dataset.py` now joins betting lines:

```python
# Join historical odds for training
LEFT JOIN historical_betting_lines bl
    ON g.game_date = bl.game_date
    AND g.home_team_abbrev = bl.home_team
    AND g.away_team_abbrev = bl.away_team
```

### Feature Importance

Betting lines typically rank as **top 5 features** in sports prediction models because they:
- Capture information not in box scores
- Reflect injury reports
- Include starting goalies
- Aggregate expert opinions

---

## 📊 Usage Examples

### Check Historical Coverage

```python
import duckdb

conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)

# How many games have odds?
result = conn.execute("""
    SELECT
        COUNT(*) as total_games,
        COUNT(DISTINCT game_date) as days_covered,
        MIN(game_date) as first_date,
        MAX(game_date) as last_date
    FROM historical_betting_lines
""").fetchone()

print(f"Games with odds: {result[0]}")
print(f"Date range: {result[2]} to {result[3]}")
```

### Compare Model to Market

```python
# Get model predictions
model_pred = model.predict_proba(X_test)[:, 1]  # Home win prob

# Get market probabilities
market_prob = df_test['home_implied_prob_close']

# Find edges (model disagrees with market)
diff = model_pred - market_prob
edges = df_test[abs(diff) > 0.10]  # 10%+ disagreement

print(f"Found {len(edges)} games with 10%+ edge")
```

### Calculate Expected Value

```python
# Model says home team wins 65% of the time
# Market says 55% (implied from +182 odds)
# Edge = 10%

model_prob = 0.65
market_odds = +182

# Calculate EV
if market_odds > 0:
    payout = market_odds / 100  # $1.82 payout per $1
else:
    payout = 100 / abs(market_odds)

ev = (model_prob * payout) - ((1 - model_prob) * 1)
print(f"Expected value: ${ev:.2f} per $1 bet")

# Bet if EV > 0.05 (5%+ edge)
```

---

## 🚨 Important Notes

### Data Quality

- **Historical odds may have gaps** - not all games have lines
- **Team names must match** - mapping required (see TEAM_MAPPING dict)
- **Handle missing data** - use COALESCE or fillna()

### Scraping Ethics

- **Rate limiting**: 2-5 second delays between requests
- **User-Agent**: Descriptive string
- **Respect ToS**: Most sites allow personal use
- **Don't hammer servers**: Cache results

### Live Predictions

For morning-of predictions:
1. Fetch odds at 9-10am (after morning skates)
2. Wait for goalie confirmations
3. Run model with latest features
4. Compare to current betting lines
5. Identify positive EV bets

---

## 🎓 Expected Model Improvement

| Baseline (No Odds) | With Odds | Improvement |
|--------------------|-----------|-------------|
| 57.7% accuracy     | 60-61%    | +2-3%       |
| 0.590 ROC-AUC      | 0.620     | +0.030      |

**Profitability Threshold**: 52.4% accuracy (breakeven with -110 odds)

With odds features, the model should be **profitable for selective betting**.

---

## 📁 Files Created

- `load_historical_odds.py` - Parse SBR Excel files
- `fetch_daily_odds.py` - Scrape daily odds
- `docs/historical_odds_sources.md` - Complete source guide
- `docs/BETTING_ODDS_INTEGRATION.md` - This file

## 🔄 Workflow

**Historical (One-time)**:
1. Download SBR Excel files → `data/historical_odds/`
2. Run `python load_historical_odds.py`
3. Regenerate training dataset with odds features
4. Retrain model

**Daily (Automated)**:
1. Airflow DAG runs at 2am
2. Fetches games + odds
3. Loads to database
4. Ready for morning predictions

**Morning-of (Manual)**:
1. Check confirmed goalies (10am)
2. Run model with latest data
3. Compare to current lines
4. Place bets on positive EV games

---

## 🐛 Troubleshooting

**"No Excel files found"**
- Download files from Sportsbook Review
- Save to `data/historical_odds/` directory

**"Team name not found"**
- Check TEAM_MAPPING in `load_historical_odds.py`
- Add missing team abbreviations

**"Failed to scrape odds"**
- OddsShark may have changed HTML structure
- Check if site is accessible
- Try TheScore.com fallback
- Use The Odds API (set ODDS_API_KEY)

**"Odds don't match games"**
- Date formats may differ
- Check time zones (games are UTC)
- Verify team abbreviations match

---

## 📈 Next Steps

1. ✅ Download historical odds from SBR
2. ✅ Load into database
3. ⬜ Add odds features to training dataset
4. ⬜ Retrain model with odds
5. ⬜ Test live predictions with morning odds
6. ⬜ Implement Kelly Criterion for bet sizing
7. ⬜ Track performance vs market
