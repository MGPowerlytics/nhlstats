# Database Schema Documentation

## Overview

The multi-sport betting system uses PostgreSQL as its primary database. This document describes all database tables, their relationships, and the DAG tasks that populate them.

Last Updated: 2026-01-24

## Table Summary

| Table Name | Description | Primary Key | Rows (approx) | DAG Producer Tasks |
|------------|-------------|-------------|---------------|-------------------|
| unified_games | Centralized game schedule for all sports | game_id | Varies by sport | {sport}_download_games, {sport}_load_bets_db |
| game_odds | Betting odds from various bookmakers | odds_id | Varies | {sport}_fetch_markets |
| placed_bets | Tracked bets placed on Kalshi/BetMGM | bet_id | Varies | {sport}_place_bets |
| portfolio_snapshots | Hourly portfolio value snapshots | snapshot_id | Hourly records | portfolio_hourly_snapshot |
| elo_ratings | Historical Elo ratings for teams/players | rating_id | Cumulative | {sport}_update_elo |
| bet_recommendations | Daily bet recommendations | recommendation_id | Daily | {sport}_identify_bets |

## Table Details

### unified_games
Centralized game schedule table storing games from all supported sports.

**Columns:**
- `game_id` (VARCHAR PRIMARY KEY): Unique identifier (e.g., NHL_20240120_LAK_BOS)
- `sport` (VARCHAR NOT NULL): Sport code (NHL, NBA, MLB, NCAAB, TENNIS, EPL, LIGUE1, NFL)
- `game_date` (DATE NOT NULL): Date of the game
- `season` (INTEGER): Season year (e.g., 2023 for 2023-2024 season)
- `status` (VARCHAR): Game status (Scheduled, Final, InProgress, Postponed, Cancelled)
- `home_team_id` (VARCHAR): Normalized team identifier
- `home_team_name` (VARCHAR): Human-readable home team name
- `away_team_id` (VARCHAR): Normalized team identifier
- `away_team_name` (VARCHAR): Human-readable away team name
- `home_score` (INTEGER): Home team final score (NULL if not played)
- `away_score` (INTEGER): Away team final score (NULL if not played)
- `commence_time` (TIMESTAMP): Original UTC start time
- `venue` (VARCHAR): Game venue/location
- `loaded_at` (TIMESTAMP DEFAULT CURRENT_TIMESTAMP): When record was loaded

**Indexes:**
- Index on `sport`, `game_date` for sport-specific queries
- Index on `home_team_id`, `away_team_id` for team lookups
- Index on `status` for filtering active games

**DAG Producers:**
- `{sport}_download_games`: Downloads game schedules from APIs
- `{sport}_load_bets_db`: Loads game data into database

### game_odds
Betting odds from various bookmakers (Kalshi, BetMGM, etc.).

**Columns:**
- `odds_id` (VARCHAR PRIMARY KEY): Unique identifier for odds record
- `game_id` (VARCHAR NOT NULL): Foreign key to unified_games
- `bookmaker` (VARCHAR NOT NULL): Odds source (Kalshi, BetMGM, DraftKings, SBR)
- `market_name` (VARCHAR NOT NULL): Market type (moneyline, spread, total)
- `outcome_name` (VARCHAR): Outcome (home_team_win, away_team_win, draw, over, under)
- `price` (DECIMAL(10,4) NOT NULL): Odds value (decimal format)
- `line` (DECIMAL(10,4)): Line for spread/total markets
- `last_update` (TIMESTAMP): When odds were last updated
- `is_pregame` (BOOLEAN DEFAULT TRUE): Whether odds are pre-game
- `loaded_at` (TIMESTAMP DEFAULT CURRENT_TIMESTAMP): When record was loaded
- `external_id` (VARCHAR): External ID from source system

**Foreign Keys:**
- `game_id` REFERENCES `unified_games`(`game_id`)

**Indexes:**
- Index on `game_id` for game lookups
- Index on `bookmaker`, `market_name` for source filtering
- Index on `last_update` for freshness checks

**DAG Producers:**
- `{sport}_fetch_markets`: Fetches odds from Kalshi/BetMGM APIs

### placed_bets
Tracked bets placed on prediction markets.

**Columns:**
- `bet_id` (VARCHAR PRIMARY KEY): Unique bet identifier
- `game_id` (VARCHAR): Associated game (nullable for non-game bets)
- `market_id` (VARCHAR NOT NULL): Market identifier from bookmaker
- `bookmaker` (VARCHAR NOT NULL): Kalshi or BetMGM
- `outcome` (VARCHAR NOT NULL): Bet outcome (YES/NO for Kalshi)
- `stake` (DECIMAL(10,2) NOT NULL): Amount wagered
- `odds` (DECIMAL(10,4) NOT NULL): Odds at bet placement
- `potential_payout` (DECIMAL(10,2)): Potential payout if win
- `status` (VARCHAR): Bet status (pending, win, loss, void)
- `result` (DECIMAL(10,2)): Actual payout (positive for win, negative for loss)
- `placed_time_utc` (TIMESTAMP): When bet was placed
- `market_title` (VARCHAR): Human-readable market title
- `market_close_time_utc` (TIMESTAMP): When market closes
- `opening_odds` (DECIMAL(10,4)): Opening odds for the market
- `created_at` (TIMESTAMP DEFAULT CURRENT_TIMESTAMP): Record creation time

**Foreign Keys:**
- `game_id` REFERENCES `unified_games`(`game_id`)

**Indexes:**
- Index on `placed_time_utc` for time-based queries
- Index on `status` for filtering active bets
- Index on `bookmaker`, `market_id` for bookmaker lookups

**DAG Producers:**
- `{sport}_place_bets`: Places bets based on recommendations
- `bet_sync_hourly`: Syncs bet status from bookmakers

### portfolio_snapshots
Hourly portfolio value tracking.

**Columns:**
- `snapshot_id` (SERIAL PRIMARY KEY): Auto-incrementing ID
- `snapshot_time` (TIMESTAMP NOT NULL): Time of snapshot
- `total_value` (DECIMAL(10,2) NOT NULL): Total portfolio value
- `cash_balance` (DECIMAL(10,2)): Available cash
- `invested_amount` (DECIMAL(10,2)): Amount in active bets
- `unrealized_pnl` (DECIMAL(10,2)): Unrealized profit/loss
- `realized_pnl` (DECIMAL(10,2)): Realized profit/loss
- `created_at` (TIMESTAMP DEFAULT CURRENT_TIMESTAMP): Record creation

**Indexes:**
- Index on `snapshot_time` for time series analysis

**DAG Producers:**
- `portfolio_hourly_snapshot`: Creates hourly portfolio snapshots

### elo_ratings
Historical Elo ratings for teams and players.

**Columns:**
- `rating_id` (SERIAL PRIMARY KEY): Auto-incrementing ID
- `sport` (VARCHAR NOT NULL): Sport code
- `entity_id` (VARCHAR NOT NULL): Team or player identifier
- `entity_name` (VARCHAR NOT NULL): Team or player name
- `rating` (DECIMAL(10,2) NOT NULL): Elo rating value
- `valid_from` (DATE NOT NULL): Date rating became effective
- `valid_to` (DATE): Date rating was superseded (NULL for current)
- `games_played` (INTEGER): Number of games played
- `created_at` (TIMESTAMP DEFAULT CURRENT_TIMESTAMP): Record creation

**Indexes:**
- Index on `sport`, `entity_id`, `valid_from` for current rating lookups
- Unique constraint on `sport`, `entity_id`, `valid_from`

**DAG Producers:**
- `{sport}_update_elo`: Updates Elo ratings after games

### bet_recommendations
Daily bet recommendations generated by the system.

**Columns:**
- `recommendation_id` (SERIAL PRIMARY KEY): Auto-incrementing ID
- `sport` (VARCHAR NOT NULL): Sport code
- `game_id` (VARCHAR): Associated game
- `market_id` (VARCHAR): Target market
- `recommendation_type` (VARCHAR): Type (moneyline, spread, total)
- `side` (VARCHAR): Recommended side (home, away, over, under)
- `confidence` (DECIMAL(5,4)): Confidence score (0-1)
- `edge` (DECIMAL(5,4)): Estimated edge over market
- `recommended_stake` (DECIMAL(10,2)): Recommended stake amount
- `expected_value` (DECIMAL(10,2)): Expected value
- `generated_at` (TIMESTAMP NOT NULL): When recommendation was generated
- `expires_at` (TIMESTAMP): When recommendation expires
- `status` (VARCHAR): Status (active, executed, expired, rejected)
- `created_at` (TIMESTAMP DEFAULT CURRENT_TIMESTAMP): Record creation

**Foreign Keys:**
- `game_id` REFERENCES `unified_games`(`game_id`)

**Indexes:**
- Index on `sport`, `generated_at` for recent recommendations
- Index on `status` for filtering active recommendations

**DAG Producers:**
- `{sport}_identify_bets`: Generates daily bet recommendations

---

## Wave-4 Tables: Historical Stats + Bet Reconciliation Audit

> Source of truth for all DDL below: `plugins/database_schema_manager.py`.
> For detailed column semantics see [docs/TEAM_GAME_STATS_SPEC.md](TEAM_GAME_STATS_SPEC.md).

### team_game_stats

Core cross-sport per-game team row. One row per team per game. All other sport
extension tables foreign-key back to this table.

**Purpose:** Unified home for game-level box-score data across all 9 leagues,
enabling cross-sport feature engineering for Elo and future ML models.

**Columns:**

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `game_id` | VARCHAR | NOT NULL | Matches `unified_games.game_id` |
| `sport` | VARCHAR | NOT NULL | NBA, NHL, MLB, NFL, EPL, Ligue1, NCAAB, WNCAAB, Tennis |
| `team` | VARCHAR | NOT NULL | Canonical team name |
| `opponent` | VARCHAR | NOT NULL | Canonical opponent name |
| `is_home` | BOOLEAN | NOT NULL | TRUE if home team |
| `game_date` | DATE | NOT NULL | Local date of game |
| `season` | VARCHAR | NOT NULL | e.g. "2023-24" or "2024" |
| `points_for` | INTEGER | YES | Goals/runs/points scored |
| `points_against` | INTEGER | YES | Goals/runs/points allowed |
| `won` | BOOLEAN | YES | TRUE if team won |
| `off_rating` | NUMERIC(6,2) | YES | Offensive rating (pts per 100 possessions; basketball) |
| `def_rating` | NUMERIC(6,2) | YES | Defensive rating (pts per 100 possessions; basketball) |
| `pace` | NUMERIC(6,2) | YES | Possessions per 48 min (basketball) |
| `margin` | INTEGER | YES | points_for − points_against |
| `created_at` | TIMESTAMP | NOT NULL | DEFAULT NOW() |
| `updated_at` | TIMESTAMP | NOT NULL | DEFAULT NOW(); updated on upsert |

**Primary Key:** `(game_id, team)`

**Foreign Keys:**
- `game_id` REFERENCES `unified_games(game_id)`

**Indexes:**
- `idx_tgs_sport_date ON (sport, game_date)`
- `idx_tgs_team_date ON (team, game_date)`
- `idx_tgs_sport_season ON (sport, season)`

**DAG Producers:**
- `fetch_stats_{sport}` tasks in `historical_stats_daily` DAG
- `scripts/backfill_team_game_stats.py` (one-shot historical backfill)

---

### nba_team_game_stats_ext

**Purpose:** NBA-specific advanced box-score metrics (shooting efficiency, playmaking).
Populated from `nba_api` (BoxScoreTraditionalV2 + BoxScoreAdvancedV2; free, public).

**Columns:**

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `game_id` | VARCHAR | NOT NULL | FK to `team_game_stats` |
| `team` | VARCHAR | NOT NULL | FK to `team_game_stats` |
| `fg_pct` | NUMERIC(5,4) | YES | Field goal percentage |
| `fg3m` | INTEGER | YES | 3-point field goals made |
| `fg3a` | INTEGER | YES | 3-point field goals attempted |
| `fg3_pct` | NUMERIC(5,4) | YES | 3-point percentage |
| `ast` | INTEGER | YES | Assists |
| `reb` | INTEGER | YES | Total rebounds |
| `oreb` | INTEGER | YES | Offensive rebounds |
| `dreb` | INTEGER | YES | Defensive rebounds |
| `stl` | INTEGER | YES | Steals |
| `blk` | INTEGER | YES | Blocks |
| `tov` | INTEGER | YES | Turnovers |
| `pf` | INTEGER | YES | Personal fouls |
| `ts_pct` | NUMERIC(5,4) | YES | True Shooting % |
| `efg_pct` | NUMERIC(5,4) | YES | Effective FG% |
| `usage_pct` | NUMERIC(5,4) | YES | Team usage rate proxy |

**Primary Key:** `(game_id, team)`
**Foreign Keys:** `(game_id, team)` REFERENCES `team_game_stats(game_id, team)`

---

### nhl_team_game_stats_ext

**Purpose:** NHL shots, special teams, and physical-play metrics.
Source: NHL Web API (`api-web.nhle.com`; free).

**Columns:**

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `game_id` | VARCHAR | NOT NULL | FK |
| `team` | VARCHAR | NOT NULL | FK |
| `shots` | INTEGER | YES | Total shot attempts |
| `sog` | INTEGER | YES | Shots on goal |
| `hits` | INTEGER | YES | Body checks |
| `blocks` | INTEGER | YES | Shots blocked |
| `pim` | INTEGER | YES | Penalty minutes |
| `faceoff_pct` | NUMERIC(5,4) | YES | Faceoff win % (decimal) |
| `pp_goals` | INTEGER | YES | Power-play goals |
| `pp_opportunities` | INTEGER | YES | Power-play opportunities |
| `pp_pct` | NUMERIC(5,4) | YES | Power-play % |
| `pk_goals_against` | INTEGER | YES | Short-handed goals allowed |
| `pk_opportunities` | INTEGER | YES | Penalty-kill opportunities faced |
| `pk_pct` | NUMERIC(5,4) | YES | Penalty-kill % |
| `shooting_pct` | NUMERIC(5,4) | YES | goals / sog |

**Primary Key:** `(game_id, team)`
**Foreign Keys:** `(game_id, team)` REFERENCES `team_game_stats(game_id, team)`

---

### mlb_team_game_stats_ext

**Purpose:** MLB batting and pitching box-score aggregates.
Source: MLB Stats API (`statsapi.mlb.com`; free).

**Columns:**

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `game_id` | VARCHAR | NOT NULL | FK |
| `team` | VARCHAR | NOT NULL | FK |
| `hits` | INTEGER | YES | Total hits |
| `errors` | INTEGER | YES | Fielding errors |
| `lob` | INTEGER | YES | Left on base |
| `doubles` | INTEGER | YES | Extra-base doubles |
| `triples` | INTEGER | YES | Triples |
| `home_runs` | INTEGER | YES | Home runs |
| `rbi` | INTEGER | YES | Runs batted in |
| `stolen_bases` | INTEGER | YES | Stolen bases |
| `strikeouts` | INTEGER | YES | Batter strikeouts |
| `walks` | INTEGER | YES | Walks (BB) |
| `at_bats` | INTEGER | YES | At-bats |
| `obp` | NUMERIC(5,4) | YES | On-base percentage |
| `slg` | NUMERIC(5,4) | YES | Slugging percentage |
| `ops` | NUMERIC(5,4) | YES | OBP + SLG |
| `woba` | NUMERIC(5,4) | YES | Weighted on-base average (FanGraphs 2023 weights) |
| `era` | NUMERIC(6,2) | YES | Starting pitcher ERA |

**Primary Key:** `(game_id, team)`
**Foreign Keys:** `(game_id, team)` REFERENCES `team_game_stats(game_id, team)`

---

### nfl_team_game_stats_ext

**Purpose:** NFL passing, rushing, and situational-football metrics.
Source: `nfl_data_py` (import_schedules + import_pbp_data; free, public).

**Columns:**

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `game_id` | VARCHAR | NOT NULL | FK |
| `team` | VARCHAR | NOT NULL | FK |
| `passing_yards` | INTEGER | YES | Net passing yards |
| `passing_tds` | INTEGER | YES | Passing touchdowns |
| `passing_ints` | INTEGER | YES | Interceptions thrown |
| `rushing_yards` | INTEGER | YES | Net rushing yards |
| `rushing_tds` | INTEGER | YES | Rushing touchdowns |
| `rushing_attempts` | INTEGER | YES | Rushing attempts |
| `total_yards` | INTEGER | YES | Total net yards |
| `turnovers` | INTEGER | YES | Fumbles lost + INTs |
| `third_down_conversions` | INTEGER | YES | Third-down conversions |
| `third_down_attempts` | INTEGER | YES | Third-down attempts |
| `third_down_pct` | NUMERIC(5,4) | YES | Third-down conversion rate |
| `time_of_possession` | INTEGER | YES | Seconds of possession |
| `penalties` | INTEGER | YES | Penalty count |
| `penalty_yards` | INTEGER | YES | Penalty yards |
| `sacks_allowed` | INTEGER | YES | Sacks allowed |
| `first_downs` | INTEGER | YES | Total first downs |

**Primary Key:** `(game_id, team)`
**Foreign Keys:** `(game_id, team)` REFERENCES `team_game_stats(game_id, team)`

---

### soccer_team_game_stats_ext

**Purpose:** Soccer possession, set-piece, and xG metrics shared by EPL and Ligue 1
(the `sport` column in `team_game_stats` disambiguates).
Sources: football-data.co.uk CSVs (primary) + FBRef optional enrichment
(User-Agent: `nhlstats-research-bot/1.0`, 3 s crawl delay; both free).

**Columns:**

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `game_id` | VARCHAR | NOT NULL | FK |
| `team` | VARCHAR | NOT NULL | FK |
| `shots` | INTEGER | YES | Total shots |
| `shots_on_target` | INTEGER | YES | Shots on target |
| `possession_pct` | NUMERIC(5,4) | YES | Ball possession 0.0–1.0 |
| `passes` | INTEGER | YES | Total passes attempted |
| `pass_accuracy` | NUMERIC(5,4) | YES | Pass completion rate |
| `xg` | NUMERIC(6,3) | YES | Expected goals (FBRef) |
| `xga` | NUMERIC(6,3) | YES | Expected goals against (FBRef) |
| `fouls` | INTEGER | YES | Fouls committed |
| `yellow_cards` | INTEGER | YES | Yellow cards |
| `red_cards` | INTEGER | YES | Red cards |
| `corners` | INTEGER | YES | Corner kicks |
| `offsides` | INTEGER | YES | Offsides |
| `saves` | INTEGER | YES | Goalkeeper saves |

**Primary Key:** `(game_id, team)`
**Foreign Keys:** `(game_id, team)` REFERENCES `team_game_stats(game_id, team)`

---

### ncaab_team_game_stats_ext

**Purpose:** NCAAB (men's college basketball) advanced box-score metrics.
Source: ESPN scoreboard/summary API (free).

### wncaab_team_game_stats_ext

**Purpose:** WNCAAB (women's college basketball) — identical schema to `ncaab_team_game_stats_ext`.
Source: ESPN scoreboard/summary API (free).

Both tables share the following schema:

**Columns:**

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `game_id` | VARCHAR | NOT NULL | FK |
| `team` | VARCHAR | NOT NULL | FK |
| `fg_pct` | NUMERIC(5,4) | YES | Field goal percentage |
| `fg3m` | INTEGER | YES | 3-point FGM |
| `fg3a` | INTEGER | YES | 3-point FGA |
| `fg3_pct` | NUMERIC(5,4) | YES | 3-point % |
| `ast` | INTEGER | YES | Assists |
| `reb` | INTEGER | YES | Total rebounds |
| `stl` | INTEGER | YES | Steals |
| `blk` | INTEGER | YES | Blocks |
| `tov` | INTEGER | YES | Turnovers |
| `pf` | INTEGER | YES | Personal fouls |
| `ts_pct` | NUMERIC(5,4) | YES | True Shooting % |
| `efg_pct` | NUMERIC(5,4) | YES | Effective FG% |

**Primary Key:** `(game_id, team)`
**Foreign Keys:** `(game_id, team)` REFERENCES `team_game_stats(game_id, team)`

---

### tennis_player_match_stats

**Purpose:** Player-level match stats for ATP/WTA (tennis is inherently
player-level, not team-level). Source: Jeff Sackmann Tennis Abstract GitHub
CSVs (free, public-domain).

**Columns:**

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `game_id` | VARCHAR | NOT NULL | FK to `unified_games` |
| `player_name` | VARCHAR | NOT NULL | Normalized player name |
| `aces` | INTEGER | YES | Aces served |
| `double_faults` | INTEGER | YES | Double faults |
| `first_serve_pct` | NUMERIC(5,4) | YES | First serve in % |
| `first_serve_won_pct` | NUMERIC(5,4) | YES | % of first-serve points won |
| `second_serve_won_pct` | NUMERIC(5,4) | YES | % of second-serve points won |
| `break_points_saved` | INTEGER | YES | Break points saved |
| `break_points_faced` | INTEGER | YES | Break points faced |
| `winners` | INTEGER | YES | Winners hit |
| `unforced_errors` | INTEGER | YES | Unforced errors |
| `sets_won` | INTEGER | YES | Sets won |
| `games_won` | INTEGER | YES | Games won |
| `won` | BOOLEAN | YES | TRUE if player won the match |
| `created_at` | TIMESTAMP | NOT NULL | DEFAULT NOW() |

**Primary Key:** `(game_id, player_name)`

**Foreign Keys:**
- `game_id` REFERENCES `unified_games(game_id)`

**Indexes:**
- `idx_tpms_game_id ON (game_id)`
- `idx_tpms_player ON (player_name)`

**DAG Producers:**
- `fetch_stats_tennis` task in `historical_stats_daily` DAG
- `scripts/backfill_team_game_stats.py --sport tennis`

---

### bet_reconciliation_audit

**Purpose:** Immutable, append-only audit log. Every field-level change made
to `placed_bets` by the reconciliation pipeline is recorded here before being
applied. Enables full traceability and rollback analysis.

**Columns:**

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `audit_id` | SERIAL | NOT NULL | Auto-incrementing surrogate PK |
| `bet_id` | VARCHAR | NOT NULL | References `placed_bets.bet_id` (logical FK) |
| `field_changed` | VARCHAR | NOT NULL | Column name that was updated |
| `old_value` | TEXT | YES | Previous value (cast to TEXT) |
| `new_value` | TEXT | YES | Updated value (cast to TEXT) |
| `source` | VARCHAR | NOT NULL | `'kalshi_reconcile'` or `'kalshi_discovered'` |
| `reconciled_at` | TIMESTAMP | NOT NULL | DEFAULT NOW() |
| `reason` | TEXT | YES | Human-readable explanation |
| `discrepancy_type` | VARCHAR | YES | Classification (e.g. `status_mismatch`) |
| `run_id` | VARCHAR | YES | UUID of the reconciliation run |

**Primary Key:** `audit_id` (SERIAL)

**Indexes:**
- `idx_bra_bet_id ON (bet_id)`
- `idx_bra_reconciled_at ON (reconciled_at)`

**DAG Producers:**
- `reconcile_placed_bets` task in `multi_sport_betting_workflow` DAG
- `scripts/reconcile_bets_historical.py` (ad-hoc / catch-up)

---

## Data Flow

### Daily Pipeline (multi_sport_betting_workflow DAG - UPDATED 2026-01-29)
**Per Sport (9 sports in parallel):**
1. **Download Games**: `{sport}_download_games` → JSON files → `{sport}_validate_games`
2. **Load Games**: `{sport}_load_db` → `unified_games` + sport-specific tables
3. **Calculate Ratings**: `{sport}_update_elo` → `elo_ratings` + CSV files → `{sport}_validate_elo`
4. **Fetch Markets**: `{sport}_fetch_markets` → `game_odds` + JSON files → `{sport}_validate_markets`
   *Note: Runs in parallel with Elo calculation*
5. **Identify Bets**: `{sport}_identify_bets` → JSON files → `{sport}_validate_bets`
6. **Load Bets**: `{sport}_load_bets_db` → `bet_recommendations` (CRITICAL: Primary source for portfolio)

**Unified Portfolio:**
7. **Portfolio Betting**: `portfolio_optimized_betting` ← `bet_recommendations` → Kalshi API + `placed_bets`
8. **CLV Update**: `update_clv_data` → CLV tracking tables
9. **Daily Summary**: `send_daily_summary` → SMS notifications

### Hourly Pipeline
1. **Portfolio Snapshot**: `portfolio_hourly_snapshot` → `portfolio_snapshots`
2. **Bet Sync**: `bet_sync_hourly` → `placed_bets` (updates status from Kalshi)

### Key Data Flow Changes (2026-01-29):
- **Database-First**: Portfolio betting now reads from `bet_recommendations` table (not JSON files)
- **Validation Tasks**: Added 36 validation tasks to ensure data integrity
- **Parallel Processing**: Markets fetch independent of Elo calculations
- **Deprecated**: Removed sport-specific `place_bets` tasks (unified portfolio only)

## Schema Validation

To validate schema integrity, run:
```bash
python scripts/check_schema.py
```

## Migration Notes

- Migrated from DuckDB to PostgreSQL on 2026-01-20
- Schema managed by `plugins/database_schema_manager.py`
- All tables use `CREATE TABLE IF NOT EXISTS` for idempotent creation
- Foreign keys enforce referential integrity
- Timestamps use UTC timezone

## Maintenance

### Adding New Tables
1. Add `CREATE TABLE` statement to `database_schema_manager.py`
2. Update this documentation
3. Add producing DAG task to relevant DAG
4. Run schema validation

### Schema Changes
1. Use `ALTER TABLE` statements in migration scripts
2. Document changes in CHANGELOG.md
3. Update this documentation
4. Test with `scripts/check_schema.py`

## Related Files
- `plugins/database_schema_manager.py`: Schema creation/management
- `scripts/check_schema.py`: Schema validation
- `scripts/migrate_placed_bets_schema.py`: Example migration script
- `docs/bet_tracker_schema_migration.md`: Migration documentation
