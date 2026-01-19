"""Tests for stats modules - testing actual classes"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
import sys


class TestNBAStatsFetcher:
    """Test NBAStatsFetcher class"""
    
    def test_import(self):
        import nba_stats
        assert hasattr(nba_stats, 'NBAStatsFetcher')
    
    def test_init(self):
        from nba_stats import NBAStatsFetcher
        stats = NBAStatsFetcher()
        assert stats is not None


class TestMLBStatsFetcher:
    """Test MLBStatsFetcher class"""
    
    def test_import(self):
        import mlb_stats
        assert hasattr(mlb_stats, 'MLBStatsFetcher')
    
    def test_init(self):
        from mlb_stats import MLBStatsFetcher
        stats = MLBStatsFetcher()
        assert stats is not None


class TestNFLStatsMocked:
    """Test NFLStats with mocked nfl_data_py"""
    
    def test_class_exists_when_mocked(self):
        # Mock nfl_data_py before import
        mock_nfl = MagicMock()
        mock_nfl.import_schedules = MagicMock(return_value=pd.DataFrame())
        mock_nfl.import_pbp_data = MagicMock(return_value=pd.DataFrame())
        mock_nfl.import_weekly_data = MagicMock(return_value=pd.DataFrame())
        mock_nfl.import_seasonal_data = MagicMock(return_value=pd.DataFrame())
        mock_nfl.import_rosters = MagicMock(return_value=pd.DataFrame())
        mock_nfl.import_team_desc = MagicMock(return_value=pd.DataFrame())
        mock_nfl.import_injuries = MagicMock(return_value=pd.DataFrame())
        mock_nfl.import_depth_charts = MagicMock(return_value=pd.DataFrame())
        mock_nfl.import_ngs_data = MagicMock(return_value=pd.DataFrame())
        
        # Save original state
        had_nfl_data_py = 'nfl_data_py' in sys.modules
        had_nfl_stats = 'nfl_stats' in sys.modules
        orig_nfl_data_py = sys.modules.get('nfl_data_py')
        orig_nfl_stats = sys.modules.get('nfl_stats')
        
        try:
            sys.modules['nfl_data_py'] = mock_nfl
            if 'nfl_stats' in sys.modules:
                del sys.modules['nfl_stats']
            
            import nfl_stats
            assert hasattr(nfl_stats, 'NFLStatsFetcher')
        finally:
            # Restore original state
            if had_nfl_data_py:
                sys.modules['nfl_data_py'] = orig_nfl_data_py
            elif 'nfl_data_py' in sys.modules:
                del sys.modules['nfl_data_py']
            
            if had_nfl_stats:
                sys.modules['nfl_stats'] = orig_nfl_stats
            elif 'nfl_stats' in sys.modules:
                del sys.modules['nfl_stats']


class TestModuleImports:
    """Test all stats modules can be imported"""
    
    def test_import_nba_stats(self):
        import nba_stats
        assert 'NBAStatsFetcher' in dir(nba_stats)
    
    def test_import_mlb_stats(self):
        import mlb_stats
        assert 'MLBStatsFetcher' in dir(mlb_stats)
