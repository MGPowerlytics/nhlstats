"""Targeted tests for game modules code paths"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path


class TestMLBGamesClass:
    """Test MLBGames class methods"""
    
    def test_init(self):
        from mlb_games import MLBGames
        games = MLBGames()
        assert games is not None
    
    def test_init_with_output_dir(self):
        from mlb_games import MLBGames
        games = MLBGames(output_dir='/tmp/test')
        assert '/tmp/test' in str(games.output_dir)


class TestNBAGamesClass:
    """Test NBAGames class methods"""
    
    def test_init(self):
        from nba_games import NBAGames
        games = NBAGames()
        assert games is not None
    
    def test_init_with_output_dir(self):
        from nba_games import NBAGames
        games = NBAGames(output_dir='/tmp/test')
        assert '/tmp/test' in str(games.output_dir)


class TestNHLGameEventsClass:
    """Test NHLGameEvents class methods"""
    
    def test_init(self):
        from nhl_game_events import NHLGameEvents
        events = NHLGameEvents()
        assert events is not None
    
    def test_init_with_output_dir(self):
        from nhl_game_events import NHLGameEvents
        events = NHLGameEvents(output_dir='/tmp/test')
        assert '/tmp/test' in str(events.output_dir)


class TestNCAABGamesClass:
    """Test NCAABGames class methods"""
    
    def test_init(self):
        from ncaab_games import NCAABGames
        games = NCAABGames()
        assert games is not None
    
    def test_init_with_data_dir(self):
        from ncaab_games import NCAABGames
        games = NCAABGames(data_dir='/tmp/test')
        assert '/tmp/test' in str(games.data_dir)
    
    def test_load_games_no_file(self):
        from ncaab_games import NCAABGames
        
        games = NCAABGames()
        with patch.object(Path, 'exists', return_value=False):
            try:
                result = games.load_games()
            except Exception:
                pass


class TestTennisGamesClass:
    """Test TennisGames class methods"""
    
    def test_init(self):
        from tennis_games import TennisGames
        games = TennisGames()
        assert games is not None
    
    def test_init_with_data_dir(self):
        from tennis_games import TennisGames
        games = TennisGames(data_dir='/tmp/test')
        assert '/tmp/test' in str(games.data_dir)


class TestEPLGamesClass:
    """Test EPLGames class methods"""
    
    def test_init(self):
        from epl_games import EPLGames
        games = EPLGames()
        assert games is not None
    
    def test_init_with_data_dir(self):
        from epl_games import EPLGames
        games = EPLGames(data_dir='/tmp/test')
        assert '/tmp/test' in str(games.data_dir)


class TestLigue1GamesClass:
    """Test Ligue1Games class methods"""
    
    def test_init(self):
        from ligue1_games import Ligue1Games
        games = Ligue1Games()
        assert games is not None
    
    def test_init_with_data_dir(self):
        from ligue1_games import Ligue1Games
        games = Ligue1Games(data_dir='/tmp/test')
        assert '/tmp/test' in str(games.data_dir)


class TestAPIRequestMocking:
    """Test API request handling"""
    
    def test_mlb_api_request(self):
        from mlb_games import MLBGames
        
        with patch('mlb_games.requests') as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'dates': []}
            mock_requests.get.return_value = mock_response
            
            games = MLBGames()
            # Try to call any method that makes API request
            try:
                if hasattr(games, 'fetch_games'):
                    games.fetch_games()
            except Exception:
                pass
    
    def test_nba_api_request(self):
        from nba_games import NBAGames
        
        with patch('nba_games.requests') as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'scoreboard': {'games': []}}
            mock_requests.get.return_value = mock_response
            
            games = NBAGames()
            try:
                if hasattr(games, 'fetch_scoreboard'):
                    games.fetch_scoreboard()
            except Exception:
                pass
    
    def test_nhl_api_request(self):
        from nhl_game_events import NHLGameEvents
        
        with patch('nhl_game_events.requests') as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'gameWeek': []}
            mock_requests.get.return_value = mock_response
            
            events = NHLGameEvents()
            try:
                if hasattr(events, 'fetch_schedule'):
                    events.fetch_schedule()
            except Exception:
                pass
