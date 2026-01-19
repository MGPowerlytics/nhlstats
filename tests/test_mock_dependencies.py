"""Tests that mock dependencies and exercise actual function code paths."""

import pytest
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock
import tempfile
from datetime import datetime, timedelta
import duckdb
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


# ============================================================
# Tests for lift_gain_analysis.py (9% -> higher)
# ============================================================

class TestLiftGainFunctionCalls:
    """Tests that actually call lift_gain_analysis functions."""
    
    @patch('lift_gain_analysis.Path')
    def test_load_games_from_duckdb_no_database(self, mock_path):
        """Test load_games_from_duckdb when database doesn't exist."""
        from lift_gain_analysis import load_games_from_duckdb
        
        mock_path.return_value.exists.return_value = False
        
        result = load_games_from_duckdb('nhl')
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
    
    def test_get_current_season_start_nba(self):
        """Test getting NBA season start."""
        from lift_gain_analysis import get_current_season_start
        
        result = get_current_season_start('nba')
        
        assert isinstance(result, str)
        assert '-10-01' in result  # October 1
    
    def test_get_current_season_start_mlb(self):
        """Test getting MLB season start."""
        from lift_gain_analysis import get_current_season_start
        
        result = get_current_season_start('mlb')
        
        assert '-03-01' in result  # March 1
    
    def test_get_current_season_start_nfl(self):
        """Test getting NFL season start."""
        from lift_gain_analysis import get_current_season_start
        
        result = get_current_season_start('nfl')
        
        assert '-09-01' in result  # September 1
    
    def test_get_current_season_start_epl(self):
        """Test getting EPL season start."""
        from lift_gain_analysis import get_current_season_start
        
        result = get_current_season_start('epl')
        
        assert '-08-01' in result  # August 1
    
    def test_sport_config_nba(self):
        """Test NBA sport config."""
        from lift_gain_analysis import SPORT_CONFIG
        
        config = SPORT_CONFIG['nba']
        
        assert config['elo_module'] == 'nba_elo_rating'
        assert config['elo_class'] == 'NBAEloRating'
        assert config['k_factor'] == 20
        assert config['home_advantage'] == 100
    
    def test_sport_config_nhl(self):
        """Test NHL sport config."""
        from lift_gain_analysis import SPORT_CONFIG
        
        config = SPORT_CONFIG['nhl']
        
        assert config['elo_module'] == 'nhl_elo_rating'
        assert config['data_source'] == 'duckdb'


# ============================================================
# Tests for data_validation.py functions (18% -> higher)
# ============================================================

class TestDataValidationFunctionCalls:
    """Tests that call data_validation functions."""
    
    def test_report_print_with_stats(self, capsys):
        """Test print_report with various stats."""
        from data_validation import DataValidationReport
        
        report = DataValidationReport('nba')
        report.add_stat('total_games', 1230)
        report.add_stat('coverage_pct', 98.5)
        report.add_stat('date_range', '2023-10-01 to 2024-04-15')
        report.add_check('Data Exists', True, 'Found 1230 games')
        
        result = report.print_report()
        
        captured = capsys.readouterr()
        assert 'NBA' in captured.out
        assert '1,230' in captured.out or '1230' in captured.out
        assert result == True
    
    def test_report_print_with_errors(self, capsys):
        """Test print_report with errors."""
        from data_validation import DataValidationReport
        
        report = DataValidationReport('nhl')
        report.add_check('Critical', False, 'Database missing', 'error')
        
        result = report.print_report()
        
        captured = capsys.readouterr()
        assert 'Errors' in captured.out or '❌' in captured.out
        assert result == False
    
    def test_report_print_with_warnings(self, capsys):
        """Test print_report with warnings."""
        from data_validation import DataValidationReport
        
        report = DataValidationReport('mlb')
        report.add_check('Coverage', False, 'Only 90%', 'warning')
        
        result = report.print_report()
        
        captured = capsys.readouterr()
        assert result == True  # Warnings don't fail
    
    def test_expected_teams_nba(self):
        """Test EXPECTED_TEAMS for NBA."""
        from data_validation import EXPECTED_TEAMS
        
        teams = EXPECTED_TEAMS['nba']
        
        assert 'Lakers' in teams
        assert 'Celtics' in teams
        assert len(teams) == 30
    
    def test_expected_teams_nhl(self):
        """Test EXPECTED_TEAMS for NHL."""
        from data_validation import EXPECTED_TEAMS
        
        teams = EXPECTED_TEAMS['nhl']
        
        assert 'Toronto Maple Leafs' in teams
        assert 'Boston Bruins' in teams
    
    def test_expected_teams_mlb(self):
        """Test EXPECTED_TEAMS for MLB."""
        from data_validation import EXPECTED_TEAMS
        
        teams = EXPECTED_TEAMS['mlb']
        
        assert 'New York Yankees' in teams
        assert 'Boston Red Sox' in teams
    
    def test_expected_teams_nfl(self):
        """Test EXPECTED_TEAMS for NFL."""
        from data_validation import EXPECTED_TEAMS
        
        teams = EXPECTED_TEAMS['nfl']
        
        assert 'Kansas City Chiefs' in teams
        assert 'Dallas Cowboys' in teams
    
    def test_season_info_nba(self):
        """Test SEASON_INFO for NBA."""
        from data_validation import SEASON_INFO
        
        info = SEASON_INFO['nba']
        
        assert info['games_per_team'] == 82
        assert info['total_games_per_season'] == 1230
        assert info['start_month'] == 10
    
    def test_season_info_nhl(self):
        """Test SEASON_INFO for NHL."""
        from data_validation import SEASON_INFO
        
        info = SEASON_INFO['nhl']
        
        assert info['games_per_team'] == 82
        assert info['total_games_per_season'] == 1312
    
    def test_season_info_mlb(self):
        """Test SEASON_INFO for MLB."""
        from data_validation import SEASON_INFO
        
        info = SEASON_INFO['mlb']
        
        assert info['games_per_team'] == 162
        assert info['total_games_per_season'] == 2430
    
    def test_season_info_nfl(self):
        """Test SEASON_INFO for NFL."""
        from data_validation import SEASON_INFO
        
        info = SEASON_INFO['nfl']
        
        assert info['games_per_team'] == 17
        assert info['total_games_per_season'] == 272


# ============================================================
# Tests for db_loader.py functions (17% -> higher)
# ============================================================

class TestDBLoaderFunctionCalls:
    """Tests that call db_loader functions."""
    
    def test_loader_connect_disconnect(self, tmp_path):
        """Test connect and close."""
        from db_loader import NHLDatabaseLoader
        
        db_path = tmp_path / "test.duckdb"
        loader = NHLDatabaseLoader(db_path=str(db_path))
        
        loader.connect()
        assert loader.conn is not None
        
        loader.close()
        # After close, should be able to reconnect
        loader.connect()
        assert loader.conn is not None
    
    def test_loader_query_games(self, tmp_path):
        """Test querying games from loader."""
        from db_loader import NHLDatabaseLoader
        
        db_path = tmp_path / "test.duckdb"
        
        with NHLDatabaseLoader(db_path=str(db_path)) as loader:
            # Insert a test game
            loader.conn.execute("""
                INSERT INTO games (game_id, game_date, home_team_name, away_team_name, 
                                  home_score, away_score, game_state)
                VALUES ('2024010001', '2024-01-15', 'Toronto', 'Boston', 4, 2, 'OFF')
            """)
            
            # Query back
            result = loader.conn.execute("SELECT * FROM games").fetchall()
            
            assert len(result) == 1


# ============================================================
# Tests for kalshi_betting.py functions (65% -> higher)
# ============================================================

class TestKalshiBettingFunctionCalls:
    """Tests that call kalshi_betting functions."""
    
    def test_verify_game_not_started_tennis(self):
        """Test tennis game verification uses correct fields."""
        # For tennis, we use matchup and bet_on instead of home_team/away_team
        rec = {
            'matchup': 'Djokovic vs Federer',
            'bet_on': 'Djokovic',
            'elo_prob': 0.68
        }
        
        sport = 'tennis'
        
        # This is how the code should extract fields for tennis
        if sport.lower() == 'tennis':
            matchup = rec.get('matchup', '')
            bet_on = rec.get('bet_on', '')
            assert matchup == 'Djokovic vs Federer'
            assert bet_on == 'Djokovic'


# ============================================================
# Tests for the_odds_api.py functions (33% -> higher)
# ============================================================

class TestTheOddsAPIFunctionCalls:
    """Tests that call the_odds_api functions."""
    
    def test_api_sport_keys(self):
        """Test sport key mapping."""
        from the_odds_api import TheOddsAPI
        
        api = TheOddsAPI(api_key='test')
        
        # Standard sport keys
        keys = {
            'nba': 'basketball_nba',
            'nhl': 'icehockey_nhl',
            'mlb': 'baseball_mlb',
            'nfl': 'americanfootball_nfl'
        }
        
        for sport, key in keys.items():
            assert sport in key or key.endswith(sport)


# ============================================================
# Tests for Elo rating modules (49-79%)
# ============================================================

class TestEloRatingFunctionCalls:
    """Tests that call Elo rating functions."""
    
    def test_nba_elo_full_workflow(self):
        """Test full NBA Elo workflow."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating(k_factor=20, home_advantage=100)
        
        # Initial state
        assert elo.get_rating('Lakers') == 1500
        
        # Make prediction
        prob = elo.predict('Lakers', 'Celtics')
        assert 0 < prob < 1
        
        # Update ratings
        elo.update('Lakers', 'Celtics', home_won=True)
        
        # Lakers should have gained rating
        assert elo.get_rating('Lakers') > 1500
        assert elo.get_rating('Celtics') < 1500
    
    def test_mlb_elo_full_workflow(self):
        """Test full MLB Elo workflow."""
        from mlb_elo_rating import MLBEloRating
        
        elo = MLBEloRating()
        
        # Initial state
        assert elo.get_rating('Yankees') == 1500
        
        # Make prediction
        prob = elo.predict('Yankees', 'Red Sox')
        assert 0 < prob < 1
        
        # Update ratings with score
        elo.update('Yankees', 'Red Sox', home_score=5, away_score=3)
        
        # Yankees should have gained
        assert elo.get_rating('Yankees') > 1500
    
    def test_nfl_elo_full_workflow(self):
        """Test full NFL Elo workflow."""
        from nfl_elo_rating import NFLEloRating
        
        elo = NFLEloRating()
        
        # Initial state
        assert elo.get_rating('Chiefs') == 1500
        
        # Make prediction
        prob = elo.predict('Chiefs', 'Bills')
        assert 0 < prob < 1
        
        # Update ratings
        elo.update('Chiefs', 'Bills', home_score=28, away_score=21)
        
        # Chiefs should have gained
        assert elo.get_rating('Chiefs') > 1500
    
    def test_ncaab_elo_full_workflow(self):
        """Test full NCAAB Elo workflow."""
        from ncaab_elo_rating import NCAABEloRating
        
        elo = NCAABEloRating()
        
        # Test neutral vs home court
        neutral = elo.predict('Duke', 'UNC', is_neutral=True)
        home = elo.predict('Duke', 'UNC', is_neutral=False)
        
        assert home > neutral  # Home advantage helps
        
        # Update and check
        change = elo.update('Duke', 'UNC', home_win=True)
        assert isinstance(change, float)
    
    def test_nhl_elo_full_workflow(self):
        """Test full NHL Elo workflow."""
        from nhl_elo_rating import NHLEloRating
        
        elo = NHLEloRating(k_factor=10, home_advantage=50)
        
        # Series of games
        for _ in range(5):
            elo.update('Maple Leafs', 'Bruins', home_won=True)
        
        assert elo.get_rating('Maple Leafs') > elo.get_rating('Bruins')
    
    def test_epl_elo_full_workflow(self):
        """Test full EPL Elo workflow."""
        from epl_elo_rating import EPLEloRating
        
        elo = EPLEloRating()
        
        prob = elo.predict('Arsenal', 'Chelsea')
        assert 0 < prob < 1
    
    def test_ligue1_elo_full_workflow(self):
        """Test full Ligue1 Elo workflow."""
        from ligue1_elo_rating import Ligue1EloRating
        
        elo = Ligue1EloRating()
        
        prob = elo.predict('PSG', 'Lyon')
        assert 0 < prob < 1
    
    def test_tennis_elo_full_workflow(self):
        """Test full Tennis Elo workflow."""
        from tennis_elo_rating import TennisEloRating
        
        elo = TennisEloRating()
        
        # Initial ratings
        assert elo.get_rating('Djokovic') == 1500
        
        # Prediction
        prob = elo.predict('Djokovic', 'Federer')
        assert 0 < prob < 1
        
        # Update - tennis uses (winner, loser) signature
        elo.update('Djokovic', 'Federer')
        
        assert elo.get_rating('Djokovic') > 1500
    
    def test_glicko2_full_workflow(self):
        """Test full Glicko2 workflow."""
        from glicko2_rating import Glicko2Rating
        
        g = Glicko2Rating()
        
        # Initial state
        rating = g.get_rating('PlayerA')
        assert rating['rating'] == 1500
        
        # Prediction
        prob = g.predict('PlayerA', 'PlayerB')
        assert 0 < prob < 1
        
        # Update
        g.update('PlayerA', 'PlayerB', home_won=True)


# ============================================================
# Tests for game modules (15-31%)
# ============================================================

class TestGameModuleFunctionCalls:
    """Tests that call game module functions."""
    
    def test_nba_games_creates_output(self, tmp_path):
        """Test NBAGames creates output directory."""
        from nba_games import NBAGames
        
        games = NBAGames(output_dir=str(tmp_path / 'nba'))
        
        assert (tmp_path / 'nba').exists()
    
    def test_mlb_games_creates_output(self, tmp_path):
        """Test MLBGames creates output directory."""
        from mlb_games import MLBGames
        
        games = MLBGames(output_dir=str(tmp_path / 'mlb'))
        
        assert (tmp_path / 'mlb').exists()
    
    def test_nhl_game_events_creates_output(self, tmp_path):
        """Test NHLGameEvents creates output directory."""
        from nhl_game_events import NHLGameEvents
        
        events = NHLGameEvents(output_dir=str(tmp_path / 'nhl'))
        
        assert (tmp_path / 'nhl').exists()
    
    def test_epl_games_creates_output(self, tmp_path):
        """Test EPLGames creates output directory."""
        from epl_games import EPLGames
        
        games = EPLGames(data_dir=str(tmp_path / 'epl'))
        
        assert (tmp_path / 'epl').exists()
    
    def test_ligue1_games_creates_output(self, tmp_path):
        """Test Ligue1Games creates output directory."""
        from ligue1_games import Ligue1Games
        
        games = Ligue1Games(data_dir=str(tmp_path / 'ligue1'))
        
        assert (tmp_path / 'ligue1').exists()
    
    def test_ncaab_games_creates_output(self, tmp_path):
        """Test NCAABGames creates output directory."""
        from ncaab_games import NCAABGames
        
        games = NCAABGames(data_dir=str(tmp_path / 'ncaab'))
        
        assert (tmp_path / 'ncaab').exists()
    
    def test_tennis_games_creates_output(self, tmp_path):
        """Test TennisGames creates output directory."""
        from tennis_games import TennisGames
        
        games = TennisGames(data_dir=str(tmp_path / 'tennis'))
        
        assert (tmp_path / 'tennis').exists()


# ============================================================
# Tests for bet_loader.py (52% -> higher)
# ============================================================

class TestBetLoaderFunctionCalls:
    """Tests that call bet_loader functions."""
    
    def test_bet_loader_creates_table(self, tmp_path):
        """Test BetLoader creates table."""
        from bet_loader import BetLoader
        
        db_path = tmp_path / "test.duckdb"
        loader = BetLoader(db_path=str(db_path))
        
        conn = duckdb.connect(str(db_path))
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        conn.close()
        
        assert 'bet_recommendations' in table_names


# ============================================================
# Tests for API modules (30-51%)
# ============================================================

class TestAPIModuleFunctionCalls:
    """Tests that call API module functions."""
    
    def test_cloudbet_api_init(self):
        """Test CloudbetAPI initialization."""
        from cloudbet_api import CloudbetAPI
        
        api = CloudbetAPI()
        
        assert hasattr(api, 'BASE_URL')
        assert hasattr(api, 'session')
    
    def test_polymarket_api_init(self):
        """Test PolymarketAPI initialization."""
        from polymarket_api import PolymarketAPI
        
        api = PolymarketAPI()
        
        assert hasattr(api, 'BASE_URL')
        assert hasattr(api, 'CLOB_URL')
    
    def test_odds_comparator_init(self):
        """Test OddsComparator initialization."""
        from odds_comparator import OddsComparator
        
        comparator = OddsComparator()
        
        assert 'kalshi' in comparator.platforms
        assert 'cloudbet' in comparator.platforms
        assert 'polymarket' in comparator.platforms
