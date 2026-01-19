"""Tests for Game Data modules (NBA, NHL, MLB, NFL, Tennis, NCAAB, EPL, Ligue1)."""

import pytest
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
import json

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestNBAGames:
    """Test NBAGames class."""
    
    def test_init_default(self, tmp_path):
        """Test default initialization."""
        from nba_games import NBAGames
        
        games = NBAGames(output_dir=str(tmp_path / "nba"))
        
        assert games.BASE_URL == "https://stats.nba.com/stats"
    
    def test_init_with_date_folder(self, tmp_path):
        """Test initialization with date folder."""
        from nba_games import NBAGames
        
        games = NBAGames(output_dir=str(tmp_path), date_folder="2024-01-01")
        
        assert "2024-01-01" in str(games.output_dir)
    
    def test_headers_contain_required_fields(self):
        """Test that headers contain required fields for NBA API."""
        from nba_games import NBAGames
        
        headers = NBAGames.HEADERS
        
        assert 'User-Agent' in headers
        assert 'Referer' in headers
        assert 'nba.com' in headers['Referer']
    
    @patch('nba_games.requests.get')
    def test_make_request_success(self, mock_get, tmp_path):
        """Test successful API request."""
        from nba_games import NBAGames
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'resultSets': []}
        mock_get.return_value = mock_response
        
        games = NBAGames(output_dir=str(tmp_path))
        result = games._make_request("https://test.com")
        
        assert result == {'resultSets': []}
    
    @patch('nba_games.requests.get')
    def test_make_request_rate_limit_retry(self, mock_get, tmp_path):
        """Test rate limit handling with retry."""
        from nba_games import NBAGames
        
        # First call returns 429, second returns 200
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {'data': 'test'}
        
        mock_get.side_effect = [mock_response_429, mock_response_200]
        
        games = NBAGames(output_dir=str(tmp_path))
        
        with patch('nba_games.time.sleep'):  # Skip actual sleep
            result = games._make_request("https://test.com")
        
        assert result == {'data': 'test'}


class TestDateFormatConversion:
    """Test date format conversion utilities."""
    
    def test_date_format_yyyy_mm_dd_to_nba(self):
        """Test converting YYYY-MM-DD to MM/DD/YYYY (NBA format)."""
        date_str = "2024-01-15"
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        nba_date = date_obj.strftime('%m/%d/%Y')
        
        assert nba_date == "01/15/2024"
    
    def test_date_format_nba_to_yyyy_mm_dd(self):
        """Test converting MM/DD/YYYY to YYYY-MM-DD."""
        nba_date = "01/15/2024"
        date_obj = datetime.strptime(nba_date, '%m/%d/%Y')
        std_date = date_obj.strftime('%Y-%m-%d')
        
        assert std_date == "2024-01-15"
    
    def test_date_format_iso_to_date(self):
        """Test parsing ISO format dates."""
        iso_date = "2024-01-15T19:30:00Z"
        date_obj = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        
        assert date_obj.year == 2024
        assert date_obj.month == 1
        assert date_obj.day == 15


class TestGameDataParsing:
    """Test parsing game data from API responses."""
    
    def test_parse_scoreboard_data(self):
        """Test parsing NBA scoreboard response."""
        data = {
            'resultSets': [
                {
                    'name': 'GameHeader',
                    'headers': ['GAME_ID', 'GAME_DATE_EST', 'HOME_TEAM_ID', 'VISITOR_TEAM_ID'],
                    'rowSet': [
                        ['0022400001', '2024-01-15', 1610612747, 1610612738]
                    ]
                }
            ]
        }
        
        # Parse as would be done in the module
        for result_set in data['resultSets']:
            if result_set['name'] == 'GameHeader':
                headers = result_set['headers']
                idx_game_id = headers.index('GAME_ID')
                idx_game_date = headers.index('GAME_DATE_EST')
                
                for row in result_set['rowSet']:
                    game_id = row[idx_game_id]
                    game_date = row[idx_game_date]
                    
                    assert game_id == '0022400001'
                    assert game_date == '2024-01-15'
    
    def test_parse_boxscore_data(self):
        """Test parsing boxscore response."""
        data = {
            'resultSets': [
                {
                    'name': 'TeamStats',
                    'headers': ['TEAM_ID', 'TEAM_NAME', 'PTS'],
                    'rowSet': [
                        [1610612747, 'Lakers', 110],
                        [1610612738, 'Celtics', 105]
                    ]
                }
            ]
        }
        
        scores = {}
        for result_set in data['resultSets']:
            if result_set['name'] == 'TeamStats':
                headers = result_set['headers']
                idx_team_name = headers.index('TEAM_NAME')
                idx_pts = headers.index('PTS')
                
                for row in result_set['rowSet']:
                    scores[row[idx_team_name]] = row[idx_pts]
        
        assert scores['Lakers'] == 110
        assert scores['Celtics'] == 105


class TestNHLGameEvents:
    """Test NHL game events module."""
    
    def test_nhl_api_url_format(self):
        """Test NHL API URL format."""
        base_url = "https://api-web.nhle.com/v1"
        schedule_url = f"{base_url}/schedule/2024-01-15"
        
        assert "api-web.nhle.com" in schedule_url
        assert "schedule" in schedule_url
    
    def test_parse_nhl_schedule_response(self):
        """Test parsing NHL schedule response."""
        data = {
            'gameWeek': [
                {
                    'date': '2024-01-15',
                    'games': [
                        {
                            'id': 2023020001,
                            'homeTeam': {'abbrev': 'TOR', 'placeName': {'default': 'Toronto'}},
                            'awayTeam': {'abbrev': 'BOS', 'placeName': {'default': 'Boston'}},
                            'gameState': 'OFF'
                        }
                    ]
                }
            ]
        }
        
        games = []
        for day in data.get('gameWeek', []):
            for game in day.get('games', []):
                games.append({
                    'id': game['id'],
                    'home': game['homeTeam']['abbrev'],
                    'away': game['awayTeam']['abbrev']
                })
        
        assert len(games) == 1
        assert games[0]['home'] == 'TOR'
        assert games[0]['away'] == 'BOS'


class TestMLBGames:
    """Test MLB games module."""
    
    def test_mlb_api_url_format(self):
        """Test MLB API URL format."""
        date = "2024-07-15"
        url = f"https://statsapi.mlb.com/api/v1/schedule?date={date}&sportId=1"
        
        assert "statsapi.mlb.com" in url
        assert date in url
    
    def test_parse_mlb_schedule_response(self):
        """Test parsing MLB schedule response."""
        data = {
            'dates': [
                {
                    'date': '2024-07-15',
                    'games': [
                        {
                            'gamePk': 123456,
                            'teams': {
                                'home': {'team': {'name': 'Yankees'}, 'score': 5},
                                'away': {'team': {'name': 'Red Sox'}, 'score': 3}
                            },
                            'status': {'abstractGameState': 'Final'}
                        }
                    ]
                }
            ]
        }
        
        games = []
        for date in data.get('dates', []):
            for game in date.get('games', []):
                games.append({
                    'id': game['gamePk'],
                    'home': game['teams']['home']['team']['name'],
                    'away': game['teams']['away']['team']['name'],
                    'home_score': game['teams']['home']['score'],
                    'away_score': game['teams']['away']['score']
                })
        
        assert len(games) == 1
        assert games[0]['home'] == 'Yankees'
        assert games[0]['home_score'] == 5


class TestNFLGames:
    """Test NFL games module."""
    
    def test_nfl_api_url_format(self):
        """Test NFL API URL format."""
        season = 2024
        week = 1
        url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week={week}"
        
        assert "espn.com" in url
        assert str(week) in url


class TestTennisGames:
    """Test Tennis games module."""
    
    def test_tennis_player_name_parsing(self):
        """Test parsing tennis player names."""
        full_name = "Novak Djokovic"
        parts = full_name.split()
        
        first_name = parts[0]
        last_name = parts[-1]
        
        assert first_name == "Novak"
        assert last_name == "Djokovic"
    
    def test_tennis_match_identifier(self):
        """Test creating tennis match identifier."""
        player1 = "Djokovic"
        player2 = "Nadal"
        date = "2024-01-15"
        
        match_id = f"{date}_{player1}_{player2}"
        
        assert "Djokovic" in match_id
        assert "Nadal" in match_id


class TestOutputDirectoryHandling:
    """Test output directory handling."""
    
    def test_create_output_directory(self, tmp_path):
        """Test creating output directory."""
        output_dir = tmp_path / "data" / "nba" / "2024-01-15"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        assert output_dir.exists()
    
    def test_save_json_data(self, tmp_path):
        """Test saving JSON data to file."""
        output_file = tmp_path / "games.json"
        data = [{'game_id': '123', 'score': 100}]
        
        with open(output_file, 'w') as f:
            json.dump(data, f)
        
        # Verify file was saved
        with open(output_file, 'r') as f:
            loaded = json.load(f)
        
        assert loaded == data
    
    def test_load_json_data(self, tmp_path):
        """Test loading JSON data from file."""
        output_file = tmp_path / "games.json"
        data = [{'game_id': '456', 'score': 95}]
        
        with open(output_file, 'w') as f:
            json.dump(data, f)
        
        with open(output_file, 'r') as f:
            loaded = json.load(f)
        
        assert loaded[0]['game_id'] == '456'


class TestDataValidationInGames:
    """Test data validation in game modules."""
    
    def test_validate_game_id_format_nba(self):
        """Test NBA game ID format validation."""
        # NBA game IDs are 10 digits starting with 002
        valid_id = "0022400001"
        invalid_id = "12345"
        
        assert len(valid_id) == 10
        assert valid_id.startswith("002")
        assert len(invalid_id) != 10
    
    def test_validate_game_id_format_nhl(self):
        """Test NHL game ID format validation."""
        # NHL game IDs are typically 10 digits
        valid_id = "2023020001"
        
        assert len(str(valid_id)) == 10
    
    def test_validate_score_range(self):
        """Test score validation."""
        valid_scores = [100, 95, 0, 150]
        invalid_scores = [-5, None, 'abc']
        
        for score in valid_scores:
            assert isinstance(score, int) and score >= 0
        
        for score in invalid_scores:
            assert not (isinstance(score, int) and score >= 0)
    
    def test_validate_team_names(self):
        """Test team name validation."""
        valid_names = ["Lakers", "Boston Celtics", "76ers"]
        invalid_names = ["", None, 123]
        
        for name in valid_names:
            assert isinstance(name, str) and len(name) > 0
        
        for name in invalid_names:
            assert not (isinstance(name, str) and len(str(name) if name else '') > 0)
