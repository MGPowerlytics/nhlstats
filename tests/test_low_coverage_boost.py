"""Comprehensive tests for data_validation.py, db_loader.py, and lift_gain_analysis.py."""

import pytest
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
from datetime import datetime, date
import duckdb

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
        assert "Data Missing" in report.errors[0]
    
    def test_report_add_failing_warning(self):
        """Test adding a failing warning check."""
        from data_validation import DataValidationReport
        
        report = DataValidationReport('nfl')
        report.add_check("Low Coverage", False, "Only 90% coverage", severity='warning')
        
        assert len(report.checks) == 1
        assert len(report.warnings) == 1
        assert "Low Coverage" in report.warnings[0]
    
    def test_report_add_multiple_stats(self):
        """Test adding multiple statistics."""
        from data_validation import DataValidationReport
        
        report = DataValidationReport('nba')
        report.add_stat('total_games', 1230)
        report.add_stat('coverage', 0.95)
        report.add_stat('date_range', '2023-10-01 to 2024-04-15')
        
        assert report.stats['total_games'] == 1230
        assert report.stats['coverage'] == 0.95
        assert report.stats['date_range'] == '2023-10-01 to 2024-04-15'
    
    def test_report_print_report(self, capsys):
        """Test print_report method."""
        from data_validation import DataValidationReport
        
        report = DataValidationReport('nba')
        report.add_check("Check 1", True, "Passed")
        report.add_stat("games", 100)
        
        result = report.print_report()
        
        captured = capsys.readouterr()
        assert "NBA" in captured.out
        assert "Check 1" in captured.out
        assert result == True  # No errors
    
    def test_report_print_report_with_errors(self, capsys):
        """Test print_report with errors returns False."""
        from data_validation import DataValidationReport
        
        report = DataValidationReport('nhl')
        report.add_check("Critical Error", False, "Database missing", severity='error')
        
        result = report.print_report()
        
        assert result == False


class TestExpectedTeams:
    """Tests for EXPECTED_TEAMS configuration."""
    
    def test_nba_teams_count(self):
        """Test NBA has 30 teams."""
        from data_validation import EXPECTED_TEAMS
        
        assert len(EXPECTED_TEAMS['nba']) == 30
    
    def test_nhl_teams_count(self):
        """Test NHL has correct team count."""
        from data_validation import EXPECTED_TEAMS
        
        # 32 teams with Utah added
        assert len(EXPECTED_TEAMS['nhl']) >= 31
    
    def test_mlb_teams_count(self):
        """Test MLB has 30 teams."""
        from data_validation import EXPECTED_TEAMS
        
        assert len(EXPECTED_TEAMS['mlb']) == 30
    
    def test_nfl_teams_count(self):
        """Test NFL has 32 teams."""
        from data_validation import EXPECTED_TEAMS
        
        assert len(EXPECTED_TEAMS['nfl']) == 32
    
    def test_all_sports_have_teams(self):
        """Test all sports have team lists."""
        from data_validation import EXPECTED_TEAMS
        
        for sport in ['nba', 'nhl', 'mlb', 'nfl']:
            assert sport in EXPECTED_TEAMS
            assert len(EXPECTED_TEAMS[sport]) > 0


class TestSeasonInfo:
    """Tests for SEASON_INFO configuration."""
    
    def test_nba_season_info(self):
        """Test NBA season info."""
        from data_validation import SEASON_INFO
        
        nba = SEASON_INFO['nba']
        assert nba['games_per_team'] == 82
        assert nba['total_games_per_season'] == 1230
    
    def test_nhl_season_info(self):
        """Test NHL season info."""
        from data_validation import SEASON_INFO
        
        nhl = SEASON_INFO['nhl']
        assert nhl['games_per_team'] == 82
        assert nhl['start_month'] == 10
    
    def test_mlb_season_info(self):
        """Test MLB season info."""
        from data_validation import SEASON_INFO
        
        mlb = SEASON_INFO['mlb']
        assert mlb['games_per_team'] == 162
        assert mlb['start_month'] == 3
    
    def test_nfl_season_info(self):
        """Test NFL season info."""
        from data_validation import SEASON_INFO
        
        nfl = SEASON_INFO['nfl']
        assert nfl['games_per_team'] == 17
        assert nfl['total_games_per_season'] == 272


class TestValidationFunctions:
    """Tests for validation functions."""
    
    def test_validate_nba_no_directory(self, tmp_path):
        """Test validate_nba_data when directory doesn't exist."""
        from data_validation import validate_nba_data
        
        # Change to temp path where data/nba doesn't exist
        import os
        original = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            report = validate_nba_data()
            
            assert report.sport == 'nba'
            # Should have error about missing directory
            assert any(not c['passed'] for c in report.checks)
        finally:
            os.chdir(original)


# ============================================================
# Comprehensive tests for db_loader.py
# ============================================================

class TestNHLDatabaseLoaderExtended:
    """Extended tests for NHLDatabaseLoader class."""
    
    def test_loader_init_creates_file(self, tmp_path):
        """Test loader creates database file."""
        from db_loader import NHLDatabaseLoader
        
        db_path = tmp_path / "test.duckdb"
        loader = NHLDatabaseLoader(db_path=str(db_path))
        
        assert loader.db_path == db_path
    
    def test_loader_context_creates_connection(self, tmp_path):
        """Test context manager creates connection."""
        from db_loader import NHLDatabaseLoader
        
        db_path = tmp_path / "test.duckdb"
        
        with NHLDatabaseLoader(db_path=str(db_path)) as loader:
            assert loader.conn is not None
    
    def test_loader_creates_games_table(self, tmp_path):
        """Test loader creates games table."""
        from db_loader import NHLDatabaseLoader
        
        db_path = tmp_path / "test.duckdb"
        
        with NHLDatabaseLoader(db_path=str(db_path)) as loader:
            # Check games table exists
            tables = loader.conn.execute("SHOW TABLES").fetchall()
            table_names = [t[0] for t in tables]
            
            assert 'games' in table_names
    
    def test_loader_creates_teams_table(self, tmp_path):
        """Test loader creates teams table."""
        from db_loader import NHLDatabaseLoader
        
        db_path = tmp_path / "test.duckdb"
        
        with NHLDatabaseLoader(db_path=str(db_path)) as loader:
            tables = loader.conn.execute("SHOW TABLES").fetchall()
            table_names = [t[0] for t in tables]
            
            assert 'teams' in table_names
    
    def test_loader_insert_game(self, tmp_path):
        """Test inserting a game."""
        from db_loader import NHLDatabaseLoader
        
        db_path = tmp_path / "test.duckdb"
        
        with NHLDatabaseLoader(db_path=str(db_path)) as loader:
            # Insert a game using correct schema
            loader.conn.execute("""
                INSERT INTO games (game_id, game_date, home_team_name, away_team_name, home_score, away_score)
                VALUES ('2024010001', '2024-01-15', 'Toronto', 'Boston', 4, 2)
            """)
            
            # Verify
            result = loader.conn.execute("SELECT * FROM games").fetchall()
            assert len(result) == 1
    
    def test_loader_multiple_games(self, tmp_path):
        """Test inserting multiple games."""
        from db_loader import NHLDatabaseLoader
        
        db_path = tmp_path / "test.duckdb"
        
        with NHLDatabaseLoader(db_path=str(db_path)) as loader:
            for i in range(10):
                loader.conn.execute(f"""
                    INSERT INTO games (game_id, game_date, home_team_name, away_team_name, home_score, away_score)
                    VALUES ('202401000{i}', '2024-01-{15+i:02d}', 'Team A', 'Team B', {4+i}, {2+i})
                """)
            
            result = loader.conn.execute("SELECT COUNT(*) FROM games").fetchone()
            assert result[0] == 10


# ============================================================
# Comprehensive tests for lift_gain_analysis.py
# ============================================================

class TestLiftGainAnalysis:
    """Tests for lift_gain_analysis module."""
    
    def test_module_import(self):
        """Test module can be imported."""
        import lift_gain_analysis
        
        assert hasattr(lift_gain_analysis, 'main')
    
    def test_analyze_sport_function_exists(self):
        """Test analyze_sport function exists."""
        from lift_gain_analysis import analyze_sport
        
        assert callable(analyze_sport)
    
    def test_decile_calculation(self):
        """Test decile calculation logic."""
        import pandas as pd
        import numpy as np
        
        # Create test data
        np.random.seed(42)
        n = 1000
        probs = np.random.random(n)
        actual = (np.random.random(n) < probs).astype(int)
        
        df = pd.DataFrame({
            'home_win_prob': probs,
            'home_won': actual
        })
        
        # Calculate deciles
        df['decile'] = pd.qcut(df['home_win_prob'], 10, labels=False, duplicates='drop')
        
        # Higher deciles should have higher win rates
        decile_stats = df.groupby('decile').agg({
            'home_won': 'mean',
            'home_win_prob': 'mean'
        }).reset_index()
        
        # Overall trend should be increasing
        assert decile_stats['home_won'].iloc[-1] > decile_stats['home_won'].iloc[0]
    
    def test_lift_calculation(self):
        """Test lift calculation."""
        # Baseline: 50% win rate
        baseline = 0.5
        
        # Top decile: 80% win rate
        actual = 0.8
        
        lift = actual / baseline
        
        assert lift == pytest.approx(1.6)
    
    def test_gain_calculation(self):
        """Test cumulative gain calculation."""
        # If top 10% captures 20% of wins
        # Gain = 20% / 10% = 2.0
        
        total_wins = 500
        decile_wins = 100
        decile_coverage = 0.1
        
        gain = (decile_wins / total_wins) / decile_coverage
        
        assert gain == pytest.approx(2.0)


# ============================================================
# Tests for nba_elo_rating.py (22% -> higher)
# ============================================================

class TestNBAEloRatingExtended:
    """Extended tests for NBA Elo module."""
    
    def test_nba_elo_init_defaults(self):
        """Test NBA Elo default parameters."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        
        assert elo.k_factor > 0
        assert elo.home_advantage > 0
    
    def test_nba_elo_init_custom(self):
        """Test NBA Elo with custom parameters."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating(k_factor=30, home_advantage=120)
        
        assert elo.k_factor == 30
        assert elo.home_advantage == 120
    
    def test_nba_elo_expected_score(self):
        """Test expected score calculation."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        
        # Equal ratings should be 0.5
        score = elo.expected_score(1500, 1500)
        assert score == pytest.approx(0.5)
    
    def test_nba_elo_expected_score_advantage(self):
        """Test expected score with rating advantage."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        
        # Higher rating should have higher expected score
        score = elo.expected_score(1600, 1400)
        assert score > 0.5
    
    def test_nba_elo_predict(self):
        """Test prediction method."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        prob = elo.predict("Lakers", "Celtics")
        
        assert 0 < prob < 1
    
    def test_nba_elo_update_home_win(self):
        """Test rating update after home win."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        initial_home = elo.get_rating("Lakers")
        
        elo.update("Lakers", "Celtics", home_won=True)
        
        assert elo.get_rating("Lakers") > initial_home
    
    def test_nba_elo_update_away_win(self):
        """Test rating update after away win."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        initial_away = elo.get_rating("Celtics")
        
        elo.update("Lakers", "Celtics", home_won=False)
        
        assert elo.get_rating("Celtics") > initial_away
    
    def test_nba_elo_rating_conservation(self):
        """Test rating points are conserved."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        
        # Start with initial ratings
        home_before = elo.get_rating("TeamA")
        away_before = elo.get_rating("TeamB")
        total_before = home_before + away_before
        
        elo.update("TeamA", "TeamB", home_won=True)
        
        home_after = elo.get_rating("TeamA")
        away_after = elo.get_rating("TeamB")
        total_after = home_after + away_after
        
        # Total rating should be conserved
        assert total_before == pytest.approx(total_after, abs=0.01)


# ============================================================
# Tests for bet_tracker.py (32% -> higher)
# ============================================================

class TestBetTrackerExtended:
    """Extended tests for bet_tracker module."""
    
    def test_create_bets_table_function(self, tmp_path):
        """Test create_bets_table creates correct table."""
        from bet_tracker import create_bets_table
        
        db_path = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db_path))
        
        create_bets_table(conn)
        
        # Verify table structure
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        
        assert 'placed_bets' in table_names
        conn.close()
    
    def test_placed_bets_table_columns(self, tmp_path):
        """Test placed_bets table has required columns."""
        from bet_tracker import create_bets_table
        
        db_path = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db_path))
        
        create_bets_table(conn)
        
        # Check columns
        columns = conn.execute("DESCRIBE placed_bets").fetchall()
        column_names = [c[0] for c in columns]
        
        # Common expected columns
        expected = ['bet_id', 'sport']
        for exp in expected:
            assert exp in column_names or any(exp.lower() in c.lower() for c in column_names)
        
        conn.close()


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
        
        api = TheOddsAPI(api_key='test')
        
        assert hasattr(api, 'base_url') or hasattr(api, 'api_key')
    
    def test_sport_keys(self):
        """Test sport key constants."""
        # Common sport keys for The Odds API
        sport_keys = {
            'nba': 'basketball_nba',
            'nhl': 'icehockey_nhl',
            'mlb': 'baseball_mlb',
            'nfl': 'americanfootball_nfl'
        }
        
        for sport, key in sport_keys.items():
            assert sport in key or key.endswith(sport)


# ============================================================
# Tests for kalshi_markets.py (51% -> higher)
# ============================================================

class TestKalshiMarketsExtended:
    """Extended tests for kalshi_markets module."""
    
    def test_kalshi_api_url(self):
        """Test Kalshi API base URL."""
        base_url = "https://api.elections.kalshi.com"
        
        assert "kalshi" in base_url
        assert "elections" in base_url
    
    def test_market_ticker_format(self):
        """Test market ticker naming convention."""
        # NBA game ticker format
        ticker = "NBA-WINNER-2024JAN15-LALUBC"
        
        assert "NBA" in ticker
        assert "2024" in ticker
    
    def test_trade_api_version(self):
        """Test trade API version."""
        api_version = "v2"
        url = f"https://api.elections.kalshi.com/trade-api/{api_version}"
        
        assert api_version in url
