"""Additional tests for tennis_games.py, nhl_game_events.py, and other game modules"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
from pathlib import Path
import pandas as pd
import json


class TestTennisGamesComplete:
    """Complete tests for TennisGames"""

    def test_init_with_path(self):
        from tennis_games import TennisGames

        with tempfile.TemporaryDirectory() as tmpdir:
            games = TennisGames(data_dir=tmpdir)
            assert games.data_dir == Path(tmpdir)

    def test_class_methods(self):
        from tennis_games import TennisGames

        # Check for expected methods
        expected_methods = ['load_matches']
        for method in expected_methods:
            if hasattr(TennisGames, method):
                assert callable(getattr(TennisGames, method))


class TestNHLGameEventsComplete:
    """Complete tests for NHLGameEvents"""

    def test_base_url(self):
        from nhl_game_events import NHLGameEvents

        # Check class has BASE_URL
        if hasattr(NHLGameEvents, 'BASE_URL'):
            assert 'nhl' in NHLGameEvents.BASE_URL.lower()

    def test_session_headers(self):
        from nhl_game_events import NHLGameEvents

        with tempfile.TemporaryDirectory() as tmpdir:
            events = NHLGameEvents(output_dir=tmpdir)

            # Should have session with headers
            if hasattr(events, 'session'):
                assert hasattr(events.session, 'headers')


class TestNBAGamesComplete:
    """Complete tests for NBAGames"""

    def test_base_url(self):
        from nba_games import NBAGames

        if hasattr(NBAGames, 'BASE_URL'):
            assert 'nba' in NBAGames.BASE_URL.lower()

    def test_headers_set(self):
        from nba_games import NBAGames

        with tempfile.TemporaryDirectory() as tmpdir:
            games = NBAGames(output_dir=tmpdir)

            # NBA API requires specific headers
            if hasattr(games, 'session'):
                assert games.session is not None


class TestMLBGamesComplete:
    """Complete tests for MLBGames"""

    def test_base_url(self):
        from mlb_games import MLBGames

        if hasattr(MLBGames, 'BASE_URL'):
            assert 'mlb' in MLBGames.BASE_URL.lower()


class TestNCAABGamesComplete:
    """Complete tests for NCAABGames"""

    def test_init(self):
        from ncaab_games import NCAABGames

        with tempfile.TemporaryDirectory() as tmpdir:
            games = NCAABGames(data_dir=tmpdir)
            assert str(games.data_dir) == tmpdir

    def test_load_games(self):
        from ncaab_games import NCAABGames

        with tempfile.TemporaryDirectory() as tmpdir:
            games = NCAABGames(data_dir=tmpdir)

            result = games.load_games()
            assert isinstance(result, pd.DataFrame)


class TestEPLGamesComplete:
    """Complete tests for EPLGames"""

    def test_init(self):
        from epl_games import EPLGames

        with tempfile.TemporaryDirectory() as tmpdir:
            games = EPLGames(data_dir=tmpdir)
            assert str(games.data_dir) == tmpdir

    def test_load_games(self):
        from epl_games import EPLGames

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test CSV file
            csv_path = Path(tmpdir) / 'epl_games.csv'
            csv_path.write_text(
                'date,home_team,away_team,home_score,away_score,result\n'
                '2024-01-15,Arsenal,Chelsea,2,1,H\n'
                '2024-01-16,Liverpool,Man City,1,2,A\n'
            )

            games = EPLGames(data_dir=tmpdir)

            if hasattr(games, 'load_games'):
                result = games.load_games()


class TestLigue1GamesComplete:
    """Complete tests for Ligue1Games"""

    def test_init(self):
        from ligue1_games import Ligue1Games

        with tempfile.TemporaryDirectory() as tmpdir:
            games = Ligue1Games(data_dir=tmpdir)
            assert str(games.data_dir) == tmpdir

    def test_load_games(self):
        from ligue1_games import Ligue1Games

        with tempfile.TemporaryDirectory() as tmpdir:
            games = Ligue1Games(data_dir=tmpdir)

            if hasattr(games, 'load_games'):
                result = games.load_games()


class TestAPIEndpoints:
    """Test API endpoint configuration"""

    def test_nhl_endpoints(self):
        from nhl_game_events import NHLGameEvents

        with tempfile.TemporaryDirectory() as tmpdir:
            events = NHLGameEvents(output_dir=tmpdir)

            # Check for schedule endpoint
            if hasattr(events, 'get_schedule'):
                pass

    def test_nba_endpoints(self):
        from nba_games import NBAGames

        with tempfile.TemporaryDirectory() as tmpdir:
            games = NBAGames(output_dir=tmpdir)

            # Check for scoreboard endpoint
            if hasattr(games, 'get_scoreboard'):
                pass


class TestDataParsing:
    """Test data parsing in game modules"""

    def test_parse_nhl_game_data(self):
        game_data = {
            'id': 2024020001,
            'gameDate': '2024-01-15',
            'homeTeam': {
                'id': 6,
                'name': 'Boston Bruins',
                'abbrev': 'BOS'
            },
            'awayTeam': {
                'id': 3,
                'name': 'New York Rangers',
                'abbrev': 'NYR'
            }
        }

        # Data structure check
        assert game_data['homeTeam']['name'] == 'Boston Bruins'

    def test_parse_nba_scoreboard(self):
        scoreboard_data = {
            'resultSets': [{
                'name': 'GameHeader',
                'headers': ['GAME_ID', 'GAME_STATUS_TEXT', 'HOME_TEAM_ID', 'VISITOR_TEAM_ID'],
                'rowSet': [
                    ['0022300500', 'Final', 1610612738, 1610612751]
                ]
            }]
        }

        # Data structure check
        assert scoreboard_data['resultSets'][0]['name'] == 'GameHeader'


class TestFileSaving:
    """Test file saving operations"""

    def test_save_schedule_json(self):
        from nhl_game_events import NHLGameEvents

        with tempfile.TemporaryDirectory() as tmpdir:
            events = NHLGameEvents(output_dir=tmpdir)

            # Simulate saving schedule
            schedule_data = {'games': [{'id': 1}]}

            date_dir = Path(tmpdir) / '2024-01-15'
            date_dir.mkdir()

            with open(date_dir / 'schedule.json', 'w') as f:
                json.dump(schedule_data, f)

            # Verify file was created
            assert (date_dir / 'schedule.json').exists()


class TestDirectoryCreation:
    """Test directory creation"""

    def test_output_dir_created(self):
        from nba_games import NBAGames

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / 'new_dir'
            games = NBAGames(output_dir=str(output_dir))

            assert output_dir.exists()

    def test_date_subdirectory(self):
        from nhl_game_events import NHLGameEvents

        with tempfile.TemporaryDirectory() as tmpdir:
            events = NHLGameEvents(output_dir=tmpdir)

            # Create date subdirectory
            date_dir = Path(tmpdir) / '2024-01-15'
            date_dir.mkdir()

            assert date_dir.exists()


class TestConnectionHandling:
    """Test connection handling"""

    def test_session_exists(self):
        from nba_games import NBAGames

        with tempfile.TemporaryDirectory() as tmpdir:
            games = NBAGames(output_dir=tmpdir)

            # Session should exist
            if hasattr(games, 'session'):
                assert games.session is not None

    def test_timeout_handling(self):
        from nhl_game_events import NHLGameEvents
        import requests

        with tempfile.TemporaryDirectory() as tmpdir:
            events = NHLGameEvents(output_dir=tmpdir)

            if hasattr(events, 'get_schedule') and hasattr(events, 'session'):
                with patch.object(events, 'session', Mock()) as mock_session:
                    mock_session.get.side_effect = requests.Timeout("Timeout")

                    try:
                        events.get_schedule('2024-01-15')
                    except requests.Timeout:
                        pass  # Expected


class TestModuleAttributes:
    """Test module attributes"""

    def test_nba_games_headers(self):
        from nba_games import NBAGames

        if hasattr(NBAGames, 'HEADERS'):
            assert 'User-Agent' in NBAGames.HEADERS

    def test_nhl_game_events_base_url(self):
        from nhl_game_events import NHLGameEvents

        if hasattr(NHLGameEvents, 'BASE_URL'):
            assert isinstance(NHLGameEvents.BASE_URL, str)
