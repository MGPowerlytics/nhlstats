# DAG Task Data Flow Documentation

## Overview
This document describes the data flow for all tasks in the multi-sport betting system DAGs. Each task's data sources, destinations, and dependencies are documented to ensure data integrity and proper pipeline execution.

Last Updated: 2026-01-29
Author: Integration Engineering Team

## DAG Summary

| DAG Name | Tasks | Schedule | Purpose |
|----------|-------|----------|---------|
| `multi_sport_betting_workflow` | 97 | Daily @ 5AM ET | Main betting pipeline for 9 sports |
| `bet_sync_hourly` | 1 | Hourly | Sync placed bets from Kalshi to database |
| `portfolio_hourly_snapshot` | 1 | Hourly | Record portfolio value snapshots |

---

## Multi-Sport Betting Workflow DAG

### Sport-Specific Task Pattern (per sport)
Each of the 9 sports follows this pattern with sport-specific variations:

#### 1. **{sport}_download_games**
**Purpose**: Download game data from external APIs
**Data Source**: External APIs (The Odds API, sports data providers)
**Data Destination**:
  - JSON files: `data/{sport}/games_{date}.json`
  - (Indirectly) Database via load task
**Dependencies**: None (first task in chain)
**Validation**: `{sport}_validate_games` checks output

#### 2. **{sport}_validate_games**
**Purpose**: Validate games were downloaded successfully
**Data Source**:
  - Files: `data/{sport}/games_{date}.json`
  - Database: `unified_games` table
**Data Destination**: None (validation only)
**Dependencies**: `{sport}_download_games`
**Failure Action**: Raises ValueError if no games found

#### 3. **{sport}_load_db**
**Purpose**: Load downloaded games into PostgreSQL
**Data Source**: JSON files from download task
**Data Destination**:
  - `unified_games` table (centralized)
  - Sport-specific tables (e.g., `nba_games`, `nhl_games`)
**Dependencies**: `{sport}_validate_games`
**Notes**: Uses `db_loader.NHLDatabaseLoader` for all sports

#### 4. **{sport}_update_elo**
**Purpose**: Calculate Elo ratings based on historical games
**Data Source**:
  - Database: Sport-specific game tables
  - Previous Elo ratings from CSV files
**Data Destination**:
  - CSV files: `data/{sport}_current_elo_ratings.csv`
  - XCom: `{sport}_elo_ratings` (for downstream tasks)
  - (Tennis only): Separate ATP/WTA CSV files
**Dependencies**: `{sport}_load_db`
**Validation**: `{sport}_validate_elo` checks output

#### 5. **{sport}_validate_elo**
**Purpose**: Validate Elo ratings were calculated
**Data Source**:
  - Files: `data/{sport}_current_elo_ratings.csv`
  - XCom: `{sport}_elo_ratings` from update task
**Data Destination**: None (validation only)
**Dependencies**: `{sport}_update_elo`
**Failure Action**: Raises ValueError if no Elo ratings

#### 6. **{sport}_fetch_markets** (Runs in parallel with Elo)
**Purpose**: Fetch betting markets from Kalshi API
**Data Source**: Kalshi API (external)
**Data Destination**:
  - JSON files: `data/{sport}/markets_{date}.json`
  - Database: `game_odds` table
  - XCom: `{sport}_markets` (legacy, not used by downstream)
**Dependencies**: `{sport}_load_db` (needs games to know what to fetch)
**Validation**: `{sport}_validate_markets` checks output

#### 7. **{sport}_validate_markets**
**Purpose**: Validate markets were fetched successfully
**Data Source**:
  - Files: `data/{sport}/markets_{date}.json`
  - Database: `game_odds` table
**Data Destination**: None (validation only)
**Dependencies**: `{sport}_fetch_markets`
**Failure Action**: Raises ValueError if no markets found

#### 8. **{sport}_identify_bets**
**Purpose**: Identify betting opportunities using OddsComparator
**Data Source**:
  - XCom: `{sport}_elo_ratings` from Elo task
  - Database: `game_odds` table for market data
  - Database: `unified_games` for game information
**Data Destination**:
  - JSON files: `data/{sport}/bets_{date}.json`
  - (Indirectly) Database via load_bets task
**Dependencies**: `{sport}_validate_elo` AND `{sport}_validate_markets`
**Algorithm**: Uses MARKET AGREEMENT strategy (Elo and market agree on winner)

#### 9. **{sport}_validate_bets**
**Purpose**: Validate bets were identified successfully
**Data Source**:
  - Files: `data/{sport}/bets_{date}.json`
  - Database: `bet_recommendations` table
**Data Destination**: None (validation only)
**Dependencies**: `{sport}_identify_bets`
**Failure Action**: Raises ValueError if no bets identified

#### 10. **{sport}_load_bets_db**
**Purpose**: Load bet recommendations into database
**Data Source**: JSON files from identify_bets task
**Data Destination**:
  - `bet_recommendations` table (primary storage)
  - Updates `unified_games` with betting information
**Dependencies**: `{sport}_validate_bets`
**Critical Role**: This task makes bets available to portfolio betting

### Sport-Specific Variations

#### Glicko-2 Sports (NBA, NHL, MLB, NFL only)
**{sport}_update_glicko2**:
- **Purpose**: Calculate Glicko-2 ratings (alternative to Elo)
- **Data Source**: Database game tables
- **Data Destination**: `data/{sport}_current_glicko2_ratings.csv`
- **Dependencies**: `{sport}_load_db`
- **Notes**: Runs in parallel with Elo, no validation task

#### Tennis Special Handling
- **Elo Ratings**: Separate ATP and WTA ratings stored in separate CSV files
- **Market Structure**: Different from team sports (player1 vs player2)
- **Bet Identification**: Special logic for tennis matchups

---

## Unified Portfolio Tasks

### 11. **portfolio_optimized_betting**
**Purpose**: Place portfolio-optimized bets across all sports using Kelly Criterion
**Data Source**:
  - **PRIMARY**: Database `bet_recommendations` table (via `load_opportunities_from_database`)
  - **FALLBACK**: JSON files `data/{sport}/bets_{date}.json` (if database empty)
**Data Destination**:
  - Kalshi API (places actual bets)
  - JSON files: `data/portfolio/betting_results_{date}.json`
  - JSON files: `data/portfolio/betting_report_{date}.txt`
  - Database: `placed_bets` table (via separate sync task)
**Dependencies**: ALL `{sport}_load_bets_db` tasks (9 sports)
**Critical Change**: Now reads from database by default (was JSON files)
**Algorithm**: PortfolioOptimizer with Kelly Criterion, risk limits

### 12. **update_clv_data**
**Purpose**: Update CLV (Closing Line Value) data for closed markets
**Data Source**:
  - Database: `placed_bets` table
  - Database: `game_odds` table for closing odds
**Data Destination**: Database CLV tracking tables
**Dependencies**: `portfolio_optimized_betting`
**Notes**: Runs after betting to capture final market prices

### 13. **send_daily_summary**
**Purpose**: Send daily summary via SMS
**Data Source**:
  - Kalshi API (current balance)
  - Database: `portfolio_value_snapshots` (yesterday's balance)
  - JSON files: `data/portfolio/betting_results_{date}.json`
**Data Destination**: SMS via Verizon email gateway
**Dependencies**: `update_clv_data`
**Content**: Balance, P/L, bets placed, portfolio value

---

## Hourly DAGs

### bet_sync_hourly DAG

#### sync_bets_from_kalshi
**Purpose**: Sync placed bets from Kalshi API to PostgreSQL
**Data Source**: Kalshi API (fills/orders endpoint)
**Data Destination**:
  - Database: `placed_bets` table (upsert)
  - Console: Print summary of added/updated bets
**Schedule**: Hourly
**Critical Role**: Ensures dashboard has current bet status

### portfolio_hourly_snapshot DAG

#### snapshot_portfolio_value
**Purpose**: Record hourly portfolio value snapshots
**Data Source**: Kalshi API (balance endpoint)
**Data Destination**:
  - Database: `portfolio_value_snapshots` table
  - Timestamp: Current UTC hour
**Schedule**: Hourly
**Dashboard Use**: Streamlit dashboard uses this for time-series charts

---

## Data Flow Architecture

### Primary Data Path (Recommended)
```
External APIs → JSON Files → Database → Portfolio Betting → Kalshi API
      ↓              ↓           ↓              ↓               ↓
  Download       Load to     Identify      Optimize &      Place Bets
   Games          DB          Bets          Place
```

### Critical Integration Points

#### 1. **Database as Single Source of Truth**
- **Before**: JSON files and database had parallel data
- **After**: Database is primary source, JSON files are temporary/backup
- **Validation**: Tasks check both sources but prefer database

#### 2. **Portfolio Betting Data Source**
- **Primary**: `bet_recommendations` table (validated, consistent)
- **Fallback**: JSON files (if database empty or corrupted)
- **Benefit**: Eliminates JSON/database inconsistency risk

#### 3. **Validation Chain**
```
Download → Validate → Load → Process → Validate → Next Step
    ↓         ↓         ↓        ↓         ↓         ↓
   Raw     Exists?   DB OK?   Process   Output    Continue
  Data                           OK?     Valid?
```

### Data Storage Locations

#### 1. **PostgreSQL Tables**
- `unified_games`: Central game schedule
- `game_odds`: Market odds from all bookmakers
- `bet_recommendations`: Daily bet recommendations (CRITICAL)
- `placed_bets`: Tracked bets with status
- `portfolio_value_snapshots`: Hourly portfolio values
- `elo_ratings`: Historical Elo ratings

#### 2. **JSON Files (Temporary/Backup)**
- `data/{sport}/games_{date}.json`: Raw game data
- `data/{sport}/markets_{date}.json`: Raw market data
- `data/{sport}/bets_{date}.json`: Bet recommendations
- `data/portfolio/betting_results_{date}.json`: Betting results

#### 3. **CSV Files (Model Output)**
- `data/{sport}_current_elo_ratings.csv`: Current Elo ratings
- `data/{sport}_current_glicko2_ratings.csv`: Current Glicko-2 ratings

#### 4. **XCom (Airflow Internal)**
- `{sport}_elo_ratings`: Elo ratings between tasks
- `{sport}_markets`: Market data (legacy, being phased out)

---

## Error Handling & Data Validation

### Validation Tasks (New)
Each processing step now has a validation task:
1. **Games Downloaded?** → `{sport}_validate_games`
2. **Elo Calculated?** → `{sport}_validate_elo`
3. **Markets Fetched?** → `{sport}_validate_markets`
4. **Bets Identified?** → `{sport}_validate_bets`

### Failure Modes
1. **Missing Data**: Raises ValueError with clear message
2. **API Failure**: Retry logic (3 attempts, 5-minute delay)
3. **Database Issue**: Connection pooling with retry
4. **File System**: Check existence before reading

### Data Consistency Checks
1. **Database vs Files**: Validation tasks check both
2. **Required Fields**: Each task validates input schema
3. **Timeliness**: Skip stale games/markets
4. **Integrity**: Foreign key relationships in database

---

## Dependencies Graph

### Sport Pipeline (per sport)
```
download_games → validate_games → load_db
                                      ↓
                              [elo_task, markets_task] (parallel)
                                      ↓
                          [validate_elo, validate_markets]
                                      ↓
                              identify_bets → validate_bets → load_bets_db
```

### Unified Pipeline
```
[All 9 sports' load_bets_db] → portfolio_optimized_betting → update_clv_data → send_daily_summary
```

### Key Dependency Changes
1. **Markets Parallel**: No longer waits for Elo completion
2. **Portfolio Depends on DB Load**: Was `identify_bets`, now `load_bets_db`
3. **Validation Interleaved**: Between each processing step

---

## Monitoring & Troubleshooting

### Critical Data Checkpoints
1. **After load_db**: Check `unified_games` has today's games
2. **After identify_bets**: Check `bet_recommendations` has bets
3. **After portfolio betting**: Check `placed_bets` has new bets
4. **Hourly**: Check `portfolio_value_snapshots` has recent entries

### Common Issues
1. **No Games Downloaded**: Check API keys, network connectivity
2. **No Markets Fetched**: Check Kalshi API, market availability
3. **No Bets Identified**: Check Elo ratings, market data alignment
4. **Database Empty**: Check `load_*` tasks completed successfully

### Recovery Procedures
1. **Partial Failure**: Rerun specific sport pipeline
2. **Complete Failure**: Rerun entire DAG with catchup disabled
3. **Data Corruption**: Restore from JSON backup files
4. **API Issues**: Implement circuit breaker, use cached data

---

## Dashboard Data Dependencies

The Streamlit dashboard (`dashboard/dashboard_app.py`) consumes data produced by the DAG tasks.

### Required Database Tables
| Table | Pages Using | Required Columns |
|-------|-------------|------------------|
| `unified_games` | Elo Analysis, Data Quality | game_id, sport, game_date, home_team, away_team, home_score, away_score, season |
| `placed_bets` | Betting Performance, CLV Analysis, EV Analysis | bet_id, ticker, side, amount, price, created_at, settled, outcome, pnl, clv, expected_value, elo_prob, market_prob, kelly_fraction, edge |
| `portfolio_value_snapshots` | Financial Performance | snapshot_time, portfolio_value |

### Required Columns in `placed_bets` Table
These columns are populated by various DAG tasks:

| Column | Produced By | Purpose |
|--------|-------------|---------|
| `bet_id`, `ticker`, `side`, `amount`, `price` | `bet_sync_hourly` | Core bet data from Kalshi |
| `settled`, `outcome`, `pnl` | `bet_sync_hourly` | Settlement status |
| `clv` | `update_clv_data` | Closing Line Value metric |
| `expected_value` | `portfolio_optimized_betting` | Pre-bet EV calculation |
| `elo_prob` | `portfolio_optimized_betting` | Elo model prediction |
| `market_prob` | `portfolio_optimized_betting` | Market-implied probability |
| `kelly_fraction` | `portfolio_optimized_betting` | Kelly Criterion sizing |
| `edge` | `portfolio_optimized_betting` | Elo edge over market |

### Module Dependencies
The dashboard imports these modules from `plugins/`:
- `db_manager.DBManager`: Database connection management
- `elo/*_elo_rating.py`: Sport-specific Elo calculations for live predictions
- `data_validation.py`: Data quality checks (optional)
- `clv_tracker.py`: CLV calculation utilities (optional)

### Data Freshness Requirements
- **Games**: Updated daily by `multi_sport_betting_workflow`
- **Bets**: Updated hourly by `bet_sync_hourly`
- **Portfolio**: Updated hourly by `portfolio_hourly_snapshot`
- **CLV**: Updated daily by `update_clv_data`

---

## Performance Considerations

### Parallel Processing
- **9 Sports**: Processed in parallel
- **Elo vs Markets**: Run concurrently (no dependency)
- **Validation**: Minimal overhead, fail-fast

### Data Volume
- **Games**: ~85K historical, ~10-100 daily per sport
- **Markets**: ~10-50 daily per sport
- **Bets**: ~5-20 daily per sport
- **Portfolio**: 24 hourly snapshots daily

### Storage Strategy
- **Hot Data**: PostgreSQL (current season)
- **Warm Data**: JSON files (30-day rolling)
- **Cold Data**: Archived/compressed (historical)

---

## Future Improvements

### Planned Enhancements
1. **Event-Driven Triggers**: Trigger tasks when data arrives vs schedule
2. **Data Lineage Tracking**: Track data provenance through pipeline
3. **Schema Versioning**: Handle schema changes gracefully
4. **Quality Metrics**: Track data completeness, accuracy metrics

### Technical Debt
1. **XCom Usage**: Phase out in favor of database
2. **JSON Files**: Reduce reliance, use database as primary
3. **Error Messages**: Standardize across all tasks
4. **Monitoring**: Add comprehensive health checks

---

## Appendix: Task Count Summary

### multi_sport_betting_workflow.py
- **Base tasks per sport**: 10 × 9 sports = 90 tasks
  - download_games, validate_games, load_db, update_elo, validate_elo
  - fetch_markets, validate_markets, identify_bets, validate_bets, load_bets_db
- **Glicko-2 tasks**: 1 × 4 sports = 4 tasks
- **Unified tasks**: 3 tasks
- **TOTAL**: 97 tasks

### Hourly DAGs
- **bet_sync_hourly**: 1 task
- **portfolio_hourly_snapshot**: 1 task

### GRAND TOTAL: 99 tasks across 3 DAGs

---

## Change Log

### 2026-01-29: Integration Engineering Fixes
1. **Database-First Architecture**: Portfolio betting now reads from `bet_recommendations` table
2. **Validation Tasks**: Added 36 validation tasks (4 per sport × 9 sports)
3. **Error Handling**: Improved with ValueError raises instead of silent returns
4. **Dependency Cleanup**: Removed deprecated `place_bets_task`, simplified chains
5. **Parallel Processing**: Markets fetch independent of Elo calculations
6. **Documentation**: This comprehensive data flow document

### Key Benefits
- **Data Consistency**: Eliminated JSON/database mismatch risk
- **Reliability**: Validation catches issues early
- **Maintainability**: Clear data flow, proper error handling
- **Performance**: Parallel processing where possible
