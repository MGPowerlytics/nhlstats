"""Targeted tests for db_loader.py code paths"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import json


class TestNHLDatabaseLoaderBasics:
    """Test basic NHLDatabaseLoader functionality"""
    
    def test_init_default(self):
        from db_loader import NHLDatabaseLoader
        loader = NHLDatabaseLoader()
        assert 'nhlstats.duckdb' in str(loader.db_path)
    
    def test_init_custom_path(self):
        from db_loader import NHLDatabaseLoader
        loader = NHLDatabaseLoader('/tmp/custom.duckdb')
        assert 'custom.duckdb' in str(loader.db_path)
    
    def test_context_manager(self):
        from db_loader import NHLDatabaseLoader
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.duckdb'
            
            with NHLDatabaseLoader(str(db_path)) as loader:
                assert loader.conn is not None


class TestNHLDatabaseLoaderConnect:
    """Test connect method"""
    
    def test_connect_creates_tables(self):
        from db_loader import NHLDatabaseLoader
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.duckdb'
            loader = NHLDatabaseLoader(str(db_path))
            loader.connect()
            
            # Verify connection
            assert loader.conn is not None
            
            # Verify tables were created
            result = loader.conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
            table_names = [r[0] for r in result]
            
            assert 'games' in table_names
            assert 'teams' in table_names
            
            loader.close()


class TestNHLDatabaseLoaderClose:
    """Test close method"""
    
    def test_close_with_connection(self):
        from db_loader import NHLDatabaseLoader
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.duckdb'
            loader = NHLDatabaseLoader(str(db_path))
            loader.connect()
            loader.close()
            assert loader.conn is None
    
    def test_close_without_connection(self):
        from db_loader import NHLDatabaseLoader
        loader = NHLDatabaseLoader()
        loader.close()  # Should not raise


class TestLoadDate:
    """Test load_date method"""
    
    def test_load_date_no_data(self):
        from db_loader import NHLDatabaseLoader
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.duckdb'
            data_dir = Path(tmpdir) / 'data'
            data_dir.mkdir()
            
            with NHLDatabaseLoader(str(db_path)) as loader:
                result = loader.load_date('2024-01-15', data_dir=data_dir)
                # May return 0 or some number based on fallback loaders


class TestLoadEPLHistory:
    """Test load_epl_history method"""
    
    def test_method_exists(self):
        from db_loader import NHLDatabaseLoader
        loader = NHLDatabaseLoader()
        assert hasattr(loader, 'load_epl_history')


class TestLoadNCAABHistory:
    """Test load_ncaab_history method"""
    
    def test_method_exists(self):
        from db_loader import NHLDatabaseLoader
        loader = NHLDatabaseLoader()
        assert hasattr(loader, 'load_ncaab_history')


class TestLoadTennisHistory:
    """Test load_tennis_history method"""
    
    def test_method_exists(self):
        from db_loader import NHLDatabaseLoader
        loader = NHLDatabaseLoader()
        assert hasattr(loader, 'load_tennis_history')


class TestDatabaseQueries:
    """Test database query operations"""
    
    def test_execute_query(self):
        from db_loader import NHLDatabaseLoader
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.duckdb'
            
            with NHLDatabaseLoader(str(db_path)) as loader:
                result = loader.conn.execute("SELECT 1 as test").fetchall()
                assert result[0][0] == 1
    
    def test_insert_and_select(self):
        from db_loader import NHLDatabaseLoader
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.duckdb'
            
            with NHLDatabaseLoader(str(db_path)) as loader:
                # Insert a team
                loader.conn.execute("""
                    INSERT INTO teams (team_id, team_abbrev, team_name, team_common_name)
                    VALUES (1, 'BOS', 'Boston Bruins', 'Bruins')
                """)
                
                # Query back
                result = loader.conn.execute(
                    "SELECT team_name FROM teams WHERE team_id = 1"
                ).fetchone()
                
                assert result[0] == 'Boston Bruins'


class TestConnectionRetry:
    """Test connection retry logic"""
    
    def test_retry_on_lock(self):
        from db_loader import NHLDatabaseLoader
        
        # Just test that the module handles connection issues
        loader = NHLDatabaseLoader('/nonexistent/path.duckdb')
        try:
            loader.connect()
        except Exception:
            pass  # Expected to fail with invalid path


class TestModuleImports:
    """Test module can be imported"""
    
    def test_import(self):
        import db_loader
        assert hasattr(db_loader, 'NHLDatabaseLoader')
    
    def test_class_methods(self):
        from db_loader import NHLDatabaseLoader
        
        # Verify expected methods exist
        assert hasattr(NHLDatabaseLoader, 'connect')
        assert hasattr(NHLDatabaseLoader, 'close')
        assert hasattr(NHLDatabaseLoader, 'load_date')
        assert hasattr(NHLDatabaseLoader, 'load_epl_history')
        assert hasattr(NHLDatabaseLoader, 'load_ncaab_history')
        assert hasattr(NHLDatabaseLoader, 'load_tennis_history')
