# Data Model Documentation

This document provides a comprehensive overview of the database schema for the Multi-Sport Betting System.

**Database:** DuckDB (`data/nhlstats.duckdb`)

---

## Table of Contents

1. [Entity Relationship Overview](#entity-relationship-overview)
2. [Core Game Tables](#core-game-tables)
3. [NHL-Specific Tables](#nhl-specific-tables)
4. [Betting & Market Tables](#betting--market-tables)
5. [Feature Engineering Tables](#feature-engineering-tables)
6. [Indexes](#indexes)
7. [Data Quality Notes](#data-quality-notes)

---

## Entity Relationship Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CORE RELATIONSHIPS                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────┐         ┌──────────────┐         ┌───────────────┐                │
│  │  teams   │◄────────│    games     │────────►│   players     │                │
│  │  (51)    │         │   (6,297)    │         │   (2,295)     │                │
│  └────┬─────┘         └──────┬───────┘         └───────┬───────┘                │
│       │                      │                         │                         │
│       │         ┌────────────┼────────────┐            │                         │
│       │         │            │            │            │                         │
│       │         ▼            ▼            ▼            │                         │
│       │  ┌──────────┐ ┌──────────┐ ┌──────────────┐    │                         │
│       └──│game_team │ │play_evts │ │player_shifts │◄───┘                         │
│          │_stats(0) │ │(1.5M)    │ │  (3.4M)      │                              │
│          └──────────┘ └──────────┘ └──────────────┘                              │
│                                           │                                      │
│                                           ▼                                      │
│                                    ┌──────────────┐                              │
│                                    │player_game   │                              │
│                                    │_stats(195K)  │                              │
│                                    └──────────────┘                              │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                         UNIFIED GAMES LAYER                                │ │
│  │  ┌──────────────┐                                                          │ │
│  │  │unified_games │◄──── game_odds (FK)                                      │ │
│  │  │   (85,610)   │                                                          │ │
│  │  └──────┬───────┘                                                          │ │
│  │         │ Aggregates from:                                                 │ │
│  │         ├── games (NHL)         ├── nba_games (706)                        │ │
│  │         ├── mlb_games (14,518)  ├── nfl_games (1,421)                      │ │
│  │         ├── ncaab_games (25,773)├── wncaab_games (6,982)                   │ │
│  │         ├── epl_games (1,730)   ├── ligue1_games (1,534)                   │ │
│  │         └── tennis_games (25,723)                                          │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                         BETTING LAYER                                      │ │
│  │  ┌─────────────────┐    ┌─────────────┐    ┌──────────────────────────┐    │ │
│  │  │bet_recommendations│──►│ placed_bets │    │portfolio_value_snapshots│    │ │
│  │  │      (115)       │    │    (26)     │    │          (6)            │    │ │
│  │  └─────────────────┘    └─────────────┘    └──────────────────────────┘    │ │
│  │                                                                            │ │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐              │ │
│  │  │kalshi_markets │  │ kalshi_trades │  │kalshi_candlesticks│              │ │
│  │  │    (6,398)    │  │   (11M)       │  │       (16)        │              │ │
│  │  └───────────────┘  └───────────────┘  └───────────────────┘              │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Game Tables

### `unified_games` ⭐ (Central Multi-Sport Table)
**Purpose:** Normalized view of all games across sports for unified querying.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `game_id` | VARCHAR | **PK** | Unique game identifier (format varies by sport) |
| `sport` | VARCHAR | NOT NULL | Sport code: NHL, NBA, MLB, NFL, NCAAB, WNCAAB, EPL, LIGUE1, TENNIS |
| `game_date` | DATE | NOT NULL | Date of the game |
| `season` | INTEGER | | Season year or formatted season (e.g., 2021, 20212022) |
| `status` | VARCHAR | | Game status (Final, OFF, scheduled, etc.) |
| `home_team_id` | VARCHAR | | Home team identifier |
| `home_team_name` | VARCHAR | | Full home team name |
| `away_team_id` | VARCHAR | | Away team identifier |
| `away_team_name` | VARCHAR | | Full away team name |
| `home_score` | INTEGER | | Final home score |
| `away_score` | INTEGER | | Final away score |
| `commence_time` | TIMESTAMP | | Game start time (UTC) |
| `venue` | VARCHAR | | Venue name |
| `loaded_at` | TIMESTAMP | | ETL timestamp |

**Indexes:** `idx_unified_games_date`, `idx_unified_games_sport`
**Row Count:** 85,610

---

### `games` (NHL Games - Detailed)
**Purpose:** Detailed NHL game data with full metadata.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `game_id` | VARCHAR | **PK** | NHL game ID (e.g., 2021020031) |
| `season` | INTEGER | NOT NULL | Season in YYYYYYYY format (e.g., 20212022) |
| `game_type` | INTEGER | NOT NULL | 1=Preseason, 2=Regular, 3=Playoffs |
| `game_date` | DATE | NOT NULL | Date of game |
| `start_time_utc` | TIMESTAMP | | Scheduled start time |
| `venue` | VARCHAR | | Arena name |
| `venue_location` | VARCHAR | | City |
| `home_team_id` | INTEGER | NOT NULL | Team ID (FK to teams) |
| `home_team_abbrev` | VARCHAR | NOT NULL | 3-letter abbreviation |
| `home_team_name` | VARCHAR | NOT NULL | Full team name |
| `away_team_id` | INTEGER | NOT NULL | Team ID (FK to teams) |
| `away_team_abbrev` | VARCHAR | NOT NULL | 3-letter abbreviation |
| `away_team_name` | VARCHAR | NOT NULL | Full team name |
| `home_score` | INTEGER | | Final home score |
| `away_score` | INTEGER | | Final away score |
| `winning_team_id` | INTEGER | | Winner's team ID |
| `losing_team_id` | INTEGER | | Loser's team ID |
| `game_outcome_type` | VARCHAR | | REG, OT, SO |
| `game_state` | VARCHAR | | OFF=completed, LIVE, FUT |
| `period_count` | INTEGER | | Number of periods played |
| `loaded_at` | TIMESTAMP | | ETL timestamp |

**Indexes:** `idx_games_date`, `idx_games_season`, `idx_games_home_team`, `idx_games_away_team`
**Row Count:** 6,297

---

### Sport-Specific Game Tables

#### `nba_games`
| Column | Type | Description |
|--------|------|-------------|
| `game_id` | VARCHAR (PK) | NBA game ID |
| `game_date` | DATE | |
| `season` | VARCHAR | Format: "2024-2025" |
| `game_status` | VARCHAR | Final, etc. |
| `home_team_id` | INTEGER | NBA team ID |
| `away_team_id` | INTEGER | NBA team ID |
| `home_team_name` | VARCHAR | |
| `away_team_name` | VARCHAR | |
| `home_score` | INTEGER | |
| `away_score` | INTEGER | |

**Row Count:** 706

#### `mlb_games`
| Column | Type | Description |
|--------|------|-------------|
| `game_id` | INTEGER (PK) | MLB game ID |
| `game_date` | DATE | |
| `season` | INTEGER | |
| `game_type` | VARCHAR | R=Regular, P=Playoff |
| `home_team` | VARCHAR | Team name |
| `away_team` | VARCHAR | Team name |
| `home_score` | INTEGER | |
| `away_score` | INTEGER | |
| `status` | VARCHAR | Final |

**Row Count:** 14,518

#### `nfl_games`
| Column | Type | Description |
|--------|------|-------------|
| `game_id` | VARCHAR (PK) | Format: "2021_01_DAL_TB" |
| `game_date` | DATE | |
| `season` | INTEGER | |
| `week` | INTEGER | Week number |
| `game_type` | VARCHAR | REG, POST |
| `home_team` | VARCHAR | 2-3 letter code |
| `away_team` | VARCHAR | 2-3 letter code |
| `home_score` | INTEGER | |
| `away_score` | INTEGER | |
| `status` | VARCHAR | |

**Row Count:** 1,421

#### `ncaab_games`
| Column | Type | Description |
|--------|------|-------------|
| `game_id` | VARCHAR (PK) | Format: "NCAAB_YYYY-MM-DD_Home_Away" |
| `game_date` | DATE | |
| `season` | INTEGER | Ending year of season |
| `home_team` | VARCHAR | Team name (underscores for spaces) |
| `away_team` | VARCHAR | Team name |
| `home_score` | INTEGER | |
| `away_score` | INTEGER | |
| `is_neutral` | BOOLEAN | Neutral site game |

**Row Count:** 25,773

#### `wncaab_games`
| Column | Type | Description |
|--------|------|-------------|
| `game_id` | VARCHAR (PK) | |
| `game_date` | DATE | |
| `season` | INTEGER | |
| `home_team` | VARCHAR | |
| `away_team` | VARCHAR | |
| `home_score` | INTEGER | |
| `away_score` | INTEGER | |
| `neutral_site` | BOOLEAN | |
| `home_win` | BOOLEAN | Derived field |

**Row Count:** 6,982

#### `epl_games` (English Premier League)
| Column | Type | Description |
|--------|------|-------------|
| `game_id` | VARCHAR (PK) | Format: "EPL_YYYY-MM-DD_Home_Away" |
| `game_date` | DATE | |
| `season` | VARCHAR | Format: "2526" |
| `home_team` | VARCHAR | Team name |
| `away_team` | VARCHAR | Team name |
| `home_score` | INTEGER | |
| `away_score` | INTEGER | |
| `result` | VARCHAR | H=Home, A=Away, D=Draw |

**Row Count:** 1,730

#### `ligue1_games` (French Ligue 1)
| Column | Type | Description |
|--------|------|-------------|
| `game_date` | DATE | |
| `season` | INTEGER | |
| `home_team` | VARCHAR | |
| `away_team` | VARCHAR | |
| `home_score` | INTEGER | |
| `away_score` | INTEGER | |
| `result` | VARCHAR | H, A, D |

**Row Count:** 1,534

#### `tennis_games`
| Column | Type | Description |
|--------|------|-------------|
| `game_date` | DATE | |
| `winner` | VARCHAR | Player name |
| `loser` | VARCHAR | Player name |
| `tournament` | VARCHAR | Tournament name |
| `tour` | VARCHAR | ATP, WTA |
| `round` | VARCHAR | 1st Round, Final, etc. |
| `winner_rank` | INTEGER | World ranking |
| `loser_rank` | INTEGER | World ranking |

**Row Count:** 25,723

---

## NHL-Specific Tables

### `teams`
**Purpose:** NHL team reference data.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `team_id` | INTEGER | **PK** | NHL team ID |
| `team_abbrev` | VARCHAR | NOT NULL | 3-letter code (EDM, BOS) |
| `team_name` | VARCHAR | NOT NULL | Full name (Edmonton Oilers) |
| `team_common_name` | VARCHAR | | Short name (Oilers) |
| `last_updated` | TIMESTAMP | | |

**Row Count:** 51

---

### `players`
**Purpose:** NHL player biographical data.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `player_id` | INTEGER | **PK** | NHL player ID |
| `first_name` | VARCHAR | | |
| `last_name` | VARCHAR | | |
| `sweater_number` | INTEGER | | Jersey number |
| `position_code` | VARCHAR | | C, LW, RW, D, G |
| `shoots_catches` | VARCHAR | | L, R |
| `height_in_inches` | INTEGER | | |
| `weight_in_pounds` | INTEGER | | |
| `birth_date` | DATE | | |
| `birth_city` | VARCHAR | | |
| `birth_country` | VARCHAR | | |
| `last_updated` | TIMESTAMP | | |

**Row Count:** 2,295
**Note:** Many player records have NULL biographical data.

---

### `player_game_stats`
**Purpose:** Per-game statistics for each player.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `game_id` | VARCHAR | **PK** | FK to games |
| `player_id` | INTEGER | **PK** | FK to players |
| `team_id` | INTEGER | NOT NULL | FK to teams |
| `position` | VARCHAR | | |
| `goals` | INTEGER | | |
| `assists` | INTEGER | | |
| `points` | INTEGER | | |
| `plus_minus` | INTEGER | | |
| `shots` | INTEGER | | |
| `hits` | INTEGER | | |
| `blocked_shots` | INTEGER | | |
| `pim` | INTEGER | | Penalty minutes |
| `toi_seconds` | INTEGER | | Time on ice |
| `power_play_goals` | INTEGER | | |
| `power_play_points` | INTEGER | | |
| `shorthanded_goals` | INTEGER | | |
| `game_winning_goals` | INTEGER | | |
| `faceoff_wins` | INTEGER | | |
| `faceoff_attempts` | INTEGER | | |
| `shots_against` | INTEGER | | Goalies only |
| `goals_against` | INTEGER | | Goalies only |
| `saves` | INTEGER | | Goalies only |
| `save_pct` | DECIMAL(5,3) | | Goalies only |
| `shutout` | BOOLEAN | | |
| `toi_goalie_seconds` | INTEGER | | Goalies only |

**Indexes:** `idx_player_stats_game`, `idx_player_stats_player`
**Row Count:** 195,887

---

### `player_shifts`
**Purpose:** Detailed shift-by-shift data for NHL games.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `shift_id` | VARCHAR | **PK** | Composite: game_player_shift |
| `game_id` | VARCHAR | NOT NULL | FK to games |
| `player_id` | INTEGER | NOT NULL | FK to players |
| `team_id` | INTEGER | NOT NULL | FK to teams |
| `period` | INTEGER | NOT NULL | |
| `shift_number` | INTEGER | NOT NULL | Sequential within game |
| `start_time` | VARCHAR | NOT NULL | MM:SS format |
| `end_time` | VARCHAR | NOT NULL | MM:SS format |
| `duration` | VARCHAR | NOT NULL | MM:SS format |
| `event_number` | INTEGER | | |
| `event_description` | VARCHAR | | |

**Indexes:** `idx_shifts_game`, `idx_shifts_player`
**Row Count:** 3,442,897

---

### `play_events`
**Purpose:** Play-by-play events for NHL games.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `event_id` | INTEGER | **PK** | Event sequence number |
| `game_id` | VARCHAR | **PK** | FK to games |
| `period` | INTEGER | NOT NULL | |
| `period_type` | VARCHAR | | REG, OT |
| `time_in_period` | VARCHAR | | MM:SS |
| `time_remaining` | VARCHAR | | MM:SS |
| `sort_order` | INTEGER | | |
| `type_code` | INTEGER | NOT NULL | Event type code |
| `type_desc_key` | VARCHAR | NOT NULL | goal, shot-on-goal, faceoff, etc. |
| `event_owner_team_id` | INTEGER | | |
| `scoring_player_id` | INTEGER | | For goals |
| `assist1_player_id` | INTEGER | | |
| `assist2_player_id` | INTEGER | | |
| `shot_type` | VARCHAR | | wrist, slap, etc. |
| `penalty_player_id` | INTEGER | | |
| `penalty_type` | VARCHAR | | |
| `penalty_duration` | INTEGER | | Minutes |
| `x_coord` | INTEGER | | Rink coordinates |
| `y_coord` | INTEGER | | Rink coordinates |
| `zone_code` | VARCHAR | | O, N, D |
| `home_team_defending_side` | VARCHAR | | left, right |
| `away_score` | INTEGER | | Score at event time |
| `home_score` | INTEGER | | Score at event time |

**Indexes:** `idx_events_game`, `idx_events_type`
**Row Count:** 1,537,181

---

### `game_team_stats`
**Purpose:** Aggregated team-level statistics per game.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `game_id` | VARCHAR | **PK** | FK to games |
| `team_id` | INTEGER | **PK** | FK to teams |
| `is_home` | BOOLEAN | NOT NULL | |
| `goals` | INTEGER | | |
| `shots` | INTEGER | | |
| `blocked_shots` | INTEGER | | |
| `power_play_goals` | INTEGER | | |
| `power_play_opportunities` | INTEGER | | |
| `power_play_pct` | DECIMAL(5,2) | | |
| `penalty_kill_pct` | DECIMAL(5,2) | | |
| `pim` | INTEGER | | Penalty minutes |
| `faceoff_win_pct` | DECIMAL(5,2) | | |
| `hits` | INTEGER | | |

**Row Count:** 0 (not populated)

---

## Betting & Market Tables

### `bet_recommendations`
**Purpose:** Generated betting recommendations from Elo model.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `bet_id` | VARCHAR | **PK** | Unique ID: sport_date_idx_teams |
| `sport` | VARCHAR | NOT NULL | nba, nhl, mlb, nfl |
| `recommendation_date` | DATE | NOT NULL | |
| `home_team` | VARCHAR | NOT NULL | |
| `away_team` | VARCHAR | NOT NULL | |
| `bet_on` | VARCHAR | NOT NULL | home or away |
| `elo_prob` | DOUBLE | NOT NULL | Model probability |
| `market_prob` | DOUBLE | NOT NULL | Implied market probability |
| `edge` | DOUBLE | NOT NULL | elo_prob - market_prob |
| `confidence` | VARCHAR | NOT NULL | HIGH, MEDIUM |
| `yes_ask` | INTEGER | | Kalshi YES price (cents) |
| `no_ask` | INTEGER | | Kalshi NO price (cents) |
| `ticker` | VARCHAR | | Kalshi market ticker |
| `created_at` | TIMESTAMP | | |

**Index:** `idx_bet_recs_date_sport`
**Row Count:** 115

---

### `placed_bets`
**Purpose:** Actual bets placed on Kalshi.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `bet_id` | VARCHAR | **PK** | Kalshi-generated ID |
| `sport` | VARCHAR | | NBA, NHL, etc. |
| `placed_date` | DATE | | |
| `ticker` | VARCHAR | | Kalshi market ticker |
| `home_team` | VARCHAR | | |
| `away_team` | VARCHAR | | |
| `bet_on` | VARCHAR | | Team bet on |
| `side` | VARCHAR | | yes, no |
| `contracts` | INTEGER | | Number of contracts |
| `price_cents` | INTEGER | | Price per contract |
| `cost_dollars` | DOUBLE | | Total cost |
| `fees_dollars` | DOUBLE | | Transaction fees |
| `elo_prob` | DOUBLE | | Model probability at time of bet |
| `market_prob` | DOUBLE | | Market probability at time of bet |
| `edge` | DOUBLE | | Calculated edge |
| `confidence` | VARCHAR | | HIGH, MEDIUM |
| `status` | VARCHAR | | open, won, lost |
| `settled_date` | DATE | | |
| `payout_dollars` | DOUBLE | | |
| `profit_dollars` | DOUBLE | | |
| `created_at` | TIMESTAMP | | |

**Row Count:** 26

---

### `portfolio_value_snapshots`
**Purpose:** Hourly portfolio value tracking.

| Column | Type | Description |
|--------|------|-------------|
| `snapshot_hour_utc` | TIMESTAMP (PK) | Hour of snapshot |
| `balance_dollars` | DOUBLE | Cash balance |
| `portfolio_value_dollars` | DOUBLE | Value of open positions |
| `created_at_utc` | TIMESTAMP | |

**Row Count:** 6

---

### `kalshi_markets`
**Purpose:** Kalshi prediction market metadata.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `ticker` | VARCHAR | **PK** | Market ticker |
| `event_ticker` | VARCHAR | | Parent event |
| `status` | VARCHAR | | open, finalized |
| `yes_sub_title` | VARCHAR | | YES outcome label |
| `no_sub_title` | VARCHAR | | NO outcome label |
| `open_time` | TIMESTAMP | | Market open time |
| `close_time` | TIMESTAMP | | Market close time |
| `settlement_ts` | TIMESTAMP | | Settlement time |
| `result` | VARCHAR | | yes, no |
| `market_type` | VARCHAR | | binary |
| `retrieved_at` | TIMESTAMP | | |

**Row Count:** 6,398

---

### `kalshi_trades`
**Purpose:** Historical trade data from Kalshi markets.

| Column | Type | Description |
|--------|------|-------------|
| `trade_id` | VARCHAR (UNIQUE) | Trade UUID |
| `ticker` | VARCHAR | Market ticker |
| `yes_price` | INTEGER | Price in cents (1-99) |
| `no_price` | INTEGER | Price in cents (1-99) |
| `count` | BIGINT | Number of contracts |
| `count_fp` | VARCHAR | Fractional part |
| `taker_side` | VARCHAR | yes, no |
| `created_time` | TIMESTAMP | Trade timestamp |
| `retrieved_at` | TIMESTAMP | |

**Row Count:** 11,076,050

---

### `kalshi_candlesticks`
**Purpose:** OHLC price data for Kalshi markets.

| Column | Type | Description |
|--------|------|-------------|
| `market_ticker` | VARCHAR | |
| `period_interval` | INTEGER | Interval in minutes |
| `end_period_ts` | BIGINT | Unix timestamp |
| `price_open` | INTEGER | |
| `price_high` | INTEGER | |
| `price_low` | INTEGER | |
| `price_close` | INTEGER | |
| `price_mean` | INTEGER | |
| `price_previous` | INTEGER | |
| `volume` | BIGINT | |
| `open_interest` | BIGINT | |
| `retrieved_at` | TIMESTAMP | |

**Row Count:** 16

---

### `kalshi_decision_prices`
**Purpose:** Price snapshots at specific times before market close.

| Column | Type | Description |
|--------|------|-------------|
| `ticker` | VARCHAR (PK) | Market ticker |
| `decision_minutes_before_close` | INTEGER (PK) | Minutes before close |
| `decision_ts` | TIMESTAMP | |
| `trade_created_time` | TIMESTAMP | |
| `yes_price_dollars` | DOUBLE | |
| `no_price_dollars` | DOUBLE | |
| `retrieved_at` | TIMESTAMP | |

**Row Count:** 1,606

---

### `game_odds`
**Purpose:** Sportsbook odds for games.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `odds_id` | VARCHAR | **PK** | Composite ID |
| `game_id` | VARCHAR | NOT NULL | FK to unified_games |
| `bookmaker` | VARCHAR | NOT NULL | SBR, etc. |
| `market_name` | VARCHAR | NOT NULL | moneyline, spread, total |
| `outcome_name` | VARCHAR | | home, away, over, under |
| `price` | DECIMAL(10,4) | NOT NULL | Decimal odds |
| `line` | DECIMAL(10,4) | | Spread/total line |
| `last_update` | TIMESTAMP | | |
| `is_pregame` | BOOLEAN | | |
| `loaded_at` | TIMESTAMP | | |

**Indexes:** `idx_game_odds_game_id`, `idx_game_odds_bookmaker`
**Row Count:** 21,818

---

### `historical_betting_lines`
**Purpose:** Historical moneyline odds with open/close prices.

| Column | Type | Description |
|--------|------|-------------|
| `game_date` | DATE | |
| `home_team` | VARCHAR | Team abbreviation |
| `away_team` | VARCHAR | Team abbreviation |
| `home_ml_open` | FLOAT | Opening American odds |
| `home_ml_close` | FLOAT | Closing American odds |
| `away_ml_open` | FLOAT | |
| `away_ml_close` | FLOAT | |
| `home_implied_prob_open` | FLOAT | |
| `home_implied_prob_close` | FLOAT | |
| `away_implied_prob_open` | FLOAT | |
| `away_implied_prob_close` | FLOAT | |
| `line_movement` | FLOAT | Close - Open implied prob |
| `source` | VARCHAR | OddsPortal |
| `fetched_at` | TIMESTAMP | |

**Row Count:** 821

---

## Feature Engineering Tables

These tables contain pre-computed features for machine learning and analysis.

### `game_team_advanced_stats`
**Purpose:** Advanced analytics per game (Corsi, Fenwick, etc.).

| Column | Type | Description |
|--------|------|-------------|
| `game_id` | VARCHAR | |
| `game_date` | DATE | |
| `home_team_id` | INTEGER | |
| `away_team_id` | INTEGER | |
| `home_team_name` | VARCHAR | |
| `away_team_name` | VARCHAR | |
| `home_corsi_for` | BIGINT | Shot attempts for |
| `home_fenwick_for` | BIGINT | Unblocked shot attempts |
| `home_shots_for` | BIGINT | |
| `home_goals_for` | BIGINT | |
| `home_hd_chances_for` | BIGINT | High-danger chances |
| `home_corsi_against` | BIGINT | |
| `home_fenwick_against` | BIGINT | |
| `home_shots_against_from_plays` | BIGINT | |
| `home_goals_against` | BIGINT | |
| `home_save_pct` | DOUBLE | |
| `home_shots_against` | HUGEINT | |
| `away_*` | ... | Same stats for away team |
| `home_win` | INTEGER | 1=home win, 0=away win |

**Row Count:** 5,723

---

### `team_rolling_stats`
**Purpose:** Rolling window statistics (L3, L10 games).

| Column | Type | Description |
|--------|------|-------------|
| `game_id` | VARCHAR | |
| `game_date` | DATE | |
| `team_id` | INTEGER | |
| `corsi_for_l3` | DOUBLE | Last 3 games |
| `corsi_against_l3` | DOUBLE | |
| `fenwick_for_l3` | DOUBLE | |
| `fenwick_against_l3` | DOUBLE | |
| `shots_l3` | DOUBLE | |
| `goals_l3` | DOUBLE | |
| `hd_chances_l3` | DOUBLE | |
| `save_pct_l3` | DOUBLE | |
| `*_l10` | DOUBLE | Same stats for last 10 games |

**Row Count:** 11,446 (2 rows per game - home and away)

---

### `team_schedule_fatigue`
**Purpose:** Rest and schedule context.

| Column | Type | Description |
|--------|------|-------------|
| `game_id` | VARCHAR | |
| `team_id` | INTEGER | |
| `days_rest` | BIGINT | Days since last game |
| `is_back_to_back` | INTEGER | 1=yes |
| `is_3_in_4` | INTEGER | 3 games in 4 days |
| `is_4_in_6` | INTEGER | 4 games in 6 days |
| `is_home_game` | INTEGER | |
| `is_away_game` | INTEGER | |
| `just_came_home` | INTEGER | First home after road |
| `just_went_away` | INTEGER | First away after home |
| `back_to_backs_l10` | HUGEINT | Count in last 10 games |
| `is_well_rested` | INTEGER | 3+ days rest |
| `rest_advantage_raw` | BIGINT | Team rest - opponent rest |

**Row Count:** 11,446

---

### `team_momentum`
**Purpose:** Streak and rivalry context.

| Column | Type | Description |
|--------|------|-------------|
| `game_id` | VARCHAR | |
| `home_team_id` | INTEGER | |
| `away_team_id` | INTEGER | |
| `home_revenge_game` | INTEGER | Lost to this team recently |
| `home_division_rival` | INTEGER | |
| `home_conf_matchup` | INTEGER | Conference game |
| `home_win_streak` | INTEGER | Current streak length |
| `home_losing_streak` | INTEGER | |
| `away_*` | ... | Same for away team |

**Row Count:** 5,723

---

### `team_h2h_history`
**Purpose:** Head-to-head historical performance.

| Column | Type | Description |
|--------|------|-------------|
| `game_id` | VARCHAR | |
| `home_team_id` | INTEGER | |
| `away_team_id` | INTEGER | |
| `h2h_home_win_pct_all` | DOUBLE | All-time H2H |
| `h2h_home_win_pct_season` | DOUBLE | Current season H2H |
| `h2h_home_win_pct_l5` | DOUBLE | Last 5 H2H games |
| `h2h_home_avg_goals` | DOUBLE | |
| `h2h_home_avg_goals_against` | DOUBLE | |
| `h2h_games_count` | BIGINT | Total H2H games |
| `h2h_away_*` | ... | Same for away team perspective |

**Row Count:** 5,723

---

### `team_situational_context`
**Purpose:** Standings and playoff context.

| Column | Type | Description |
|--------|------|-------------|
| `game_id` | VARCHAR | |
| `home_team_id` | INTEGER | |
| `away_team_id` | INTEGER | |
| `game_date` | DATE | |
| `season` | INTEGER | |
| `home_points_pct` | FLOAT | Points percentage |
| `home_games_played` | BIGINT | |
| `home_league_rank` | BIGINT | Overall standing |
| `home_in_playoff_spot` | INTEGER | 1=in playoffs |
| `home_bubble_team` | INTEGER | On the bubble |
| `home_eliminated` | INTEGER | Mathematically eliminated |
| `away_*` | ... | Same for away team |
| `playoff_matchup_preview` | INTEGER | Both playoff teams |

**Row Count:** 5,794

---

### `betting_line_features`
**Purpose:** Betting line derived features.

| Column | Type | Description |
|--------|------|-------------|
| `game_id` | VARCHAR | |
| `game_date` | DATE | |
| `home_team_abbrev` | VARCHAR | |
| `away_team_abbrev` | VARCHAR | |
| `home_ml_close` | FLOAT | Closing moneyline |
| `away_ml_close` | FLOAT | |
| `home_implied_prob` | FLOAT | |
| `away_implied_prob` | FLOAT | |
| `home_favorite` | INTEGER | 1=home favored |
| `line_movement` | FLOAT | |
| `market_confidence` | FLOAT | |

**Row Count:** 5,723

---

### `team_season_stats`
**Purpose:** Season-to-date team statistics.

| Column | Type | Description |
|--------|------|-------------|
| `game_id` | VARCHAR | |
| `team_id` | INTEGER | |
| `is_home` | BOOLEAN | |
| `season_shooting_pct` | FLOAT | |
| `season_save_pct_approx` | FLOAT | |
| `season_pp_pct` | FLOAT | Power play % |
| `season_pk_pct` | DOUBLE | Penalty kill % |
| `season_faceoff_pct` | DOUBLE | |

**Row Count:** 0 (not populated)

---

## Indexes

| Table | Index Name | Columns |
|-------|------------|---------|
| bet_recommendations | idx_bet_recs_date_sport | recommendation_date, sport |
| play_events | idx_events_game | game_id |
| play_events | idx_events_type | type_desc_key |
| games | idx_games_away_team | away_team_id |
| games | idx_games_date | game_date |
| games | idx_games_home_team | home_team_id |
| games | idx_games_season | season |
| game_odds | idx_game_odds_bookmaker | bookmaker |
| game_odds | idx_game_odds_game_id | game_id |
| player_game_stats | idx_player_stats_game | game_id |
| player_game_stats | idx_player_stats_player | player_id |
| player_shifts | idx_shifts_game | game_id |
| player_shifts | idx_shifts_player | player_id |
| unified_games | idx_unified_games_date | game_date |
| unified_games | idx_unified_games_sport | sport |

---

## Data Quality Notes

### Empty Tables (Need Population)
- `game_team_stats` - 0 rows
- `team_season_stats` - 0 rows

### Tables with NULL/Missing Data
- `players` - Many biographical fields are NULL
- `betting_line_features` - ML columns often NULL for older games
- `team_rolling_stats` - NULL for early season games (no history)

### ID Format Inconsistencies
| Table | game_id Format |
|-------|---------------|
| games (NHL) | `2021020031` (numeric string) |
| nba_games | `0012400001` |
| mlb_games | `634642` (integer) |
| nfl_games | `2021_01_DAL_TB` |
| ncaab_games | `NCAAB_YYYY-MM-DD_Home_Away` |
| epl_games | `EPL_YYYY-MM-DD_Home_Away` |
| unified_games | `NHL_20211016_EDM_CGY` (normalized) |

### Foreign Key Relationships

```
game_odds.game_id → unified_games.game_id
game_team_stats.game_id → games.game_id
game_team_stats.team_id → teams.team_id
play_events.game_id → games.game_id
player_game_stats.game_id → games.game_id
player_game_stats.player_id → players.player_id
player_game_stats.team_id → teams.team_id
player_shifts.game_id → games.game_id
player_shifts.player_id → players.player_id
player_shifts.team_id → teams.team_id
```

---

## Summary Statistics

| Category | Tables | Total Rows |
|----------|--------|------------|
| Core Games | 10 | ~84,000 |
| NHL Detail | 5 | ~5.4M |
| Betting/Markets | 9 | ~11.1M |
| Features | 7 | ~51,000 |
| **Total** | **31** | **~16.6M** |

---

*Last Updated: 2026-01-20*
