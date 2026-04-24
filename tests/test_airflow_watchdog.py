"""Unit tests for the Airflow watchdog health rules."""

from datetime import datetime, timezone

from scripts.airflow_watchdog import DagStatus, evaluate_dag_health


def test_evaluate_dag_health_reports_missing_dag() -> None:
    """Missing DAG metadata should be reported as unhealthy."""
    issues = evaluate_dag_health(
        dag_id="multi_sport_betting_workflow",
        status=None,
        now_utc=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
        grace_minutes=20,
    )

    assert issues == [
        "multi_sport_betting_workflow: DAG is not registered in Airflow metadata"
    ]


def test_evaluate_dag_health_reports_paused_and_overdue() -> None:
    """Paused and overdue DAGs should both be surfaced."""
    status = DagStatus(
        dag_id="multi_sport_betting_workflow",
        is_paused=True,
        next_dagrun=datetime(2026, 4, 21, 5, 0, tzinfo=timezone.utc),
        next_dagrun_create_after=datetime(2026, 4, 21, 5, 0, tzinfo=timezone.utc),
        last_logical_date=datetime(2026, 4, 20, 5, 0, tzinfo=timezone.utc),
        last_run_state="success",
    )

    issues = evaluate_dag_health(
        dag_id=status.dag_id,
        status=status,
        now_utc=datetime(2026, 4, 21, 5, 25, tzinfo=timezone.utc),
        grace_minutes=20,
    )

    assert any("DAG is paused" in issue for issue in issues)
    assert any("is overdue by more than 20 minutes" in issue for issue in issues)


def test_evaluate_dag_health_accepts_recent_active_dag() -> None:
    """Healthy active DAGs should not produce issues."""
    status = DagStatus(
        dag_id="bet_sync_hourly",
        is_paused=False,
        next_dagrun=datetime(2026, 4, 21, 11, 0, tzinfo=timezone.utc),
        next_dagrun_create_after=datetime(2026, 4, 21, 11, 0, tzinfo=timezone.utc),
        last_logical_date=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
        last_run_state="running",
    )

    issues = evaluate_dag_health(
        dag_id=status.dag_id,
        status=status,
        now_utc=datetime(2026, 4, 21, 10, 10, tzinfo=timezone.utc),
        grace_minutes=20,
    )

    assert issues == []
