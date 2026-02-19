#!/bin/bash
# Monitor DAG run progress

DAG_RUN_ID="manual__2026-02-05T22:03:03.450872+00:00"
echo "🔍 Monitoring DAG run: $DAG_RUN_ID"
echo "====================================="

# Check overall status
echo "1. Checking DAG run status..."
docker compose exec airflow-scheduler airflow dags state multi_sport_betting_workflow "$DAG_RUN_ID" 2>&1 | grep -v "RemovedInAirflow4Warning" || echo "Could not get state"

# List tasks and their status
echo ""
echo "2. Checking task statuses..."
docker compose exec airflow-scheduler airflow tasks states-for-dag-run multi_sport_betting_workflow "$DAG_RUN_ID" --output table 2>&1 | grep -v "RemovedInAirflow4Warning" | head -30 || echo "Could not get task states"

# Check for Elo update tasks specifically
echo ""
echo "3. Looking for Elo update task logs..."
for task in nhl_update_elo nba_update_elo mlb_update_elo nfl_update_elo; do
    echo "   Checking $task..."
    LOG_OUTPUT=$(docker compose exec airflow-scheduler airflow tasks logs -d multi_sport_betting_workflow -t "$task" --dag-run-id "$DAG_RUN_ID" 2>&1 | tail -10 | grep -v "RemovedInAirflow4Warning" || echo "No logs yet")

    if echo "$LOG_OUTPUT" | grep -q "unified_games\|Rating Changes\|Loaded.*games"; then
        echo "   ✅ $task is using unified_games!"
        echo "   Sample output:"
        echo "$LOG_OUTPUT" | tail -3
    elif echo "$LOG_OUTPUT" | grep -q "running\|success\|failed"; then
        echo "   ⚠️  $task logs available but no unified_games mention"
        echo "   Status: $(echo "$LOG_OUTPUT" | tail -1)"
    else
        echo "   ⏳ $task not started or no logs yet"
    fi
    echo ""
done

# Check worker logs for recent activity
echo "4. Checking recent worker logs..."
docker compose logs airflow-worker --tail=20 2>&1 | grep -i "executing\|finished\|success\|failed" | tail -10

echo ""
echo "====================================="
echo "To view full logs in Airflow UI:"
echo "1. Go to http://localhost:8080"
echo "2. Login with admin/admin"
echo "3. Find 'multi_sport_betting_workflow' DAG"
echo "4. Click on the run with ID: $DAG_RUN_ID"
echo "5. Click on individual tasks to view logs"
