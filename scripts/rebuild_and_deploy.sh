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

# Step 4: Start services
echo "4. Starting Airflow services..."
docker compose up -d

# Step 5: Wait for services to be healthy
echo "5. Waiting for services to be healthy..."
sleep 30

# Step 6: Check service status
echo "6. Checking service status..."
docker compose ps

# Step 7: Initialize Airflow database (if needed)
echo "7. Initializing Airflow database..."
docker compose exec airflow-scheduler airflow db init 2>/dev/null || true

# Step 8: Create admin user (if needed)
echo "8. Creating admin user..."
docker compose exec airflow-scheduler airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin 2>/dev/null || true

# Step 9: Wait for DAG to be loaded
echo "9. Waiting for DAG to be loaded..."
sleep 20

# Step 10: List DAGs
echo "10. Listing available DAGs..."
docker compose exec airflow-scheduler airflow dags list

echo ""
echo "=============================================="
echo "✅ Rebuild and deployment complete!"
echo ""
echo "Next steps:"
echo "1. Access Airflow UI at: http://localhost:8080"
echo "2. Login with: admin / admin"
echo "3. Find 'multi_sport_betting_workflow' DAG"
echo "4. Trigger the DAG manually"
echo "5. Monitor logs for 'Rating Changes' output"
echo ""
echo "To trigger DAG from command line:"
echo "  docker compose exec airflow-scheduler airflow dags trigger multi_sport_betting_workflow"
