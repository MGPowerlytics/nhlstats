#!/usr/bin/env bash
# apply_stats_schema_migrations.sh
#
# Materialise the new stats/audit tables defined in plugins/database_schema_manager.py
# against the production PostgreSQL instance that the Airflow scheduler can reach.
#
# Usage (from repo root):
#   bash scripts/apply_stats_schema_migrations.sh [CONTAINER]
#
# CONTAINER defaults to 'nhlstats-airflow-scheduler-1'.
# The script will also attempt a direct host-side Python run first if psycopg2
# is available and POSTGRES_HOST is set to localhost.

set -euo pipefail

CONTAINER="${1:-nhlstats-airflow-scheduler-1}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== apply_stats_schema_migrations.sh ==="
echo "Repo: ${REPO_ROOT}"
echo ""

# ---------------------------------------------------------------------------
# Option A: run inside Docker (always available, uses internal 'postgres' host)
# ---------------------------------------------------------------------------
run_in_docker() {
    echo "▶ Running schema migration inside container: ${CONTAINER}"
    docker exec "${CONTAINER}" python -c "
import sys
sys.path.insert(0, '/opt/airflow/plugins')
from database_schema_manager import DatabaseSchemaManager
from db_manager import DBManager
db = DBManager()
mgr = DatabaseSchemaManager(db)
mgr._schema_initialized = False
mgr.initialize_schema()
print('✓ Schema migration complete.')
"
}

# ---------------------------------------------------------------------------
# Option B: run on host (requires POSTGRES_HOST=localhost and psycopg2)
# ---------------------------------------------------------------------------
run_on_host() {
    echo "▶ Running schema migration on host (POSTGRES_HOST=localhost)"
    POSTGRES_HOST=localhost python -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/plugins')
from database_schema_manager import DatabaseSchemaManager
from db_manager import DBManager
db = DBManager()
mgr = DatabaseSchemaManager(db)
mgr._schema_initialized = False
mgr.initialize_schema()
print('✓ Schema migration complete.')
"
}

# ---------------------------------------------------------------------------
# Verify: list the tables just created
# ---------------------------------------------------------------------------
verify_in_docker() {
    echo ""
    echo "▶ Verifying tables in information_schema..."
    docker exec "${CONTAINER}" python -c "
import sys
sys.path.insert(0, '/opt/airflow/plugins')
from db_manager import DBManager
from sqlalchemy import text

db = DBManager()
with db.engine.connect() as conn:
    result = conn.execute(text(\"\"\"
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name IN (
              'team_game_stats',
              'nba_team_game_stats_ext',
              'nhl_team_game_stats_ext',
              'mlb_team_game_stats_ext',
              'nfl_team_game_stats_ext',
              'soccer_team_game_stats_ext',
              'ncaab_team_game_stats_ext',
              'wncaab_team_game_stats_ext',
              'tennis_player_match_stats',
              'bet_reconciliation_audit'
          )
        ORDER BY table_name
    \"\"\"))
    tables = [row[0] for row in result]
print(f'Tables verified ({len(tables)}/10):')
for t in tables:
    print(f'  ✓ {t}')
if len(tables) < 10:
    print('⚠️  Some tables are missing!')
    sys.exit(1)
"
}

# Try host first, fall back to Docker
if POSTGRES_HOST=localhost python -c "import psycopg2; import sys; sys.path.insert(0,'${REPO_ROOT}/plugins'); from db_manager import DBManager; DBManager(connection_string='postgresql+psycopg2://airflow:airflow@localhost:5432/airflow').engine.connect().execute(__import__('sqlalchemy').text('SELECT 1'))" 2>/dev/null; then
    run_on_host
else
    run_in_docker
fi

verify_in_docker

echo ""
echo "✓ apply_stats_schema_migrations.sh finished successfully."
