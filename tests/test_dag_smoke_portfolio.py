"""
Smoke Tests for portfolio_hourly_snapshot DAG

These tests verify that the portfolio snapshot DAG:
1. Can be imported without errors
2. Has correct DAG configuration
3. Task function works with mocked dependencies
4. Handles Kalshi API interactions correctly
5. Stores snapshots to database

Run on every commit to catch breaking changes early.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timedelta, timezone

# Add plugins and dags to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))
sys.path.insert(0, str(Path(__file__).parent.parent / "dags"))


# ============================================================================
# DAG Import and Structure Tests
# ============================================================================


class TestPortfolioSnapshotDAGStructure:
    """Test portfolio_hourly_snapshot DAG structure and configuration."""

    def test_dag_imports_without_error(self):
        """The DAG module should import without errors."""
        import portfolio_hourly_snapshot

        assert portfolio_hourly_snapshot is not None

    def test_dag_object_exists(self):
        """The DAG object should be defined."""
        from portfolio_hourly_snapshot import dag

        assert dag is not None
        assert dag.dag_id == "portfolio_hourly_snapshot"

    def test_dag_schedule_is_hourly(self):
        """DAG should run on hourly schedule."""
        from portfolio_hourly_snapshot import dag

        assert dag.schedule == "@hourly"

    def test_dag_has_correct_start_date(self):
        """DAG should have appropriate start date."""
        from portfolio_hourly_snapshot import dag

        assert dag.start_date is not None
        assert dag.start_date.year == 2026

    def test_dag_catchup_is_disabled(self):
        """DAG should not catch up on missed runs."""
        from portfolio_hourly_snapshot import dag

        assert dag.catchup is False

    def test_dag_max_active_runs_is_one(self):
        """DAG should only have one active run at a time."""
        from portfolio_hourly_snapshot import dag

        assert dag.max_active_runs == 1

    def test_dag_has_correct_tags(self):
        """DAG should have appropriate tags."""
        from portfolio_hourly_snapshot import dag

        assert "kalshi" in dag.tags
        assert "portfolio" in dag.tags
        assert "postgres" in dag.tags

    def test_dag_has_snapshot_task(self):
        """DAG should have the snapshot_portfolio_value task."""
        from portfolio_hourly_snapshot import dag

        task_ids = [task.task_id for task in dag.tasks]
        assert "snapshot_portfolio_value" in task_ids

    def test_dag_default_args_retries(self):
        """DAG default args should have retry configuration."""
        from portfolio_hourly_snapshot import default_args

        assert default_args["retries"] == 2
        assert default_args["retry_delay"] == timedelta(minutes=5)


# ============================================================================
# Task Function Tests
# ============================================================================


class TestSnapshotPortfolioValueTask:
    """Test snapshot_portfolio_value task function."""

    def test_snapshot_function_is_callable(self):
        """snapshot_portfolio_value should be callable."""
        from portfolio_hourly_snapshot import snapshot_portfolio_value

        assert callable(snapshot_portfolio_value)

    def test_snapshot_creates_kalshi_client(self):
        """snapshot_portfolio_value should create KalshiBetting client."""
        from portfolio_hourly_snapshot import snapshot_portfolio_value

        from kalshi_betting import KalshiConfig

        mock_config = KalshiConfig(api_key_id="test", private_key_path="test.pem")

        with patch(
            "kalshi_betting.KalshiConfig.from_kalshkey", return_value=mock_config
        ):
            with patch("kalshi_betting.KalshiBetting") as mock_kalshi:
                with patch("portfolio_snapshots.upsert_hourly_snapshot") as mock_upsert:
                    mock_client = MagicMock()
                    mock_client.get_balance.return_value = (100.0, 150.0)
                    mock_kalshi.return_value = mock_client

                    snapshot_portfolio_value()

                    mock_kalshi.assert_called_once()

    def test_snapshot_calls_get_balance(self):
        """snapshot_portfolio_value should call get_balance on client."""
        from portfolio_hourly_snapshot import snapshot_portfolio_value

        from kalshi_betting import KalshiConfig

        mock_config = KalshiConfig(api_key_id="test", private_key_path="test.pem")

        with patch(
            "kalshi_betting.KalshiConfig.from_kalshkey", return_value=mock_config
        ):
            with patch("kalshi_betting.KalshiBetting") as mock_kalshi:
                with patch("portfolio_snapshots.upsert_hourly_snapshot") as mock_upsert:
                    mock_client = MagicMock()
                    mock_client.get_balance.return_value = (250.50, 320.75)
                    mock_kalshi.return_value = mock_client

                    snapshot_portfolio_value()

                    mock_client.get_balance.assert_called_once()

    def test_snapshot_calls_upsert(self):
        """snapshot_portfolio_value should call upsert_hourly_snapshot."""
        from portfolio_hourly_snapshot import snapshot_portfolio_value

        from kalshi_betting import KalshiConfig

        mock_config = KalshiConfig(api_key_id="test", private_key_path="test.pem")

        with patch(
            "kalshi_betting.KalshiConfig.from_kalshkey", return_value=mock_config
        ):
            with patch("kalshi_betting.KalshiBetting") as mock_kalshi:
                with patch("portfolio_snapshots.upsert_hourly_snapshot") as mock_upsert:
                    mock_client = MagicMock()
                    mock_client.get_balance.return_value = (100.0, 150.0)
                    mock_kalshi.return_value = mock_client

                    snapshot_portfolio_value()

                    mock_upsert.assert_called_once()
                    call_kwargs = mock_upsert.call_args[1]
                    assert call_kwargs["balance_dollars"] == 100.0
                    assert call_kwargs["portfolio_value_dollars"] == 150.0


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestPortfolioSnapshotErrorHandling:
    """Test error handling in portfolio snapshot task."""

    @patch("kalshi_betting.KalshiConfig.from_kalshkey")
    def test_snapshot_raises_on_missing_kalshkey(self, mock_from_kalshkey):
        """snapshot_portfolio_value should raise when kalshkey not found."""
        from portfolio_hourly_snapshot import snapshot_portfolio_value

        mock_from_kalshkey.side_effect = FileNotFoundError("kalshkey file not found")

        with pytest.raises(FileNotFoundError, match="kalshkey"):
            snapshot_portfolio_value()

    @patch("kalshi_betting.KalshiConfig.from_kalshkey")
    def test_snapshot_raises_on_missing_api_key(self, mock_from_kalshkey):
        """snapshot_portfolio_value should raise when API key not in file."""
        from portfolio_hourly_snapshot import snapshot_portfolio_value

        mock_from_kalshkey.side_effect = ValueError("Could not find API key ID")

        with pytest.raises(ValueError, match="API key ID"):
            snapshot_portfolio_value()

    @patch("kalshi_betting.KalshiConfig.from_kalshkey")
    def test_snapshot_raises_on_missing_private_key(self, mock_from_kalshkey):
        """snapshot_portfolio_value should raise when private key not in file."""
        from portfolio_hourly_snapshot import snapshot_portfolio_value

        mock_from_kalshkey.side_effect = ValueError("Could not extract RSA private key")

        with pytest.raises(ValueError, match="private key"):
            snapshot_portfolio_value()

    def test_snapshot_propagates_kalshi_errors(self):
        """snapshot_portfolio_value should propagate Kalshi API errors."""
        from portfolio_hourly_snapshot import snapshot_portfolio_value

        from kalshi_betting import KalshiConfig

        mock_config = KalshiConfig(api_key_id="test", private_key_path="test.pem")

        with patch(
            "kalshi_betting.KalshiConfig.from_kalshkey", return_value=mock_config
        ):
            with patch("kalshi_betting.KalshiBetting") as mock_kalshi:
                with patch("portfolio_snapshots.upsert_hourly_snapshot"):
                    mock_client = MagicMock()
                    mock_client.get_balance.side_effect = Exception(
                        "API rate limit exceeded"
                    )
                    mock_kalshi.return_value = mock_client

                    with pytest.raises(Exception, match="API rate limit"):
                        snapshot_portfolio_value()


# ============================================================================
# Dependency Import Tests
# ============================================================================


class TestPortfolioSnapshotDependencies:
    """Test that portfolio snapshot dependencies can be imported."""

    def test_kalshi_betting_imports(self):
        """kalshi_betting module should import successfully."""
        from kalshi_betting import KalshiBetting

        assert KalshiBetting is not None

    def test_portfolio_snapshots_imports(self):
        """portfolio_snapshots module should import successfully."""
        from portfolio_snapshots import upsert_hourly_snapshot

        assert callable(upsert_hourly_snapshot)

    def test_airflow_imports(self):
        """Airflow imports should work."""
        from airflow import DAG
        from airflow.providers.standard.operators.python import PythonOperator

        assert DAG is not None
        assert PythonOperator is not None


# ============================================================================
# Data Flow Tests
# ============================================================================


class TestPortfolioDataFlow:
    """Test data flow through portfolio snapshot task."""

    def test_snapshot_passes_correct_values_to_upsert(self):
        """snapshot should pass balance and portfolio value to upsert."""
        from portfolio_hourly_snapshot import snapshot_portfolio_value

        kalshkey_content = """
API key id: test-api-key
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z3VS5JJcds
-----END RSA PRIVATE KEY-----
"""

        # Test with specific values
        test_cases = [
            (0.0, 0.0),
            (100.0, 100.0),
            (500.50, 750.25),
            (1000.00, 1500.00),
        ]

        for balance, portfolio_value in test_cases:
            with patch("portfolio_hourly_snapshot.Path") as mock_path:
                mock_kalshkey = MagicMock()
                mock_kalshkey.exists.return_value = True
                mock_kalshkey.read_text.return_value = kalshkey_content
                mock_path.return_value = mock_kalshkey

                with patch("kalshi_betting.KalshiBetting") as mock_kalshi:
                    with patch(
                        "portfolio_snapshots.upsert_hourly_snapshot"
                    ) as mock_upsert:
                        mock_client = MagicMock()
                        mock_client.get_balance.return_value = (
                            balance,
                            portfolio_value,
                        )
                        mock_kalshi.return_value = mock_client

                        snapshot_portfolio_value()

                        call_kwargs = mock_upsert.call_args[1]
                        assert call_kwargs["balance_dollars"] == balance
                        assert call_kwargs["portfolio_value_dollars"] == portfolio_value

    def test_snapshot_passes_utc_timestamp(self):
        """snapshot should pass UTC timestamp to upsert."""
        from portfolio_hourly_snapshot import snapshot_portfolio_value

        kalshkey_content = """
API key id: test-api-key
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z3VS5JJcds
-----END RSA PRIVATE KEY-----
"""

        with patch("portfolio_hourly_snapshot.Path") as mock_path:
            mock_kalshkey = MagicMock()
            mock_kalshkey.exists.return_value = True
            mock_kalshkey.read_text.return_value = kalshkey_content
            mock_path.return_value = mock_kalshkey

            with patch("kalshi_betting.KalshiBetting") as mock_kalshi:
                with patch("portfolio_snapshots.upsert_hourly_snapshot") as mock_upsert:
                    mock_client = MagicMock()
                    mock_client.get_balance.return_value = (100.0, 150.0)
                    mock_kalshi.return_value = mock_client

                    snapshot_portfolio_value()

                    call_kwargs = mock_upsert.call_args[1]
                    assert "observed_at_utc" in call_kwargs
                    assert call_kwargs["observed_at_utc"].tzinfo == timezone.utc
