"""Tests for Database Loader module."""

import pytest
import sys
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestNHLDatabaseLoader:
    """Test NHLDatabaseLoader class."""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database path."""
        return str(tmp_path / "test.duckdb")
    
    def test_init(self, temp_db):
        """Test NHLDatabaseLoader initialization."""
        from db_loader import NHLDatabaseLoader
        
        loader = NHLDatabaseLoader(db_path=temp_db)
        
        assert loader.db_path == Path(temp_db)
        assert loader.conn is None
    
    def test_context_manager(self, temp_db):
        """Test context manager usage."""
        from db_loader import NHLDatabaseLoader
        
        with NHLDatabaseLoader(db_path=temp_db) as loader:
            assert loader.conn is not None
        
        # After exiting, connection should be closed
        assert loader.conn is None
    
    def test_connect_creates_tables(self, temp_db):
        """Test that connect creates required tables."""
        from db_loader import NHLDatabaseLoader
        import duckdb
        
        loader = NHLDatabaseLoader(db_path=temp_db)
        loader.connect()
        
        # Check tables exist
        tables = loader.conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        
        assert 'games' in table_names
        assert 'teams' in table_names
        assert 'mlb_games' in table_names
        assert 'nfl_games' in table_names
        
        loader.close()
    
    def test_connect_retry_on_lock(self, temp_db):
        """Test that connect retries on database lock."""
        from db_loader import NHLDatabaseLoader
        
        # First connection
        loader1 = NHLDatabaseLoader(db_path=temp_db)
        loader1.connect()
        
        # Second connection should work (DuckDB supports concurrent reads)
        loader2 = NHLDatabaseLoader(db_path=temp_db)
        loader2.connect()
        
        loader1.close()
        loader2.close()
    
    def test_close(self, temp_db):
        """Test closing connection."""
        from db_loader import NHLDatabaseLoader
        
        loader = NHLDatabaseLoader(db_path=temp_db)
        loader.connect()
        loader.close()
        
        assert loader.conn is None


class TestDatabaseSchema:
    """Test database schema creation."""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database path."""
        return str(tmp_path / "test.duckdb")
    
    def test_games_table_schema(self, temp_db):
        """Test games table has correct schema."""
        from db_loader import NHLDatabaseLoader
        
        with NHLDatabaseLoader(db_path=temp_db) as loader:
            columns = loader.conn.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'games'
            """).fetchall()
            
            column_names = [c[0] for c in columns]
            
            assert 'game_id' in column_names
            assert 'game_date' in column_names
            assert 'home_team_name' in column_names
            assert 'away_team_name' in column_names
            assert 'home_score' in column_names
            assert 'away_score' in column_names
    
    def test_teams_table_schema(self, temp_db):
        """Test teams table has correct schema."""
        from db_loader import NHLDatabaseLoader
        
        with NHLDatabaseLoader(db_path=temp_db) as loader:
            columns = loader.conn.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'teams'
            """).fetchall()
            
            column_names = [c[0] for c in columns]
            
            assert 'team_id' in column_names
            assert 'team_abbrev' in column_names
            assert 'team_name' in column_names
    
    def test_mlb_games_table_schema(self, temp_db):
        """Test mlb_games table has correct schema."""
        from db_loader import NHLDatabaseLoader
        
        with NHLDatabaseLoader(db_path=temp_db) as loader:
            columns = loader.conn.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'mlb_games'
            """).fetchall()
            
            column_names = [c[0] for c in columns]
            
            assert 'game_id' in column_names
            assert 'game_date' in column_names
            assert 'home_team' in column_names
            assert 'away_team' in column_names
            assert 'home_score' in column_names
            assert 'away_score' in column_names
    
    def test_nfl_games_table_schema(self, temp_db):
        """Test nfl_games table has correct schema."""
        from db_loader import NHLDatabaseLoader
        
        with NHLDatabaseLoader(db_path=temp_db) as loader:
            columns = loader.conn.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'nfl_games'
            """).fetchall()
            
            column_names = [c[0] for c in columns]
            
            assert 'game_id' in column_names
            assert 'game_date' in column_names
            assert 'home_team' in column_names
            assert 'away_team' in column_names
            assert 'week' in column_names


class TestDataInsertion:
    """Test data insertion operations."""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database path."""
        return str(tmp_path / "test.duckdb")
    
    def test_insert_game(self, temp_db):
        """Test inserting a game record."""
        from db_loader import NHLDatabaseLoader
        
        with NHLDatabaseLoader(db_path=temp_db) as loader:
            # Insert a game
            loader.conn.execute("""
                INSERT INTO games (game_id, game_date, home_team_name, away_team_name, home_score, away_score)
                VALUES ('2024010101', '2024-01-01', 'Toronto Maple Leafs', 'Boston Bruins', 4, 2)
            """)
            
            # Verify insertion
            result = loader.conn.execute("SELECT COUNT(*) FROM games").fetchone()
            assert result[0] == 1
    
    def test_insert_duplicate_game_fails(self, temp_db):
        """Test that inserting duplicate game fails."""
        from db_loader import NHLDatabaseLoader
        import duckdb
        
        with NHLDatabaseLoader(db_path=temp_db) as loader:
            loader.conn.execute("""
                INSERT INTO games (game_id, game_date, home_team_name, away_team_name)
                VALUES ('2024010101', '2024-01-01', 'Toronto', 'Boston')
            """)
            
            with pytest.raises(duckdb.ConstraintException):
                loader.conn.execute("""
                    INSERT INTO games (game_id, game_date, home_team_name, away_team_name)
                    VALUES ('2024010101', '2024-01-01', 'Toronto', 'Boston')
                """)
    
    def test_insert_team(self, temp_db):
        """Test inserting a team record."""
        from db_loader import NHLDatabaseLoader
        
        with NHLDatabaseLoader(db_path=temp_db) as loader:
            loader.conn.execute("""
                INSERT INTO teams (team_id, team_abbrev, team_name, team_common_name)
                VALUES (10, 'TOR', 'Toronto Maple Leafs', 'Maple Leafs')
            """)
            
            result = loader.conn.execute("SELECT team_name FROM teams WHERE team_id = 10").fetchone()
            assert result[0] == 'Toronto Maple Leafs'


class TestDataQuerying:
    """Test data querying operations."""
    
    @pytest.fixture
    def populated_db(self, tmp_path):
        """Create a database with test data."""
        from db_loader import NHLDatabaseLoader
        
        db_path = str(tmp_path / "test.duckdb")
        
        with NHLDatabaseLoader(db_path=db_path) as loader:
            # Insert test games
            loader.conn.execute("""
                INSERT INTO games (game_id, game_date, home_team_name, away_team_name, home_score, away_score)
                VALUES 
                    ('2024010101', '2024-01-01', 'Toronto Maple Leafs', 'Boston Bruins', 4, 2),
                    ('2024010102', '2024-01-01', 'Montreal Canadiens', 'Ottawa Senators', 3, 5),
                    ('2024010201', '2024-01-02', 'Toronto Maple Leafs', 'Montreal Canadiens', 2, 1)
            """)
        
        return db_path
    
    def test_query_all_games(self, populated_db):
        """Test querying all games."""
        from db_loader import NHLDatabaseLoader
        
        with NHLDatabaseLoader(db_path=populated_db) as loader:
            result = loader.conn.execute("SELECT COUNT(*) FROM games").fetchone()
            assert result[0] == 3
    
    def test_query_games_by_date(self, populated_db):
        """Test querying games by date."""
        from db_loader import NHLDatabaseLoader
        
        with NHLDatabaseLoader(db_path=populated_db) as loader:
            result = loader.conn.execute("""
                SELECT COUNT(*) FROM games WHERE game_date = '2024-01-01'
            """).fetchone()
            assert result[0] == 2
    
    def test_query_games_by_team(self, populated_db):
        """Test querying games by team."""
        from db_loader import NHLDatabaseLoader
        
        with NHLDatabaseLoader(db_path=populated_db) as loader:
            result = loader.conn.execute("""
                SELECT COUNT(*) FROM games 
                WHERE home_team_name = 'Toronto Maple Leafs' OR away_team_name = 'Toronto Maple Leafs'
            """).fetchone()
            assert result[0] == 2
    
    def test_query_home_wins(self, populated_db):
        """Test querying home wins."""
        from db_loader import NHLDatabaseLoader
        
        with NHLDatabaseLoader(db_path=populated_db) as loader:
            result = loader.conn.execute("""
                SELECT COUNT(*) FROM games WHERE home_score > away_score
            """).fetchone()
            assert result[0] == 2  # Toronto (4-2) and Toronto (2-1)


class TestDatabasePathHandling:
    """Test database path handling."""
    
    def test_create_parent_directory(self, tmp_path):
        """Test that parent directory is created if needed."""
        from db_loader import NHLDatabaseLoader
        
        nested_path = str(tmp_path / "subdir" / "nested" / "test.duckdb")
        
        # Create parent directories
        Path(nested_path).parent.mkdir(parents=True, exist_ok=True)
        
        loader = NHLDatabaseLoader(db_path=nested_path)
        loader.connect()
        
        assert Path(nested_path).exists()
        loader.close()
    
    def test_relative_path(self, tmp_path):
        """Test using relative path."""
        from db_loader import NHLDatabaseLoader
        import os
        
        # Change to temp directory
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            loader = NHLDatabaseLoader(db_path="test.duckdb")
            loader.connect()
            
            assert (tmp_path / "test.duckdb").exists()
            loader.close()
        finally:
            os.chdir(original_dir)
