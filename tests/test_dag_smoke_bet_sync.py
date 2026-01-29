"""
Smoke Tests for bet_sync_hourly DAG

These tests verify that the bet sync DAG:
1. Can be imported without errors
2. Has correct DAG configuration
3. Task function works with mocked dependencies
4. Handles errors appropriately

Run on every commit to catch breaking changes early.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Add plugins and dags to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))
sys.path.insert(0, str(Path(__file__).parent.parent / "dags"))


# ============================================================================
# DAG Import and Structure Tests
# ============================================================================

class TestBetSyncDAGStructure:
    """Test bet_sync_hourly DAG structure and configuration."""

    def test_dag_imports_without_error(self):
        """The DAG module should import without errors."""
        import bet_sync_hourly
        assert bet_sync_hourly is not None

    def test_dag_object_exists(self):
        """The DAG object should be defined."""
        from bet_sync_hourly import dag
        assert dag is not None
        assert dag.dag_id == "bet_sync_hourly"

    def test_dag_schedule_is_hourly(self):
        """DAG should run on hourly schedule."""
        from bet_sync_hourly import dag
        assert dag.schedule == "@hourly"

    def test_dag_has_correct_start_date(self):
        """DAG should have appropriate start date."""
        from bet_sync_hourly import dag
        assert dag.start_date is not None
        assert dag.start_date.year == 2026

    def test_dag_catchup_is_disabled(self):
        """DAG should not catch up on missed runs."""
        from bet_sync_hourly import dag
        assert dag.catchup is False

    def test_dag_max_active_runs_is_one(self):
        """DAG should only have one active run at a time."""
        from bet_sync_hourly import dag
        assert dag.max_active_runs == 1

    def test_dag_has_correct_tags(self):
        """DAG should have appropriate tags."""
        from bet_sync_hourly import dag
        assert "betting" in dag.tags
        assert "kalshi" in dag.tags
        assert "sync" in dag.tags

    def test_dag_has_sync_task(self):
        """DAG should have the sync_bets_from_kalshi task."""
        from bet_sync_hourly import dag

        task_ids = [task.task_id for task in dag.tasks]
        assert "sync_bets_from_kalshi" in task_ids

    def test_dag_default_args_retries(self):
        """DAG default args should have retry configuration."""
        from bet_sync_hourly import default_args

        assert default_args["retries"] == 3
        assert default_args["retry_delay"] == timedelta(minutes=5)


# ============================================================================
# Task Function Tests
# ============================================================================

class TestSyncBetsFromKalshiTask:
    """Test sync_bets_from_kalshi task function."""

    def test_sync_function_is_callable(self):
        """sync_bets_from_kalshi should be callable."""
        from bet_sync_hourly import sync_bets_from_kalshi
        assert callable(sync_bets_from_kalshi)

    def test_sync_calls_bet_tracker(self):
        """sync_bets_from_kalshi should call bet_tracker.sync_bets_to_database."""
        from bet_sync_hourly import sync_bets_from_kalshi

        with patch("bet_tracker.sync_bets_to_database") as mock_sync:
            mock_sync.return_value = (5, 3)

            sync_bets_from_kalshi()

            mock_sync.assert_called_once()

    def test_sync_handles_success(self, capsys):
        """sync_bets_from_kalshi should print success message."""
        from bet_sync_hourly import sync_bets_from_kalshi

        with patch("bet_tracker.sync_bets_to_database") as mock_sync:
            mock_sync.return_value = (10, 5)

            sync_bets_from_kalshi()

            captured = capsys.readouterr()
            assert "Synced bets" in captured.out
            assert "10 added" in captured.out
            assert "5 updated" in captured.out

    def test_sync_propagates_errors(self):
        """sync_bets_from_kalshi should propagate exceptions for Airflow retry."""
        from bet_sync_hourly import sync_bets_from_kalshi

        with patch("bet_tracker.sync_bets_to_database") as mock_sync:
            mock_sync.side_effect = Exception("API connection failed")

            with pytest.raises(Exception, match="API connection failed"):
                sync_bets_from_kalshi()

    def test_sync_handles_zero_results(self, capsys):
        """sync_bets_from_kalshi should handle no new bets gracefully."""
        from bet_sync_hourly import sync_bets_from_kalshi

        with patch("bet_tracker.sync_bets_to_database") as mock_sync:
            mock_sync.return_value = (0, 0)

            sync_bets_from_kalshi()

            captured = capsys.readouterr()
            assert "0 added" in captured.out
            assert "0 updated" in captured.out


# ============================================================================
# Dependency Import Tests
# ============================================================================

class TestBetSyncDependencies:
    """Test that bet_sync_hourly dependencies can be imported."""

    def test_bet_tracker_module_imports(self):
        """bet_tracker module should import successfully."""
        from bet_tracker import sync_bets_to_database
        assert callable(sync_bets_to_database)

    def test_airflow_imports(self):
        """Airflow imports should work."""
        from airflow import DAG
        from airflow.providers.standard.operators.python import PythonOperator

        assert DAG is not None
        assert PythonOperator is not None


# ============================================================================
# Integration Tests
# ============================================================================

class TestBetSyncIntegration:
    """Integration tests for bet sync functionality."""

    def test_full_task_execution(self):
        """Test complete task execution path."""
        from bet_sync_hourly import sync_bets_from_kalshi

        # Simulate different scenarios
        test_cases = [
            ((0, 0), "empty sync"),
            ((1, 0), "one added"),
            ((0, 1), "one updated"),
            ((10, 5), "mixed batch"),
            ((100, 50), "large batch"),
        ]

        for (added, updated), description in test_cases:
            with patch("bet_tracker.sync_bets_to_database") as mock_sync:
                mock_sync.return_value = (added, updated)

                # Should not raise for any case
                sync_bets_from_kalshi()

                mock_sync.assert_called()
