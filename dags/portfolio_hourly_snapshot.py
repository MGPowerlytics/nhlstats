"""Hourly Kalshi portfolio snapshot DAG.

Writes portfolio value snapshots into PostgreSQL for the Streamlit dashboard.

This DAG is intentionally small and safe:
- Reads Kalshi auth from runtime environment secrets
- Upserts a single row per UTC hour into PostgreSQL
- Does not trigger any downstream betting logic
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator


def snapshot_portfolio_value() -> None:
    """Fetch Kalshi portfolio balance/value and store an hourly snapshot."""

    import sys

    # Ensure plugins can be imported when running in Airflow.
    sys.path.append(str(Path(__file__).resolve().parents[1] / "plugins"))

    from kalshi_betting import KalshiBetting, KalshiConfig
    from portfolio_snapshots import upsert_hourly_snapshot

    # Load credentials using the centralized helper
    config = KalshiConfig.from_env(production=True)
    client = KalshiBetting(config=config)

    balance, portfolio_value = client.get_balance()

    upsert_hourly_snapshot(
        observed_at_utc=datetime.now(tz=timezone.utc),
        balance_dollars=float(balance),
        portfolio_value_dollars=float(portfolio_value),
    )


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


with DAG(
    dag_id="portfolio_hourly_snapshot",
    default_args=default_args,
    description="Hourly Kalshi portfolio value snapshot to PostgreSQL",
    schedule="@hourly",
    start_date=datetime(2026, 1, 20, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    tags=["kalshi", "portfolio", "postgres"],
) as dag:
    snapshot_task = PythonOperator(
        task_id="snapshot_portfolio_value",
        python_callable=snapshot_portfolio_value,
    )

    snapshot_task
