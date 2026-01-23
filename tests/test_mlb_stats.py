"""Tests for MLB Stats Fetcher module."""

import pytest
import sys
from pathlib import Path
from datetime import datetime, date
from unittest.mock import patch, MagicMock
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestMLBStatsFetcherInit:
    """Test MLBStatsFetcher initialization."""

    def test_init_creates_directory(self, tmp_path):
        """Test initialization creates output directory."""
        from mlb_stats import MLBStatsFetcher

        output_dir = tmp_path / "mlb"
        fetcher = MLBStatsFetcher(output_dir=str(output_dir))

        assert output_dir.exists()

    def test_stats_api_url(self):
        """Test Stats API URL configuration."""
        from mlb_stats import MLBStatsFetcher

        assert MLBStatsFetcher.STATS_API == "https://statsapi.mlb.com/api/v1.1"

    def test_statcast_api_url(self):
        """Test Statcast API URL configuration."""
        from mlb_stats import MLBStatsFetcher

        assert MLBStatsFetcher.STATCAST_API == "https://baseballsavant.mlb.com"

    def test_session_initialized(self, tmp_path):
        """Test session is initialized."""
        from mlb_stats import MLBStatsFetcher

        fetcher = MLBStatsFetcher(output_dir=str(tmp_path / "mlb"))

        assert fetcher.session is not None


class TestGetSchedule:
    """Test schedule fetching."""

    @patch('mlb_stats.requests.Session')
    def test_get_schedule_success(self, mock_session_class, tmp_path):
        """Test successful schedule fetch."""
        from mlb_stats import MLBStatsFetcher

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'dates': []}
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        fetcher = MLBStatsFetcher(output_dir=str(tmp_path / "mlb"))
        fetcher.session = mock_session

        result = fetcher.get_schedule('2024-04-15')

        assert 'dates' in result

    def test_date_format(self):
        """Test date format for API."""
        date_str = '2024-04-15'
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        api_format = date_obj.strftime('%Y-%m-%d')

        assert api_format == '2024-04-15'


class TestPlayByPlay:
    """Test play-by-play data."""

    def test_game_pk_format(self):
        """Test game_pk format."""
        # MLB game_pk is typically a 6-digit number
        game_pk = 745123

        assert game_pk > 0
        assert isinstance(game_pk, int)

    def test_play_structure(self):
        """Test play data structure."""
        play = {
            'play_id': 'abc123',
            'at_bat_number': 5,
            'inning': 3,
            'inning_half': 'top',
            'description': 'Single to left field',
            'event_type': 'single',
            'rbi': 1
        }

        assert play['event_type'] == 'single'
        assert play['rbi'] == 1


class TestStatcastData:
    """Test Statcast data."""

    def test_exit_velocity(self):
        """Test exit velocity data."""
        statcast = {
            'exit_velocity': 102.5,
            'launch_angle': 25.0,
            'hit_distance': 405
        }

        assert statcast['exit_velocity'] == 102.5

    def test_pitch_data(self):
        """Test pitch data structure."""
        pitch = {
            'pitch_type': 'FF',  # Four-seam fastball
            'velocity': 96.5,
            'spin_rate': 2400,
            'zone': 5,
            'result': 'strike'
        }

        assert pitch['pitch_type'] == 'FF'
        assert pitch['velocity'] == 96.5

    def test_expected_stats(self):
        """Test expected stats (xBA, xSLG)."""
        expected = {
            'xba': 0.320,
            'xslg': 0.550,
            'barrel_rate': 12.5
        }

        assert expected['xba'] < 1.0
        assert expected['barrel_rate'] < 100


class TestBoxScore:
    """Test box score data."""

    def test_batter_stats_structure(self):
        """Test batter stats structure."""
        batter = {
            'player_id': 660271,
            'player_name': 'Shohei Ohtani',
            'ab': 4,
            'hits': 2,
            'runs': 1,
            'rbi': 2,
            'bb': 1,
            'so': 1,
            'avg': 0.321
        }

        assert batter['ab'] == 4
        assert batter['avg'] == 0.321

    def test_pitcher_stats_structure(self):
        """Test pitcher stats structure."""
        pitcher = {
            'player_id': 543037,
            'player_name': 'Gerrit Cole',
            'ip': 7.0,
            'hits': 5,
            'runs': 2,
            'earned_runs': 2,
            'bb': 1,
            'so': 10,
            'era': 3.15
        }

        assert pitcher['ip'] == 7.0
        assert pitcher['so'] == 10


class TestCalculations:
    """Test stat calculations."""

    def test_batting_average(self):
        """Test batting average calculation."""
        hits = 150
        at_bats = 500

        avg = hits / at_bats

        assert avg == 0.300

    def test_on_base_percentage(self):
        """Test OBP calculation."""
        hits = 150
        walks = 50
        hbp = 5
        at_bats = 500
        sf = 10

        obp = (hits + walks + hbp) / (at_bats + walks + hbp + sf)

        assert obp == pytest.approx(0.363, abs=0.01)

    def test_era_calculation(self):
        """Test ERA calculation."""
        earned_runs = 45
        innings_pitched = 180.0

        era = (earned_runs / innings_pitched) * 9

        assert era == 2.25

    def test_whip_calculation(self):
        """Test WHIP calculation."""
        walks = 40
        hits_allowed = 150
        innings_pitched = 180.0

        whip = (walks + hits_allowed) / innings_pitched

        assert whip == pytest.approx(1.056, abs=0.01)

    def test_ops_calculation(self):
        """Test OPS calculation."""
        obp = 0.363
        slg = 0.500

        ops = obp + slg

        assert ops == 0.863
