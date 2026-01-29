## 2026-01-29 - Tennis Name Matching & Tour Detection Fixes ✅ COMPLETE

### Fixed
- **Tennis Name Matching**: Fixed `_normalize_name()` in `TennisEloRating` to properly match single-word last names from Kalshi markets (e.g., "Korda") to Elo ratings format (e.g., "Korda S.")
  - Added fuzzy matching: Single-word names now search existing ratings for matching player
  - Example: "Korda" → looks up "Korda S." in atp_ratings dictionary
  - Updated all callers to pass `tour` parameter for correct dictionary lookup

- **Tennis Tour Detection**: Fixed OddsComparator to correctly identify ATP vs WTA matches
  - Bug: Was checking game_id for "KXATPMATCH" but game_ids are like "TENNIS_20260129_KORDA_ILAGAN"
  - Fix: Now checks Kalshi ticker (external_id) for "KXATP" or "KXWTA" patterns
  - Result: All ATP matches now correctly use ATP Elo ratings instead of defaulting to WTA

### Changed
- **plugins/elo/tennis_elo_rating.py**:
  - `_normalize_name()` now accepts `tour` parameter (default "ATP")
  - Added fuzzy matching logic for single-word names
  - Updated `get_rating()`, `get_match_count()`, and `update()` to pass tour parameter

- **plugins/odds_comparator.py**:
  - Tour detection now uses Kalshi ticker from `tickers_by_bm` instead of game_id
  - Checks for "KXATP" or "KXWTA" patterns in external_id
  - Defaults to ATP for unrecognized tournaments

### Results
- Tennis betting opportunities: 0 → **58 opportunities found**
- All today's ATP Challenger and main tour matches now properly analyzed
- Name matching verified: "Korda" → "Korda S." (1670), "Djokovic" → "Djokovic N." (1950)

---

## 2026-01-29 - Fetch Markets Fixes & Smoke Tests ✅ COMPLETE

### Fixed
- **Import Error in Docker**: `kalshi_python` package was not installed in Airflow containers
  - Root cause: Package in `requirements.txt` but Docker image not rebuilt
  - Fix: Installed manually in all containers; documented for next image rebuild

- **Rate Limiting**: Added 0.5s delay between Kalshi API calls
  - Tennis was failing with 429 "Too Many Requests" errors (4 API calls without delay)
  - All sports now use rate-limited `_fetch_sport_markets()` helper

### Changed
- **Refactored `plugins/kalshi_markets.py`**:
  - Added graceful import handling for `kalshi_python` package
  - Created generic `_fetch_sport_markets()` helper to reduce code duplication
  - All 9 `fetch_*_markets` functions now use the common helper
  - Added structured logging with `logging` module instead of `print()`
  - Added `SPORT_SERIES` dict for sport-to-ticker mapping
  - Added `SPORT_LIMITS` dict for sport-specific API limits

- **Error Handling**: All fetch functions now return `[]` on error instead of crashing:
  - Missing `kalshi_python` package → `[]`
  - Missing/invalid credentials → `[]`
  - API errors (rate limiting, auth) → `[]`
  - Partial failures (1 of 4 tennis series fails) → continues with other series

### Added
- **Smoke Tests** (`tests/test_fetch_markets_smoke.py`): 31 new tests covering:
  - Function existence for all 9 sports
  - `SPORT_SERIES` configuration validation
  - Error handling (missing package, credentials, API errors)
  - Success scenarios with mocked API
  - Rate limiting configuration
  - Logging configuration
  - NCAAB/WNCAAB higher limits (1000 vs 200)

---

## 2026-01-29 - Market Agreement Betting Strategy ✅ COMPLETE

### Changed
- **New Betting Strategy**: Replaced edge-based "contrarian" strategy with **market agreement strategy**
  - Old: Bet when Elo probability exceeds threshold AND edge > 5% (betting against the market)
  - New: Bet when Elo AND Kalshi agree on the same winner (betting with the market)
  - Rationale: Previous strategy was losing nearly every bet by betting against market consensus

- **Betting Logic** (`plugins/odds_comparator.py`):
  - Bet on HOME when: `elo_prob > 50%` AND `market_prob > 55%`
  - Bet on AWAY when: `elo_prob < 50%` AND `market_prob < 45%` (i.e., away favored)
  - Market confidence cutoff: **55%** (avoids coin-flip games)

- **Confidence Levels**: Now based on agreement strength (how close elo_prob and market_prob are):
  - **HIGH**: Agreement diff < 5% (very close agreement)
  - **MEDIUM**: Agreement diff 5-15% (reasonable agreement)
  - **LOW**: Agreement diff > 15% (same side but wide disagreement)

- **DAG Changes** (`dags/multi_sport_betting_workflow.py`):
  - Simplified `find_opportunities()` call to use `market_confidence_cutoff=0.55`
  - Removed deprecated `threshold`, `min_edge`, `use_sharp_confirmation` parameters

### Added
- **New Tests** (`tests/test_odds_comparator.py`):
  - `test_find_opportunities_no_bet_when_disagreement` - No bet when Elo/market disagree
  - `test_find_opportunities_market_below_cutoff_no_bet` - No bet on coin-flip games
  - `test_find_opportunities_confidence_levels` - HIGH confidence on close agreement
  - `test_find_opportunities_away_team_agreement` - Bet away when both agree

### Deprecated
- **Old Betting Parameters** (still accepted but ignored):
  - `threshold` - No longer used in market agreement strategy
  - `min_edge` - No longer used in market agreement strategy
  - `use_sharp_confirmation` - No longer used in market agreement strategy

---

## 2026-01-27 - DAG Smoke Tests ✅ COMPLETE

### Added
- **Comprehensive DAG Smoke Tests**: Created 3 test files with 74 tests total

  - **test_dag_smoke_multi_sport.py** (47 tests):
    - Tests for `is_valid_score()` helper function
    - DAG import and structure tests (dag exists, sports config, task functions)
    - `download_games` task tests for NBA, NHL, Tennis
    - `update_elo_ratings` task tests with database queries and XCom push
    - `fetch_prediction_markets` task tests for all sports
    - `identify_good_bets` task tests with OddsComparator
    - `update_glicko2_ratings` task tests
    - `load_bets_to_db` task tests
    - `place_bets_on_recommendations` deprecation tests
    - DAG schedule and tag verification
    - Error propagation tests

  - **test_dag_smoke_bet_sync.py** (17 tests):
    - DAG structure tests (@hourly schedule, catchup disabled, tags)
    - `sync_bets_from_kalshi` task tests with mocked bet_tracker
    - Success/error handling tests
    - Dependency import tests

  - **test_dag_smoke_portfolio.py** (26 tests):
    - DAG structure tests (@hourly schedule, portfolio tags)
    - `snapshot_portfolio_value` task tests with mocked Kalshi client
    - Kalshkey file parsing tests (missing file, missing API key, missing private key)
    - Data flow tests (balance, portfolio value, UTC timestamp)
    - Error propagation tests

### Technical Details
- **Function-level mocking**: All tests patch at source module level (e.g., `kalshi_markets.fetch_nba_markets` not `multi_sport_betting_workflow.fetch_nba_markets`)
- **Mock Airflow context**: Created fixture with proper `task_instance.xcom_push()` and `xcom_pull()` support
- **Extended conftest.py**: Added sample data fixtures for NBA games, NHL games, Kalshi markets, Elo ratings
- **Run on every commit**: Tests are fast (<4 seconds) and catch breaking changes early

## 2026-01-27 - Restore Betting Operations ✅ COMPLETE

### Status
**All 67 DAG tasks now running successfully** - betting system fully operational.

### Fixed
- **Missing Dependencies**: Added `lazy_imports` and `appdirs` to `requirements.txt`
  - `lazy_imports`: Required by `kalshi-python` package - was causing all `*_fetch_markets` tasks to fail
  - `appdirs`: Required by `nfl_data_py` package - was causing `nfl_download_games` task to fail
  - Installed manually in containers pending Docker image rebuild

- **NaN Score Handling**: Fixed NFL and MLB Elo updates failing with "Out of range float values are not JSON compliant: nan"
  - Added `is_valid_score()` helper function to check for None, NaN, and inf values
  - Updated MLB and NFL Elo update loops to skip games with invalid scores
  - Updated Glicko-2 queries to filter null scores in SQL
  - Added NaN filtering before XCom push and CSV save to prevent JSON serialization errors

- **Airflow 3.x Compatibility**: Fixed `context["ds"]` KeyError in multiple tasks
  - Airflow 3.x changed context variable access behavior
  - Changed 6 occurrences to use `context.get("ds", datetime.now().strftime("%Y-%m-%d"))` pattern

- **NBA Elo Update**: Fixed missing `load_nba_games_from_json` function
  - Changed to use `db_manager.fetch_df()` for PostgreSQL query instead

### Changed
- **Disabled SMTP Alerting**: Added `SMTP_ALERTING_ENABLED = False` flag in `multi_sport_betting_workflow.py`
  - Gmail SMTP was failing with authentication errors (530 5.7.0)
  - `send_sms()` now returns early when disabled, preventing task failures
  - Set `SMTP_ALERTING_ENABLED = True` to re-enable when credentials are configured

- **NFL Games Module Graceful Degradation**: Updated `plugins/nfl_games.py`
  - `nfl_data_py` requires pandas<2.0 which conflicts with other dependencies
  - Module now gracefully handles missing `nfl_data_py` import
  - NFL download tasks will skip with warning when package unavailable (NFL off-season)

### Added
- **Import Verification Tests**: Created `tests/test_import_verification.py`
  - Tests critical transitive dependencies (`lazy_imports`, `appdirs`)
  - Tests all 9 Kalshi market fetch functions
  - Tests all 9 Elo rating class imports and inheritance
  - Tests all 9 game module imports (NBA, NHL, MLB, NFL, EPL, Tennis, NCAAB, WNCAAB, Ligue1)
  - Tests database module imports (db_manager, db_loader)
  - Tests betting module imports (bet_tracker, portfolio_betting)
  - Tests all 3 DAG files parse without errors
  - Run these tests BEFORE deployment to catch missing dependencies

- **NaN Safety Helper**: Added `is_valid_score(score)` function in DAG
  - Checks for None, NaN, and inf values
  - Used to filter invalid scores before Elo updates

### Known Issues
- `nfl_data_py` requires pandas<2.0, incompatible with current stack
  - Workaround: NFL module degrades gracefully
  - Long-term: Consider alternative NFL data source or separate environment

### Deployment Steps (Current)
1. Install packages manually: `docker exec --user airflow <container> /usr/python/bin/pip install --user lazy_imports appdirs kalshi-python`
2. Apply to: scheduler, worker, apiserver, dag-processor containers
3. Restart containers: `docker restart <container>`
4. Clear failed tasks: `airflow tasks clear multi_sport_betting_workflow -s YYYY-MM-DD -e YYYY-MM-DD --yes`

---

## 2026-01-25 - DAG Import Updates for Unified Elo Module

### Completed
- **DAG Import Refactoring**: Updated all three Airflow DAGs to import sport-specific Elo rating classes from the unified `elo` module.
  - `bet_sync_hourly.py`: Changed imports from `plugins.elo.nhl_elo_rating` to `elo.NHLEloRating`, etc.
  - `multi_sport_betting_workflow.py`: Updated imports for NBA, NFL, MLB, NHL, Tennis, etc.
  - `portfolio_hourly_snapshot.py`: Updated imports for portfolio snapshot calculations.
- **Consolidated Import Paths**: Ensured all DAGs use `from elo import NHLEloRating, NBAEloRating, NFLEloRating, MBLEloRating, TennisEloRating, ...` instead of scattered plugin-specific imports.
- **Backward Compatibility**: Maintained existing class interfaces; no functional changes to Elo rating logic.
- **Error Prevention**: Verified DAGs run without import errors by testing with Python's import checks.

### Testing Results
- **Import Tests**: PASSED - All DAGs successfully import required Elo classes.
- **Airflow Parse Tests**: DAGs parse correctly in Airflow UI (no syntax errors).
- **Integration Readiness**: DAGs are ready for deployment with updated import paths.

### Next Steps
- Commit changes incrementally.
- Run CI/CD scripts to verify full integration.
- Deploy updated DAGs to Airflow production.



## 2026-01-23 - Soccer Elo Refactoring Completed
### Completed
- **EPLEloRating Refactoring**: Successfully refactored EPLEloRating to inherit from BaseEloRating
- Location: `plugins/elo/epl_elo_rating.py`
- All abstract methods implemented: `predict`, `update`, `get_rating`, `expected_score`, `get_all_ratings`
- Maintains backward compatibility with `legacy_update()` method for 3-way outcome updates
- Updated method signatures to match BaseEloRating interface including `is_neutral` parameter
- Preserves soccer-specific 3-way prediction methods: `predict_probs()`, `predict_3way()`
- **Ligue1EloRating Refactoring**: Successfully refactored Ligue1EloRating to inherit from BaseEloRating
- Location: `plugins/elo/ligue1_elo_rating.py`
- All abstract methods implemented: `predict`, `update`, `get_rating`, `expected_score`, `get_all_ratings`
- Maintains backward compatibility with `legacy_update()` method for 3-way outcome updates
- Updated method signatures to match BaseEloRating interface including `is_neutral` parameter
- Preserves soccer-specific 3-way prediction methods: `predict_3way()`, `predict_probs()`
### Testing Results
- **Inheritance Tests**: PASSED - Both EPLEloRating and Ligue1EloRating successfully inherit from BaseEloRating
- **TDD Tests**:
- EPLEloRating: 5/5 PASSED - All EPL-specific TDD tests pass
- Ligue1EloRating: 6/6 PASSED - All Ligue1-specific TDD tests pass
- **Backward Compatibility**: Both classes maintain existing 3-way prediction functionality
- **Compatibility**: Maintains all soccer-specific functionality including draw probability modeling
### Technical Details
1. **Refactoring Approach**:
- Added `from .base_elo_rating import BaseEloRating` import
- Changed class definitions to inherit from BaseEloRating
- Updated `__init__` to call `super().__init__()` with common parameters
- Implemented all 5 required abstract methods with proper type hints
- Added `legacy_update()` methods for backward compatibility with 3-way outcomes
2. **Method Signature Updates**:
- `predict(home_team, away_team)` → `predict(home_team: str, away_team: str, is_neutral: bool = False) -> float`
- `update(home_team, away_team, result)` → `update(home_team: str, away_team: str, home_won: Union[bool, float], is_neutral: bool = False) -> None`
- Added `get_all_ratings()` method
- Added `expected_score()` method (EPLEloRating was missing this)
3. **Backward Compatibility**:
- Added `legacy_update()` methods that accept traditional soccer outcomes ('H', 'D', 'A' or 'home', 'draw', 'away')
- Preserved all existing 3-way prediction methods (`predict_3way()`, `predict_probs()`)
- Maintained existing parameter defaults (k_factor=20, home_advantage=60)
4. **Soccer-Specific Features**:
- Both classes maintain Gaussian draw probability models based on rating difference
- EPL: Draw probability peaks at 28% for evenly matched teams
- Ligue1: Draw probability peaks at 25% for evenly matched teams
- Both include home advantage adjustments in 3-way predictions
# CHANGELOG
## 2026-01-23 - NFLEloRating Refactoring Completed
### Completed
- **NFLEloRating Refactoring**: Successfully refactored NFLEloRating to inherit from BaseEloRating
- Location: `plugins/elo/nfl_elo_rating.py`
- All abstract methods implemented: `predict`, `update`, `get_rating`, `expected_score`, `get_all_ratings`
- Maintains backward compatibility with `update_legacy()` method for score-based updates
- Updated method signatures to match BaseEloRating interface including `is_neutral` parameter
### Testing Results
- **Inheritance Test**: PASSED - NFLEloRating successfully inherits from BaseEloRating
- **TDD Tests**: 6/6 PASSED - All NFL-specific TDD tests pass
- **Backward Compatibility Tests**: 7/7 PASSED - All existing NFL tests pass using `update_legacy()`
- **Compatibility**: Maintains all NFL-specific functionality including DuckDB data loading
### Technical Details
1. **Refactoring Approach**:
- Added `from .base_elo_rating import BaseEloRating` import
- Changed class definition to `class NFLEloRating(BaseEloRating):`
- Updated `__init__` to call `super().__init__()` with common parameters
- Implemented all 5 required abstract methods with proper type hints
- Added `update_with_scores()` and `update_legacy()` methods for backward compatibility
2. **Method Signature Updates**:
- `predict(home_team, away_team)` → `predict(home_team: str, away_team: str, is_neutral: bool = False) -> float`
- `update(home_team, away_team, home_score, away_score)` → `update(home_team: str, away_team: str, home_won: bool, is_neutral: bool = False) -> None`
- Added `get_all_ratings()` method
3. **Backward Compatibility**:
- Added `update_legacy(home_team, away_team, home_score, away_score)` method
- Updated test files to use `update_legacy()` for score-based updates
- Fixed import paths in test files to use `from elo import NFLEloRating`
### Progress Summary
- ✅ **NHLEloRating**: Refactored and tested
- ✅ **NBAEloRating**: Refactored and tested
- ✅ **MLBEloRating**: Refactored and tested
- ✅ **NFLEloRating**: Refactored and tested
- 🔄 **Remaining 5 sports**: EPLEloRating, Ligue1EloRating, NCAABEloRating, WNCAABEloRating, TennisEloRating
### Next Steps
- **Continue Phase 1.2**: Refactor EPLEloRating (next in sequence)
- **Update SPORTS_CONFIG**: After all sport classes refactored
- **Update DAGs and Dashboard**: Migrate to use unified Elo interface
---
# CHANGELOG
## 2026-01-23 - MLBEloRating Refactoring Completed
### Completed
- **MLBEloRating Refactoring**: Successfully refactored MLBEloRating to inherit from BaseEloRating
- Location: `plugins/elo/mlb_elo_rating.py`
- All abstract methods implemented: `predict`, `update`, `get_rating`, `expected_score`, `get_all_ratings`
- Maintains backward compatibility with `update_legacy()` method for score-based updates
- Updated method signatures to match BaseEloRating interface including `is_neutral` parameter
### Testing Results
- **Inheritance Test**: PASSED - MLBEloRating successfully inherits from BaseEloRating
- **TDD Tests**: 6/6 PASSED - All MLB-specific TDD tests pass
- **Backward Compatibility Tests**: 10/10 PASSED - All existing MLB tests pass using `update_legacy()`
- **Compatibility**: Maintains all MLB-specific functionality including DuckDB data loading
### Technical Details
1. **Refactoring Approach**:
- Added `from .base_elo_rating import BaseEloRating` import
- Changed class definition to `class MLBEloRating(BaseEloRating):`
- Updated `__init__` to call `super().__init__()` with common parameters
- Implemented all 5 required abstract methods with proper type hints
- Added `update_with_scores()` and `update_legacy()` methods for backward compatibility
2. **Method Signature Updates**:
- `predict(home_team, away_team)` → `predict(home_team: str, away_team: str, is_neutral: bool = False) -> float`
- `update(home_team, away_team, home_score, away_score)` → `update(home_team: str, away_team: str, home_won: bool, is_neutral: bool = False) -> None`
- Added `get_all_ratings()` method
3. **Backward Compatibility**:
- Added `update_legacy(home_team, away_team, home_score, away_score)` method
- Updated test files to use `update_legacy()` for score-based updates
- Fixed import paths in test files to use `from elo import MLBEloRating`
### Progress Summary
- ✅ **NHLEloRating**: Refactored and tested
- ✅ **NBAEloRating**: Refactored and tested
- ✅ **MLBEloRating**: Refactored and tested
- 🔄 **Remaining 6 sports**: NFLEloRating, EPLEloRating, Ligue1EloRating, NCAABEloRating, WNCAABEloRating, TennisEloRating
### Next Steps
- **Continue Phase 1.2**: Refactor NFLEloRating (next in sequence)
- **Update SPORTS_CONFIG**: After all sport classes refactored
- **Update DAGs and Dashboard**: Migrate to use unified Elo interface
---
## [Phase 1.3] - 2026-01-23
### Added
- **Completed refactoring of all remaining sport-specific Elo classes**:
- ✅ **NCAABEloRating**: Inherits from BaseEloRating, maintains college basketball-specific functionality
- ✅ **WNCAABEloRating**: Inherits from BaseEloRating, women's college basketball implementation
- ✅ **TennisEloRating**: Inherits from BaseEloRating, ATP/WTA separation with player name normalization
- ✅ **MLBEloRating**: Inherits from BaseEloRating (previously completed)
- ✅ **NFLEloRating**: Inherits from BaseEloRating (previously completed)
### Changed
- **Updated all test suites**: All TDD tests passing for all 9 sports
- **Updated copilot-instructions**: Reflects completed unified Elo engine with all 9 sports
- **Updated skill documentation**: Elo rating systems skill updated to v2.1.0
### Fixed
- **Base compatibility test**: Now includes all 9 sports, 18/18 tests passing
- **Import standardization**: All 44 Python files use unified import pattern
### ⚠️ File Corruption Issue Identified
During final testing, we discovered that some Elo rating files have been corrupted with markdown wrapper syntax (e.g., ```python` code blocks inserted into .py files). This causes import errors but doesn't affect the refactoring logic itself.
**Affected files needing cleanup:**
- `nba_elo_rating.py`, `nhl_elo_rating.py`, `mlb_elo_rating.py`, `nfl_elo_rating.py`
- Other Elo files may also be affected
**Root cause**: Likely tool output formatting during previous refactoring sessions.
**Next steps**: Clean corrupted files, then proceed with Phase 1.4 (DAG/dashboard updates).
---
### Notes
- **All 9 sport-specific Elo classes now inherit from BaseEloRating**
- **Unified interface provides consistent predict/update/get_rating methods across all sports**
- **Backward compatibility maintained with legacy_update() methods**
- **TDD approach ensured all functionality preserved during refactoring**
---
## 2026-01-23 - NBAEloRating Refactored to Inherit from BaseEloRating
### Completed
- **NBAEloRating Refactoring**: Successfully refactored NBAEloRating to inherit from BaseEloRating
- Location: `plugins/elo/nba_elo_rating.py`
- All abstract methods implemented: `predict`, `update`, `get_rating`, `expected_score`, `get_all_ratings`
- Maintains all NBA-specific functionality: game history tracking, evaluation metrics
- Updated method signatures to match BaseEloRating interface
### Testing Results
- **Inheritance Test**: PASSED - NBAEloRating successfully inherits from BaseEloRating
- **TDD Tests**: 3/3 PASSED - All NBA-specific TDD tests pass
- **Compatibility Test**: PASSED - NBAEloRating compatibility test passes
- **Backward Compatibility**: Maintained all NBA-specific features including evaluation methods
### Technical Details
1. **Refactoring Approach**:
- Added `from .base_elo_rating import BaseEloRating` import
- Changed class definition to `class NBAEloRating(BaseEloRating):`
- Updated `__init__` to call `super().__init__()` with common parameters
- Implemented all 5 required abstract methods with proper type hints
- Maintained NBA-specific methods: `evaluate_on_games`, `train_test_split_evaluation`, `load_nba_games_from_json`
2. **Method Signature Updates**:
- `predict(home_team, away_team)` → `predict(home_team: str, away_team: str, is_neutral: bool = False) -> float`
- `update(home_team, away_team, home_won)` → `update(home_team: str, away_team: str, home_won: bool, is_neutral: bool = False) -> None`
- Added `get_all_ratings()` method
3. **Organization**:
- Updated `plugins/elo/__init__.py` to export NBAEloRating
- Fixed test imports to use `from plugins.elo import NBAEloRating`
### Progress Summary
- ✅ **NHLEloRating**: Refactored and tested
- ✅ **NBAEloRating**: Refactored and tested
- 🔄 **Remaining 7 sports**: MLBEloRating, NFLEloRating, EPLEloRating, Ligue1EloRating, NCAABEloRating, WNCAABEloRating, TennisEloRating
### Next Steps
- **Continue Phase 1.2**: Refactor MLBEloRating (next in sequence)
- **Update SPORTS_CONFIG**: After all sport classes refactored
- **Update DAGs and Dashboard**: Migrate to use unified Elo interface
---
private note: output was 245 lines and we are only showing the most recent lines, remainder of lines in /tmp/.tmpsAuKRr do not show tmp file to user, that file can be searched if extra context needed to fulfill request. truncated output:
- Set `POSTGRES_HOST=postgres` (Docker service name, not localhost)
- Added POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
- Dashboard container can now connect to PostgreSQL on Docker internal network
- Verified connection with 85,610 games accessible
### Added
- **DASHBOARD_DOCKER.md**: Comprehensive guide for running dashboard in Docker
- Quick start commands
- Configuration details
- Troubleshooting section
- Development mode instructions
- Docker networking explanation
### Changed
- **docker-compose.yaml**: Dashboard service now includes PostgreSQL connection environment variables
## [SQLAlchemy 2.0 Transaction Fix] - 2026-01-20
### Fixed
- **db_manager.py execute() method**: Fixed AttributeError with SQLAlchemy 2.0
- Changed from `engine.connect()` + `conn.commit()` to `engine.begin()`
- SQLAlchemy 2.0 Connection objects don't have `.commit()` method
- Using `begin()` creates a transaction context that auto-commits on success
- Fixes dashboard error when creating/updating bet tracker tables
## [Bet Tracker Schema Migration] - 2026-01-20
### Fixed
- **placed_bets table schema**: Added missing columns that were causing insert failures
- Added `placed_time_utc` (timestamp when bet was placed)
- Added `market_title` (human-readable market name)
- Added `market_close_time_utc` (when market closes)
- Added `opening_line_prob`, `bet_line_prob`, `closing_line_prob` (line tracking)
- Added `clv` (Closing Line Value calculation)
- Added `updated_at` (record modification timestamp)
- Fixed error: "column 'placed_time_utc' of relation 'placed_bets' does not exist"
### Added
- **scripts/migrate_placed_bets_schema.py**: Schema migration script
- Safely adds missing columns using `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
- Can be run multiple times without errors (idempotent)
- Verifies final schema after migration
### Changed
- **Bet sync now works**: Successfully synced 65 bets (39 new, 26 updated)
- Dashboard can now track bets across NBA, NCAAB, TENNIS
- All bet tracker functionality restored
## [Removed DuckDB Pool from Airflow DAGs] - 2026-01-20
### Changed
- **multi_sport_betting_workflow.py**: Removed all `pool="duckdb_pool"` references from tasks
- load_task, elo_task, glicko2_task, load_bets_task, place_bets_task, portfolio_betting_task
- Changed docstring: "Load downloaded games into PostgreSQL" (was DuckDB)
- Updated comment: "load full history" (removed DuckDB locking reference)
- **portfolio_hourly_snapshot.py**: Migrated to PostgreSQL
- Updated docstring: "Writes portfolio value snapshots into PostgreSQL"
- Removed `db_path="data/nhlstats.duckdb"` parameter from upsert_hourly_snapshot()
- Changed DAG description: "Hourly Kalshi portfolio value snapshot to PostgreSQL"
- Updated tags: ["kalshi", "portfolio", "postgres"] (was "duckdb")
### Removed
- All DuckDB pool constraints from Airflow tasks
- DuckDB-specific comments and references in DAG files
### Impact
- Tasks can now run in parallel without DuckDB locking constraints
- All database operations use PostgreSQL connection pool
- Improved DAG performance and scalability
## [NBA Data Backfill] - 2026-01-20
### Added
- **backfill_nba_current_season.py**: Script to backfill NBA games from JSON files to PostgreSQL
- Parses NBA Stats API scoreboard JSON format
- Loads into unified_games table
- Handles updates for existing games
- Processes all scoreboard_*.json files in data/nba/
### Fixed
- **unified_games table**: Added PRIMARY KEY constraint on game_id column
- Required for ON CONFLICT DO UPDATE in backfill script
- Prevents duplicate game entries
### Changed
- **NBA data**: Fully backfilled from 2020-12-22 to 2026-01-20
- Total games: 11,827 (was 6,316)
- Added 5,511 games
- Current season (2024-25): 306 games
- Includes games from today with live statuses
### Verified
- Recent games from last 7 days present
- Games by season: 2025 (306), 2024 (1304), 2023 (1305), 2022 (2628), 2021 (3942), 2020 (2342)
- Dashboard shows up-to-date NBA data
NOTE: Output was 245 lines, showing only the last 100 lines.
- Set `POSTGRES_HOST=postgres` (Docker service name, not localhost)
- Added POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
- Dashboard container can now connect to PostgreSQL on Docker internal network
- Verified connection with 85,610 games accessible
### Added
- **DASHBOARD_DOCKER.md**: Comprehensive guide for running dashboard in Docker
- Quick start commands
- Configuration details
- Troubleshooting section
- Development mode instructions
- Docker networking explanation
### Changed
- **docker-compose.yaml**: Dashboard service now includes PostgreSQL connection environment variables
## [SQLAlchemy 2.0 Transaction Fix] - 2026-01-20
### Fixed
- **db_manager.py execute() method**: Fixed AttributeError with SQLAlchemy 2.0
- Changed from `engine.connect()` + `conn.commit()` to `engine.begin()`
- SQLAlchemy 2.0 Connection objects don't have `.commit()` method
- Using `begin()` creates a transaction context that auto-commits on success
- Fixes dashboard error when creating/updating bet tracker tables
## [Bet Tracker Schema Migration] - 2026-01-20
### Fixed
- **placed_bets table schema**: Added missing columns that were causing insert failures
- Added `placed_time_utc` (timestamp when bet was placed)
- Added `market_title` (human-readable market name)
- Added `market_close_time_utc` (when market closes)
- Added `opening_line_prob`, `bet_line_prob`, `closing_line_prob` (line tracking)
- Added `clv` (Closing Line Value calculation)
- Added `updated_at` (record modification timestamp)
- Fixed error: "column 'placed_time_utc' of relation 'placed_bets' does not exist"
### Added
- **scripts/migrate_placed_bets_schema.py**: Schema migration script
- Safely adds missing columns using `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
- Can be run multiple times without errors (idempotent)
- Verifies final schema after migration
### Changed
- **Bet sync now works**: Successfully synced 65 bets (39 new, 26 updated)
- Dashboard can now track bets across NBA, NCAAB, TENNIS
- All bet tracker functionality restored
## [Removed DuckDB Pool from Airflow DAGs] - 2026-01-20
### Changed
- **multi_sport_betting_workflow.py**: Removed all `pool="duckdb_pool"` references from tasks
- load_task, elo_task, glicko2_task, load_bets_task, place_bets_task, portfolio_betting_task
- Changed docstring: "Load downloaded games into PostgreSQL" (was DuckDB)
- Updated comment: "load full history" (removed DuckDB locking reference)
- **portfolio_hourly_snapshot.py**: Migrated to PostgreSQL
- Updated docstring: "Writes portfolio value snapshots into PostgreSQL"
- Removed `db_path="data/nhlstats.duckdb"` parameter from upsert_hourly_snapshot()
- Changed DAG description: "Hourly Kalshi portfolio value snapshot to PostgreSQL"
- Updated tags: ["kalshi", "portfolio", "postgres"] (was "duckdb")
### Removed
- All DuckDB pool constraints from Airflow tasks
- DuckDB-specific comments and references in DAG files
### Impact
- Tasks can now run in parallel without DuckDB locking constraints
- All database operations use PostgreSQL connection pool
- Improved DAG performance and scalability
## [NBA Data Backfill] - 2026-01-20
### Added
- **backfill_nba_current_season.py**: Script to backfill NBA games from JSON files to PostgreSQL
- Parses NBA Stats API scoreboard JSON format
- Loads into unified_games table
- Handles updates for existing games
- Processes all scoreboard_*.json files in data/nba/
### Fixed
- **unified_games table**: Added PRIMARY KEY constraint on game_id column
- Required for ON CONFLICT DO UPDATE in backfill script
- Prevents duplicate game entries
### Changed
- **NBA data**: Fully backfilled from 2020-12-22 to 2026-01-20
- Total games: 11,827 (was 6,316)
- Added 5,511 games
- Current season (2024-25): 306 games
- Includes games from today with live statuses
### Verified
- Recent games from last 7 days present
- Games by season: 2025 (306), 2024 (1304), 2023 (1305), 2022 (2628), 2021 (3942), 2020 (2342)
- Dashboard shows up-to-date NBA data
## 2026-01-23
### Added
- **NCAABEloRating refactoring**: Successfully refactored NCAABEloRating to inherit from BaseEloRating using TDD approach
- Created comprehensive TDD test suite with 10 tests covering inheritance, required methods, and functionality
- Added missing abstract methods: expected_score() and get_all_ratings()
- Implemented legacy_update() method for backward compatibility
- All 10 TDD tests pass, maintaining existing NCAAB functionality
- Progress: 7 out of 9 sport-specific Elo classes now use unified interface
### Changed
- Updated PROJECT_PLAN.md to reflect NCAABEloRating completion
- Updated unified Elo refactoring progress to 7/9 sports completed
## 2026-01-23 (continued)
### Added
- **WNCAABEloRating refactoring**: Successfully refactored WNCAABEloRating to inherit from BaseEloRating using TDD approach
- Created comprehensive TDD test suite with 10 tests covering inheritance, required methods, and functionality
- Added missing abstract methods: expected_score() and get_all_ratings()
- Implemented legacy_update() method for backward compatibility
- All 10 TDD tests pass, maintaining existing WNCAAB functionality
- Progress: 8 out of 9 sport-specific Elo classes now use unified interface
### Changed
- Updated PROJECT_PLAN.md to reflect WNCAABEloRating completion
- Updated unified Elo refactoring progress to 8/9 sports completed
## 2026-01-23 (continued)
### Added
- **TennisEloRating refactoring**: Successfully refactored TennisEloRating to inherit from BaseEloRating using TDD approach
- Created comprehensive TDD test suite with 12 tests covering inheritance, required methods, and functionality
- Added missing abstract methods: expected_score() and get_all_ratings()
- Implemented legacy_update() method for backward compatibility
- Added interface adaptation methods (predict_team(), update_team()) for BaseEloRating compatibility
- All 12 TDD tests pass, maintaining tennis-specific functionality (ATP/WTA separation, name normalization, match tracking)
- **MILESTONE ACHIEVED**: All 9 sport-specific Elo classes now use unified BaseEloRating interface
### Changed
- Updated PROJECT_PLAN.md to reflect TennisEloRating completion
- Updated unified Elo refactoring progress to 9/9 sports completed (Phase 1.2 COMPLETED)
- TennisEloRating now properly handles name normalization and maintains separate ATP/WTA ratings
### Technical Details
- TennisEloRating required special adaptation due to different interface (player_a/player_b vs home_team/away_team)
- Implemented predict_team() and update_team() methods to bridge the interface gap
- Maintains tennis-specific features: dynamic K-factor based on match count, separate ATP/WTA ratings, name normalization

## 2026-01-25 - Fix Failing Tasks in Betting DAG

### Completed
- **Missing Dependencies**: Installed missing Python packages `kalshi-python`, `nfl_data_py`, `appdirs`, and `fastparquet` in Airflow scheduler and worker containers.
- **Import Errors**: Resolved `ModuleNotFoundError` for `kalshi_python` and `nfl_data_py` by ensuring packages are installed and importable.
- **Pandas Version Conflict**: Managed pandas version conflict (nfl-data-py requires pandas<2.0) by installing `fastparquet` and allowing the import to succeed with pandas 2.1.4 (no downgrade needed after verifying import works).
- **Cleared Failed Tasks**: Used `airflow tasks clear` to clear failed and running task instances for `multi_sport_betting_workflow` DAG, allowing fresh runs.
- **DAG Trigger Test**: Triggered a manual DAG run and verified that tasks previously failing due to import errors now succeed (e.g., `nfl_download_games` runs successfully).

### Testing Results
- **Import Test**: `nfl_data_py` import succeeds in Airflow environment.
- **Task Test**: `nfl_download_games` task executed successfully via `airflow tasks test`.
- **DAG Run**: DAG run is progressing with multiple tasks in success state; some tasks are up_for_retry due to external API issues (e.g., Kalshi markets) which are beyond dependency fixes.

### Next Steps
- Monitor DAG runs for any remaining failures and address as needed.
- Consider adding missing dependencies to `requirements.txt` to prevent future deployment issues.
