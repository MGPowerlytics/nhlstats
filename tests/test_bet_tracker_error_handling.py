"""Test error handling improvements in bet_tracker.py.

Tests the enhanced error handling for database connection failures
added to increase system resilience and profitability.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from plugins.bet_tracker import sync_bets_to_database


class TestBetTrackerErrorHandling:
    """Test error handling improvements in bet_tracker.py."""

    def test_sync_bets_handles_database_connection_failure(self):
        """Test that sync_bets_to_database handles database connection failures gracefully."""
        # Mock Kalshi client and API responses
        mock_client = Mock()
        mock_fills = [
            {
                "ticker": "NBAGAME_LAL_BOS_20240226",
                "trade_id": "12345",
                "side": "yes",
                "count": 10,
                "yes_price": 60,
                "created_time": "2024-02-26T20:00:00Z",
            }
        ]

        # Mock database that raises exceptions on all operations
        mock_db = Mock()
        mock_db.fetch_df.side_effect = Exception("Database connection failed")
        mock_db.execute.side_effect = Exception("Database connection failed")

        from plugins.kalshi_betting import KalshiConfig

        with patch(
            "plugins.bet_tracker.KalshiConfig.from_kalshkey",
            return_value=KalshiConfig(
                api_key_id="api_key", private_key_path="/tmp/key.pem"
            ),
        ):
            with patch("plugins.bet_tracker.KalshiBetting", return_value=mock_client):
                with patch(
                    "plugins.bet_tracker.load_fills_from_kalshi",
                    return_value=mock_fills,
                ):
                    with patch(
                        "plugins.bet_tracker.get_market_status", return_value={}
                    ):
                        # Call the function with mocked database
                        added, updated = sync_bets_to_database(db=mock_db)

                        # Verify function handled the error gracefully
                        # No bets should be added or updated if database is completely down
                        assert added == 0
                        assert updated == 0
                        # Verify it tried to fetch existing bets (which failed)
                        mock_db.fetch_df.assert_called_once_with(
                            "SELECT bet_id FROM placed_bets"
                        )
                        # Verify it tried to insert the bet (which also failed)
                        assert mock_db.execute.call_count >= 1

    def test_sync_bets_handles_table_creation_failure(self):
        """Test that sync_bets_to_database handles table creation failures."""
        # Mock Kalshi client and API responses
        mock_client = Mock()
        mock_fills = [
            {
                "ticker": "NBAGAME_LAL_BOS_20240226",
                "trade_id": "12345",
                "side": "yes",
                "count": 10,
                "yes_price": 60,
                "created_time": "2024-02-26T20:00:00Z",
            }
        ]

        # Mock database that raises an exception on create_bets_table
        mock_db = Mock()
        mock_db.fetch_df.return_value = MagicMock(
            empty=False, __getitem__=lambda self, key: []
        )

        # Mock create_bets_table to raise exception
        with patch(
            "plugins.bet_tracker.create_bets_table",
            side_effect=Exception("Table creation failed"),
        ):
            from plugins.kalshi_betting import KalshiConfig

            with patch(
                "plugins.bet_tracker.KalshiConfig.from_kalshkey",
                return_value=KalshiConfig(
                    api_key_id="api_key", private_key_path="/tmp/key.pem"
                ),
            ):
                with patch(
                    "plugins.bet_tracker.KalshiBetting", return_value=mock_client
                ):
                    with patch(
                        "plugins.bet_tracker.load_fills_from_kalshi",
                        return_value=mock_fills,
                    ):
                        with patch(
                            "plugins.bet_tracker.get_market_status", return_value={}
                        ):
                            # Call the function with mocked database
                            added, updated = sync_bets_to_database(db=mock_db)

                            # Verify function handled the error gracefully
                            # It should still try to insert bets even if table creation failed
                            assert mock_db.execute.call_count >= 1

    def test_sync_bets_handles_individual_bet_insert_failure(self):
        """Test that sync_bets_to_database handles individual bet insert failures."""
        # Mock Kalshi client and API responses
        mock_client = Mock()
        mock_fills = [
            {
                "ticker": "NBAGAME_LAL_BOS_20240226",
                "trade_id": "12345",
                "side": "yes",
                "count": 10,
                "yes_price": 60,
                "created_time": "2024-02-26T20:00:00Z",
            },
            {
                "ticker": "NBAGAME_GSW_PHX_20240226",
                "trade_id": "67890",
                "side": "no",
                "count": 5,
                "no_price": 40,
                "created_time": "2024-02-26T21:00:00Z",
            },
        ]

        # Mock database that fails on first insert but succeeds on second
        mock_db = Mock()
        mock_db.fetch_df.return_value = MagicMock(
            empty=True, __getitem__=lambda self, key: []
        )

        # Track execute calls
        execute_calls = []

        def execute_side_effect(*args, **kwargs):
            execute_calls.append(args[0] if args else "unknown")
            # Fail on first bet insert (not table creation)
            if len(execute_calls) == 2:  # First bet insert (after table creation)
                raise Exception("Insert failed for first bet")
            # Other calls succeed
            return None

        mock_db.execute.side_effect = execute_side_effect

        from plugins.kalshi_betting import KalshiConfig

        with patch(
            "plugins.bet_tracker.KalshiConfig.from_kalshkey",
            return_value=KalshiConfig(
                api_key_id="api_key", private_key_path="/tmp/key.pem"
            ),
        ):
            with patch("plugins.bet_tracker.KalshiBetting", return_value=mock_client):
                with patch(
                    "plugins.bet_tracker.load_fills_from_kalshi",
                    return_value=mock_fills,
                ):
                    with patch(
                        "plugins.bet_tracker.get_market_status", return_value={}
                    ):
                        # Call the function with mocked database
                        added, updated = sync_bets_to_database(db=mock_db)

                        # Verify function handled partial failure
                        # One bet should have been added successfully (second one)
                        assert added == 1
                        assert updated == 0
                        # Should have attempted to insert both bets
                        assert (
                            mock_db.execute.call_count >= 3
                        )  # Table creation + 2 bet inserts

    def test_sync_bets_handles_backfill_metrics_failure(self):
        """Test that sync_bets_to_database handles backfill_metrics failures."""
        # Mock Kalshi client and API responses
        mock_client = Mock()
        mock_fills = [
            {
                "ticker": "NBAGAME_LAL_BOS_20240226",
                "trade_id": "12345",
                "side": "yes",
                "count": 10,
                "yes_price": 60,
                "created_time": "2024-02-26T20:00:00Z",
            }
        ]

        # Mock database
        mock_db = Mock()
        mock_db.fetch_df.return_value = MagicMock(
            empty=True, __getitem__=lambda self, key: []
        )

        # Mock backfill_bet_metrics to raise exception
        with patch(
            "plugins.bet_tracker.backfill_bet_metrics",
            side_effect=Exception("Backfill failed"),
        ):
            from plugins.kalshi_betting import KalshiConfig

            with patch(
                "plugins.bet_tracker.KalshiConfig.from_kalshkey",
                return_value=KalshiConfig(
                    api_key_id="api_key", private_key_path="/tmp/key.pem"
                ),
            ):
                with patch(
                    "plugins.bet_tracker.KalshiBetting", return_value=mock_client
                ):
                    with patch(
                        "plugins.bet_tracker.load_fills_from_kalshi",
                        return_value=mock_fills,
                    ):
                        with patch(
                            "plugins.bet_tracker.get_market_status", return_value={}
                        ):
                            # Call the function with mocked database
                            added, updated = sync_bets_to_database(db=mock_db)

                            # Verify function completed despite backfill failure
                            assert added == 1
                            assert updated == 0
                            # Should have attempted backfill
                            assert mock_db.execute.call_count >= 1
