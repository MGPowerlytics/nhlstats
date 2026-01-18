# External Data Integration Plan
## Morning-of-Game Data Sources

### Priority 1: Starting Goalies (HIGHEST IMPACT)

**Why Critical**: Starting goalie is typically a top-3 predictor in NHL models. Save % difference between starter and backup can be 5-10 percentage points.

**Data Sources (Available Morning-of)**:
1. **NHL API** (`https://api-web.nhle.com/v1/schedule/{date}`)
   - Lists "probable" goalies 2-3 hours before game
   - Not always accurate until ~90 minutes before puck drop

2. **DailyFaceoff.com** (`https://www.dailyfaceoff.com/starting-goalies/`)
   - Community-updated, usually confirmed by 10-11am EST
   - Most reliable source for morning predictions
   - Scraping required (no API)

3. **Social Media** (Twitter/X)
   - Team beat reporters tweet morning skate updates
   - NHL teams' official accounts
   - Too manual for automation

**Implementation Strategy**:
```python
# Historical Training: Identify starter from player_game_stats
# - Filter goalies with TOI > 50 minutes = starter
# - Calculate rolling stats (L3, L5, L10 starts)

# Morning-of Prediction:
# 1. Fetch probable goalies from NHL API (8am)
# 2. Scrape DailyFaceoff.com for confirmations (10am)
# 3. Calculate goalie features from historical stats
# 4. Generate predictions with confirmed starters
```

**Goalie Features to Add** (10 features):
- Starting goalie's save % (L3, L5, L10 starts)
- Starting goalie's GAA (goals against average)
- Days rest since goalie's last start
- Goalie's save % vs this specific opponent (career)
- Goalie's save % at this venue
- Flag: Is backup starting? (typically worse)
- Goalie quality differential (home save% - away save%)
- Goalie's high-danger save % (if available)
- Goalie's performance on rest vs no rest
- Goalie's record (W-L-OTL) in last 10 starts

---

### Priority 2: Betting Lines (MARKET WISDOM)

**Why Important**: Betting markets aggregate information from thousands of bettors. Line movement indicates where sharp money is going.

**Data Sources (Available Morning-of)**:
1. **The Odds API** (`https://the-odds-api.com/`)
   - Free tier: 500 requests/month
   - Moneyline, puck line, totals
   - Multiple sportsbooks (consensus)

2. **Pinnacle API** (Most respected, sharpest lines)
   - Requires account
   - Best for line movement tracking

3. **DraftKings/FanDuel** (Public books)
   - Scraping required
   - Opening vs closing line movement

**Implementation Strategy**:
```python
# Historical Training:
# - Backfill historical lines from sports-reference or archives
# - Or train without, add for live predictions only

# Morning-of Prediction:
# 1. Fetch opening lines (usually 2-7 days before game)
# 2. Fetch current lines (morning of)
# 3. Calculate implied probability from moneyline
# 4. Track line movement (opening to current)
```

**Betting Line Features** (8 features):
- Home team moneyline (converted to implied win %)
- Away team moneyline (converted to implied win %)
- Puck line (spread, typically +/- 1.5 goals)
- Line movement (opening to closing, in $)
- Reverse line movement flag (line moves against public betting %)
- Over/under total (indicates expected scoring)
- Home favorite flag (negative moneyline)
- Consensus vs outlier book (if line is off market)

---

### Priority 3: Injuries & Key Player Absences

**Why Important**: Losing a star player (top line center, #1 defenseman) significantly impacts win probability.

**Data Sources (Available Morning-of)**:
1. **NHL Injury Report** (`https://www.nhl.com/info/injury-report`)
   - Official source, updated daily
   - Lists: Out, Day-to-Day, IR (Injured Reserve)

2. **DailyFaceoff.com Injuries** 
   - More detailed, includes projected return dates

3. **Line Combinations** (DailyFaceoff)
   - Shows which players are scratched
   - Indicates lineup changes

**Implementation Strategy**:
```python
# Challenge: Defining "key player" quantitatively
# - Points per game (skaters)
# - Average TOI (time on ice)
# - Plus/minus rating
# - Position (centers more valuable than wingers)

# Simple Approach:
# - Count top-6 forwards out
# - Count top-4 defensemen out
# - Binary flag: #1 center out

# Advanced Approach:
# - Calculate team's Points Above Replacement (PAR)
# - Sum missing PAR for all injured players
```

**Injury Features** (5 features):
- Count of top-6 forwards out (home)
- Count of top-4 defensemen out (home)
- Count of top-6 forwards out (away)
- Count of top-4 defensemen out (away)
- Star player out flag (>1.0 PPG player missing)

---

### Priority 4: Weather & Arena Conditions

**Why Lower Priority**: NHL games indoors, minimal impact. But worth checking for outdoor games.

**Data Sources**:
- Weather API for outdoor games (Winter Classic, Heritage Classic)
- Arena conditions (not really available publicly)

**Skip for now** - negligible impact.

---

## Implementation Roadmap

### Phase 1: Goalie Features (Week 1)
1. **Historical Data**: 
   - Identify starting goalies from player_game_stats (TOI > 50 min)
   - Calculate rolling goalie stats (save %, GAA, etc.)
   - Add goalie features to training dataset

2. **Morning-of Integration**:
   - Create `fetch_probable_goalies.py` script
   - Scrape DailyFaceoff.com for confirmed starters
   - Store in database: `confirmed_starters` table

3. **Model Integration**:
   - Retrain model with goalie features
   - Expected improvement: +3-5% accuracy (based on industry research)

### Phase 2: Betting Lines (Week 2)
1. **API Setup**:
   - Sign up for The Odds API (free tier)
   - Create `fetch_betting_lines.py` script
   - Store in database: `betting_lines` table

2. **Feature Engineering**:
   - Convert moneyline to implied probability
   - Calculate line movement
   - Identify reverse line movement

3. **Model Integration**:
   - Add betting line features
   - Compare model predictions to market
   - Identify edge opportunities

### Phase 3: Injuries (Week 3)
1. **Data Collection**:
   - Scrape NHL injury report daily
   - Parse player names, status, position
   - Store in database: `injury_reports` table

2. **Key Player Identification**:
   - Calculate player value metrics (PPG, TOI, PAR)
   - Define thresholds for "key player"
   - Create binary flags for missing players

3. **Model Integration**:
   - Add injury count features
   - Expected improvement: +1-2% accuracy

---

## Morning-of Prediction Workflow

```
6:00 AM  - Fetch opening betting lines (if not already stored)
9:00 AM  - Scrape injury reports (official NHL)
10:00 AM - Scrape DailyFaceoff for goalie confirmations
11:00 AM - Fetch current betting lines (track movement)
12:00 PM - Run prediction model with all external data
1:00 PM  - Compare model predictions to betting lines
          - Identify games with edge (model disagrees with market)
2:00 PM  - Final check before first games (usually 7pm ET start)
```

---

## Expected Impact

| Data Source | Accuracy Gain | Implementation Effort | Data Availability |
|-------------|---------------|----------------------|-------------------|
| **Goalies** | +3-5% | Medium | 10am morning-of |
| **Betting Lines** | +2-3% | Easy (API) | Real-time |
| **Injuries** | +1-2% | Medium | 9am morning-of |
| **TOTAL** | **+6-10%** | - | - |

**Current Model**: 57.7% accuracy (+0.6% vs baseline)
**With External Data**: **63-67% accuracy** (+6-10% vs baseline)

At 65% accuracy, the model becomes **profitable for betting** (breakeven ~52.4% with -110 odds).

---

## Next Steps

1. ✅ Create this plan document
2. ⬜ Identify historical starting goalies from existing data
3. ⬜ Implement goalie rolling stats calculation
4. ⬜ Add goalie features to training dataset
5. ⬜ Retrain model with goalie features
6. ⬜ Build morning-of data fetching pipeline
7. ⬜ Integrate betting lines API
8. ⬜ Build injury scraper

**Start with**: Goalie features (highest impact, 3-5% gain expected)
