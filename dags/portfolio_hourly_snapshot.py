"""Hourly Kalshi portfolio snapshot DAG.

Writes portfolio value snapshots into DuckDB for the Streamlit dashboard.

This DAG is intentionally small and safe:
- Reads Kalshi auth from `kalshkey` (same pattern as other DAGs)
- Upserts a single row per UTC hour into DuckDB
- Does not trigger any downstream betting logic
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator


def snapshot_portfolio_value() -> None:
    """Fetch Kalshi portfolio balance/value and store an hourly snapshot."""

    import sys

    # Ensure plugins can be imported when running in Airflow.
    sys.path.append(str(Path(__file__).resolve().parents[1] / "plugins"))

    from kalshi_betting import KalshiBetting
    from portfolio_snapshots import upsert_hourly_snapshot

    # Load credentials from kalshkey (supports local and /opt/airflow paths).
    kalshkey_file = Path("/opt/airflow/kalshkey")
    if not kalshkey_file.exists():
        kalshkey_file = Path("kalshkey")
    if not kalshkey_file.exists():
        raise FileNotFoundError("kalshkey file not found")

    content = kalshkey_file.read_text(encoding="utf-8")

    api_key_id = None
    for line in content.splitlines():
        if "API key id:" in line:
            api_key_id = line.split(":", 1)[1].strip()
            break
    if not api_key_id:
        raise ValueError("Could not find API key ID in kalshkey file")

    private_key_lines = []
    in_key = False
    for line in content.splitlines():
        if "-----BEGIN RSA PRIVATE KEY-----" in line:
            in_key = True
        if in_key:
            private_key_lines.append(line)
        if "-----END RSA PRIVATE KEY-----" in line:
            break

    if not private_key_lines:
        raise ValueError("Could not extract RSA private key from kalshkey")

    temp_key_file = Path("/tmp/kalshi_private_key.pem")
    temp_key_file.write_text("\n".join(private_key_lines), encoding="utf-8")

    client = KalshiBetting(
        api_key_id=api_key_id,
        private_key_path=str(temp_key_file),
        max_bet_size=5.0,
        production=True,
    )

    balance, portfolio_value = client.get_balance()

    upsert_hourly_snapshot(
        db_path="data/nhlstats.duckdb",
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
    description="Hourly Kalshi portfolio value snapshot to DuckDB",
    schedule="@hourly",
    start_date=datetime(2026, 1, 20, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    tags=["kalshi", "portfolio", "duckdb"],
) as dag:
    snapshot_task = PythonOperator(
        task_id="snapshot_portfolio_value",
        python_callable=snapshot_portfolio_value,
    )

    snapshot_task
