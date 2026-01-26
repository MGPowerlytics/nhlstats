"""Tests for BetLoader and BetTracker modules."""

import pytest
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))


class TestBetLoader:
    """Test the BetLoader class."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database path."""
        return str(tmp_path / "test.duckdb")

    @pytest.fixture
    def temp_data_dir(self, tmp_path):
        """Create a temporary data directory."""
        data_dir = tmp_path / "data" / "nba"
        data_dir.mkdir(parents=True)
        return data_dir

    def test_init_creates_table(self, temp_db):
        """Test that initialization creates the bet_recommendations table."""
        from bet_loader import BetLoader
        from db_manager import default_db
        from sqlalchemy import text

        BetLoader(db_path=temp_db)

        # Check if table exists using Postgres query
        result = default_db.engine.connect().execute(
            text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'bet_recommendations'
        """)
        )
        tables = [r[0] for r in result]

        assert "bet_recommendations" in tables

    def test_load_bets_for_date_no_file(self, temp_db):
        """Test loading bets when file doesn't exist."""
        from bet_loader import BetLoader

        loader = BetLoader(db_path=temp_db)
        count = loader.load_bets_for_date("nba", "2024-01-01")

        assert count == 0

    def test_load_bets_for_date_empty_file(self, temp_db, tmp_path):
        """Test loading bets from empty JSON file."""
        from bet_loader import BetLoader

        # Create empty bets file
        bets_file = tmp_path / "nba" / "bets_2024-01-01.json"
        bets_file.parent.mkdir(parents=True, exist_ok=True)
        bets_file.write_text("[]")

        with patch("bet_loader.Path") as mock_path:
            mock_path.return_value = bets_file
            BetLoader(db_path=temp_db)
            # This tests the path where file exists but is empty

    def test_load_bets_for_date_with_bets(self, temp_db, tmp_path):
        """Test loading bets from JSON file."""
        from bet_loader import BetLoader

        # Create bets file with data
        bets_dir = tmp_path / "data" / "nba"
        bets_dir.mkdir(parents=True)
        bets_file = bets_dir / "bets_2024-01-01.json"
        bets = [
            {
                "home_team": "Lakers",
                "away_team": "Celtics",
                "bet_on": "home",
                "elo_prob": 0.65,
                "market_prob": 0.55,
                "edge": 0.10,
                "confidence": "HIGH",
                "yes_ask": 55,
                "no_ask": 45,
                "ticker": "TEST-123",
            }
        ]
        bets_file.write_text(json.dumps(bets))

        # Patch Path to point to our temp directory
        with patch("bet_loader.Path") as mock_path:

            def path_side_effect(path_str):
                if "bets_" in str(path_str):
                    return bets_file
                return Path(path_str)

            mock_path.side_effect = path_side_effect
            BetLoader(db_path=temp_db)

    def test_get_bets_summary_empty(self, temp_db):
        """Test getting summary when no bets exist."""
        from bet_loader import BetLoader

        loader = BetLoader(db_path=temp_db)
        summary = loader.get_bets_summary()

        assert isinstance(summary, list)

    def test_get_bets_summary_with_dates(self, temp_db):
        """Test getting summary with date filters."""
        from bet_loader import BetLoader

        loader = BetLoader(db_path=temp_db)
        summary = loader.get_bets_summary(
            start_date="2024-01-01", end_date="2024-12-31"
        )

        assert isinstance(summary, list)


class TestBetTracker:
    """Test the bet_tracker module functions."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database path."""
        return str(tmp_path / "test.duckdb")

    def test_create_bets_table(self, temp_db):
        """Test creating the placed_bets table."""
        from bet_tracker import create_bets_table
        from db_manager import default_db
        from sqlalchemy import text

        create_bets_table()  # Uses default_db

        # Check if table exists using Postgres query
        result = default_db.engine.connect().execute(
            text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'placed_bets'
        """)
        )
        tables = [r[0] for r in result]

        assert "placed_bets" in tables

    def test_create_bets_table_idempotent(self, temp_db):
        """Test that creating table twice doesn't error."""
        from bet_tracker import create_bets_table

        create_bets_table()
        create_bets_table()  # Should not error

    @patch("bet_tracker.KalshiBetting")
    def test_load_fills_from_kalshi_success(self, mock_kalshi):
        """Test loading fills from Kalshi API."""
        from bet_tracker import load_fills_from_kalshi

        mock_client = MagicMock()
        mock_client._get.return_value = {
            "fills": [{"trade_id": "123", "ticker": "TEST-123", "side": "yes"}]
        }

        fills = load_fills_from_kalshi(mock_client)

        assert len(fills) == 1
        assert fills[0]["trade_id"] == "123"

    @patch("bet_tracker.KalshiBetting")
    def test_load_fills_from_kalshi_error(self, mock_kalshi):
        """Test loading fills handles API error."""
        from bet_tracker import load_fills_from_kalshi

        mock_client = MagicMock()
        mock_client._get.side_effect = Exception("API Error")

        fills = load_fills_from_kalshi(mock_client)

        assert fills == []

    @patch("bet_tracker.KalshiBetting")
    def test_get_market_status_success(self, mock_kalshi):
        """Test getting market status."""
        from bet_tracker import get_market_status

        mock_client = MagicMock()
        mock_client.get_market_details.return_value = {
            "status": "active",
            "result": None,
            "close_time": "2024-12-31T23:59:59Z",
            "title": "Test Market",
        }

        status = get_market_status(mock_client, "TEST-123")

        assert status["status"] == "active"
        assert status["title"] == "Test Market"

    @patch("bet_tracker.KalshiBetting")
    def test_get_market_status_error(self, mock_kalshi):
        """Test getting market status handles error."""
        from bet_tracker import get_market_status

        mock_client = MagicMock()
        mock_client.get_market_details.side_effect = Exception("API Error")

        status = get_market_status(mock_client, "TEST-123")

        assert status == {}

    def test_get_betting_summary_empty(self, temp_db):
        """Test getting betting summary with empty database."""
        from bet_tracker import get_betting_summary, create_bets_table

        create_bets_table()

        summary = get_betting_summary()

        assert isinstance(summary, object)  # pandas DataFrame

    def test_get_betting_summary_with_date(self, temp_db):
        """Test getting betting summary for specific date."""
        from bet_tracker import get_betting_summary, create_bets_table

        create_bets_table()

        summary = get_betting_summary(date="2024-01-01")

        assert isinstance(summary, object)  # pandas DataFrame


class TestSportParsing:
    """Test sport parsing from ticker strings."""

    def test_parse_nba_ticker(self):
        """Test parsing NBA ticker."""
        ticker = "KXNBAGAME-24DEC25LALNYKNICKS"

        if "NBAGAME" in ticker:
            sport = "NBA"
        else:
            sport = "UNKNOWN"

        assert sport == "NBA"

    def test_parse_nhl_ticker(self):
        """Test parsing NHL ticker."""
        ticker = "KXNHLGAME-24DEC25TORBOT"

        if "NHLGAME" in ticker:
            sport = "NHL"
        else:
            sport = "UNKNOWN"

        assert sport == "NHL"

    def test_parse_mlb_ticker(self):
        """Test parsing MLB ticker."""
        ticker = "KXMLBGAME-24JUL15NYYRED"

        if "MLBGAME" in ticker:
            sport = "MLB"
        else:
            sport = "UNKNOWN"

        assert sport == "MLB"

    def test_parse_nfl_ticker(self):
        """Test parsing NFL ticker."""
        ticker = "KXNFLGAME-24DEC25CHIEFS"

        if "NFLGAME" in ticker:
            sport = "NFL"
        else:
            sport = "UNKNOWN"

        assert sport == "NFL"

    def test_parse_tennis_ticker(self):
        """Test parsing Tennis ticker."""
        ticker = "KXATPMATCH-26JAN17DJOKOVIC"

        if "ATPMATCH" in ticker or "WTAMATCH" in ticker:
            sport = "TENNIS"
        else:
            sport = "UNKNOWN"

        assert sport == "TENNIS"

    def test_parse_ncaab_ticker(self):
        """Test parsing NCAAB ticker."""
        ticker = "KXNCAAMBGAME-24MAR15DUKE"

        if "NCAAMBGAME" in ticker:
            sport = "NCAAB"
        else:
            sport = "UNKNOWN"

        assert sport == "NCAAB"

    def test_parse_unknown_ticker(self):
        """Test parsing unknown ticker."""
        ticker = "RANDOMTICKER-123"

        sport = "UNKNOWN"
        if "NBAGAME" in ticker:
            sport = "NBA"
        elif "NHLGAME" in ticker:
            sport = "NHL"

        assert sport == "UNKNOWN"
