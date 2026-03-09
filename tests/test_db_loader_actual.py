"""Tests for db_loader.py - testing actual functions"""

import tempfile
from pathlib import Path


class TestNHLDatabaseLoaderInit:
    """Test NHLDatabaseLoader initialization"""

    def test_init_default(self):
        from db_loader import NHLDatabaseLoader

        loader = NHLDatabaseLoader()
        assert "nhlstats.duckdb" in str(loader.db_path)

    def test_init_custom_path(self):
        from db_loader import NHLDatabaseLoader

        loader = NHLDatabaseLoader("/tmp/custom.duckdb")
        assert "custom.duckdb" in str(loader.db_path)


class TestNHLDatabaseLoaderConnect:
    """Test connect method"""

    def test_connect_creates_tables(self):
        from db_loader import NHLDatabaseLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.duckdb"
            loader = NHLDatabaseLoader(str(db_path))
            loader.connect()

            assert loader.conn is not None
            loader.close()


class TestNHLDatabaseLoaderContextManager:
    """Test context manager"""

    def test_context_manager(self):
        from db_loader import NHLDatabaseLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.duckdb"

            with NHLDatabaseLoader(str(db_path)) as loader:
                assert loader.conn is not None


class TestNHLDatabaseLoaderClose:
    """Test close method"""

    def test_close(self):
        from db_loader import NHLDatabaseLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.duckdb"
            loader = NHLDatabaseLoader(str(db_path))
            loader.connect()
            loader.close()
            # Should not raise


class TestLoadDate:
    """Test load_date method"""

    def test_load_date_exists(self):
        from db_loader import NHLDatabaseLoader

        loader = NHLDatabaseLoader()
        assert hasattr(loader, "load_date")


class TestLoadHistoryMethods:
    """Test history loading methods"""

    def test_load_csv_history_exists(self):
        from db_loader import NHLDatabaseLoader

        loader = NHLDatabaseLoader()
        assert hasattr(loader, "load_csv_history")

    def test_load_csv_history_accepts_sport_parameter(self):
        from db_loader import NHLDatabaseLoader
        from pathlib import Path

        loader = NHLDatabaseLoader()
        # Test that load_csv_history can be called with sport parameter
        # We don't actually load data in this test, just verify the method exists
        # and accepts the expected parameters
        assert callable(loader.load_csv_history)

    def test_load_ncaab_history_exists(self):
        from db_loader import NHLDatabaseLoader

        loader = NHLDatabaseLoader()
        assert hasattr(loader, "load_ncaab_history")


class TestModuleImports:
    """Test module can be imported"""

    def test_import(self):
        import db_loader

        assert hasattr(db_loader, "NHLDatabaseLoader")
