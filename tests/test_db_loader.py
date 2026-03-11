"""Tests for Database Loader module."""

import pytest
import sys
from pathlib import Path
from plugins.db_manager import default_db

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))


class TestNHLDatabaseLoader:
    """Test NHLDatabaseLoader class."""

    def test_init(self):
        """Test NHLDatabaseLoader initialization."""
        from db_loader import NHLDatabaseLoader

        loader = NHLDatabaseLoader(db=default_db)
        assert loader.db == default_db

    def test_context_manager(self):
        """Test context manager usage."""
        from db_loader import NHLDatabaseLoader

        with NHLDatabaseLoader(db=default_db) as loader:
            assert loader.conn is not None

        assert loader._schema_initialized

    def test_connect(self):
        """Test that connect works."""
        from db_loader import NHLDatabaseLoader

        loader = NHLDatabaseLoader(db=default_db)
        loader.connect()
        assert loader._schema_initialized

    def test_close(self):
        """Test closing connection."""
        from db_loader import NHLDatabaseLoader

        loader = NHLDatabaseLoader(db=default_db)
        loader.connect()
        loader.close()
        # No-op in Postgres but should not error


class TestDataInsertion:
    """Test data insertion operations."""

    def test_determine_sport_from_game_id(self):
        """Test sport determination logic."""
        from db_loader import NHLDatabaseLoader

        loader = NHLDatabaseLoader(db=default_db)

        # NHL IDs
        assert loader._determine_sport_from_game_id("2023020001") == "NHL"
        # NBA IDs
        assert loader._determine_sport_from_game_id("0022300001") == "NBA"
        # Default
        assert loader._determine_sport_from_game_id("invalid") == "NHL"

    def test_load_boxscore_invalid_file(self):
        """Test loading non-existent boxscore."""
        from db_loader import NHLDatabaseLoader

        loader = NHLDatabaseLoader(db=default_db)
        # Should not raise exception, just print error
        loader._load_boxscore("test_id", Path("nonexistent.json"))

    def test_load_date_missing_dir(self):
        """Test loading date from missing directory."""
        from db_loader import NHLDatabaseLoader

        loader = NHLDatabaseLoader(db=default_db)
        count = loader.load_date("2024-01-01", data_dir="/tmp/nonexistent_data")
        assert count == 0
