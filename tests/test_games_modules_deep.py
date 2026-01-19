"""Comprehensive tests for game modules to increase coverage."""
import pytest
import sys
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import json


class TestNBAGamesDeep:
    """Tests for NBAGames class."""
    
    @pytest.fixture
    def nba_games(self):
        from nba_games import NBAGames
        with tempfile.TemporaryDirectory() as tmpdir:
            yield NBAGames(output_dir=tmpdir)
    
    def test_init_creates_output_dir(self):
        from nba_games import NBAGames
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'new_subdir'
            ng = NBAGames(output_dir=str(path))
            assert path.exists()
    
    def test_init_with_date_folder(self):
        from nba_games import NBAGames
        with tempfile.TemporaryDirectory() as tmpdir:
            ng = NBAGames(output_dir=tmpdir, date_folder='2024-01-01')
            expected = Path(tmpdir) / '2024-01-01'
            assert ng.output_dir == expected
    
    def test_class_attributes(self):
        from nba_games import NBAGames
        assert 'stats.nba.com' in NBAGames.BASE_URL
        assert 'User-Agent' in NBAGames.HEADERS
    
    @patch('nba_games.requests.get')
    def test_make_request_success(self, mock_get, nba_games):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': 'test'}
        mock_get.return_value = mock_response
        
        result = nba_games._make_request('http://test.com')
        assert result == {'data': 'test'}
    
    @patch('nba_games.requests.get')
    @patch('nba_games.time.sleep')
    def test_make_request_rate_limit_retry(self, mock_sleep, mock_get, nba_games):
        # First call: 429, second call: success
        mock_rate_limited = Mock()
        mock_rate_limited.status_code = 429
        
        mock_success = Mock()
        mock_success.status_code = 200
        mock_success.json.return_value = {'data': 'success'}
        
        mock_get.side_effect = [mock_rate_limited, mock_success]
        
        result = nba_games._make_request('http://test.com')
        assert result == {'data': 'success'}
        mock_sleep.assert_called()
    
    @patch('nba_games.requests.get')
    @patch('nba_games.time.sleep')
    def test_make_request_exception_retry(self, mock_sleep, mock_get, nba_games):
        import requests as req
        
        mock_success = Mock()
        mock_success.status_code = 200
        mock_success.json.return_value = {'data': 'success'}
        
        mock_get.side_effect = [req.exceptions.Timeout(), mock_success]
        
        result = nba_games._make_request('http://test.com')
        assert result == {'data': 'success'}
    
    @patch('nba_games.requests.get')
    @patch('nba_games.time.sleep')
    def test_make_request_all_retries_fail(self, mock_sleep, mock_get, nba_games):
        import requests as req
        mock_get.side_effect = req.exceptions.Timeout()
        
        with pytest.raises(req.exceptions.Timeout):
            nba_games._make_request('http://test.com', max_retries=2)
    
    @patch('nba_games.NBAGames._make_request')
    def test_get_games_for_date(self, mock_request, nba_games):
        mock_request.return_value = {'resultSets': []}
        
        result = nba_games.get_games_for_date('2024-01-15')
        
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert 'scoreboardv2' in call_args[0][0]
    
    @patch('nba_games.NBAGames._make_request')
    def test_get_game_boxscore(self, mock_request, nba_games):
        mock_request.return_value = {'data': 'boxscore'}
        
        result = nba_games.get_game_boxscore('0022300123')
        
        assert 'boxscoretraditionalv2' in mock_request.call_args[0][0]
    
    @patch('nba_games.requests.get')
    def test_get_game_playbyplay_success(self, mock_get, nba_games):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'game': {'actions': [1, 2, 3]}}
        mock_get.return_value = mock_response
        
        result = nba_games.get_game_playbyplay('0022300123')
        assert result == {'game': {'actions': [1, 2, 3]}}
    
    @patch('nba_games.requests.get')
    def test_get_game_playbyplay_failure(self, mock_get, nba_games):
        mock_get.side_effect = Exception('Network error')
        
        result = nba_games.get_game_playbyplay('0022300123')
        assert result is None
    
    @patch('nba_games.NBAGames.get_games_for_date')
    @patch('nba_games.NBAGames.get_game_boxscore')
    @patch('nba_games.NBAGames.get_game_playbyplay')
    @patch('nba_games.time.sleep')
    def test_download_games_for_date(self, mock_sleep, mock_pbp, mock_box, mock_games, nba_games):
        mock_games.return_value = {
            'resultSets': [{
                'name': 'GameHeader',
                'headers': ['A', 'B', 'GAME_ID'],
                'rowSet': [['x', 'y', '001'], ['a', 'b', '002']]
            }]
        }
        mock_box.return_value = {'boxscore': 'data'}
        mock_pbp.return_value = {'game': {'actions': [1]}}
        
        count = nba_games.download_games_for_date('2024-01-15')
        
        assert count == 2
        assert mock_box.call_count == 2
    
    @patch('nba_games.NBAGames.get_games_for_date')
    def test_download_games_no_result_sets(self, mock_games, nba_games):
        mock_games.return_value = {}
        
        count = nba_games.download_games_for_date('2024-01-15')
        assert count == 0
    
    @patch('nba_games.NBAGames.get_games_for_date')
    @patch('nba_games.NBAGames.get_game_boxscore')
    def test_download_games_boxscore_exists(self, mock_box, mock_games, nba_games):
        # Create existing boxscore file
        boxscore_file = nba_games.output_dir / 'boxscore_001.json'
        boxscore_file.write_text('{}')
        
        mock_games.return_value = {
            'resultSets': [{
                'name': 'GameHeader',
                'headers': ['GAME_ID'],
                'rowSet': [['001']]
            }]
        }
        
        count = nba_games.download_games_for_date('2024-01-15')
        # Should skip downloading boxscore since it exists
        mock_box.assert_not_called()
    
    @patch('nba_games.NBAGames.get_games_for_date')
    @patch('nba_games.NBAGames.get_game_boxscore')
    @patch('nba_games.NBAGames.get_game_playbyplay')
    def test_download_games_error_handling(self, mock_pbp, mock_box, mock_games, nba_games):
        mock_games.return_value = {
            'resultSets': [{
                'name': 'GameHeader',
                'headers': ['GAME_ID'],
                'rowSet': [['001']]
            }]
        }
        mock_box.side_effect = Exception('API Error')
        
        # Should not raise, just print error
        count = nba_games.download_games_for_date('2024-01-15')


class TestMLBGamesDeep:
    """Tests for MLBGames class."""
    
    @pytest.fixture
    def mlb_games(self):
        from mlb_games import MLBGames
        with tempfile.TemporaryDirectory() as tmpdir:
            yield MLBGames(output_dir=tmpdir)
    
    def test_init_creates_output_dir(self):
        from mlb_games import MLBGames
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'mlb_data'
            mg = MLBGames(output_dir=str(path))
            assert path.exists()
    
    def test_init_with_date_folder(self):
        from mlb_games import MLBGames
        with tempfile.TemporaryDirectory() as tmpdir:
            mg = MLBGames(output_dir=tmpdir, date_folder='2024-06-15')
            expected = Path(tmpdir) / '2024-06-15'
            assert mg.output_dir == expected
    
    def test_base_url(self):
        from mlb_games import MLBGames
        assert 'statsapi.mlb.com' in MLBGames.BASE_URL
    
    @patch('mlb_games.requests.get')
    def test_make_request_success(self, mock_get, mlb_games):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'dates': []}
        mock_get.return_value = mock_response
        
        result = mlb_games._make_request('http://test.com')
        assert result == {'dates': []}
    
    @patch('mlb_games.requests.get')
    def test_make_request_404(self, mock_get, mlb_games):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = mlb_games._make_request('http://test.com')
        assert result == {}
    
    @patch('mlb_games.requests.get')
    @patch('mlb_games.time.sleep')
    def test_make_request_rate_limit(self, mock_sleep, mock_get, mlb_games):
        mock_429 = Mock()
        mock_429.status_code = 429
        
        mock_success = Mock()
        mock_success.status_code = 200
        mock_success.json.return_value = {'data': 'ok'}
        
        mock_get.side_effect = [mock_429, mock_success]
        
        result = mlb_games._make_request('http://test.com')
        assert result == {'data': 'ok'}
    
    @patch('mlb_games.MLBGames._make_request')
    def test_get_schedule_for_date(self, mock_request, mlb_games):
        mock_request.return_value = {'dates': []}
        
        result = mlb_games.get_schedule_for_date('2024-06-15')
        
        mock_request.assert_called_once()
        # Check that URL and params were used
    
    @patch('mlb_games.MLBGames._make_request')
    def test_get_game_data(self, mock_request, mlb_games):
        mock_request.return_value = {'gamePk': 123}
        
        result = mlb_games.get_game_data(123456)
        
        assert 'feed/live' in mock_request.call_args[0][0]
    
    @patch('mlb_games.MLBGames._make_request')
    def test_get_game_boxscore(self, mock_request, mlb_games):
        mock_request.return_value = {'teams': {}}
        
        result = mlb_games.get_game_boxscore(123456)
        
        assert 'boxscore' in mock_request.call_args[0][0]
    
    @patch('mlb_games.MLBGames.get_schedule_for_date')
    @patch('mlb_games.MLBGames.get_game_data')
    @patch('mlb_games.MLBGames.get_game_boxscore')
    @patch('mlb_games.time.sleep')
    def test_download_games_for_date(self, mock_sleep, mock_box, mock_data, mock_sched, mlb_games):
        mock_sched.return_value = {
            'dates': [{
                'games': [{'gamePk': 111}, {'gamePk': 222}]
            }]
        }
        mock_data.return_value = {'game': 'data'}
        mock_box.return_value = {'box': 'score'}
        
        count = mlb_games.download_games_for_date('2024-06-15')
        
        assert count == 2
        assert mock_data.call_count == 2
        assert mock_box.call_count == 2
    
    @patch('mlb_games.MLBGames.get_schedule_for_date')
    def test_download_games_empty_schedule(self, mock_sched, mlb_games):
        mock_sched.return_value = {'dates': []}
        
        count = mlb_games.download_games_for_date('2024-01-01')
        assert count == 0
    
    @patch('mlb_games.MLBGames.get_schedule_for_date')
    @patch('mlb_games.MLBGames.get_game_data')
    def test_download_games_error_handling(self, mock_data, mock_sched, mlb_games):
        mock_sched.return_value = {
            'dates': [{'games': [{'gamePk': 111}]}]
        }
        mock_data.side_effect = Exception('API error')
        
        # Should handle error gracefully
        count = mlb_games.download_games_for_date('2024-06-15')


class TestTennisGamesDeep:
    """Tests for TennisGames class."""
    
    @pytest.fixture
    def tennis_games(self):
        from tennis_games import TennisGames
        with tempfile.TemporaryDirectory() as tmpdir:
            yield TennisGames(data_dir=tmpdir)
    
    def test_init(self, tennis_games):
        assert tennis_games.data_dir.exists()
        assert 'atp' in tennis_games.tours
        assert 'wta' in tennis_games.tours
        assert len(tennis_games.years) > 0
    
    def test_init_creates_dir(self):
        from tennis_games import TennisGames
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'tennis_data'
            tg = TennisGames(data_dir=str(path))
            assert path.exists()
    
    @patch('tennis_games.requests.get')
    def test_download_games_success(self, mock_get, tennis_games):
        import pandas as pd
        
        # Mock Excel download
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'fake excel data'
        mock_get.return_value = mock_response
        
        # Mock pandas read_excel
        with patch('tennis_games.pd.read_excel') as mock_read:
            mock_df = pd.DataFrame({
                'Date': ['2024-01-01'],
                'Winner': ['Player A'],
                'Loser': ['Player B']
            })
            mock_read.return_value = mock_df
            
            # Clear years to test just one
            tennis_games.years = ['2024']
            tennis_games.tours = ['atp']
            
            result = tennis_games.download_games()
            assert result is True
    
    @patch('tennis_games.requests.get')
    def test_download_games_404(self, mock_get, tennis_games):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        tennis_games.years = ['2030']
        tennis_games.tours = ['atp']
        
        # Should continue without error
        tennis_games.download_games()
    
    @patch('tennis_games.requests.get')
    def test_download_games_network_error(self, mock_get, tennis_games):
        mock_get.side_effect = Exception('Network error')
        
        tennis_games.years = ['2024']
        tennis_games.tours = ['atp']
        
        result = tennis_games.download_games()
        assert result is False
    
    @patch('tennis_games.TennisGames.download_games')
    def test_load_games_empty(self, mock_download, tennis_games):
        mock_download.return_value = True
        
        result = tennis_games.load_games()
        
        assert len(result) == 0  # No CSV files
    
    @patch('tennis_games.TennisGames.download_games')
    def test_load_games_with_data(self, mock_download, tennis_games):
        import pandas as pd
        mock_download.return_value = True
        
        # Create test CSV
        csv_path = tennis_games.data_dir / 'atp_2024.csv'
        df = pd.DataFrame({
            'Date': ['01/01/2024', '02/01/2024'],
            'Tournament': ['Australian Open', 'US Open'],
            'Surface': ['Hard', 'Hard'],
            'Winner': ['Novak Djokovic', 'Carlos Alcaraz'],
            'Loser': ['Rafael Nadal', 'Daniil Medvedev'],
            'WRank': [1, 2],
            'LRank': [3, 4],
            'Score': ['6-4 6-2', '7-5 6-4']
        })
        df.to_csv(csv_path, index=False)
        
        tennis_games.years = ['2024']
        tennis_games.tours = ['atp']
        
        result = tennis_games.load_games()
        
        assert len(result) == 2
        assert 'winner' in result.columns
        assert 'loser' in result.columns
    
    @patch('tennis_games.TennisGames.download_games')
    def test_load_games_missing_date_column(self, mock_download, tennis_games):
        import pandas as pd
        mock_download.return_value = True
        
        # Create CSV without Date column
        csv_path = tennis_games.data_dir / 'atp_2024.csv'
        df = pd.DataFrame({
            'Winner': ['Player A'],
            'Loser': ['Player B']
        })
        df.to_csv(csv_path, index=False)
        
        tennis_games.years = ['2024']
        tennis_games.tours = ['atp']
        
        result = tennis_games.load_games()
        assert len(result) == 0  # Should skip file without Date
    
    @patch('tennis_games.TennisGames.download_games')
    def test_load_games_with_nan_values(self, mock_download, tennis_games):
        import pandas as pd
        mock_download.return_value = True
        
        csv_path = tennis_games.data_dir / 'atp_2024.csv'
        df = pd.DataFrame({
            'Date': ['01/01/2024', None],
            'Winner': ['Player A', None],
            'Loser': ['Player B', 'Player C']
        })
        df.to_csv(csv_path, index=False)
        
        tennis_games.years = ['2024']
        tennis_games.tours = ['atp']
        
        result = tennis_games.load_games()
        # Should skip rows with NaN in Date, Winner, or Loser
        assert len(result) == 1
    
    @patch('tennis_games.TennisGames.download_games')
    def test_load_games_encoding_fallback(self, mock_download, tennis_games):
        import pandas as pd
        mock_download.return_value = True
        
        # Create CSV with UTF-8 encoding
        csv_path = tennis_games.data_dir / 'wta_2024.csv'
        df = pd.DataFrame({
            'Date': ['01/01/2024'],
            'Winner': ['Iga Świątek'],
            'Loser': ['Aryna Sabalenka']
        })
        df.to_csv(csv_path, index=False, encoding='utf-8')
        
        tennis_games.years = ['2024']
        tennis_games.tours = ['wta']
        
        result = tennis_games.load_games()
        assert len(result) == 1
    
    @patch('tennis_games.TennisGames.download_games')
    def test_load_games_exception_handling(self, mock_download, tennis_games):
        import pandas as pd
        mock_download.return_value = True
        
        # Create a corrupted CSV file
        csv_path = tennis_games.data_dir / 'atp_2024.csv'
        csv_path.write_text('corrupted,data\n"unclosed quote')
        
        tennis_games.years = ['2024']
        tennis_games.tours = ['atp']
        
        # Should handle error gracefully
        result = tennis_games.load_games()
    
    @patch('tennis_games.requests.get')
    def test_download_games_wta_url(self, mock_get, tennis_games):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        tennis_games.years = ['2024']
        tennis_games.tours = ['wta']
        
        tennis_games.download_games()
        
        # Check WTA URL format
        call_url = mock_get.call_args[0][0]
        assert '2024w' in call_url
    
    @patch('tennis_games.requests.get')
    def test_download_games_skip_existing_csv(self, mock_get, tennis_games):
        import pandas as pd
        
        # Create existing CSV for old year
        csv_path = tennis_games.data_dir / 'atp_2023.csv'
        df = pd.DataFrame({'Date': [], 'Winner': [], 'Loser': []})
        df.to_csv(csv_path, index=False)
        
        tennis_games.years = ['2023']
        tennis_games.tours = ['atp']
        
        tennis_games.download_games()
        
        # Should not make request for existing old year
        mock_get.assert_not_called()
    
    @patch('tennis_games.requests.get')
    @patch('tennis_games.pd.read_excel')
    def test_download_games_excel_conversion_error(self, mock_read, mock_get, tennis_games):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'fake data'
        mock_get.return_value = mock_response
        
        mock_read.side_effect = Exception('Cannot read excel')
        
        tennis_games.years = ['2024']
        tennis_games.tours = ['atp']
        
        # Should handle error
        tennis_games.download_games()


class TestNHLGameEventsDeep:
    """Tests for NHLGameEvents class."""
    
    @pytest.fixture
    def nhl_events(self):
        from nhl_game_events import NHLGameEvents
        with tempfile.TemporaryDirectory() as tmpdir:
            yield NHLGameEvents(output_dir=tmpdir)
    
    def test_init(self):
        from nhl_game_events import NHLGameEvents
        with tempfile.TemporaryDirectory() as tmpdir:
            nhl = NHLGameEvents(output_dir=tmpdir)
            assert nhl.output_dir.exists()
    
    def test_base_url(self):
        from nhl_game_events import NHLGameEvents
        assert 'nhl' in NHLGameEvents.BASE_URL.lower()
    
    @patch('nhl_game_events.requests.get')
    def test_make_request_success(self, mock_get, nhl_events):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': 'test'}
        mock_get.return_value = mock_response
        
        result = nhl_events._make_request('http://test.com')
        assert result == {'data': 'test'}
    
    @patch('nhl_game_events.requests.get')
    @patch('nhl_game_events.time.sleep')
    def test_make_request_rate_limited(self, mock_sleep, mock_get, nhl_events):
        mock_429 = Mock()
        mock_429.status_code = 429
        
        mock_success = Mock()
        mock_success.status_code = 200
        mock_success.json.return_value = {'data': 'ok'}
        
        mock_get.side_effect = [mock_429, mock_success]
        
        result = nhl_events._make_request('http://test.com')
        assert result == {'data': 'ok'}
    
    @patch('nhl_game_events.NHLGameEvents._make_request')
    def test_get_schedule_by_date(self, mock_request, nhl_events):
        mock_request.return_value = {'games': []}
        
        # NHLGameEvents uses get_schedule_by_date not get_schedule_for_date
        result = nhl_events.get_schedule_by_date('2024-01-15')
        mock_request.assert_called_once()
    
    @patch('nhl_game_events.NHLGameEvents._make_request')
    def test_get_game_data(self, mock_request, nhl_events):
        mock_request.return_value = {'id': 123}
        
        result = nhl_events.get_game_data(2024020001)
        assert 'play-by-play' in mock_request.call_args[0][0]
    
    @patch('nhl_game_events.NHLGameEvents._make_request')
    def test_get_game_boxscore(self, mock_request, nhl_events):
        mock_request.return_value = {'plays': []}
        
        result = nhl_events.get_game_boxscore(2024020001)
        assert 'boxscore' in mock_request.call_args[0][0]


class TestEPLGamesDeep:
    """Tests for EPLGames class."""
    
    @pytest.fixture
    def epl_games(self):
        from epl_games import EPLGames
        with tempfile.TemporaryDirectory() as tmpdir:
            yield EPLGames(data_dir=tmpdir)
    
    def test_init(self, epl_games):
        assert epl_games.data_dir.exists()
    
    @patch('epl_games.requests.get')
    def test_download_games(self, mock_get, epl_games):
        import pandas as pd
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n01/01/2024,Arsenal,Chelsea,2,1,H'
        mock_get.return_value = mock_response
        
        epl_games.seasons = ['2324']
        result = epl_games.download_games()
        assert result is True
    
    @patch('epl_games.EPLGames.download_games')
    def test_load_games(self, mock_download, epl_games):
        import pandas as pd
        mock_download.return_value = True
        
        # Create test CSV with correct filename format E0_{season}.csv
        csv_path = epl_games.data_dir / 'E0_2324.csv'
        df = pd.DataFrame({
            'Date': ['01/01/2024'],
            'HomeTeam': ['Arsenal'],
            'AwayTeam': ['Chelsea'],
            'FTHG': [2],
            'FTAG': [1],
            'FTR': ['H']
        })
        df.to_csv(csv_path, index=False)
        
        epl_games.seasons = ['2324']
        result = epl_games.load_games()
        
        assert len(result) > 0


class TestLigue1GamesDeep:
    """Tests for Ligue1Games class."""
    
    @pytest.fixture
    def ligue1_games(self):
        from ligue1_games import Ligue1Games
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Ligue1Games(data_dir=tmpdir)
    
    def test_init(self, ligue1_games):
        assert ligue1_games.data_dir.exists()
    
    @patch('ligue1_games.requests.get')
    def test_download_games(self, mock_get, ligue1_games):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n01/01/2024,PSG,Lyon,3,1,H'
        mock_get.return_value = mock_response
        
        ligue1_games.seasons = ['2324']
        result = ligue1_games.download_games()
        assert result is True
    
    @patch('ligue1_games.Ligue1Games.download_games')
    def test_load_games(self, mock_download, ligue1_games):
        import pandas as pd
        mock_download.return_value = True
        
        # Correct filename format F1_{season}.csv
        csv_path = ligue1_games.data_dir / 'F1_2324.csv'
        df = pd.DataFrame({
            'Date': ['01/01/2024'],
            'HomeTeam': ['PSG'],
            'AwayTeam': ['Lyon'],
            'FTHG': [3],
            'FTAG': [1],
            'FTR': ['H']
        })
        df.to_csv(csv_path, index=False)
        
        ligue1_games.seasons = ['2324']
        result = ligue1_games.load_games()
        
        assert len(result) > 0


class TestNCAABGamesDeep:
    """Tests for NCAABGames class."""
    
    @pytest.fixture
    def ncaab_games(self):
        from ncaab_games import NCAABGames
        with tempfile.TemporaryDirectory() as tmpdir:
            yield NCAABGames(data_dir=tmpdir)
    
    def test_init(self, ncaab_games):
        assert ncaab_games.data_dir.exists()
    
    @patch('ncaab_games.requests.get')
    def test_download_games(self, mock_get, ncaab_games):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'Date,HomeTeam,AwayTeam,HomeScore,AwayScore\n01/01/2024,Duke,UNC,75,70'
        mock_get.return_value = mock_response
        
        # Should handle download
        ncaab_games.seasons = ['2324']
        result = ncaab_games.download_games()


# Additional edge case tests
class TestGameModulesEdgeCases:
    """Edge case tests for game modules."""
    
    def test_nba_games_import(self):
        from nba_games import NBAGames
        assert NBAGames is not None
    
    def test_mlb_games_import(self):
        from mlb_games import MLBGames
        assert MLBGames is not None
    
    def test_tennis_games_import(self):
        from tennis_games import TennisGames
        assert TennisGames is not None
    
    def test_nhl_game_events_import(self):
        from nhl_game_events import NHLGameEvents
        assert NHLGameEvents is not None
    
    def test_epl_games_import(self):
        from epl_games import EPLGames
        assert EPLGames is not None
    
    def test_ligue1_games_import(self):
        from ligue1_games import Ligue1Games
        assert Ligue1Games is not None
    
    def test_ncaab_games_import(self):
        from ncaab_games import NCAABGames
        assert NCAABGames is not None
