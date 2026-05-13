#!/usr/bin/env bash
# Local/CI dashboard validation gate.
#
# Runs the non-skipping dashboard provider and browser validation path with only
# local test credentials.  Local default:
#
#   bash scripts/validate_dashboard_gate.sh
#
# CI with a pre-provisioned PostgreSQL service:
#
#   DASHBOARD_GATE_USE_EXISTING_POSTGRES=1 bash scripts/validate_dashboard_gate.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
POSTGRES_CONTAINER="${DASHBOARD_GATE_POSTGRES_CONTAINER:-nhlstats-dashboard-ci-postgres}"
STARTED_POSTGRES=0
STREAMLIT_PID=""

export PYTHONPATH="${REPO_ROOT}:${REPO_ROOT}/plugins:${PYTHONPATH:-}"
export POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
export POSTGRES_PORT="${POSTGRES_PORT:-55432}"
export POSTGRES_DB="${POSTGRES_DB:-dashboard_ci}"
export POSTGRES_USER="${POSTGRES_USER:-dashboard_ci}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-dashboard_ci_password}"
export DASHBOARD_STREAMLIT_PORT="${DASHBOARD_STREAMLIT_PORT:-18501}"
export DASHBOARD_DISABLE_AUTO_REFRESH=1
export STREAMLIT_SERVER_HEADLESS=true
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

cleanup() {
    if [[ -n "${STREAMLIT_PID}" ]] && ps -p "${STREAMLIT_PID}"; then
        echo "Stopping Streamlit PID ${STREAMLIT_PID}"
        kill "${STREAMLIT_PID}"
        wait "${STREAMLIT_PID}" || true
    fi
    if [[ "${STARTED_POSTGRES}" == "1" ]]; then
        echo "Removing PostgreSQL test container ${POSTGRES_CONTAINER}"
        docker rm -f "${POSTGRES_CONTAINER}"
    fi
}
trap cleanup EXIT

connection_string() {
    echo "postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
}

assert_safe_test_configuration() {
    case "${POSTGRES_HOST}" in
        127.0.0.1|localhost|postgres)
            ;;
        *)
            echo "Refusing dashboard gate: POSTGRES_HOST must be local/test only."
            exit 2
            ;;
    esac

    case "${POSTGRES_DB}:${POSTGRES_USER}" in
        *prod*|*production*)
            echo "Refusing dashboard gate: production-like PostgreSQL identifiers are not allowed."
            exit 2
            ;;
    esac

    unset KALSHI_API_KEY_ID
    unset KALSHI_PRIVATE_KEY_PATH
    unset KALSHI_PRIVATE_KEY_FILE
    unset ODDS_API_KEY
    unset GMAIL_APP_PASSWORD
}

install_python_requirements() {
    if [[ "${DASHBOARD_GATE_INSTALL_DEPS:-1}" != "1" ]]; then
        echo "Skipping Python dependency install because DASHBOARD_GATE_INSTALL_DEPS is not 1."
        return
    fi
    "${PYTHON_BIN}" -m pip install -r "${REPO_ROOT}/requirements.txt" -r "${REPO_ROOT}/requirements_dashboard.txt"
}

install_playwright() {
    if [[ "${DASHBOARD_GATE_INSTALL_PLAYWRIGHT:-1}" != "1" ]]; then
        echo "Skipping Playwright install because DASHBOARD_GATE_INSTALL_PLAYWRIGHT is not 1."
        return
    fi
    if [[ "${DASHBOARD_GATE_INSTALL_PLAYWRIGHT_DEPS:-1}" == "1" ]]; then
        "${PYTHON_BIN}" -m playwright install --with-deps chromium
    else
        "${PYTHON_BIN}" -m playwright install chromium
    fi
}

start_postgres_if_needed() {
    if [[ "${DASHBOARD_GATE_USE_EXISTING_POSTGRES:-0}" == "1" ]]; then
        echo "Using existing PostgreSQL test service at ${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}."
        return
    fi

    docker info
    if docker ps -a --format '{{.Names}}' | grep -Fx "${POSTGRES_CONTAINER}"; then
        docker rm -f "${POSTGRES_CONTAINER}"
    fi
    docker run \
        --name "${POSTGRES_CONTAINER}" \
        --detach \
        --publish "127.0.0.1:${POSTGRES_PORT}:5432" \
        --env POSTGRES_USER="${POSTGRES_USER}" \
        --env POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
        --env POSTGRES_DB="${POSTGRES_DB}" \
        postgres:16
    STARTED_POSTGRES=1
}

wait_for_postgres() {
    echo "Waiting for PostgreSQL test service."
    for attempt in $(seq 1 90); do
        if PGPASSWORD="${POSTGRES_PASSWORD}" pg_isready \
            --host "${POSTGRES_HOST}" \
            --port "${POSTGRES_PORT}" \
            --username "${POSTGRES_USER}" \
            --dbname "${POSTGRES_DB}"; then
            return
        fi
        echo "PostgreSQL not ready yet (${attempt}/90)."
        sleep 1
    done
    echo "PostgreSQL test service did not become ready."
    exit 1
}

apply_and_verify_migrations() {
    local db_url
    db_url="$(connection_string)"
    "${PYTHON_BIN}" -m plugins.schema_migrations apply --connection-string "${db_url}"
    "${PYTHON_BIN}" -m plugins.schema_migrations verify --connection-string "${db_url}"
}

seed_dashboard_fixtures() {
    "${PYTHON_BIN}" -c '
import os
from plugins.db_manager import DBManager
from tests.contracts.fixtures.dashboard_seed_samples import build_dashboard_source_seed_payload, seed_dashboard_source_rows
db = DBManager(connection_string=os.environ["DASHBOARD_GATE_DB_URL"])
counts = seed_dashboard_source_rows(db, build_dashboard_source_seed_payload())
print("Seeded dashboard fixture rows: " + ", ".join(f"{table}={count}" for table, count in sorted(counts.items())))
db.engine.dispose()
'
}

run_static_dashboard_checks() {
    "${PYTHON_BIN}" -m pytest -q \
        tests/test_dashboard_healthcheck.py \
        tests/contracts/test_dashboard_read_model_contracts.py \
        tests/contracts/test_dashboard_seed_fixtures.py
}

run_provider_checks() {
    DASHBOARD_USE_LIVE_POSTGRES=1 \
    DASHBOARD_REQUIRE_LIVE_POSTGRES=1 \
        "${PYTHON_BIN}" -m pytest -q tests/contracts/test_dashboard_read_model_provider.py -rs
}

start_streamlit_and_healthcheck() {
    "${PYTHON_BIN}" -m streamlit run "${REPO_ROOT}/dashboard/app.py" \
        --server.address 127.0.0.1 \
        --server.port "${DASHBOARD_STREAMLIT_PORT}" \
        --server.headless true \
        --server.fileWatcherType none \
        --browser.gatherUsageStats false &
    STREAMLIT_PID="$!"

    "${PYTHON_BIN}" -c '
import os
import sys
import time
import urllib.request
url = "http://127.0.0.1:" + os.environ["DASHBOARD_STREAMLIT_PORT"] + "/_stcore/health"
for attempt in range(90):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            if response.status < 400:
                print(f"Streamlit health endpoint is ready at {url}")
                sys.exit(0)
    except Exception:
        pass
    print(f"Streamlit not ready yet ({attempt + 1}/90).")
    time.sleep(1)
raise SystemExit("Streamlit did not become ready.")
'

    "${PYTHON_BIN}" -m dashboard.healthcheck \
        --streamlit-url "http://127.0.0.1:${DASHBOARD_STREAMLIT_PORT}/_stcore/health" \
        --db-mode required
}

run_playwright_e2e() {
    RUN_DASHBOARD_E2E=1 \
    DASHBOARD_USE_LIVE_POSTGRES=1 \
    DASHBOARD_REQUIRE_LIVE_POSTGRES=1 \
        "${PYTHON_BIN}" -m pytest -q tests/test_dashboard_playwright.py -rs
}

main() {
    cd "${REPO_ROOT}"
    assert_safe_test_configuration
    export DASHBOARD_GATE_DB_URL
    DASHBOARD_GATE_DB_URL="$(connection_string)"
    install_python_requirements
    install_playwright
    start_postgres_if_needed
    wait_for_postgres
    apply_and_verify_migrations
    seed_dashboard_fixtures
    run_static_dashboard_checks
    run_provider_checks
    start_streamlit_and_healthcheck
    run_playwright_e2e
    echo "Dashboard validation gate completed successfully."
}

main "$@"
