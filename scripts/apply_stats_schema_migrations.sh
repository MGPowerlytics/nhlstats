#!/usr/bin/env bash
# Governed stats-schema migration entrypoint backed by schema_migrations.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCAL_MIGRATION_DIR="${REPO_ROOT}/migrations/stats_schema"
CONTAINER_MIGRATION_DIR="/opt/airflow/migrations/stats_schema"

echo "=== apply_stats_schema_migrations.sh ==="
echo "Repo: ${REPO_ROOT}"
echo ""

run_locally() {
    echo "▶ Applying migrations from host via localhost PostgreSQL"
    (
        cd "${REPO_ROOT}"
        POSTGRES_HOST=localhost PYTHONPATH="${REPO_ROOT}" \
            python -m plugins.schema_migrations apply \
            --migration-dir "${LOCAL_MIGRATION_DIR}"
    )
}

run_in_compose() {
    echo "▶ Applying migrations from airflow-scheduler container"
    docker compose exec -T airflow-scheduler bash -lc \
        "cd /opt/airflow && python -m plugins.schema_migrations apply --migration-dir ${CONTAINER_MIGRATION_DIR}"
}

if (
    cd "${REPO_ROOT}" &&
    POSTGRES_HOST=localhost PYTHONPATH="${REPO_ROOT}" python -c \
        "from sqlalchemy import text; from plugins.db_manager import DBManager; DBManager(connection_string='postgresql+psycopg2://airflow:airflow@localhost:5432/airflow').engine.connect().execute(text('SELECT 1'))"
) >/dev/null 2>&1; then
    run_locally
else
    run_in_compose
fi

echo ""
echo "✓ apply_stats_schema_migrations.sh finished successfully."
