# Phase 1.1 Test Fixes
## Identified Issues:

### 1. Repository Hygiene Test Failure
**Test**: `test_no_scripts_in_root`
**Issue**: There are Python scripts in the root directory that should be moved to `scripts/` directory
**Files found in root**:
./cleanup_test_files_python.py
./cleanup_test_files.sh

./cleanup_test_files_python.py
./cleanup_test_files.sh


### 2. Portfolio Snapshots Test Failure
**Test**: `test_load_snapshots_since`
**Issue**: Database table doesn't exist (sqlite3.OperationalError: no such table: portfolio_value_snapshots)
**Root Cause**: Test is trying to access a PostgreSQL table but SQLite is being used in test environment

### 3. Bet Tracker Column Tests Failures
**Tests**: `test_create_bets_table_columns` and `test_placed_bets_table_columns`
**Issue**: Schema mismatch between expected and actual columns in placed_bets table

## Recommended Fixes:

### Fix 1: Move root scripts to scripts/ directory
```bash
# Move Python scripts from root to scripts/
mv *.py scripts/ 2>/dev/null || true
mv *.sh scripts/ 2>/dev/null || true

# Keep essential files in root
# Note: dashboard_app.py should stay in dashboard/ directory
# Note: test files should stay in tests/ directory
```

### Fix 2: Update portfolio snapshots test to use proper test database
- Need to ensure test uses in-memory SQLite with proper schema
- Or mock the database connection

### Fix 3: Update bet tracker schema tests
- Update expected column list to match actual schema
- Check `plugins/bet_tracker.py` for current schema

## Immediate Action:
Let's fix the repository hygiene issue first since it's straightforward.
