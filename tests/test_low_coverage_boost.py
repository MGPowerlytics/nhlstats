"""Comprehensive tests for data_validation.py, db_loader.py, and lift_gain_analysis.py."""

import pytest
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
from datetime import datetime, date
import duckdb
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


# ============================================================
# Comprehensive tests for data_validation.py
# ============================================================

class TestDataValidationReportExtended:
    """Extended tests for DataValidationReport class."""

    def test_report_init_empty(self):
        """Test empty report initialization."""
        from data_validation import DataValidationReport

        report = DataValidationReport('nba')

        assert report.sport == 'nba'
        assert report.checks == []
        assert report.errors == []
        assert report.warnings == []
        assert report.stats == {}

    def test_report_add_passing_check(self):
        """Test adding a passing check."""
        from data_validation import DataValidationReport

        report = DataValidationReport('nhl')
        report.add_check("Test Check", True, "All good", severity='info')

        assert len(report.checks) == 1
        assert report.checks[0]['passed'] == True
        assert len(report.errors) == 0

    def test_report_add_failing_error(self):
        """Test adding a failing error check."""
        from data_validation import DataValidationReport

        report = DataValidationReport('mlb')
        report.add_check("Data Missing", False, "No data found", severity='error')

        assert len(report.checks) == 1
        assert report.checks[0]['passed'] == False
        assert len(report.errors) == 1


# ============================================================
# Tests for bet_tracker.py (low coverage -> higher)
# ============================================================

class TestBetTrackerExtended:
    """Extended tests for bet_tracker module."""

    def test_placed_bets_table_columns(self):
        """Test placed_bets table has required columns."""
        from bet_tracker import create_bets_table
        from db_manager import DBManager

        # Create a test SQLite database
        db = DBManager(connection_string="sqlite:///:memory:")

        create_bets_table(db)

        # Check columns
        with db.engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(placed_bets)"))
            columns = result.fetchall()

            # Flatten and convert to lower strings
            all_values = [str(item).lower() for col in columns for item in col]

            # Common expected columns
            expected = ['bet_id', 'sport']

            for exp in expected:
                assert exp.lower() in all_values


# ============================================================
# Tests for the_odds_api.py (33% -> higher)
# ============================================================

class TestTheOddsAPIExtended:
    """Extended tests for the_odds_api module."""

    def test_api_init(self):
        """Test TheOddsAPI initialization."""
        from the_odds_api import TheOddsAPI

        api = TheOddsAPI(api_key='test_key')

        assert api is not None

    def test_api_has_base_url(self):
        """Test API has base URL."""
        from the_odds_api import TheOddsAPI

        api = TheOddsAPI(api_key='test_key')
        assert hasattr(api, 'base_url')
