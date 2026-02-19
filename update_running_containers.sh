#!/bin/bash
# Update running containers with code changes

set -e

echo "Updating running containers with betting system changes..."

# Find the Airflow scheduler container
SCHEDULER_CONTAINER=$(docker ps --filter "name=airflow-scheduler" --format "{{.Names}}")
WORKER_CONTAINER=$(docker ps --filter "name=airflow-worker" --format "{{.Names}}")

if [ -z "$SCHEDULER_CONTAINER" ] || [ -z "$WORKER_CONTAINER" ]; then
    echo "Error: Could not find Airflow containers"
    exit 1
fi

echo "Found containers:"
echo "  Scheduler: $SCHEDULER_CONTAINER"
echo "  Worker: $WORKER_CONTAINER"

# Copy updated files to containers
echo "Copying updated files to containers..."

# 1. Update DAG file
echo "Updating DAG file..."
docker cp dags/multi_sport_betting_workflow.py $SCHEDULER_CONTAINER:/opt/airflow/dags/multi_sport_betting_workflow.py
docker cp dags/multi_sport_betting_workflow.py $WORKER_CONTAINER:/opt/airflow/dags/multi_sport_betting_workflow.py

# 2. Update bet_tracker.py
echo "Updating bet_tracker.py..."
docker cp plugins/bet_tracker.py $SCHEDULER_CONTAINER:/opt/airflow/plugins/bet_tracker.py
docker cp plugins/bet_tracker.py $WORKER_CONTAINER:/opt/airflow/plugins/bet_tracker.py

# 3. Restart Airflow services to pick up changes
echo "Restarting Airflow services..."
docker exec $SCHEDULER_CONTAINER bash -c "pkill -f airflow || true"
docker exec $WORKER_CONTAINER bash -c "pkill -f airflow || true"

echo "Waiting for services to restart..."
sleep 10

# 4. Test the changes
echo "Testing changes..."

# Test DAG parsing
echo "Testing DAG parsing..."
docker exec $SCHEDULER_CONTAINER airflow dags list | grep multi_sport_betting_workflow

# Unpause DAG
echo "Unpausing DAG..."
docker exec $SCHEDULER_CONTAINER airflow dags unpause multi_sport_betting_workflow

# Check DAG details
echo "Checking DAG details..."
docker exec $SCHEDULER_CONTAINER airflow dags list-runs -d multi_sport_betting_workflow | head -5

echo "========================================="
echo "UPDATE COMPLETE"
echo "========================================="
echo "Changes applied to running containers:"
echo "1. Updated DAG with new excluded segments"
echo "2. Updated bet_tracker.py with proper sport classification"
echo "3. Restarted Airflow services"
echo ""
echo "The DAG will run at its next scheduled time with the new configuration."
echo "========================================="
