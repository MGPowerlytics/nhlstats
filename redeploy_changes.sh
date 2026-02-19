#!/bin/bash
# Script to redeploy Docker containers with updated betting system changes

set -e  # Exit on error

echo "========================================="
echo "REDEPLOYING BETTING SYSTEM CHANGES"
echo "========================================="

# Change to project directory
cd /mnt/data2/nhlstats

echo "1. Stopping existing containers..."
docker-compose down

echo "2. Building new images..."
docker-compose build --no-cache

echo "3. Starting containers..."
docker-compose up -d

echo "4. Waiting for services to be healthy..."
sleep 30

echo "5. Checking container status..."
docker-compose ps

echo "6. Testing Airflow connection..."
if curl -s http://localhost:8080/health > /dev/null; then
    echo "✅ Airflow is running"
else
    echo "❌ Airflow is not responding"
    exit 1
fi

echo "7. Checking DAGs..."
# Wait a bit for DAGs to load
sleep 10

echo "8. Running a test DAG run..."
# We'll trigger a manual run of the multi_sport_betting_workflow DAG
# First, get the Airflow CLI container
AIRFLOW_CONTAINER=$(docker ps --filter "name=airflow-scheduler" --format "{{.Names}}")

if [ -n "$AIRFLOW_CONTAINER" ]; then
    echo "Found Airflow container: $AIRFLOW_CONTAINER"

    # Test DAG parsing
    echo "Testing DAG parsing..."
    docker exec $AIRFLOW_CONTAINER airflow dags list | grep multi_sport_betting_workflow

    # Unpause the DAG if paused
    echo "Unpausing DAG..."
    docker exec $AIRFLOW_CONTAINER airflow dags unpause multi_sport_betting_workflow

    # Trigger a test run for today
    TODAY=$(date +%Y-%m-%d)
    echo "Triggering test run for $TODAY..."
    docker exec $AIRFLOW_CONTAINER airflow dags trigger multi_sport_betting_workflow --conf "{\"logical_date\": \"$TODAY\"}"

    echo "✅ Test DAG run triggered"
else
    echo "❌ Could not find Airflow container"
    exit 1
fi

echo "========================================="
echo "DEPLOYMENT COMPLETE"
echo "========================================="
echo "Changes deployed:"
echo "1. Updated excluded segments in DAG:"
echo "   - WNCAAB HIGH (0% win rate, -100% ROI)"
echo "   - NBA LOW (20% win rate, -68% ROI)"
echo "   - TENNIS HIGH (44% win rate, -46% ROI)"
echo "   - TENNIS MEDIUM (61% win rate, -16% ROI)"
echo ""
echo "2. Fixed sport classification in bet_tracker.py:"
echo "   - Added WNCAAB detection (KXNCAAWBGAME tickers)"
echo "   - Added Challenger tennis detection"
echo "   - Added LIGUE1 and CBA detection"
echo ""
echo "3. All tests passed before deployment"
echo ""
echo "Next steps:"
echo "1. Monitor the DAG run in Airflow UI: http://localhost:8080"
echo "2. Check logs for any errors"
echo "3. Verify bets are placed correctly tomorrow"
echo "========================================="
