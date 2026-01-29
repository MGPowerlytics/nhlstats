# Data Model

## Database Overview

The Multi-Sport Betting System uses a hybrid database approach: PostgreSQL for production and DuckDB for development/analytics. The schema is designed to support multi-sport game data, Elo ratings, betting recommendations, and portfolio tracking.

## Core Tables

### `unified_games` (Central Table)
**Purpose**: Normalized view of all games across 9 sports for unified querying.

| Column | Type | Description |
|--------|------|-------------|
| `game_id` | VARCHAR | Unique game identifier (format varies by sport) |
| `sport` | VARCHAR | Sport code: NHL, NBA, MLB, NFL, NCAAB, WNCAAB, EPL, LIGUE1, TENNIS |
| `game_date` | DATE | Date of the game |
| `season` | INTEGER | Season year or formatted season |
| `status` | VARCHAR | Game status (Final, OFF, scheduled, etc.) |
| `home_team_id` | VARCHAR | Home team identifier |
| `home_team_name` | VARCHAR | Full home team name |
| `away_team_id` | VARCHAR | Away team identifier |
| `away_team_name` | VARCHAR | Full away team name |
| `home_score` | INTEGER | Final home score |
| `away_score` | INTEGER | Final away score |
| `commence_time` | TIMESTAMP | Game start time (UTC) |
| `venue` | VARCHAR | Venue name |
| `loaded_at` | TIMESTAMP | ETL timestamp |

**Row Count**: ~85,610 games across all sports

### Sport-Specific Game Tables
Each sport has its own detailed game table that feeds into `unified_games`:

- `games` (NHL) - 6,297 rows with detailed NHL metadata
- `nba_games` - 706 rows
- `mlb_games` - 14,518 rows
- `nfl_games` - 1,421 rows
- `ncaab_games` - 25,773 rows
- `wncaab_games` - 6,982 rows
- `epl_games` - 1,730 rows
- `ligue1_games` - 1,534 rows
- `tennis_games` - 25,723 rows

## Betting & Market Tables

### `bet_recommendations`
**Purpose**: Generated betting recommendations from Elo model.

| Column | Type | Description |
|--------|------|-------------|
| `bet_id` | VARCHAR | Unique ID: sport_date_idx_teams |
| `sport` | VARCHAR | nba, nhl, mlb, nfl |
| `recommendation_date` | DATE | Date recommendation generated |
| `home_team` | VARCHAR | Home team name |
| `away_team` | VARCHAR | Away team name |
| `bet_on` | VARCHAR | home or away |
| `elo_prob` | DOUBLE | Model probability |
| `market_prob` | DOUBLE | Implied market probability |
| `edge` | DOUBLE | elo_prob - market_prob |
| `confidence` | VARCHAR | HIGH, MEDIUM |
| `yes_ask` | INTEGER | Kalshi YES price (cents) |
| `no_ask` | INTEGER | Kalshi NO price (cents) |
| `ticker` | VARCHAR | Kalshi market ticker |
| `created_at` | TIMESTAMP | Creation timestamp |

**Row Count**: 115 recommendations

### `placed_bets`
**Purpose**: Actual bets placed on Kalshi.

| Column | Type | Description |
|--------|------|-------------|
| `bet_id` | VARCHAR | Kalshi-generated ID |
| `sport` | VARCHAR | NBA, NHL, etc. |
| `placed_date` | DATE | Date bet placed |
| `ticker` | VARCHAR | Kalshi market ticker |
| `home_team` | VARCHAR | Home team name |
| `away_team` | VARCHAR | Away team name |
| `bet_on` | VARCHAR | Team bet on |
| `side` | VARCHAR | yes, no |
| `contracts` | INTEGER | Number of contracts |
| `price_cents` | INTEGER | Price per contract |
| `cost_dollars` | DOUBLE | Total cost |
| `fees_dollars` | DOUBLE | Transaction fees |
| `elo_prob` | DOUBLE | Model probability at time of bet |
| `market_prob` | DOUBLE | Market probability at time of bet |
| `edge` | DOUBLE | Calculated edge |
| `confidence` | VARCHAR | HIGH, MEDIUM |
| `status` | VARCHAR | open, won, lost |
| `settled_date` | DATE | Settlement date |
| `payout_dollars` | DOUBLE | Payout amount |
| `profit_dollars` | DOUBLE | Profit/loss |
| `created_at` | TIMESTAMP | Creation timestamp |

**Row Count**: 26 placed bets

### `portfolio_value_snapshots`
**Purpose**: Hourly portfolio value tracking.

| Column | Type | Description |
|--------|------|-------------|
| `snapshot_hour_utc` | TIMESTAMP | Hour of snapshot |
| `balance_dollars` | DOUBLE | Cash balance |
| `portfolio_value_dollars` | DOUBLE | Value of open positions |
| `created_at_utc` | TIMESTAMP | Creation timestamp |

**Row Count**: 6 snapshots

### `kalshi_markets`
**Purpose**: Kalshi prediction market metadata.

| Column | Type | Description |
|--------|------|-------------|
| `ticker` | VARCHAR | Market ticker |
| `event_ticker` | VARCHAR | Parent event |
| `status` | VARCHAR | open, finalized |
| `yes_sub_title` | VARCHAR | YES outcome label |
| `no_sub_title` | VARCHAR | NO outcome label |
| `open_time` | TIMESTAMP | Market open time |
| `close_time` | TIMESTAMP | Market close time |
| `settlement_ts` | TIMESTAMP | Settlement time |
| `result` | VARCHAR | yes, no |
| `market_type` | VARCHAR | binary |
| `retrieved_at` | TIMESTAMP | Retrieval timestamp |

**Row Count**: 6,398 markets

### `kalshi_trades`
**Purpose**: Historical trade data from Kalshi markets.

| Column | Type | Description |
|--------|------|-------------|
| `trade_id` | VARCHAR | Trade UUID |
| `ticker` | VARCHAR | Market ticker |
| `yes_price` | INTEGER | Price in cents (1-99) |
| `no_price` | INTEGER | Price in cents (1-99) |
| `count` | BIGINT | Number of contracts |
| `count_fp` | VARCHAR | Fractional part |
| `taker_side` | VARCHAR | yes, no |
| `created_time` | TIMESTAMP | Trade timestamp |
| `retrieved_at` | TIMESTAMP | Retrieval timestamp |

**Row Count**: ~11 million trades

### `game_odds`
**Purpose**: Sportsbook odds for games.

| Column | Type | Description |
|--------|------|-------------|
| `odds_id` | VARCHAR | Composite ID |
| `game_id` | VARCHAR | Foreign key to unified_games |
| `bookmaker` | VARCHAR | SBR, etc. |
| `market_name` | VARCHAR | moneyline, spread, total |
| `outcome_name` | VARCHAR | home, away, over, under |
| `price` | DECIMAL(10,4) | Decimal odds |
| `line` | DECIMAL(10,4) | Spread/total line |
| `last_update` | TIMESTAMP | Last update time |
| `is_pregame` | BOOLEAN | Whether odds are pregame |
| `loaded_at` | TIMESTAMP | Loading timestamp |

**Row Count**: 21,818 odds records

## Elo System Tables

### Team Ratings Storage
Elo ratings are stored in memory during pipeline execution and can be persisted to:
- `team_elo_ratings` table (if implemented)
- JSON files in `data/{sport}/elo_ratings.json`
- In-memory Python objects within the Elo engine

### Rating Parameters
Each sport has configurable Elo parameters:
- `k_factor`: Update sensitivity (typically 20-40)
- `home_advantage`: Home court/field advantage (typically 50-100 rating points)
- `regression_factor`: Season-to-season regression (typically 1/3 of rating difference to mean)

## Feature Engineering Tables

### Advanced Analytics
- `game_team_advanced_stats`: Corsi, Fenwick, high-danger chances (5,723 rows)
- `team_rolling_stats`: Rolling window statistics L3, L10 (11,446 rows)
- `team_schedule_fatigue`: Rest and schedule context (11,446 rows)
- `team_momentum`: Streak and rivalry context (5,723 rows)
- `team_h2h_history`: Head-to-head historical performance (5,723 rows)
- `team_situational_context`: Standings and playoff context (5,794 rows)
- `betting_line_features`: Betting line derived features (5,723 rows)

## Data Flow

### 1. Game Data Collection
```
External APIs → Sport-specific game tables → unified_games
```

### 2. Elo Rating Updates
```
unified_games → Elo engine → Updated team ratings
```

### 3. Bet Identification
```
Team ratings + game_odds → Probability comparison → bet_recommendations
```

### 4. Bet Execution
```
bet_recommendations → Kalshi API → placed_bets
```

### 5. Portfolio Tracking
```
placed_bets + kalshi_markets → portfolio_value_snapshots
```

## Key Relationships

### Foreign Key Constraints
```
game_odds.game_id → unified_games.game_id
bet_recommendations references unified_games via home_team/away_team
placed_bets references bet_recommendations via ticker/sport
```

### Data Consistency Rules
1. All games must have a corresponding entry in `unified_games`
2. Bet recommendations must reference valid games (existing in unified_games)
3. Placed bets must reference valid Kalshi markets
4. Portfolio snapshots must include all open positions

## Indexing Strategy

### Primary Indexes
- `unified_games`: `(game_date, sport)` for time-based queries
- `bet_recommendations`: `(recommendation_date, sport)` for daily recommendations
- `placed_bets`: `(placed_date, status)` for active bet tracking
- `game_odds`: `(game_id, bookmaker)` for odds lookup

### Performance Considerations
1. Large tables (`kalshi_trades` with 11M rows) use partitioning by date
2. Frequent queries use covering indexes
3. Analytics queries leverage DuckDB's columnar storage

## Data Quality

### Validation Rules
1. Game scores must be non-negative integers
2. Probabilities must be between 0 and 1
3. Edge calculations must be mathematically valid
4. Bet status must follow lifecycle: open → (won|lost)

### Common Issues
1. Missing biographical data in player tables
2. Inconsistent team naming across sports
3. NULL values in early-season rolling statistics
4. Format inconsistencies in game_id across sports

## Migration Notes

### PostgreSQL vs DuckDB
- **Production**: PostgreSQL with full ACID compliance
- **Development**: DuckDB for fast analytics and local testing
- **Schema**: Identical between both databases
- **ETL**: Airflow DAGs populate both databases

### Schema Evolution
1. Added `unified_games` to normalize multi-sport data
2. Introduced `portfolio_value_snapshots` for hourly tracking
3. Extended `placed_bets` with profit/loss calculations
4. Added feature engineering tables for ML models

---

*Last Updated: 2026-01-26*
