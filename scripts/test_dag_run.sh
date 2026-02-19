#!/bin/bash
# Test DAG run after deployment

set -e

echo "🧪 Testing DAG run after deployment..."
echo "======================================"

# Wait for services to be ready
echo "1. Waiting for Airflow services to be ready..."
sleep 10

# Check if DAG exists
echo "2. Checking if DAG exists..."
DAG_EXISTS=$(docker compose exec airflow-scheduler airflow dags list | grep -c "multi_sport_betting_workflow" || true)

if [ "$DAG_EXISTS" -eq "0" ]; then
    echo "❌ DAG not found! Waiting and retrying..."
    sleep 30
    DAG_EXISTS=$(docker compose exec airflow-scheduler airflow dags list | grep -c "multi_sport_betting_workflow" || true)

    if [ "$DAG_EXISTS" -eq "0" ]; then
        echo "❌ DAG still not found after waiting. Check Airflow logs."
        exit 1
    fi
fi

echo "✅ DAG found: multi_sport_betting_workflow"

# Trigger the DAG
echo "3. Triggering DAG run..."
TRIGGER_OUTPUT=$(docker compose exec airflow-scheduler airflow dags trigger multi_sport_betting_workflow 2>&1)

if echo "$TRIGGER_OUTPUT" | grep -q "Created <DagRun"; then
    DAG_RUN_ID=$(echo "$TRIGGER_OUTPUT" | grep -o "multi_sport_betting_workflow @ [^ ]*" | awk '{print $3}')
    echo "✅ DAG triggered successfully! Run ID: $DAG_RUN_ID"
else
    echo "❌ Failed to trigger DAG:"
    echo "$TRIGGER_OUTPUT"
    exit 1
fi

# Wait for DAG to complete
echo "4. Waiting for DAG to complete (this may take several minutes)..."
echo "   Monitoring progress..."

MAX_WAIT=600  # 10 minutes
WAIT_INTERVAL=30
elapsed=0
success=false

while [ $elapsed -lt $MAX_WAIT ]; do
    # Check DAG run status
    STATUS=$(docker compose exec airflow-scheduler airflow dags list-runs -d multi_sport_betting_workflow --output json 2>/dev/null | \
        python3 -c "import sys, json; data=json.load(sys.stdin); \
        runs=[r for r in data if r.get('dag_run_id') == '$DAG_RUN_ID']; \
        print(runs[0]['state'] if runs else 'not found')" 2>/dev/null || echo "unknown")

    echo "   Status after $elapsed seconds: $STATUS"

    if [ "$STATUS" = "success" ]; then
        success=true
        break
    elif [ "$STATUS" = "failed" ]; then
        echo "❌ DAG run failed!"
        break
    elif [ "$STATUS" = "running" ]; then
        # Show task progress
        TASK_PROGRESS=$(docker compose exec airflow-scheduler airflow tasks list -d multi_sport_betting_workflow -t "update_elo_ratings" --tree 2>/dev/null | head -5 || echo "Checking...")
        echo "   Tasks running..."
    fi

    sleep $WAIT_INTERVAL
    elapsed=$((elapsed + WAIT_INTERVAL))
done

if [ "$success" = true ]; then
    echo "✅ DAG run completed successfully!"

    # Show logs for key tasks
    echo ""
    echo "5. Checking key task logs..."

    # Get task instances for this run
    echo "   Looking for Elo update tasks..."

    # Try to get logs for NHL Elo update
    echo "   Attempting to get NHL Elo update logs..."
    NHL_LOGS=$(docker compose exec airflow-scheduler airflow tasks logs -d multi_sport_betting_workflow -t nhl_update_elo --dag-run-id "$DAG_RUN_ID" 2>/dev/null | tail -20 || echo "Logs not available yet")

    if echo "$NHL_LOGS" | grep -q "Rating Changes\|unified_games"; then
        echo "   ✅ Found updated Elo logs with unified_games"
        echo "   Sample output:"
        echo "$NHL_LOGS" | tail -5
    else
        echo "   ⚠️  Could not find expected log output"
        echo "   Actual output:"
        echo "$NHL_LOGS"
    fi

else
    echo "❌ DAG run did not complete successfully within timeout"
    echo "   Final status: $STATUS"
fi

echo ""
echo "======================================"
echo "Test complete!"
echo ""
echo "To view full logs:"
echo "1. Access Airflow UI: http://localhost:8080"
echo "2. Go to DAGs → multi_sport_betting_workflow"
echo "3. Click on the latest run"
echo "4. View task logs"
echo ""
echo "Or from command line:"
echo "  docker compose exec airflow-scheduler airflow tasks logs -d multi_sport_betting_workflow -t nhl_update_elo"
