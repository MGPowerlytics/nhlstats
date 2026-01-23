"""
Tests for hourly bet sync DAG.

Following TDD approach - these tests define the expected behavior
before implementation.
"""

import pytest
from airflow.models import DagBag
from datetime import datetime


def test_bet_sync_hourly_dag_exists():
    """Test that the bet_sync_hourly DAG exists and loads without errors."""
    dagbag = DagBag(dag_folder="dags/", include_examples=False)
    assert "bet_sync_hourly" in dagbag.dags
    assert len(dagbag.import_errors) == 0


def test_bet_sync_hourly_has_hourly_schedule():
    """Test that the DAG runs on an hourly schedule."""
    dagbag = DagBag(dag_folder="dags/", include_examples=False)
    dag = dagbag.dags["bet_sync_hourly"]

    # Check schedule is hourly (Airflow 3.x uses 'schedule')
    assert dag.schedule == "@hourly" or dag.schedule == "0 * * * *"


def test_bet_sync_hourly_has_sync_task():
    """Test that the DAG contains a sync task."""
    dagbag = DagBag(dag_folder="dags/", include_examples=False)
    dag = dagbag.dags["bet_sync_hourly"]

    task_ids = [task.task_id for task in dag.tasks]
    assert "sync_bets_from_kalshi" in task_ids


def test_bet_sync_hourly_catchup_disabled():
    """Test that catchup is disabled (we don't need historical syncs)."""
    dagbag = DagBag(dag_folder="dags/", include_examples=False)
    dag = dagbag.dags["bet_sync_hourly"]

    assert dag.catchup is False


def test_bet_sync_hourly_single_active_run():
    """Test that only one DAG run can be active at a time."""
    dagbag = DagBag(dag_folder="dags/", include_examples=False)
    dag = dagbag.dags["bet_sync_hourly"]

    assert dag.max_active_runs == 1


def test_bet_sync_task_has_retries():
    """Test that the sync task has retry logic configured."""
    dagbag = DagBag(dag_folder="dags/", include_examples=False)
    dag = dagbag.dags["bet_sync_hourly"]

    sync_task = dag.get_task("sync_bets_from_kalshi")
    assert sync_task.retries >= 2
