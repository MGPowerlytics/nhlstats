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

## Data Flow

### Daily Pipeline (multi_sport_betting_workflow DAG)
1. **Download Games**: `{sport}_download_games` → `unified_games`
2. **Fetch Markets**: `{sport}_fetch_markets` → `game_odds`
3. **Update Elo**: `{sport}_update_elo` → `elo_ratings`
4. **Identify Bets**: `{sport}_identify_bets` → `bet_recommendations`
5. **Place Bets**: `{sport}_place_bets` → `placed_bets`
6. **Load to DB**: `{sport}_load_bets_db` → `unified_games` (updates)

### Hourly Pipeline
1. **Portfolio Snapshot**: `portfolio_hourly_snapshot` → `portfolio_snapshots`
2. **Bet Sync**: `bet_sync_hourly` → `placed_bets` (updates status)

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
