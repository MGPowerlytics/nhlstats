"""Tests for lift_gain_analysis.py - testing actual functions"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys


class TestSportConfig:
    """Test SPORT_CONFIG"""
    
    def test_all_sports_present(self):
        from lift_gain_analysis import SPORT_CONFIG
        for sport in ['nba', 'nhl', 'mlb', 'nfl', 'epl', 'ncaab']:
            assert sport in SPORT_CONFIG
    
    def test_sport_config_fields(self):
        from lift_gain_analysis import SPORT_CONFIG
        
        for sport, config in SPORT_CONFIG.items():
            assert 'elo_module' in config
            assert 'elo_class' in config
            assert 'k_factor' in config
            assert 'home_advantage' in config
            assert 'data_source' in config
            assert 'season_start_month' in config


class TestGetCurrentSeasonStart:
    """Test get_current_season_start function"""
    
    def test_nba_season(self):
        from lift_gain_analysis import get_current_season_start
        
        with patch('lift_gain_analysis.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 11, 15)
            result = get_current_season_start('nba')
            assert result == '2024-10-01'
    
    def test_mlb_season(self):
        from lift_gain_analysis import get_current_season_start
        
        with patch('lift_gain_analysis.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 7, 15)
            result = get_current_season_start('mlb')
            assert result == '2024-03-01'


class TestLoadGamesFromDuckDB:
    """Test load_games_from_duckdb function"""
    
    def test_no_database(self):
        from lift_gain_analysis import load_games_from_duckdb
        
        with patch('lift_gain_analysis.Path') as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = False
            mock_path.return_value = mock_path_instance
            
            result = load_games_from_duckdb('nhl')
            assert len(result) == 0


class TestLoadGamesFromJson:
    """Test load_games_from_json function"""
    
    def test_no_files(self):
        from lift_gain_analysis import load_games_from_json
        
        with patch('lift_gain_analysis.Path') as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.glob.return_value = []
            mock_path.return_value = mock_path_instance
            
            result = load_games_from_json('nba')
            assert len(result) == 0


class TestLoadGames:
    """Test load_games function"""
    
    def test_load_games_nba(self):
        from lift_gain_analysis import load_games
        
        with patch('lift_gain_analysis.load_games_from_json') as mock_load:
            mock_load.return_value = pd.DataFrame()
            result = load_games('nba')
            assert isinstance(result, pd.DataFrame)


class TestCalculateLiftGainByDecile:
    """Test calculate_lift_gain_by_decile function"""
    
    def test_function_exists(self):
        from lift_gain_analysis import calculate_lift_gain_by_decile
        assert callable(calculate_lift_gain_by_decile)


class TestAnalyzeSport:
    """Test analyze_sport function"""
    
    def test_function_exists(self):
        from lift_gain_analysis import analyze_sport
        assert callable(analyze_sport)


class TestMain:
    """Test main function"""
    
    def test_function_exists(self):
        from lift_gain_analysis import main
        assert callable(main)


class TestModuleImports:
    """Test module can be imported"""
    
    def test_import(self):
        import lift_gain_analysis
        assert hasattr(lift_gain_analysis, 'SPORT_CONFIG')
        assert hasattr(lift_gain_analysis, 'get_current_season_start')
        assert hasattr(lift_gain_analysis, 'load_games')
        assert hasattr(lift_gain_analysis, 'load_games_from_duckdb')
        assert hasattr(lift_gain_analysis, 'analyze_sport')
