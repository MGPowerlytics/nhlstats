#!/bin/bash
# Helper script to run the Streamlit dashboard with correct database environment variables

# Set PostgreSQL connection environment variables
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=airflow
export POSTGRES_USER=airflow
export POSTGRES_PASSWORD=airflow

# Run Streamlit dashboard
echo "Starting Streamlit dashboard with PostgreSQL connection..."
echo "Database: postgresql://${POSTGRES_USER}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
echo ""

streamlit run dashboard/dashboard_app.py "$@"
