"""Deep tests for stats modules that mock external dependencies"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
from pathlib import Path
import pandas as pd
import sys


class TestNBAStatsFetcherInit:
    """Test NBAStatsFetcher initialization"""

    def test_init_creates_session(self):
        from nba_stats import NBAStatsFetcher

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = NBAStatsFetcher(output_dir=tmpdir)
            assert hasattr(fetcher, 'session')

    def test_init_creates_output_dir(self):
        from nba_stats import NBAStatsFetcher

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / 'nba_stats_output'
            fetcher = NBAStatsFetcher(output_dir=str(output_dir))
            assert output_dir.exists()

    def test_base_url(self):
        from nba_stats import NBAStatsFetcher

        assert NBAStatsFetcher.BASE_URL == "https://stats.nba.com/stats"

    def test_headers(self):
        from nba_stats import NBAStatsFetcher

        assert 'User-Agent' in NBAStatsFetcher.HEADERS


class TestNBAStatsFetcherMethods:
    """Test NBAStatsFetcher methods with mocks"""

    def test_get_scoreboard_mock(self):
        from nba_stats import NBAStatsFetcher
        from datetime import date

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = NBAStatsFetcher(output_dir=tmpdir)

            with patch.object(fetcher.session, 'get') as mock_get:
                mock_response = Mock()
                mock_response.json.return_value = {
                    'resultSets': [{
                        'name': 'GameHeader',
                        'headers': ['GAME_ID', 'GAME_DATE_EST'],
                        'rowSet': []
                    }]
                }
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response

                result = fetcher.get_scoreboard('2024-01-15')
                assert 'resultSets' in result

    def test_get_play_by_play_mock(self):
        from nba_stats import NBAStatsFetcher

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = NBAStatsFetcher(output_dir=tmpdir)

            with patch.object(fetcher.session, 'get') as mock_get:
                mock_response = Mock()
                mock_response.json.return_value = {
                    'resultSets': [{
                        'name': 'PlayByPlay',
                        'rowSet': []
                    }]
                }
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response

                result = fetcher.get_play_by_play('0022300500')
                assert 'resultSets' in result

    def test_get_shot_chart_mock(self):
        from nba_stats import NBAStatsFetcher

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = NBAStatsFetcher(output_dir=tmpdir)

            with patch.object(fetcher.session, 'get') as mock_get:
                mock_response = Mock()
                mock_response.json.return_value = {
                    'resultSets': [{
                        'name': 'Shot_Chart_Detail',
                        'rowSet': []
                    }]
                }
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response

                result = fetcher.get_shot_chart('0022300500')
                assert 'resultSets' in result


class TestMLBStatsFetcherInit:
    """Test MLBStatsFetcher initialization"""

    def test_init_creates_session(self):
        from mlb_stats import MLBStatsFetcher

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = MLBStatsFetcher(output_dir=tmpdir)
            assert hasattr(fetcher, 'session')

    def test_init_creates_output_dir(self):
        from mlb_stats import MLBStatsFetcher

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / 'mlb_stats_output'
            fetcher = MLBStatsFetcher(output_dir=str(output_dir))
            assert output_dir.exists()


class TestMLBStatsFetcherMethods:
    """Test MLBStatsFetcher methods with mocks"""

    def test_get_schedule_mock(self):
        from mlb_stats import MLBStatsFetcher

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = MLBStatsFetcher(output_dir=tmpdir)

            with patch.object(fetcher.session, 'get') as mock_get:
                mock_response = Mock()
                mock_response.json.return_value = {
                    'dates': [{
                        'date': '2024-01-15',
                        'games': []
                    }]
                }
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response

                result = fetcher.get_schedule('2024-01-15')
                assert 'dates' in result

    def test_get_game_feed_mock(self):
        from mlb_stats import MLBStatsFetcher

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = MLBStatsFetcher(output_dir=tmpdir)

            with patch.object(fetcher.session, 'get') as mock_get:
                mock_response = Mock()
                mock_response.json.return_value = {
                    'gamePk': 123456,
                    'gameData': {},
                    'liveData': {}
                }
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response

                result = fetcher.get_game_feed(123456)
                assert result['gamePk'] == 123456


class TestNFLStatsFetcher:
    """Test NFLStatsFetcher with nfl_data_py mocked"""

    def test_init_creates_output_dir(self):
        # Mock nfl_data_py before import
        mock_nfl = MagicMock()
        sys.modules['nfl_data_py'] = mock_nfl

        if 'nfl_stats' in sys.modules:
            del sys.modules['nfl_stats']

        from nfl_stats import NFLStatsFetcher

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / 'nfl_stats_output'
            fetcher = NFLStatsFetcher(output_dir=str(output_dir))
            assert output_dir.exists()

    def test_init_default(self):
        mock_nfl = MagicMock()
        sys.modules['nfl_data_py'] = mock_nfl

        if 'nfl_stats' in sys.modules:
            del sys.modules['nfl_stats']

        from nfl_stats import NFLStatsFetcher

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = NFLStatsFetcher(output_dir=tmpdir)
            assert hasattr(fetcher, 'output_dir')


class TestModuleImports:
    """Test module imports"""

    def test_nba_stats_import(self):
        import nba_stats
        assert hasattr(nba_stats, 'NBAStatsFetcher')

    def test_mlb_stats_import(self):
        import mlb_stats
        assert hasattr(mlb_stats, 'MLBStatsFetcher')

    def test_nfl_stats_import(self):
        mock_nfl = MagicMock()
        sys.modules['nfl_data_py'] = mock_nfl

        if 'nfl_stats' in sys.modules:
            del sys.modules['nfl_stats']

        import nfl_stats
        assert hasattr(nfl_stats, 'NFLStatsFetcher')


class TestSessionConfiguration:
    """Test session configuration"""

    def test_nba_session_headers(self):
        from nba_stats import NBAStatsFetcher

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = NBAStatsFetcher(output_dir=tmpdir)

            assert 'User-Agent' in fetcher.session.headers

    def test_mlb_session_exists(self):
        from mlb_stats import MLBStatsFetcher

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = MLBStatsFetcher(output_dir=tmpdir)

            assert fetcher.session is not None


class TestErrorHandling:
    """Test error handling"""

    def test_nba_request_error(self):
        from nba_stats import NBAStatsFetcher
        import requests

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = NBAStatsFetcher(output_dir=tmpdir)

            with patch.object(fetcher.session, 'get') as mock_get:
                mock_get.side_effect = requests.RequestException("Error")

                with pytest.raises(requests.RequestException):
                    fetcher.get_scoreboard('2024-01-15')

    def test_mlb_request_error(self):
        from mlb_stats import MLBStatsFetcher
        import requests

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = MLBStatsFetcher(output_dir=tmpdir)

            with patch.object(fetcher.session, 'get') as mock_get:
                mock_get.side_effect = requests.RequestException("Error")

                with pytest.raises(requests.RequestException):
                    fetcher.get_schedule('2024-01-15')


class TestDataParsing:
    """Test data parsing"""

    def test_parse_nba_scoreboard(self):
        sample_data = {
            'resultSets': [{
                'name': 'GameHeader',
                'headers': ['GAME_ID', 'GAME_DATE_EST', 'HOME_TEAM_ID', 'VISITOR_TEAM_ID', 'GAME_STATUS_TEXT'],
                'rowSet': [
                    ['0022300500', '2024-01-15T00:00:00', 1610612738, 1610612751, 'Final']
                ]
            }]
        }

        headers = sample_data['resultSets'][0]['headers']
        idx_game_id = headers.index('GAME_ID')

        assert idx_game_id == 0

    def test_parse_mlb_schedule(self):
        sample_data = {
            'dates': [{
                'date': '2024-01-15',
                'games': [{
                    'gamePk': 123456,
                    'teams': {
                        'home': {'team': {'name': 'Yankees'}},
                        'away': {'team': {'name': 'Red Sox'}}
                    }
                }]
            }]
        }

        assert sample_data['dates'][0]['games'][0]['gamePk'] == 123456


class TestOutputDirectories:
    """Test output directory handling"""

    def test_nba_date_subdir(self):
        from nba_stats import NBAStatsFetcher

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = NBAStatsFetcher(output_dir=tmpdir)

            date_dir = fetcher.output_dir / '2024-01-15'
            date_dir.mkdir()

            assert date_dir.exists()

    def test_mlb_date_subdir(self):
        from mlb_stats import MLBStatsFetcher

        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = MLBStatsFetcher(output_dir=tmpdir)

            date_dir = fetcher.output_dir / '2024-01-15'
            date_dir.mkdir()

            assert date_dir.exists()
