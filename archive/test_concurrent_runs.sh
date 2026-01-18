#!/bin/bash
# Test pool serialization by triggering concurrent DAG runs

echo "🧪 Testing Pool Serialization"
echo "=============================="
echo ""

# Check pool configuration first
echo "1️⃣  Pool Configuration:"
docker compose exec -T airflow-scheduler airflow pools list 2>/dev/null | grep -E "Pool|duckdb"
echo ""

# Trigger 3 DAG runs for different dates (should process load tasks sequentially)
echo "2️⃣  Triggering 3 DAG runs (they will compete for the pool slot)..."
docker compose exec -T airflow-scheduler airflow dags trigger nhl_daily_download -e 2026-01-13 2>/dev/null
docker compose exec -T airflow-scheduler airflow dags trigger nhl_daily_download -e 2026-01-14 2>/dev/null
docker compose exec -T airflow-scheduler airflow dags trigger nhl_daily_download -e 2026-01-15 2>/dev/null
echo ""

# Wait a moment
sleep 3

# Check task states
echo "3️⃣  Task States (check for 'queued' - that means pool is limiting):"
echo ""
for date in 2026-01-13 2026-01-14 2026-01-15; do
    echo "   Date: $date"
    docker compose exec -T airflow-worker airflow tasks test nhl_daily_download load_into_duckdb $date --dry-run 2>&1 | grep -E "pool|Pool" | head -2
done
echo ""

echo "4️⃣  Check Airflow UI for visual confirmation:"
echo "   http://localhost:8080/dags/nhl_daily_download/grid"
echo ""
echo "   Look for:"
echo "   - ✅ Tasks in 'running' state (should see only 1 load_into_duckdb)"
echo "   - ⏳ Tasks in 'queued' state (others waiting for pool slot)"
echo ""
