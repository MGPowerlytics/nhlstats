"""External watchdog for Airflow scheduler and DAG registration health."""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional

import psycopg2
import requests
from psycopg2.extras import RealDictCursor


DEFAULT_DAG_IDS = (
    "multi_sport_betting_workflow",
    "bet_sync_hourly",
    "portfolio_hourly_snapshot",
    "historical_stats_daily",
)
DEFAULT_INTERVAL_SECONDS = 300
DEFAULT_GRACE_MINUTES = 20
DEFAULT_API_URL = "http://airflow-apiserver:8080/api/v2/version"
DEFAULT_SCHEDULER_URL = "http://airflow-scheduler:8974/health"
HTTP_TIMEOUT_SECONDS = 5


@dataclass(frozen=True)
class DagStatus:
    """Current scheduler metadata for a monitored DAG."""

    dag_id: str
    is_paused: bool
    next_dagrun: Optional[datetime]
    next_dagrun_create_after: Optional[datetime]
    last_logical_date: Optional[datetime]
    last_run_state: Optional[str]


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once", action="store_true", help="Run one health check and exit."
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=int(
            os.getenv("AIRFLOW_WATCHDOG_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)
        ),
        help="Polling interval when running in loop mode.",
    )
    parser.add_argument(
        "--grace-minutes",
        type=int,
        default=int(os.getenv("AIRFLOW_WATCHDOG_GRACE_MINUTES", DEFAULT_GRACE_MINUTES)),
        help="Allowed lateness before an overdue DAG is considered unhealthy.",
    )
    parser.add_argument(
        "--dag-ids",
        nargs="*",
        default=None,
        help="Explicit DAG IDs to monitor. Defaults to AIRFLOW_WATCHDOG_DAGS or built-ins.",
    )
    return parser.parse_args(argv)


def get_monitored_dag_ids(cli_dag_ids: Optional[List[str]]) -> List[str]:
    """Resolve the list of DAG IDs to monitor."""
    if cli_dag_ids:
        return cli_dag_ids

    dag_ids_env = os.getenv("AIRFLOW_WATCHDOG_DAGS", "")
    if dag_ids_env.strip():
        return [dag_id.strip() for dag_id in dag_ids_env.split(",") if dag_id.strip()]

    return list(DEFAULT_DAG_IDS)


def check_http_endpoint(name: str, url: str) -> Optional[str]:
    """Check that an HTTP endpoint responds successfully."""
    try:
        response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        return f"{name} endpoint check failed: {exc}"

    if response.status_code >= 400:
        return f"{name} endpoint returned HTTP {response.status_code}"
    return None


def get_db_connection():
    """Create a PostgreSQL connection using Airflow runtime environment variables."""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "airflow"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "airflow"),
    )


def load_dag_statuses(dag_ids: Iterable[str]) -> List[DagStatus]:
    """Load scheduler metadata and latest run status for the monitored DAGs."""
    dag_ids = list(dag_ids)
    if not dag_ids:
        return []

    query = """
    SELECT
        d.dag_id,
        d.is_paused,
        d.next_dagrun,
        d.next_dagrun_create_after,
        latest.logical_date AS last_logical_date,
        latest.state AS last_run_state
    FROM dag d
    LEFT JOIN LATERAL (
        SELECT logical_date, state
        FROM dag_run
        WHERE dag_id = d.dag_id
        ORDER BY logical_date DESC
        LIMIT 1
    ) latest ON TRUE
    WHERE d.dag_id = ANY(%s)
    ORDER BY d.dag_id
    """

    with get_db_connection() as conn, conn.cursor(
        cursor_factory=RealDictCursor
    ) as cursor:
        cursor.execute(query, (dag_ids,))
        rows = cursor.fetchall()

    return [
        DagStatus(
            dag_id=row["dag_id"],
            is_paused=bool(row["is_paused"]),
            next_dagrun=row["next_dagrun"],
            next_dagrun_create_after=row["next_dagrun_create_after"],
            last_logical_date=row["last_logical_date"],
            last_run_state=row["last_run_state"],
        )
        for row in rows
    ]


def evaluate_dag_health(
    dag_id: str,
    status: Optional[DagStatus],
    now_utc: datetime,
    grace_minutes: int,
) -> List[str]:
    """Evaluate whether a DAG is healthy enough to keep scheduling."""
    if status is None:
        return [f"{dag_id}: DAG is not registered in Airflow metadata"]

    issues: List[str] = []
    if status.is_paused:
        issues.append(f"{dag_id}: DAG is paused")

    if status.next_dagrun_create_after is not None:
        overdue_after = status.next_dagrun_create_after + timedelta(
            minutes=grace_minutes
        )
        if now_utc > overdue_after:
            issues.append(
                f"{dag_id}: next_dagrun_create_after {status.next_dagrun_create_after.isoformat()} "
                f"is overdue by more than {grace_minutes} minutes"
            )

    return issues


def run_health_check(dag_ids: List[str], grace_minutes: int) -> List[str]:
    """Run one complete watchdog health pass and return any issues."""
    issues: List[str] = []

    api_url = os.getenv("AIRFLOW_WATCHDOG_API_URL", DEFAULT_API_URL)
    scheduler_url = os.getenv("AIRFLOW_WATCHDOG_SCHEDULER_URL", DEFAULT_SCHEDULER_URL)

    for name, url in (("API", api_url), ("scheduler", scheduler_url)):
        issue = check_http_endpoint(name, url)
        if issue:
            issues.append(issue)

    statuses = {status.dag_id: status for status in load_dag_statuses(dag_ids)}
    now_utc = datetime.now(timezone.utc)

    for dag_id in dag_ids:
        issues.extend(
            evaluate_dag_health(
                dag_id=dag_id,
                status=statuses.get(dag_id),
                now_utc=now_utc,
                grace_minutes=grace_minutes,
            )
        )

    return issues


def main(argv: Optional[List[str]] = None) -> int:
    """Entrypoint for one-shot or looping watchdog execution."""
    args = parse_args(argv)
    dag_ids = get_monitored_dag_ids(args.dag_ids)

    while True:
        try:
            issues = run_health_check(dag_ids=dag_ids, grace_minutes=args.grace_minutes)
        except Exception as exc:
            issues = [f"watchdog execution failed: {exc}"]

        timestamp = datetime.now(timezone.utc).isoformat()
        if issues:
            for issue in issues:
                print(f"[watchdog][ERROR] {timestamp} {issue}")
            if args.once:
                return 1
        else:
            print(
                f"[watchdog][OK] {timestamp} monitored DAGs healthy: "
                f"{', '.join(dag_ids)}"
            )
            if args.once:
                return 0

        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    sys.exit(main())
