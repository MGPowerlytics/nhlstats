"""Comprehensive tests for bet_tracker.py"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
from pathlib import Path
import duckdb


class TestCreateBetsTable:
    """Test create_bets_table function"""

    def test_creates_table(self):
        from bet_tracker import create_bets_table
        from db_manager import default_db
        from sqlalchemy import text

        create_bets_table()

        # Verify table exists using Postgres
        result = default_db.engine.connect().execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename = 'placed_bets'"
        )).fetchall()

        assert len(result) == 1

    def test_idempotent(self):
        from bet_tracker import create_bets_table

        # Call twice - should not error
        create_bets_table()
        create_bets_table()


class TestLoadFillsFromKalshi:
    """Test load_fills_from_kalshi function"""

    def test_function_exists(self):
        from bet_tracker import load_fills_from_kalshi
        assert callable(load_fills_from_kalshi)

    def test_with_mock_client(self):
        from bet_tracker import load_fills_from_kalshi

        mock_client = Mock()
        mock_client._get.return_value = {'fills': [
            {'id': '1', 'ticker': 'TEST-1'},
            {'id': '2', 'ticker': 'TEST-2'}
        ]}

        result = load_fills_from_kalshi(mock_client)
        assert len(result) == 2

    def test_handles_error(self):
        from bet_tracker import load_fills_from_kalshi

        mock_client = Mock()
        mock_client._get.side_effect = Exception("API Error")

        result = load_fills_from_kalshi(mock_client)
        assert result == []


class TestGetMarketStatus:
    """Test get_market_status function"""

    def test_function_exists(self):
        from bet_tracker import get_market_status
        assert callable(get_market_status)

    def test_with_mock_client(self):
        from bet_tracker import get_market_status

        mock_client = Mock()
        mock_client.get_market_details.return_value = {
            'status': 'closed',
            'result': 'yes',
            'close_time': '2024-01-15T12:00:00Z',
            'title': 'Test Market'
        }

        result = get_market_status(mock_client, 'TEST-123')

        assert result['status'] == 'closed'
        assert result['result'] == 'yes'

    def test_handles_none_response(self):
        from bet_tracker import get_market_status

        mock_client = Mock()
        mock_client.get_market_details.return_value = None

        result = get_market_status(mock_client, 'TEST-123')
        assert result == {}

    def test_handles_error(self):
        from bet_tracker import get_market_status

        mock_client = Mock()
        mock_client.get_market_details.side_effect = Exception("API Error")

        result = get_market_status(mock_client, 'TEST-123')
        assert result == {}


class TestSyncBetsToDatabase:
    """Test sync_bets_to_database function"""

    def test_function_exists(self):
        from bet_tracker import sync_bets_to_database
        assert callable(sync_bets_to_database)

    @patch('bet_tracker.KalshiBetting')
    def test_with_missing_credentials(self, mock_kalshi):
        """Test sync_bets_to_database handles missing credentials"""
        from bet_tracker import sync_bets_to_database
        import tempfile

        # Mock _read_kalshkey to raise FileNotFoundError
        with patch('bet_tracker._read_kalshkey', side_effect=FileNotFoundError("kalshkey file not found")):
            # Should raise the error
            with pytest.raises(FileNotFoundError):
                sync_bets_to_database()


class TestModuleImports:
    """Test module imports"""

    def test_import_module(self):
        import bet_tracker
        assert hasattr(bet_tracker, 'create_bets_table')
        assert hasattr(bet_tracker, 'load_fills_from_kalshi')
        assert hasattr(bet_tracker, 'get_market_status')
        assert hasattr(bet_tracker, 'sync_bets_to_database')


class TestBetsTableSchema:
    """Test bets table schema"""

    def test_table_columns(self):
        from bet_tracker import create_bets_table
        from db_manager import default_db
        from sqlalchemy import text

        create_bets_table()

        # Get columns using Postgres query
        result = default_db.engine.connect().execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'placed_bets'"
        )).fetchall()

        column_names = [r[0] for r in result]

        expected_columns = [
            'bet_id', 'sport', 'placed_date', 'ticker', 'home_team',
            'away_team', 'bet_on', 'side', 'contracts', 'price_cents',
            'cost_dollars', 'fees_dollars', 'elo_prob', 'market_prob',
            'edge', 'confidence', 'status', 'settled_date', 'payout_dollars',
            'profit_dollars', 'created_at'
        ]

        for col in expected_columns:
            assert col in column_names


class TestFillsParsing:
    """Test fills data parsing"""

    def test_parse_fill_data(self):
        from bet_tracker import load_fills_from_kalshi

        mock_client = Mock()
        mock_client._get.return_value = {'fills': [
            {
                'id': 'fill-123',
                'ticker': 'NHL-BOS-NYR',
                'side': 'yes',
                'count': 10,
                'price': 55,
                'created_time': '2024-01-15T10:00:00Z'
            }
        ]}

        result = load_fills_from_kalshi(mock_client)
        assert result[0]['ticker'] == 'NHL-BOS-NYR'


class TestDatabaseOperations:
    """Test database operations"""

    def test_insert_and_query(self):
        from bet_tracker import create_bets_table

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.duckdb'
            conn = duckdb.connect(str(db_path))

            create_bets_table(conn)

            # Insert test bet
            conn.execute("""
                INSERT INTO placed_bets (bet_id, sport, ticker, status)
                VALUES ('test-1', 'NHL', 'NHL-TEST-123', 'open')
            """)

            # Query back
            result = conn.execute(
                "SELECT * FROM placed_bets WHERE bet_id = 'test-1'"
            ).fetchone()

            assert result is not None
            conn.close()
