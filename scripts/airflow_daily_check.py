"""Daily Airflow failure check — outputs a JSON report of failed DAG runs
in the last 24 hours to stdout.

Run inside the airflow Docker container (via docker compose run --rm)
where psycopg2 is available.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "airflow"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "airflow"),
    )


def find_recent_failures(hours: int = 24) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = """
    SELECT
        dr.dag_id,
        dr.run_id,
        dr.state,
        dr.logical_date,
        dr.start_date,
        dr.end_date,
        dr.run_type
    FROM dag_run dr
    WHERE dr.state = 'failed'
      AND dr.start_date >= %s
    ORDER BY dr.start_date DESC
    """

    with get_db_connection() as conn, conn.cursor(
        cursor_factory=RealDictCursor
    ) as cursor:
        cursor.execute(query, (since,))
        return [dict(row, start_date=str(row["start_date"]), end_date=str(row["end_date"]), logical_date=str(row["logical_date"])) for row in cursor.fetchall()]


def find_failed_task_instances(dag_id: str, run_id: str) -> list[dict]:
    query = """
    SELECT task_id, state, start_date, end_date, duration
    FROM task_instance
    WHERE dag_id = %s
      AND run_id = %s
      AND state IN ('failed', 'upstream_failed')
    ORDER BY start_date
    """

    with get_db_connection() as conn, conn.cursor(
        cursor_factory=RealDictCursor
    ) as cursor:
        cursor.execute(query, (dag_id, run_id))
        return [dict(row, start_date=str(row["start_date"]), end_date=str(row["end_date"])) for row in cursor.fetchall()]


def main() -> int:
    failures = find_recent_failures(hours=24)

    if not failures:
        print(json.dumps({"status": "pass", "failures": [], "message": "No failed DAG runs in the last 24 hours."}))
        return 0

    for f in failures:
        f["failed_tasks"] = find_failed_task_instances(f["dag_id"], f["run_id"])

    report = {
        "status": "fail",
        "count": len(failures),
        "failures": failures,
        "message": f"Found {len(failures)} failed DAG run(s) in the last 24 hours.",
    }
    print(json.dumps(report))
    return 1


if __name__ == "__main__":
    sys.exit(main())
