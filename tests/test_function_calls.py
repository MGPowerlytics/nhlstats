"""Tests that exercise actual functions with mocked dependencies."""

import pytest
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import tempfile
from datetime import datetime, timedelta
import duckdb
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


# ============================================================
# bet_tracker.py function tests (32% -> higher)
# ============================================================

class TestBetTrackerFunctions:
    """Tests for bet_tracker functions."""

    def test_create_bets_table_creates_table(self):
        """Test create_bets_table creates the table."""
        from bet_tracker import create_bets_table
        from db_manager import DBManager

        # Create a test SQLite database
        db = DBManager(connection_string="sqlite:///:memory:")

        create_bets_table(db)

        # Verify table exists
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='placed_bets'"))
            tables = result.fetchall()
            assert len(tables) == 1
            assert tables[0][0] == 'placed_bets'

    def test_create_bets_table_columns(self):
        """Test placed_bets has all required columns."""
        from bet_tracker import create_bets_table
        from db_manager import DBManager
        from sqlalchemy import create_engine, text

        # Create a test SQLite database
        db = DBManager(connection_string="sqlite:///:memory:")

        create_bets_table(db)

        # Check columns
        with db.engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(placed_bets)"))
            columns = result.fetchall()
            column_names = [col[1].lower() for col in columns]

            expected = ['bet_id', 'sport', 'placed_date', 'ticker', 'home_team',
                       'away_team', 'bet_on', 'side', 'contracts', 'price_cents',
                       'cost_dollars', 'elo_prob', 'status']

            for col in expected:
                assert col.lower() in column_names

    def test_load_fills_from_kalshi_with_mock(self):
        """Test load_fills_from_kalshi with mocked client."""
        from bet_tracker import load_fills_from_kalshi

        mock_client = MagicMock()
        mock_client._get.return_value = {
            'fills': [
                {'fill_id': '1', 'ticker': 'NBA-1'},
                {'fill_id': '2', 'ticker': 'NBA-2'}
            ]
        }

        result = load_fills_from_kalshi(mock_client)
        assert len(result) == 2
        assert result[0]['ticker'] == 'NBA-1'
