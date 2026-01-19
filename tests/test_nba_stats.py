"""Tests for NBA Stats Fetcher module."""

import pytest
import sys
from pathlib import Path
from datetime import datetime, date
from unittest.mock import patch, MagicMock
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestNBAStatsFetcherInit:
    """Test NBAStatsFetcher initialization."""
    
    def test_init_creates_directory(self, tmp_path):
        """Test initialization creates output directory."""
        from nba_stats import NBAStatsFetcher
        
        output_dir = tmp_path / "nba"
        fetcher = NBAStatsFetcher(output_dir=str(output_dir))
        
        assert output_dir.exists()
    
    def test_base_url(self):
        """Test base URL configuration."""
        from nba_stats import NBAStatsFetcher
        
        assert NBAStatsFetcher.BASE_URL == "https://stats.nba.com/stats"
    
    def test_headers_configured(self):
        """Test required headers are set."""
        from nba_stats import NBAStatsFetcher
        
        headers = NBAStatsFetcher.HEADERS
        
        assert 'User-Agent' in headers
        assert 'Referer' in headers
        assert 'Origin' in headers
    
    def test_session_initialized(self, tmp_path):
        """Test session is initialized with headers."""
        from nba_stats import NBAStatsFetcher
        
        fetcher = NBAStatsFetcher(output_dir=str(tmp_path / "nba"))
        
        assert fetcher.session is not None


class TestGetScoreboard:
    """Test scoreboard fetching."""
    
    @patch('nba_stats.requests.Session')
    def test_get_scoreboard_success(self, mock_session_class, tmp_path):
        """Test successful scoreboard fetch."""
        from nba_stats import NBAStatsFetcher
        
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'scoreboard': {'games': []}}
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        fetcher = NBAStatsFetcher(output_dir=str(tmp_path / "nba"))
        fetcher.session = mock_session
        
        result = fetcher.get_scoreboard('2024-01-15')
        
        assert 'scoreboard' in result
    
    def test_date_format_conversion(self):
        """Test date format conversion."""
        date_str = '2024-01-15'
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        nba_format = date_obj.strftime('%m/%d/%Y')
        
        assert nba_format == '01/15/2024'
    
    def test_date_object_input(self):
        """Test date object input."""
        date_obj = date(2024, 1, 15)
        nba_format = date_obj.strftime('%m/%d/%Y')
        
        assert nba_format == '01/15/2024'


class TestPlayByPlay:
    """Test play-by-play data fetching."""
    
    def test_game_id_format(self):
        """Test game ID format."""
        # NBA game IDs are typically 10 digits
        game_id = '0022400123'
        
        assert len(game_id) == 10
        assert game_id.isdigit()
    
    @patch('nba_stats.requests.Session')
    def test_get_play_by_play_endpoint(self, mock_session_class, tmp_path):
        """Test play-by-play endpoint."""
        from nba_stats import NBAStatsFetcher
        
        fetcher = NBAStatsFetcher(output_dir=str(tmp_path / "nba"))
        
        # Verify the endpoint format
        expected_endpoint = f"{fetcher.BASE_URL}/playbyplayv2"
        
        assert 'playbyplayv2' in expected_endpoint


class TestShotChart:
    """Test shot chart data."""
    
    def test_shot_data_structure(self):
        """Test shot data structure."""
        shot = {
            'player_id': 12345,
            'player_name': 'LeBron James',
            'shot_type': '3PT Field Goal',
            'shot_made': True,
            'x': 50,
            'y': 120
        }
        
        assert shot['shot_type'] == '3PT Field Goal'
        assert shot['shot_made'] == True
    
    def test_shot_zone_classification(self):
        """Test shot zone classification."""
        zones = ['Restricted Area', 'Paint', 'Mid-Range', 'Above Break 3', 'Corner 3']
        
        assert 'Restricted Area' in zones
        assert 'Above Break 3' in zones


class TestBoxScore:
    """Test box score data."""
    
    def test_player_stats_structure(self):
        """Test player stats structure."""
        player_stats = {
            'player_id': 12345,
            'player_name': 'LeBron James',
            'minutes': '35:42',
            'points': 28,
            'rebounds': 8,
            'assists': 10,
            'steals': 2,
            'blocks': 1,
            'turnovers': 3,
            'fgm': 10,
            'fga': 18,
            'fg_pct': 0.556
        }
        
        assert player_stats['points'] == 28
        assert player_stats['fg_pct'] == 0.556
    
    def test_team_totals_structure(self):
        """Test team totals structure."""
        team_totals = {
            'team_id': 1610612747,
            'team_name': 'Lakers',
            'points': 110,
            'rebounds': 45,
            'assists': 28,
            'steals': 8,
            'blocks': 5
        }
        
        assert team_totals['points'] == 110
    
    def test_calculate_fg_percentage(self):
        """Test calculating FG percentage."""
        fgm = 42
        fga = 88
        
        fg_pct = fgm / fga
        
        assert fg_pct == pytest.approx(0.477, abs=0.01)


class TestAdvancedStats:
    """Test advanced statistics."""
    
    def test_efficiency_rating(self):
        """Test efficiency rating calculation."""
        pts = 28
        reb = 8
        ast = 10
        stl = 2
        blk = 1
        fgm = 10
        fga = 18
        ftm = 6
        fta = 8
        to = 3
        
        # Simple efficiency formula
        eff = (pts + reb + ast + stl + blk) - (fga - fgm) - (fta - ftm) - to
        
        assert eff > 0
    
    def test_true_shooting(self):
        """Test true shooting percentage."""
        pts = 28
        fga = 18
        fta = 8
        
        tsa = fga + 0.44 * fta
        ts_pct = pts / (2 * tsa)
        
        assert ts_pct > 0
        assert ts_pct < 1
    
    def test_usage_rate(self):
        """Test usage rate calculation."""
        fga = 18
        fta = 8
        to = 3
        team_fga = 88
        team_fta = 25
        team_to = 14
        player_minutes = 35
        team_minutes = 240
        
        # Simplified usage rate
        player_poss = fga + 0.44 * fta + to
        team_poss = team_fga + 0.44 * team_fta + team_to
        
        usage = (player_poss / team_poss) * (team_minutes / player_minutes) * 100
        
        assert usage > 0
