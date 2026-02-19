#!/bin/bash
# Quick test of DAG after deployment

echo "🧪 Quick DAG test after deployment..."
echo "====================================="

# Wait for Airflow to be ready
echo "1. Waiting for Airflow to be ready..."
sleep 30

# Check if we can access Airflow
echo "2. Checking Airflow accessibility..."
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ Airflow UI is accessible"
else
    echo "⚠️  Airflow UI not accessible yet, waiting..."
    sleep 30
fi

# List DAGs
echo "3. Listing DAGs..."
docker compose exec airflow-scheduler airflow dags list 2>/dev/null | grep -A5 -B5 "multi_sport" || echo "DAG list not available yet"

# Check specific DAG
echo ""
echo "4. Checking multi_sport_betting_workflow DAG..."
DAG_INFO=$(docker compose exec airflow-scheduler airflow dags list 2>/dev/null | grep "multi_sport_betting_workflow" || echo "DAG not found")

if [[ "$DAG_INFO" == *"multi_sport_betting_workflow"* ]]; then
    echo "✅ DAG found in Airflow"

    # Get DAG details
    echo "5. Getting DAG details..."
    docker compose exec airflow-scheduler airflow dags list-runs -d multi_sport_betting_workflow --output table 2>/dev/null || echo "Could not get DAG runs"

    # Trigger the DAG
    echo ""
    echo "6. Triggering DAG run..."
    TRIGGER_CMD="docker compose exec airflow-scheduler airflow dags trigger multi_sport_betting_workflow"
    echo "   Command: $TRIGGER_CMD"

    TRIGGER_OUTPUT=$($TRIGGER_CMD 2>&1)
    echo "   Output: $TRIGGER_OUTPUT"

    if echo "$TRIGGER_OUTPUT" | grep -q "Created <DagRun"; then
        DAG_RUN_ID=$(echo "$TRIGGER_OUTPUT" | grep -o "multi_sport_betting_workflow @ [^ ]*" | awk '{print $3}' || echo "unknown")
        echo "✅ DAG triggered successfully! Run ID: $DAG_RUN_ID"

        # Give it time to start
        echo "7. Waiting for DAG to start processing..."
        sleep 10

        # Check task status
        echo "8. Checking task status..."
        docker compose exec airflow-scheduler airflow tasks list -d multi_sport_betting_workflow --tree 2>/dev/null | head -20 || echo "Task list not available"

    else
        echo "❌ Failed to trigger DAG"
    fi

else
    echo "❌ DAG not found in Airflow"
    echo "   Waiting and retrying..."
    sleep 30
    DAG_INFO=$(docker compose exec airflow-scheduler airflow dags list 2>/dev/null | grep "multi_sport_betting_workflow" || echo "DAG still not found")

    if [[ "$DAG_INFO" == *"multi_sport_betting_workflow"* ]]; then
        echo "✅ DAG found after waiting"
    else
        echo "❌ DAG still not found after waiting"
        echo "   Check Airflow logs: docker compose logs airflow-scheduler"
    fi
fi

echo ""
echo "====================================="
echo "Test complete!"
echo ""
echo "To monitor DAG run:"
echo "1. Go to http://localhost:8080"
echo "2. Login with admin/admin"
echo "3. Find 'multi_sport_betting_workflow' DAG"
echo "4. Click on the latest run"
echo "5. View task logs"
echo ""
echo "Or check logs directly:"
echo "  docker compose logs airflow-scheduler | grep -A10 -B10 'Rating Changes\|unified_games'"
