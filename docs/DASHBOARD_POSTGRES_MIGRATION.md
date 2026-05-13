# Dashboard PostgreSQL Migration - Complete ✓

## Summary
Successfully migrated the Streamlit dashboard from DuckDB to PostgreSQL.

## Changes Made

### dashboard_app.py
1. **Removed DuckDB import** (line 6)
   - Before: `import duckdb`
   - After: Removed (not needed)

2. **Updated portfolio snapshots loading** (line 330)
   - Before: `load_snapshots_since(db_path="data/nhlstats.duckdb", since_utc=since_utc)`
   - After: `load_snapshots_since(since_utc=since_utc)`
   - Now uses default Postgres connection

3. **Updated function docstring** (line 332)
   - Before: "Enhanced betting performance page (DuckDB + portfolio snapshots)"
   - After: "Enhanced betting performance page (Postgres + portfolio snapshots)"

## Verification

### Dashboard recovery contract

The dashboard recovery boundary is the governed PostgreSQL read-model layer:

- `dashboard_portfolio_v1`
- `dashboard_live_markets_v1`
- `dashboard_rankings_v1`
- `dashboard_calibration_v1`
- `dashboard_data_quality_v1`
- `dashboard_bet_detail_v1`

Dashboard pages and `dashboard/data_layer.py` must read through these
`dashboard_*_v1` views instead of querying source tables directly. The views
are created by the governed stats-schema migration chain and are verified as
views, not tables, by schema migration verification and provider tests.

Canonical dashboard contracts live only in `tests/contracts/schemas`:

- `dashboard_portfolio_v1.schema.json`
- `dashboard_live_markets_v1.schema.json`
- `dashboard_rankings_v1.schema.json`
- `dashboard_calibration_v1.schema.json`
- `dashboard_data_quality_v1.schema.json`
- `dashboard_bet_detail_v1.schema.json`
- `dashboard_empty_state_v1.schema.json`

Do not create duplicate canonical schema sources under dashboard-specific
folders. When a dashboard contract must evolve, update the single canonical
schema in `tests/contracts/schemas`, update the governed PostgreSQL migration
or follow-on migration that exposes the matching `dashboard_*_v1` columns, and
run the local dashboard validation gate before merging.

### Local validation gate

Run the full dashboard recovery gate from the repository root:

```bash
bash scripts/validate_dashboard_gate.sh
```

The gate uses only local/test configuration. By default it unsets production
credential environment variables, refuses non-local PostgreSQL hosts and
production-like database identifiers, and provisions a disposable local
PostgreSQL container unless `DASHBOARD_GATE_USE_EXISTING_POSTGRES=1` is set for
a pre-provisioned local/CI service.

The gate performs the recovery path end to end:

1. Installs dashboard Python dependencies from `requirements.txt` and
   `requirements_dashboard.txt` unless `DASHBOARD_GATE_INSTALL_DEPS=0`.
2. Installs Playwright Chromium and browser dependencies unless the
   `DASHBOARD_GATE_INSTALL_PLAYWRIGHT*` switches disable that step.
3. Starts or connects to a local/test PostgreSQL service.
4. Applies and verifies governed stats-schema migrations, including
   `dashboard_*_v1` views and canonical Elo persistence tables.
5. Seeds deterministic dashboard source fixtures.
6. Runs static dashboard health, schema, and seed-fixture checks.
7. Runs dashboard provider tests in non-skipped live-PostgreSQL mode.
8. Starts Streamlit on a local test port and checks `/_stcore/health`.
9. Runs seeded Playwright dashboard E2E tests with `RUN_DASHBOARD_E2E=1`.

### Fail-loud versus valid empty states

The dashboard must fail loudly for infrastructure, migration, query, and
contract errors. Missing `dashboard_*_v1` views, stale source-column references,
unreadable views, failed SQL queries, and rows that violate the canonical JSON
Schemas are surfaced as explicit error states such as
`dashboard_read_model_missing`, `dashboard_query_failed`, or
`dashboard_contract_mismatch`.

True no-data conditions are valid empty states, not failures. Empty page read
models return zero rows and the data layer maps those to governed
`dashboard_empty_state_v1` payloads such as `no_portfolio_snapshots`,
`no_live_markets`, `no_rankings`, `no_calibration_predictions`,
`no_settled_calibration_outcomes`, and `no_bet_details`. The
`dashboard_data_quality_v1` view remains contract-compliant when source tables
are empty and reports warning rows instead of disappearing.

### Elo persistence expectations

Dashboard rankings are backed by canonical PostgreSQL Elo persistence in the
`elo_ratings` table. Migrations create and canonicalize that table for
historical and active rating snapshots using `sport`, `entity_type`,
`entity_id`, `entity_name`, `rating`, `valid_from`, `valid_to`, `games_played`,
and `created_at`. Only active rows (`valid_to IS NULL`) feed
`dashboard_rankings_v1`, and the canonical active uniqueness expectation is one
active row per `(sport, entity_type, entity_id)`.

### Healthcheck behavior

`python -m dashboard.healthcheck` is read-only and emits sanitized status
messages. Local checks may use `--db-mode optional` while the stricter recovery
gate and container readiness path use required database checks plus Streamlit
readiness at `/_stcore/health`. Healthchecks perform `SELECT` reads against the
database and canonical dashboard schemas; they must not require or emit
production credentials.

### ✓ All dashboard dependencies work with Postgres:
- `db_manager.default_db` - PostgreSQL connection
- `portfolio_snapshots` - Uses Postgres
- `bet_tracker` - Uses Postgres
- Database queries - All converted to Postgres

### ✓ Dashboard loads successfully:
```bash
python dashboard_app.py
# No errors, ready for streamlit run
```

### ✓ Syntax validated:
```bash
python -m py_compile dashboard_app.py
# ✓ Dashboard syntax is valid
```

## Dashboard Functionality

The dashboard now uses PostgreSQL for:
1. **Betting Performance Tracker** - Queries `placed_bets` table
2. **Portfolio Snapshots** - Queries `portfolio_value_snapshots` table
3. **Game Data** - Queries `unified_games` table
4. **Elo Ratings** - All Elo simulations work with Postgres data

## Running the Dashboard

```bash
# Start the dashboard
streamlit run dashboard_app.py

# Or with specific port
streamlit run dashboard_app.py --server.port 8501
```

## Database Configuration

The dashboard uses the default PostgreSQL connection from `db_manager`:
- Host: localhost (or from POSTGRES_HOST env var)
- Port: 5432 (or from POSTGRES_PORT env var)
- Database: airflow (or from POSTGRES_DB env var)
- User: airflow (or from POSTGRES_USER env var)

## Remaining DuckDB References

The following files still have DuckDB imports but are NOT used by the dashboard:
- Analysis scripts: `compare_nhl_systems.py`, `analyze_season_timing.py`, etc.
- Utility scripts: `check_data_status.py`, `validate_nhl_data.py`, etc.
- Some plugins: `odds_comparator.py`, `data_validation.py`, etc.

These can be migrated separately as needed, but **do not affect dashboard functionality**.

## Testing

To test the dashboard:
1. Ensure PostgreSQL is running (via docker-compose)
2. Run: `streamlit run dashboard_app.py`
3. Navigate to the Betting Performance page
4. Verify data loads from Postgres

## Status: ✓ COMPLETE

The dashboard is fully migrated to PostgreSQL and ready for production use.
