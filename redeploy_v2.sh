#!/bin/bash
# Script to redeploy Docker containers with updated betting system changes
# Updated to use 'docker compose' instead of 'docker-compose'

set -e  # Exit on error

echo "========================================="
echo "REDEPLOYING BETTING SYSTEM CHANGES (V2)"
echo "========================================="

# Change to project directory
cd /mnt/data2/nhlstats

echo "1. Stopping existing containers..."
docker compose down

echo "2. Building new images..."
docker compose build --no-cache

echo "3. Starting containers..."
docker compose up -d

echo "4. Waiting for services to be healthy..."
sleep 30

echo "5. Checking container status..."
docker compose ps

echo "6. Testing Airflow connection..."
if curl -s http://localhost:8080/health > /dev/null; then
    echo "✅ Airflow is running"
else
    echo "❌ Airflow is not responding"
    # Try again after a bit more time
    echo "Waiting another 30 seconds for Airflow..."
    sleep 30
    if curl -s http://localhost:8080/health > /dev/null; then
        echo "✅ Airflow is running"
    else
        echo "❌ Airflow is still not responding"
        exit 1
    fi
fi

echo "7. Checking DAGs..."
# Wait a bit for DAGs to load
sleep 15

echo "8. Verifying Airflow container..."
AIRFLOW_CONTAINER=$(docker ps --filter "name=airflow-scheduler" --format "{{.Names}}")

if [ -n "$AIRFLOW_CONTAINER" ]; then
    echo "Found Airflow container: $AIRFLOW_CONTAINER"

    # Test DAG parsing
    echo "Testing DAG parsing for multi_sport_betting_workflow..."
    if docker exec $AIRFLOW_CONTAINER airflow dags list | grep -q multi_sport_betting_workflow; then
        echo "✅ multi_sport_betting_workflow DAG found"
    else
        echo "⚠️  multi_sport_betting_workflow DAG not found yet, it might still be parsing"
    fi
else
    echo "❌ Could not find Airflow container"
    # Not necessarily fatal if it's still starting, but a warning
fi

echo "========================================="
echo "REDEPLOYMENT COMPLETE"
echo "========================================="
