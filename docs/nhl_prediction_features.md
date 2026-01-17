# NHL Game Prediction Features - Comprehensive Analysis

## Overview
This document catalogs features commonly used to predict NHL game outcomes, organized by category, with analysis of what our pipeline currently collects vs. what's missing.

---

## ✅ Features We HAVE (Currently Collecting)

### 1. Advanced Shot Metrics ✅
| Feature | Description | Source | Status |
|---------|-------------|--------|--------|
| **Corsi For** | All shot attempts (shots + blocks + misses) | Play-by-play events | ✅ Calculated |
| **Corsi Against** | Opponent's shot attempts | Play-by-play events | ✅ Calculated |
| **Fenwick For** | Unblocked shots (shots + misses) | Play-by-play events | ✅ Calculated |
| **Fenwick Against** | Opponent's unblocked shots | Play-by-play events | ✅ Calculated |
| **Shots on Goal** | Actual shots that reached goalie | Play-by-play events | ✅ Collected |
| **High Danger Chances** | Shots from slot (x: -20 to 20, y > 55) | Play-by-play coordinates | ✅ Calculated |

**Impact**: High - Corsi/Fenwick are strongest predictors of puck possession and future goals. Rolling 10-game averages are highly predictive.

---

### 2. Scoring Metrics ✅
| Feature | Description | Source | Status |
|---------|-------------|--------|--------|
| **Goals For** | Goals scored | Play-by-play events | ✅ Collected |
| **Goals Against** | Goals allowed | Play-by-play events | ✅ Collected |
| **Goal Differential** | GF - GA | Calculated | ✅ Can calculate |
| **Power Play Goals** | Goals on PP | Boxscore stats | ✅ Collected |
| **Shorthanded Goals** | Goals while shorthanded | Boxscore stats | ✅ Collected |

**Impact**: Medium-High - Goals are noisy short-term but differential predicts over longer windows.

---

### 3. Goalie Performance ✅
| Feature | Description | Source | Status |
|---------|-------------|--------|--------|
| **Save Percentage** | Saves / Shots Against | Player game stats | ✅ Collected |
| **Saves** | Total saves | Player game stats | ✅ Collected |
| **Shots Against** | Shots faced | Player game stats | ✅ Collected |
| **Goals Against** | Goals allowed | Player game stats | ✅ Collected |
| **Shutouts** | Games with 0 GA | Player game stats | ✅ Collected |
| **Time on Ice** | Minutes played | Player game stats | ✅ Collected |

**Impact**: High - Goalie quality is critical. Rolling save % is very predictive.

---

### 4. Player Stats ✅
| Feature | Description | Source | Status |
|---------|-------------|--------|--------|
| **Assists** | Passes leading to goals | Player game stats | ✅ Collected |
| **Points** | Goals + Assists | Player game stats | ✅ Collected |
| **Plus/Minus** | Goal differential when on ice | Player game stats | ✅ Collected |
| **Hits** | Body checks | Player game stats | ✅ Collected |
| **Blocked Shots** | Defensive blocks | Player game stats | ✅ Collected |
| **Penalty Minutes** | PIM | Player game stats | ✅ Collected |
| **Faceoff Wins** | FO wins | Player game stats | ✅ Collected |

**Impact**: Medium - Individual stats matter less than team aggregates, but star player impact is real.

---

### 5. Special Teams ✅
| Feature | Description | Source | Status |
|---------|-------------|--------|--------|
| **Power Play %** | PP goals / PP opportunities | Game team stats | ✅ Collected |
| **Penalty Kill %** | (PP against - PP goals against) / PP against | Game team stats | ✅ Collected |
| **PP Opportunities** | Times on power play | Game team stats | ✅ Collected |

**Impact**: High - PP/PK efficiency is stable and predictive, especially in close games.

---

### 6. Game Context ✅
| Feature | Description | Source | Status |
|---------|-------------|--------|--------|
| **Home/Away** | Team location | Game data | ✅ Collected |
| **Game Date** | Date of game | Game data | ✅ Collected |
| **Season** | Year/season | Game data | ✅ Collected |
| **Game Type** | Regular/Playoffs | Game data | ✅ Collected |
| **Venue** | Arena name | Game data | ✅ Collected |

**Impact**: High - Home ice advantage is ~5-7% in NHL. Playoffs have different dynamics.

---

### 7. Time-Based Features ✅
| Feature | Description | Source | Status |
|---------|-------------|--------|--------|
| **Rolling 3-game averages** | Last 3 games for all metrics | Calculated window function | ✅ Implemented |
| **Rolling 10-game averages** | Last 10 games for all metrics | Calculated window function | ✅ Implemented |

**Impact**: Very High - Recent form matters immensely. L10 is sweet spot for signal vs. noise.

---

## ❌ Features We DON'T HAVE (Missing Critical Data)

### 1. Rest & Fatigue ❌ CRITICAL
| Feature | Description | Impact | Data Needed |
|---------|-------------|--------|-------------|
| **Days Rest** | Days since last game | **Very High** | Game schedule history |
| **Back-to-Back** | Playing 2nd night of B2B | **Very High** | Game schedule |
| **3-in-4 nights** | 3 games in 4 days | **High** | Game schedule |
| **Home/Road Streak** | Consecutive home or away games | **Medium** | Game schedule |

**Why Critical**: 
- Teams on 2nd night of back-to-back win ~42-45% (vs 50% baseline) ❌
- Win rate drops 5-8% when fatigued ❌
- Third period performance degrades significantly ❌

**How to Get**:
```python
# Calculate from game schedule
def calculate_rest_days(game_date, team_id, all_games):
    previous_game = find_previous_game(team_id, game_date, all_games)
    if previous_game:
        return (game_date - previous_game.date).days
    return None

def is_back_to_back(game_date, team_id, all_games):
    return calculate_rest_days(game_date, team_id, all_games) == 1
```

---

### 2. Travel Distance ❌ IMPORTANT
| Feature | Description | Impact | Data Needed |
|---------|-------------|--------|-------------|
| **Miles Traveled** | Distance since last game | **High** | Venue locations + schedule |
| **Time Zones Crossed** | TZ changes since last game | **High** | Venue time zones |
| **Road Trip Length** | Consecutive away games | **Medium** | Game schedule |
| **Cross-Country Travel** | East ↔ West coast trips | **High** | Venue locations |

**Why Important**:
- Long travel (especially eastward) reduces win % by 3-5% ❌
- First game after crossing 2+ time zones is worst ❌
- West Coast → East Coast is hardest travel ❌

**How to Get**:
```python
# Venue location database needed
VENUE_LOCATIONS = {
    "TD Garden": {"city": "Boston", "lat": 42.36, "lon": -71.06, "tz": "America/New_York"},
    "Scotiabank Arena": {"city": "Toronto", "lat": 43.64, "lon": -79.38, "tz": "America/Toronto"},
    # ... all 32 arenas
}

from geopy.distance import geodesic

def calculate_travel_distance(game1_venue, game2_venue):
    loc1 = VENUE_LOCATIONS[game1_venue]
    loc2 = VENUE_LOCATIONS[game2_venue]
    return geodesic((loc1['lat'], loc1['lon']), (loc2['lat'], loc2['lon'])).miles
```

---

### 3. Goalie Starter Confirmation ❌ VERY IMPORTANT
| Feature | Description | Impact | Data Needed |
|---------|-------------|--------|-------------|
| **Confirmed Starter** | Who's starting in net | **Very High** | Lineup announcements |
| **Backup vs Starter** | Is backup starting? | **Very High** | Team depth charts |
| **Goalie Rest Days** | Days since goalie's last start | **High** | Goalie game logs |
| **Goalie vs Team History** | Starter's stats vs opponent | **Medium** | Historical matchups |

**Why Critical**:
- Backup goalies have ~5-10% lower win rate ❌
- Lines shift significantly when backup confirmed ❌
- Starter confirmation usually comes 1-3 hours before game ❌

**Current Issue**: 
- We collect goalie stats AFTER game ✅
- We DON'T know who's starting BEFORE game ❌

**How to Get**:
```python
# Need to scrape:
# 1. Team websites (lineup announcements)
# 2. NHL.com/Twitter official lineups
# 3. LeftWingLock.com or DailyFaceoff.com
# 4. Beat writers on Twitter

def fetch_confirmed_starter(game_id, team_id):
    # Check official sources
    # Returns: player_id of confirmed starter or None
    pass
```

---

### 4. Team Roster Composition ❌ IMPORTANT
| Feature | Description | Impact | Data Needed |
|---------|-------------|--------|-------------|
| **Injuries/Scratches** | Key players out | **High** | Injury reports |
| **Roster Stability** | Lineup consistency | **Medium** | Daily lineups |
| **Line Combinations** | Which players play together | **Medium** | Line matching data |
| **Average Age** | Team age | **Low** | Player birthdates (we have!) |
| **Average TOI** | Ice time distribution | **Medium** | Shifts data (we have!) |

**Why Important**:
- Star player injuries shift lines by 5-15% ❌
- Roster turnover impacts chemistry ❌
- Line matching (e.g., shutdown D vs top line) matters ❌

**Partial Collection**:
- We have player birthdates ✅
- We have TOI from shifts ✅
- Missing injury status ❌
- Missing scratches ❌

---

### 5. Head-to-Head History ❌ USEFUL
| Feature | Description | Impact | Data Needed |
|---------|-------------|--------|-------------|
| **H2H Win Rate** | Win % vs opponent | **Medium** | Historical games |
| **H2H Goals For/Against** | Scoring vs opponent | **Medium** | Historical games |
| **Recent H2H** | Last 3-5 matchups | **Medium** | Historical games |
| **Divisional Rival** | Same division? | **Low** | Team divisions |

**Why Useful**:
- Some teams match up better vs others (style) ⚠️
- Divisional familiarity matters slightly ⚠️
- Impact is modest vs other features ⚠️

**How to Calculate**:
```python
# Can calculate from existing data!
def get_h2h_stats(team_a_id, team_b_id, games_df):
    h2h = games_df[
        ((games_df['home_team_id'] == team_a_id) & (games_df['away_team_id'] == team_b_id)) |
        ((games_df['home_team_id'] == team_b_id) & (games_df['away_team_id'] == team_a_id))
    ]
    return {
        'games_played': len(h2h),
        'team_a_wins': len(h2h[h2h['winning_team_id'] == team_a_id]),
        'avg_goals_for': h2h[h2h['home_team_id'] == team_a_id]['home_score'].mean()
    }
```

---

### 6. Betting Market Data ❌ ADVANCED
| Feature | Description | Impact | Data Needed |
|---------|-------------|--------|-------------|
| **Opening Line** | Initial spread/ML | **High** | Sportsbook APIs |
| **Closing Line** | Final pre-game line | **Very High** | Sportsbook APIs |
| **Line Movement** | How line shifted | **High** | Odds history |
| **Public Betting %** | % of bets on each side | **Medium** | Action Network |
| **Sharp Money** | Pro bettor positions | **High** | Premium services |

**Why Advanced**:
- Closing line is BEST predictor (incorporates all info) ❌
- Line movement reveals sharp action ❌
- Can be used as "wisdom of crowds" feature ❌

**How to Get**:
- Odds API (we researched this!) ✅
- TheOddsAPI.com or SportsDataIO ✅
- Historical odds archives ✅

---

### 7. Situational Factors ❌ MINOR
| Feature | Description | Impact | Data Needed |
|---------|-------------|--------|-------------|
| **Playoff Implications** | Fighting for playoff spot | **Medium** | Standings |
| **Playoff Clinched** | Team already in playoffs | **Low** | Standings |
| **Trade Deadline Impact** | Major trades/acquisitions | **Low** | Transaction data |
| **Coaching Change** | New coach bump | **Low** | Coaching changes |

---

## 📊 Feature Importance Ranking (Literature + Experience)

### Tier 1: Critical (Must Have) 🔴
1. **Rolling advanced metrics** (Corsi, Fenwick, xG) - ✅ HAVE
2. **Goalie save %** (L3, L10) - ✅ HAVE
3. **Rest days / Back-to-backs** - ❌ MISSING
4. **Home/Away** - ✅ HAVE
5. **Confirmed starting goalie** - ❌ MISSING

### Tier 2: Very Important (Significant Edge) 🟠
6. **Travel distance / time zones** - ❌ MISSING
7. **Power play / Penalty kill %** - ✅ HAVE
8. **Closing betting line** - ❌ MISSING
9. **Goals for/against (L10)** - ✅ HAVE
10. **High danger chances** - ✅ HAVE

### Tier 3: Important (Measurable Impact) 🟡
11. **Injuries to key players** - ❌ MISSING
12. **Shots for/against** - ✅ HAVE
13. **Head-to-head history** - ⚠️ CAN CALCULATE
14. **3-in-4 nights fatigue** - ❌ MISSING
15. **Road trip length** - ❌ MISSING

### Tier 4: Useful (Small Edge) 🟢
16. **Faceoff win %** - ✅ HAVE
17. **Hits / Blocks** - ✅ HAVE
18. **Playoff implications** - ❌ MISSING
19. **Line movement** - ❌ MISSING
20. **Plus/minus trends** - ✅ HAVE

---

## 🎯 Feature Collection Roadmap

### Phase 1: Quick Wins (Can Calculate Now)
- [x] Advanced shot metrics (Corsi, Fenwick, HDC)
- [x] Rolling windows (L3, L10)
- [x] Goalie stats aggregation
- [ ] **Head-to-head history** (from existing games)
- [ ] **Win streaks / losing streaks** (from existing games)
- [ ] **Home/away splits** (from existing games)

### Phase 2: Schedule-Based Features (Medium Effort)
- [ ] **Rest days calculation** (need to parse game schedule)
- [ ] **Back-to-back detection** (from schedule)
- [ ] **3-in-4 detection** (from schedule)
- [ ] **Home/road streak** (from schedule)

### Phase 3: External Data (Higher Effort)
- [ ] **Travel distance** (need venue lat/lon database)
- [ ] **Time zone crossings** (need venue time zones)
- [ ] **Confirmed starters** (scrape team websites/Twitter)
- [ ] **Injury reports** (scrape NHL injury reports)

### Phase 4: Market Data (Requires API)
- [ ] **Betting lines** (Odds API integration)
- [ ] **Line movement** (Historical odds)
- [ ] **Public betting %** (Action Network API)

---

## 💻 Implementation Examples

### Example 1: Add Rest Days
```python
# Add to build_training_dataset.py

def calculate_team_rest_days(games_df):
    """Calculate rest days for each team in each game"""
    
    # Create team game history
    home_games = games_df[['game_date', 'home_team_id']].rename(
        columns={'home_team_id': 'team_id'}
    )
    away_games = games_df[['game_date', 'away_team_id']].rename(
        columns={'away_team_id': 'team_id'}
    )
    all_team_games = pd.concat([home_games, away_games]).sort_values('game_date')
    
    # Calculate days since last game
    all_team_games['prev_game_date'] = all_team_games.groupby('team_id')['game_date'].shift(1)
    all_team_games['rest_days'] = (
        all_team_games['game_date'] - all_team_games['prev_game_date']
    ).dt.days
    
    return all_team_games

# Add to feature query:
"""
SELECT 
    ...existing features...,
    home_rest.rest_days as home_rest_days,
    away_rest.rest_days as away_rest_days,
    CASE WHEN home_rest.rest_days = 1 THEN 1 ELSE 0 END as home_back_to_back,
    CASE WHEN away_rest.rest_days = 1 THEN 1 ELSE 0 END as away_back_to_back
FROM ...
"""
```

### Example 2: Add Travel Distance
```python
# Create venue database
VENUES = {
    "TD Garden": {"city": "Boston", "lat": 42.366178, "lon": -71.062195},
    "Scotiabank Arena": {"city": "Toronto", "lat": 43.643466, "lon": -79.379184},
    "Bell Centre": {"city": "Montreal", "lat": 45.496111, "lon": -73.569444},
    # ... all 32 arenas
}

from geopy.distance import geodesic

def add_travel_distance(games_df):
    # Get previous game venue for each team
    games_df['home_prev_venue'] = games_df.groupby('home_team_id')['venue'].shift(1)
    games_df['away_prev_venue'] = games_df.groupby('away_team_id')['venue'].shift(1)
    
    # Calculate distance
    def calc_dist(venue1, venue2):
        if pd.isna(venue1) or pd.isna(venue2):
            return None
        loc1 = VENUES.get(venue1, {})
        loc2 = VENUES.get(venue2, {})
        if not loc1 or not loc2:
            return None
        return geodesic(
            (loc1['lat'], loc1['lon']), 
            (loc2['lat'], loc2['lon'])
        ).miles
    
    games_df['away_travel_miles'] = games_df.apply(
        lambda x: calc_dist(x['away_prev_venue'], x['venue']), axis=1
    )
    
    return games_df
```

### Example 3: Confirmed Starter (Placeholder)
```python
# This requires real-time data scraping
def get_confirmed_starter(game_id, team_id, game_date):
    """
    Fetch confirmed starting goalie from:
    1. NHL.com lineup announcements
    2. Team Twitter accounts
    3. LeftWingLock.com
    4. DailyFaceoff.com
    """
    
    # Check if game is within 4 hours
    time_to_game = (game_date - datetime.now()).total_seconds() / 3600
    if time_to_game > 4:
        return None  # Too early for confirmation
    
    # Scrape lineup sources
    starter_id = scrape_lineup_sources(game_id, team_id)
    
    # If confirmed, return goalie stats
    if starter_id:
        goalie_recent_stats = get_goalie_rolling_stats(starter_id)
        return {
            'starter_id': starter_id,
            'starter_save_pct_l5': goalie_recent_stats['save_pct_l5'],
            'is_backup': goalie_recent_stats['is_backup']
        }
    
    return None
```

---

## 📈 Feature Engineering Ideas

### Derived Features (Can Create from Existing Data)

1. **Corsi Differential**
```python
home_corsi_diff = home_corsi_for_l10 - home_corsi_against_l10
away_corsi_diff = away_corsi_for_l10 - away_corsi_against_l10
matchup_corsi_advantage = home_corsi_diff - away_corsi_diff
```

2. **Goal Efficiency**
```python
home_shooting_pct = home_goals_l10 / home_shots_l10
away_shooting_pct = away_goals_l10 / away_shots_l10
```

3. **Expected Goals (xG) Approximation**
```python
# Simple xG: weight shot types by danger
xG = (high_danger_chances * 0.25) + (shots - high_danger_chances) * 0.08
```

4. **Momentum Features**
```python
# Trend: Are they improving or declining?
home_corsi_l3 - home_corsi_l10  # Positive = hot streak
```

5. **Situational Strength**
```python
# Power play opportunity advantage
pp_advantage = (home_pp_pct - away_pk_pct) - (away_pp_pct - home_pk_pct)
```

---

## 🎯 Priority Action Items

### IMMEDIATE (This Week)
1. ✅ Verify all existing features are calculated correctly
2. ✅ Add feature correlation analysis
3. [ ] Calculate head-to-head history from existing games
4. [ ] Add win streak features

### SHORT-TERM (Next 2 Weeks)
5. [ ] **Implement rest days calculation** ⭐ CRITICAL
6. [ ] **Detect back-to-backs** ⭐ CRITICAL
7. [ ] Create venue lat/lon database
8. [ ] Calculate travel distances

### MEDIUM-TERM (Next Month)
9. [ ] Scrape confirmed goalie starters
10. [ ] Integrate betting lines API (Odds API)
11. [ ] Add injury tracking (NHL.com scraper)
12. [ ] Build goalie-specific features

### LONG-TERM (Next Quarter)
13. [ ] Line matching analysis (which lines play together)
14. [ ] Player network effects (chemistry)
15. [ ] Situational win probability models
16. [ ] Real-time feature updates (live betting)

---

## 📊 Expected Model Improvement

Based on literature and industry benchmarks:

| Feature Addition | Expected Accuracy Gain |
|------------------|----------------------|
| **Baseline (Corsi, Fenwick, Shots, Goals)** | 55-57% |
| **+ Rest days / Back-to-backs** | +2-3% → 58-60% |
| **+ Travel distance** | +1-2% → 59-61% |
| **+ Confirmed starters** | +1-2% → 60-62% |
| **+ Betting lines (closing)** | +2-3% → 62-65% |
| **+ Injury information** | +1% → 63-66% |

**Goal**: 60-65% accuracy is professional-grade for NHL betting models.

---

## 🔗 Data Sources for Missing Features

### Rest & Travel
- **NHL Schedule API**: `https://api-web.nhle.com/v1/schedule/{date}`
- **Team schedules**: Available in your existing data
- **Venue locations**: Build database from NHL.com

### Goalie Starters
- **DailyFaceoff**: `https://www.dailyfaceoff.com/teams/`
- **LeftWingLock**: `https://leftwinglock.com/starting-goalies/`
- **NHL Twitter**: Official team accounts
- **RotoBaller**: Goalie news

### Injuries
- **NHL Injury Report**: `https://www.nhl.com/news/`
- **CapFriendly**: `https://www.capfriendly.com/` (RIP, but archive exists)
- **DailyFaceoff Injuries**: Updated daily

### Betting Lines
- **The Odds API**: `https://the-odds-api.com/`
- **SportsDataIO**: `https://sportsdata.io/nhl-api`
- **Action Network**: Public betting percentages

---

## ✅ Summary

**We Currently Have (Strong Foundation):**
- ✅ Advanced shot metrics (Corsi, Fenwick, HDC)
- ✅ Goalie performance stats
- ✅ Rolling windows (L3, L10)
- ✅ Special teams efficiency
- ✅ Home/away context
- ✅ Complete play-by-play data

**Critical Gaps to Fill:**
- ❌ Rest days & back-to-back detection (PRIORITY #1)
- ❌ Travel distance & time zones (PRIORITY #2)
- ❌ Confirmed starting goalies (PRIORITY #3)
- ❌ Betting market data (PRIORITY #4)
- ❌ Injury reports (PRIORITY #5)

**Next Steps:**
1. Implement rest day calculation (2-3 hours work)
2. Build venue location database (1-2 hours)
3. Add travel distance features (2-3 hours)
4. Research goalie starter scraping options (4-6 hours)

This will take us from a good foundation to a professional-grade prediction model! 🚀
