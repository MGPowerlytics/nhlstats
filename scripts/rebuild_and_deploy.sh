#!/bin/bash
# Rebuild and redeploy Airflow with updated Elo fix

set -e  # Exit on error

echo "🚀 Starting Airflow rebuild and redeployment..."
echo "=============================================="

# Step 1: Stop current services
echo "1. Stopping current Airflow services..."
docker compose down

# Step 2: Clean up volumes (optional, comment out if you want to keep data)
# echo "2. Cleaning up volumes..."
# docker compose down -v

# Step 3: Rebuild images
echo "3. Rebuilding Docker images..."
docker compose build

# Step 4: Start backing services
echo "4. Starting PostgreSQL and Redis..."
docker compose up -d postgres redis

# Step 5: Run repo-controlled bootstrap flow
echo "5. Running Airflow preflight..."
docker compose run --rm airflow-preflight

echo "6. Running Airflow bootstrap-admin..."
docker compose run --rm airflow-bootstrap-admin

# Step 7: Start steady-state Airflow services
echo "7. Starting Airflow services..."
docker compose up -d airflow-apiserver airflow-scheduler airflow-dag-processor airflow-worker airflow-triggerer dashboard

# Step 8: Verify the runtime
echo "8. Running Airflow verification..."
docker compose run --rm airflow-verify

# Step 9: Check service status
echo "9. Checking service status..."
docker compose ps

# Step 10: Wait for DAG to be loaded
echo "10. Waiting for DAG to be loaded..."
sleep 20

# Step 11: List DAGs
echo "11. Listing available DAGs..."
docker compose exec airflow-scheduler airflow dags list

echo ""
echo "=============================================="
echo "✅ Rebuild and deployment complete!"
echo ""
echo "Next steps:"
echo "1. Access Airflow UI at: http://localhost:8080"
echo "2. Login with the bootstrap admin credentials configured via"
echo "   _AIRFLOW_WWW_USER_USERNAME / _AIRFLOW_WWW_USER_PASSWORD"
echo "3. Find 'multi_sport_betting_workflow' DAG"
echo "4. Trigger the DAG manually"
echo "5. Monitor logs for 'Rating Changes' output"
echo ""
echo "To trigger DAG from command line:"
echo "  docker compose exec airflow-scheduler airflow dags trigger multi_sport_betting_workflow"
