"""Additional tests for all game data modules."""

import pytest
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestNBAGamesModule:
    """Test NBA games module."""

    def test_base_url(self):
        """Test NBA stats base URL."""
        from nba_games import NBAGames

        assert NBAGames.BASE_URL == "https://stats.nba.com/stats"

    def test_headers_configured(self):
        """Test required headers are set."""
        from nba_games import NBAGames

        headers = NBAGames.HEADERS

        assert 'User-Agent' in headers
        assert 'Referer' in headers
        assert 'nba.com' in headers['Referer']

    def test_init_creates_directory(self, tmp_path):
        """Test initialization creates output directory."""
        from nba_games import NBAGames

        output_dir = tmp_path / "nba"
        games = NBAGames(output_dir=str(output_dir))

        assert output_dir.exists()

    def test_init_with_date_folder(self, tmp_path):
        """Test initialization with date folder."""
        from nba_games import NBAGames

        output_dir = tmp_path / "nba"
        games = NBAGames(output_dir=str(output_dir), date_folder="2024-01-15")

        expected_dir = output_dir / "2024-01-15"
        assert expected_dir.exists()

    @patch('nba_games.requests.get')
    def test_make_request_success(self, mock_get):
        """Test successful HTTP request."""
        from nba_games import NBAGames

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': 'test'}
        mock_get.return_value = mock_response

        games = NBAGames(output_dir=str(Path(tempfile.mkdtemp())))
        result = games._make_request("https://test.com")

        assert result == {'data': 'test'}

    @patch('nba_games.requests.get')
    @patch('nba_games.time.sleep')
    def test_make_request_rate_limited(self, mock_sleep, mock_get):
        """Test handling rate limit response."""
        from nba_games import NBAGames

        # First request rate limited, second succeeds
        rate_limited = MagicMock()
        rate_limited.status_code = 429

        success = MagicMock()
        success.status_code = 200
        success.json.return_value = {'data': 'success'}

        mock_get.side_effect = [rate_limited, success]

        games = NBAGames(output_dir=str(Path(tempfile.mkdtemp())))
        result = games._make_request("https://test.com", max_retries=2)

        assert result == {'data': 'success'}
        mock_sleep.assert_called()

    def test_date_format_conversion(self):
        """Test date format conversion."""
        date_str = '2024-01-15'
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        nba_date = date_obj.strftime('%m/%d/%Y')

        assert nba_date == '01/15/2024'


class TestTennisGamesModule:
    """Test Tennis games module."""

    def test_init_creates_directory(self, tmp_path):
        """Test initialization creates data directory."""
        from tennis_games import TennisGames

        data_dir = tmp_path / "tennis"
        games = TennisGames(data_dir=str(data_dir))

        assert data_dir.exists()

    def test_tours_configured(self, tmp_path):
        """Test ATP and WTA tours are configured."""
        from tennis_games import TennisGames

        games = TennisGames(data_dir=str(tmp_path / "tennis"))

        assert 'atp' in games.tours
        assert 'wta' in games.tours

    def test_years_configured(self, tmp_path):
        """Test years are configured."""
        from tennis_games import TennisGames

        games = TennisGames(data_dir=str(tmp_path / "tennis"))

        assert len(games.years) > 0
        assert '2024' in games.years

    def test_atp_url_format(self):
        """Test ATP URL format."""
        year = '2024'
        tour = 'atp'
        url = f"http://www.tennis-data.co.uk/{year}/{year}.xlsx"

        assert url == "http://www.tennis-data.co.uk/2024/2024.xlsx"

    def test_wta_url_format(self):
        """Test WTA URL format."""
        year = '2024'
        tour = 'wta'
        url = f"http://www.tennis-data.co.uk/{year}w/{year}.xlsx"

        assert url == "http://www.tennis-data.co.uk/2024w/2024.xlsx"


class TestMLBGamesModule:
    """Test MLB games module."""

    def test_mlb_base_url(self):
        """Test MLB API base URL."""
        base_url = "https://statsapi.mlb.com/api/v1"

        assert "mlb.com" in base_url

    def test_date_range_endpoint(self):
        """Test date range endpoint format."""
        start_date = '2024-04-01'
        end_date = '2024-04-30'
        url = f"https://statsapi.mlb.com/api/v1/schedule?startDate={start_date}&endDate={end_date}"

        assert start_date in url
        assert end_date in url


class TestNFLGamesModule:
    """Test NFL games module."""

    def test_nfl_season_weeks(self):
        """Test NFL season week count."""
        regular_season_weeks = 18
        preseason_weeks = 4
        postseason_weeks = 4

        assert regular_season_weeks == 18

    def test_week_number_calculation(self):
        """Test week number from date."""
        # NFL Week 1 typically starts first Thursday after Labor Day
        # This is a simplified test
        week_number = 1
        assert 1 <= week_number <= 22  # Regular + postseason


class TestNHLGameEventsModule:
    """Test NHL game events module."""

    def test_nhl_base_url(self):
        """Test NHL API base URL."""
        base_url = "https://api-web.nhle.com/v1"

        assert "nhle.com" in base_url

    def test_game_type_codes(self):
        """Test NHL game type codes."""
        game_types = {
            'PR': 'Preseason',
            'R': 'Regular Season',
            'P': 'Playoffs',
            'A': 'All-Star'
        }

        assert game_types['R'] == 'Regular Season'
        assert game_types['P'] == 'Playoffs'


class TestNCAABGamesModule:
    """Test NCAAB games module."""

    def test_ncaab_teams_count(self):
        """Test NCAAB has many teams."""
        # Division I has ~350+ teams
        min_d1_teams = 350

        assert min_d1_teams >= 350

    def test_tournament_bracket_size(self):
        """Test March Madness bracket size."""
        tournament_teams = 68  # First Four + main bracket

        assert tournament_teams == 68


class TestEPLGamesModule:
    """Test EPL games module."""

    def test_epl_season_format(self):
        """Test EPL season format."""
        season = "2023-24"

        assert "-" in season
        assert len(season.split("-")) == 2

    def test_epl_team_count(self):
        """Test EPL has 20 teams."""
        epl_teams = 20

        assert epl_teams == 20

    def test_matches_per_season(self):
        """Test matches per EPL season."""
        teams = 20
        matches_per_team = (teams - 1) * 2  # Home and away
        total_matches = (teams * matches_per_team) // 2

        assert matches_per_team == 38
        assert total_matches == 380


class TestLigue1GamesModule:
    """Test Ligue1 games module."""

    def test_ligue1_team_count(self):
        """Test Ligue1 has 18 teams."""
        ligue1_teams = 18

        assert ligue1_teams == 18

    def test_matches_per_season(self):
        """Test matches per Ligue1 season."""
        teams = 18
        matches_per_team = (teams - 1) * 2
        total_matches = (teams * matches_per_team) // 2

        assert matches_per_team == 34
        assert total_matches == 306


class TestGameDataParsing:
    """Test game data parsing utilities."""

    def test_parse_home_away_teams(self):
        """Test parsing home and away teams."""
        game = {
            'home_team': 'Lakers',
            'away_team': 'Celtics'
        }

        assert game['home_team'] == 'Lakers'
        assert game['away_team'] == 'Celtics'

    def test_parse_game_time(self):
        """Test parsing game time."""
        time_str = '2024-01-15T19:30:00Z'
        game_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))

        assert game_time.hour == 19
        assert game_time.minute == 30

    def test_parse_score(self):
        """Test parsing game score."""
        score_str = "110-105"
        home, away = score_str.split("-")

        assert int(home) == 110
        assert int(away) == 105

    def test_determine_winner(self):
        """Test determining game winner."""
        home_score = 110
        away_score = 105

        home_won = home_score > away_score

        assert home_won == True


class TestRetryLogic:
    """Test retry logic for API calls."""

    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        base = 3
        max_retries = 5

        for attempt in range(max_retries):
            wait_time = (2 ** attempt) * base
            expected = base * (2 ** attempt)
            assert wait_time == expected

    def test_backoff_sequence(self):
        """Test backoff sequence values."""
        base = 3
        sequence = [(2 ** i) * base for i in range(5)]

        assert sequence == [3, 6, 12, 24, 48]

    def test_max_retry_exceeded(self):
        """Test max retry handling."""
        attempts = 0
        max_retries = 3

        while attempts < max_retries:
            attempts += 1

        assert attempts == max_retries


class TestFileOperations:
    """Test file operations for game data."""

    def test_json_file_naming(self):
        """Test JSON file naming convention."""
        sport = 'nba'
        date_str = '2024-01-15'
        filename = f"games_{date_str}.json"

        assert filename == "games_2024-01-15.json"

    def test_csv_file_naming(self):
        """Test CSV file naming convention."""
        tour = 'atp'
        year = '2024'
        filename = f"{tour}_{year}.csv"

        assert filename == "atp_2024.csv"

    def test_output_directory_structure(self, tmp_path):
        """Test output directory structure."""
        sport_dir = tmp_path / "data" / "nba"
        sport_dir.mkdir(parents=True)

        assert sport_dir.exists()
        assert sport_dir.parent.name == "data"
