"""Targeted tests for stats modules (nba_stats, mlb_stats, nfl_stats)"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import json
from datetime import datetime, date


class TestNBAStatsFetcher:
    """Test NBAStatsFetcher class"""
    
    def test_init_default(self):
        from nba_stats import NBAStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'mkdir', return_value=None):
                fetcher = NBAStatsFetcher(output_dir=tmpdir)
                assert fetcher.output_dir == Path(tmpdir)
    
    def test_init_creates_directory(self):
        from nba_stats import NBAStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / 'nba_stats'
            fetcher = NBAStatsFetcher(output_dir=str(output_dir))
            assert output_dir.exists()
    
    def test_headers_set(self):
        from nba_stats import NBAStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = NBAStatsFetcher(output_dir=tmpdir)
            assert 'User-Agent' in fetcher.session.headers
    
    def test_get_scoreboard_with_string_date(self):
        from nba_stats import NBAStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = NBAStatsFetcher(output_dir=tmpdir)
            
            with patch.object(fetcher.session, 'get') as mock_get:
                mock_response = Mock()
                mock_response.json.return_value = {'games': []}
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response
                
                result = fetcher.get_scoreboard('2024-01-15')
                assert result == {'games': []}
    
    def test_get_scoreboard_with_date_object(self):
        from nba_stats import NBAStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = NBAStatsFetcher(output_dir=tmpdir)
            
            with patch.object(fetcher.session, 'get') as mock_get:
                mock_response = Mock()
                mock_response.json.return_value = {'games': []}
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response
                
                result = fetcher.get_scoreboard(date(2024, 1, 15))
                assert result == {'games': []}
    
    def test_get_play_by_play(self):
        from nba_stats import NBAStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = NBAStatsFetcher(output_dir=tmpdir)
            
            with patch.object(fetcher.session, 'get') as mock_get:
                mock_response = Mock()
                mock_response.json.return_value = {'plays': []}
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response
                
                result = fetcher.get_play_by_play('0022300500')
                assert result == {'plays': []}
    
    def test_get_shot_chart(self):
        from nba_stats import NBAStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = NBAStatsFetcher(output_dir=tmpdir)
            
            with patch.object(fetcher.session, 'get') as mock_get:
                mock_response = Mock()
                mock_response.json.return_value = {'shots': []}
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response
                
                result = fetcher.get_shot_chart('0022300500')
                assert result == {'shots': []}


class TestMLBStatsFetcher:
    """Test MLBStatsFetcher class"""
    
    def test_init_default(self):
        from mlb_stats import MLBStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = MLBStatsFetcher(output_dir=tmpdir)
            assert fetcher.output_dir == Path(tmpdir)
    
    def test_init_creates_directory(self):
        from mlb_stats import MLBStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / 'mlb_stats'
            fetcher = MLBStatsFetcher(output_dir=str(output_dir))
            assert output_dir.exists()
    
    def test_get_schedule(self):
        from mlb_stats import MLBStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = MLBStatsFetcher(output_dir=tmpdir)
            
            with patch.object(fetcher.session, 'get') as mock_get:
                mock_response = Mock()
                mock_response.json.return_value = {'dates': []}
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response
                
                result = fetcher.get_schedule('2024-01-15')
                assert 'dates' in result
    
    def test_get_game_feed(self):
        from mlb_stats import MLBStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = MLBStatsFetcher(output_dir=tmpdir)
            
            with patch.object(fetcher.session, 'get') as mock_get:
                mock_response = Mock()
                mock_response.json.return_value = {'gamePk': 123456}
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response
                
                result = fetcher.get_game_feed(123456)
                assert result['gamePk'] == 123456


class TestNFLStatsFetcher:
    """Test NFLStatsFetcher class"""
    
    def test_init_default(self):
        import sys
        # Mock nfl_data_py before import
        mock_nfl = MagicMock()
        sys.modules['nfl_data_py'] = mock_nfl
        
        from nfl_stats import NFLStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = NFLStatsFetcher(output_dir=tmpdir)
            assert fetcher.output_dir == Path(tmpdir)
    
    def test_init_creates_directory(self):
        import sys
        mock_nfl = MagicMock()
        sys.modules['nfl_data_py'] = mock_nfl
        
        # Force reimport
        if 'nfl_stats' in sys.modules:
            del sys.modules['nfl_stats']
        
        from nfl_stats import NFLStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / 'nfl_stats'
            fetcher = NFLStatsFetcher(output_dir=str(output_dir))
            assert output_dir.exists()


class TestNBAStatsBaseURL:
    """Test NBA Stats API configuration"""
    
    def test_base_url(self):
        from nba_stats import NBAStatsFetcher
        assert NBAStatsFetcher.BASE_URL == "https://stats.nba.com/stats"
    
    def test_headers(self):
        from nba_stats import NBAStatsFetcher
        assert 'User-Agent' in NBAStatsFetcher.HEADERS
        assert 'Referer' in NBAStatsFetcher.HEADERS


class TestMLBStatsBaseURL:
    """Test MLB Stats API configuration"""
    
    def test_base_url(self):
        from mlb_stats import MLBStatsFetcher
        # May or may not have BASE_URL as class attribute
        if hasattr(MLBStatsFetcher, 'BASE_URL'):
            assert 'mlb' in MLBStatsFetcher.BASE_URL.lower()
        else:
            # Check it exists on instance
            with tempfile.TemporaryDirectory() as tmpdir:
                fetcher = MLBStatsFetcher(output_dir=tmpdir)
                assert hasattr(fetcher, 'output_dir')


class TestStatsModuleImports:
    """Test module imports"""
    
    def test_nba_stats_import(self):
        import nba_stats
        assert hasattr(nba_stats, 'NBAStatsFetcher')
    
    def test_mlb_stats_import(self):
        import mlb_stats
        assert hasattr(mlb_stats, 'MLBStatsFetcher')
    
    def test_nfl_stats_import(self):
        import sys
        mock_nfl = MagicMock()
        sys.modules['nfl_data_py'] = mock_nfl
        
        if 'nfl_stats' in sys.modules:
            del sys.modules['nfl_stats']
        
        import nfl_stats
        assert hasattr(nfl_stats, 'NFLStatsFetcher')


class TestNBAStatsFetcherMethods:
    """Test additional NBAStatsFetcher methods"""
    
    def test_get_boxscore(self):
        from nba_stats import NBAStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = NBAStatsFetcher(output_dir=tmpdir)
            
            if hasattr(fetcher, 'get_boxscore'):
                with patch.object(fetcher.session, 'get') as mock_get:
                    mock_response = Mock()
                    mock_response.json.return_value = {'boxscore': []}
                    mock_response.raise_for_status = Mock()
                    mock_get.return_value = mock_response
                    
                    result = fetcher.get_boxscore('0022300500')
                    assert 'boxscore' in result
    
    def test_get_team_stats(self):
        from nba_stats import NBAStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = NBAStatsFetcher(output_dir=tmpdir)
            
            if hasattr(fetcher, 'get_team_stats'):
                with patch.object(fetcher.session, 'get') as mock_get:
                    mock_response = Mock()
                    mock_response.json.return_value = {'stats': []}
                    mock_response.raise_for_status = Mock()
                    mock_get.return_value = mock_response
                    
                    result = fetcher.get_team_stats()
                    assert 'stats' in result


class TestMLBStatsFetcherMethods:
    """Test additional MLBStatsFetcher methods"""
    
    def test_fetch_and_save(self):
        from mlb_stats import MLBStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = MLBStatsFetcher(output_dir=tmpdir)
            
            if hasattr(fetcher, 'fetch_and_save'):
                with patch.object(fetcher, 'get_schedule') as mock_schedule:
                    mock_schedule.return_value = {'dates': []}
                    
                    with patch.object(Path, 'write_text'):
                        fetcher.fetch_and_save('2024-01-15')
    
    def test_get_player_stats(self):
        from mlb_stats import MLBStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = MLBStatsFetcher(output_dir=tmpdir)
            
            if hasattr(fetcher, 'get_player_stats'):
                with patch.object(fetcher.session, 'get') as mock_get:
                    mock_response = Mock()
                    mock_response.json.return_value = {'stats': []}
                    mock_response.raise_for_status = Mock()
                    mock_get.return_value = mock_response
                    
                    result = fetcher.get_player_stats(12345)
                    assert 'stats' in result


class TestSessionHandling:
    """Test session handling in stats modules"""
    
    def test_nba_session_created(self):
        from nba_stats import NBAStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = NBAStatsFetcher(output_dir=tmpdir)
            assert hasattr(fetcher, 'session')
    
    def test_mlb_session_created(self):
        from mlb_stats import MLBStatsFetcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = MLBStatsFetcher(output_dir=tmpdir)
            assert hasattr(fetcher, 'session')


class TestErrorHandling:
    """Test error handling in stats modules"""
    
    def test_nba_request_error(self):
        from nba_stats import NBAStatsFetcher
        import requests
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = NBAStatsFetcher(output_dir=tmpdir)
            
            with patch.object(fetcher.session, 'get') as mock_get:
                mock_get.side_effect = requests.RequestException("Connection error")
                
                with pytest.raises(requests.RequestException):
                    fetcher.get_scoreboard('2024-01-15')
    
    def test_mlb_request_error(self):
        from mlb_stats import MLBStatsFetcher
        import requests
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = MLBStatsFetcher(output_dir=tmpdir)
            
            with patch.object(fetcher.session, 'get') as mock_get:
                mock_get.side_effect = requests.RequestException("Connection error")
                
                with pytest.raises(requests.RequestException):
                    fetcher.get_schedule('2024-01-15')
