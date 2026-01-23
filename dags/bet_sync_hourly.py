"""
Hourly DAG to sync placed bets from Kalshi API to PostgreSQL database.

This ensures the Financial Performance dashboard always has up-to-date data
without requiring manual sync button clicks.
"""

from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator


def sync_bets_from_kalshi():
    """
    Sync bets from Kalshi API to the placed_bets table.

    This function wraps the bet_tracker sync function for use in an Airflow task.
    It fetches all placed bets from Kalshi and upserts them into PostgreSQL.
    """
    import sys

    # Ensure plugins can be imported when running in Airflow
    sys.path.append(str(Path(__file__).resolve().parents[1] / "plugins"))

    from bet_tracker import sync_bets_to_database


# Default arguments for the DAG
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}

# Create the DAG
with DAG(
    dag_id="bet_sync_hourly",
    default_args=default_args,
    description="Sync placed bets from Kalshi API to database hourly",
    schedule="@hourly",
    start_date=datetime(2026, 1, 22),
    catchup=False,
    max_active_runs=1,
    tags=["betting", "kalshi", "sync"],
) as dag:

    sync_task = PythonOperator(
        task_id="sync_bets_from_kalshi",
        python_callable=sync_bets_from_kalshi,
        retries=3,
        retry_delay=timedelta(minutes=5),
    )
