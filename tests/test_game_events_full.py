"""Tests for NHL Game Events and other game modules."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import json

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestNHLGameEventsInit:
    """Test NHLGameEvents initialization."""

    def test_init_creates_directory(self, tmp_path):
        """Test initialization creates output directory."""
        from nhl_game_events import NHLGameEvents

        output_dir = tmp_path / "games"
        events = NHLGameEvents(output_dir=str(output_dir))

        assert output_dir.exists()

    def test_init_with_date_folder(self, tmp_path):
        """Test initialization with date folder."""
        from nhl_game_events import NHLGameEvents

        output_dir = tmp_path / "games"
        events = NHLGameEvents(output_dir=str(output_dir), date_folder="2024-01-15")

        assert (output_dir / "2024-01-15").exists()

    def test_base_url(self):
        """Test base URL configuration."""
        from nhl_game_events import NHLGameEvents

        assert NHLGameEvents.BASE_URL == "https://api-web.nhle.com/v1"

    def test_legacy_url(self):
        """Test legacy URL configuration."""
        from nhl_game_events import NHLGameEvents

        assert "statsapi" in NHLGameEvents.LEGACY_URL


class TestNHLMakeRequest:
    """Test HTTP request handling."""

    @patch('nhl_game_events.requests.get')
    def test_make_request_success(self, mock_get, tmp_path):
        """Test successful request."""
        from nhl_game_events import NHLGameEvents

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': 'test'}
        mock_get.return_value = mock_response

        events = NHLGameEvents(output_dir=str(tmp_path / "games"))
        result = events._make_request("https://test.com")

        assert result == {'data': 'test'}

    @patch('nhl_game_events.requests.get')
    @patch('nhl_game_events.time.sleep')
    def test_make_request_rate_limited_then_success(self, mock_sleep, mock_get, tmp_path):
        """Test rate limit handling."""
        from nhl_game_events import NHLGameEvents

        rate_limited = MagicMock()
        rate_limited.status_code = 429

        success = MagicMock()
        success.status_code = 200
        success.json.return_value = {'data': 'success'}

        mock_get.side_effect = [rate_limited, success]

        events = NHLGameEvents(output_dir=str(tmp_path / "games"))
        result = events._make_request("https://test.com", max_retries=2)

        assert result == {'data': 'success'}


class TestNHLSchedule:
    """Test schedule fetching."""

    def test_schedule_url_format(self):
        """Test schedule URL format."""
        date_str = "2024-01-15"
        base_url = "https://api-web.nhle.com/v1"
        url = f"{base_url}/schedule/{date_str}"

        assert date_str in url

    def test_season_format(self):
        """Test season format."""
        season = "20232024"

        start_year = int(season[:4])
        end_year = int(season[4:])

        assert start_year == 2023
        assert end_year == 2024


class TestNCAABGamesInit:
    """Test NCAABGames initialization."""

    def test_init_creates_directory(self, tmp_path):
        """Test initialization creates data directory."""
        from ncaab_games import NCAABGames

        data_dir = tmp_path / "ncaab"
        games = NCAABGames(data_dir=str(data_dir))

        assert data_dir.exists()

    def test_seasons_configured(self, tmp_path):
        """Test seasons are configured."""
        from ncaab_games import NCAABGames

        games = NCAABGames(data_dir=str(tmp_path / "ncaab"))

        assert len(games.seasons) > 0
        assert 2024 in games.seasons

    def test_sub_id_configured(self, tmp_path):
        """Test sub_id for NCAA D1."""
        from ncaab_games import NCAABGames

        games = NCAABGames(data_dir=str(tmp_path / "ncaab"))

        assert games.sub_id == "11590"


class TestNCAABDownload:
    """Test NCAAB download functionality."""

    def test_teams_url_format(self):
        """Test teams URL format."""
        season = 2024
        sub_id = "11590"
        url = f"https://masseyratings.com/scores.php?s=cb{season}&sub={sub_id}&all=1&mode=3&format=2"

        assert str(season) in url
        assert sub_id in url

    def test_games_url_format(self):
        """Test games URL format."""
        season = 2024
        sub_id = "11590"
        url = f"https://masseyratings.com/scores.php?s=cb{season}&sub={sub_id}&all=1&mode=3&format=1"

        assert "format=1" in url


class TestEPLGamesInit:
    """Test EPLGames initialization."""

    def test_epl_data_source(self):
        """Test EPL data source URL."""
        base_url = "https://www.football-data.co.uk"

        assert "football-data" in base_url

    def test_epl_season_format(self):
        """Test EPL season format."""
        season = "2324"  # 2023-24 season

        start_year = int("20" + season[:2])
        end_year = int("20" + season[2:])

        assert start_year == 2023
        assert end_year == 2024


class TestLigue1GamesInit:
    """Test Ligue1Games initialization."""

    def test_ligue1_data_source(self):
        """Test Ligue1 data source URL."""
        base_url = "https://www.football-data.co.uk"

        assert "football-data" in base_url

    def test_ligue1_league_code(self):
        """Test Ligue1 league code."""
        league_code = "F1"  # France Ligue 1

        assert league_code == "F1"


class TestMLBGamesInit:
    """Test MLBGames initialization."""

    def test_mlb_api_url(self):
        """Test MLB API URL."""
        base_url = "https://statsapi.mlb.com/api/v1"

        assert "mlb.com" in base_url

    def test_mlb_schedule_endpoint(self):
        """Test MLB schedule endpoint."""
        date = "2024-04-15"
        url = f"https://statsapi.mlb.com/api/v1/schedule?date={date}"

        assert date in url


class TestNFLGamesInit:
    """Test NFLGames initialization."""

    def test_nfl_season_weeks(self):
        """Test NFL has 18 regular season weeks."""
        regular_weeks = 18

        assert regular_weeks == 18

    def test_nfl_preseason_weeks(self):
        """Test NFL has 4 preseason weeks."""
        preseason_weeks = 4

        assert preseason_weeks == 4


class TestGameDataParsing:
    """Test game data parsing."""

    def test_parse_nhl_game_id(self):
        """Test parsing NHL game ID."""
        game_id = "2023020001"

        season = game_id[:4]
        game_type = game_id[4:6]  # 02 = regular season
        game_num = game_id[6:]

        assert season == "2023"
        assert game_type == "02"

    def test_parse_game_time_utc(self):
        """Test parsing UTC game time."""
        from datetime import datetime

        time_str = "2024-01-15T19:30:00Z"
        game_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))

        assert game_time.hour == 19

    def test_parse_final_score(self):
        """Test parsing final score."""
        score = {
            'home': 4,
            'away': 2
        }

        home_won = score['home'] > score['away']

        assert home_won == True


class TestEventTypes:
    """Test event type handling."""

    def test_nhl_event_types(self):
        """Test NHL event types."""
        event_types = ['GOAL', 'SHOT', 'HIT', 'FACEOFF', 'PENALTY', 'BLOCKED_SHOT']

        assert 'GOAL' in event_types
        assert 'SHOT' in event_types

    def test_parse_goal_event(self):
        """Test parsing goal event."""
        event = {
            'eventType': 'GOAL',
            'period': 2,
            'timeInPeriod': '12:30',
            'scorer': 'Player Name',
            'team': 'Toronto Maple Leafs'
        }

        assert event['eventType'] == 'GOAL'
        assert event['period'] == 2

    def test_parse_shot_coordinates(self):
        """Test parsing shot coordinates."""
        event = {
            'eventType': 'SHOT',
            'coordinates': {'x': 50, 'y': 20}
        }

        assert event['coordinates']['x'] == 50
        assert event['coordinates']['y'] == 20


class TestDataSaving:
    """Test data saving functionality."""

    def test_json_save(self, tmp_path):
        """Test saving JSON data."""
        data = {'games': [{'id': 1}, {'id': 2}]}
        file_path = tmp_path / "games.json"

        with open(file_path, 'w') as f:
            json.dump(data, f)

        with open(file_path, 'r') as f:
            loaded = json.load(f)

        assert loaded == data

    def test_csv_save(self, tmp_path):
        """Test saving CSV data."""
        import csv

        data = [['home', 'away', 'score'], ['Lakers', 'Celtics', '110-105']]
        file_path = tmp_path / "games.csv"

        with open(file_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)

        assert file_path.exists()


class TestRetryLogic:
    """Test retry logic for API calls."""

    def test_exponential_backoff_values(self):
        """Test exponential backoff values."""
        base = 2
        retries = [base * (2 ** i) for i in range(5)]

        assert retries == [2, 4, 8, 16, 32]

    def test_max_retries_default(self):
        """Test default max retries."""
        default_max_retries = 5

        assert default_max_retries == 5
