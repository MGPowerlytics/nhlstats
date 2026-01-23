"""Final coverage push tests for remaining low-coverage modules."""
import pytest
import sys
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import json
import pandas as pd


class TestNFLModulesWithMock:
    """Tests for NFL modules with proper mocking."""

    @pytest.fixture(autouse=True)
    def mock_nfl_data_py(self):
        """Mock nfl_data_py before any imports."""
        mock_module = MagicMock()
        mock_module.import_schedules = MagicMock(return_value=pd.DataFrame({
            'game_id': ['2024_01_KC_DET'],
            'season': [2024],
            'week': [1],
            'home_team': ['DET'],
            'away_team': ['KC'],
            'home_score': [28],
            'away_score': [24]
        }))
        mock_module.import_team_desc = MagicMock(return_value=pd.DataFrame({
            'team_abbr': ['KC', 'DET'],
            'team_name': ['Chiefs', 'Lions']
        }))
        mock_module.import_pbp_data = MagicMock(return_value=pd.DataFrame())
        mock_module.import_weekly_data = MagicMock(return_value=pd.DataFrame())
        mock_module.import_seasonal_data = MagicMock(return_value=pd.DataFrame())
        mock_module.import_rosters = MagicMock(return_value=pd.DataFrame())
        mock_module.import_injuries = MagicMock(return_value=pd.DataFrame())
        mock_module.import_depth_charts = MagicMock(return_value=pd.DataFrame())
        mock_module.import_ngs_data = MagicMock(return_value=pd.DataFrame())

        sys.modules['nfl_data_py'] = mock_module

        # Clear cached imports
        for mod in list(sys.modules.keys()):
            if 'nfl_games' in mod or 'nfl_stats' in mod:
                del sys.modules[mod]

        yield mock_module

        # Cleanup
        if 'nfl_data_py' in sys.modules:
            del sys.modules['nfl_data_py']

    def test_nfl_games_import(self, mock_nfl_data_py):
        from nfl_games import NFLGames
        assert NFLGames is not None

    def test_nfl_games_init(self, mock_nfl_data_py):
        with tempfile.TemporaryDirectory() as tmpdir:
            from nfl_games import NFLGames
            games = NFLGames(output_dir=tmpdir)
            assert games.output_dir.exists()

    def test_nfl_stats_import(self, mock_nfl_data_py):
        from nfl_stats import NFLStatsFetcher
        assert NFLStatsFetcher is not None

    def test_nfl_stats_init(self, mock_nfl_data_py):
        from nfl_stats import NFLStatsFetcher
        stats = NFLStatsFetcher()
        assert stats is not None


class TestPolymarketAPIMethods:
    """More tests for PolymarketAPI."""

    @pytest.fixture
    def polymarket(self):
        from polymarket_api import PolymarketAPI
        return PolymarketAPI()

    def test_base_url(self):
        from polymarket_api import PolymarketAPI
        assert 'gamma-api' in PolymarketAPI.BASE_URL

    def test_clob_url(self):
        from polymarket_api import PolymarketAPI
        assert 'clob' in PolymarketAPI.CLOB_URL


class TestOddsComparatorMethods:
    """More tests for OddsComparator."""

    @pytest.fixture
    def comparator(self):
        from odds_comparator import OddsComparator
        return OddsComparator()

    def test_import(self):
        from odds_comparator import OddsComparator
        assert OddsComparator is not None


class TestNHLGameEventsMethods:
    """More tests for NHLGameEvents."""

    @pytest.fixture
    def nhl_events(self):
        from nhl_game_events import NHLGameEvents
        with tempfile.TemporaryDirectory() as tmpdir:
            yield NHLGameEvents(output_dir=tmpdir)

    def test_both_urls(self):
        from nhl_game_events import NHLGameEvents
        assert 'api-web.nhle.com' in NHLGameEvents.BASE_URL
        assert 'statsapi' in NHLGameEvents.LEGACY_URL


class TestTheOddsAPIMethods:
    """More tests for TheOddsAPI."""

    @pytest.fixture
    def odds_api(self):
        from the_odds_api import TheOddsAPI
        return TheOddsAPI(api_key='test')

    def test_all_sport_keys(self, odds_api):
        from the_odds_api import TheOddsAPI
        assert 'nba' in TheOddsAPI.SPORT_KEYS
        assert 'nhl' in TheOddsAPI.SPORT_KEYS
        assert 'mlb' in TheOddsAPI.SPORT_KEYS
        assert 'nfl' in TheOddsAPI.SPORT_KEYS
        assert 'epl' in TheOddsAPI.SPORT_KEYS
        assert 'ncaab' in TheOddsAPI.SPORT_KEYS


class TestCloudBetMethods:
    """More tests for CloudbetAPI."""

    @pytest.fixture
    def cloudbet(self):
        from cloudbet_api import CloudbetAPI
        return CloudbetAPI(api_key='test')

    def test_session_headers(self, cloudbet):
        assert 'Authorization' in cloudbet.session.headers
        assert 'Content-Type' in cloudbet.session.headers


class TestNBAStatsMethods:
    """More tests for NBAStatsFetcher."""

    @pytest.fixture
    def nba_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from nba_stats import NBAStatsFetcher
            yield NBAStatsFetcher(output_dir=tmpdir)

    def test_all_headers(self, nba_stats):
        assert 'User-Agent' in nba_stats.HEADERS
        assert 'Accept' in nba_stats.HEADERS
        assert 'Referer' in nba_stats.HEADERS


class TestMLBStatsMethods:
    """More tests for MLBStatsFetcher."""

    @pytest.fixture
    def mlb_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from mlb_stats import MLBStatsFetcher
            yield MLBStatsFetcher(output_dir=tmpdir)

    def test_api_urls(self):
        from mlb_stats import MLBStatsFetcher
        assert 'statsapi.mlb.com' in MLBStatsFetcher.STATS_API
        assert 'baseballsavant' in MLBStatsFetcher.STATCAST_API


class TestNCAABEloMethods:
    """More tests for NCAABEloRating."""

    @pytest.fixture
    def ncaab_elo(self):
        from plugins.elo import NCAABEloRating
        return NCAABEloRating()

    def test_ratings_dict(self, ncaab_elo):
        ncaab_elo.get_rating('Duke')
        ncaab_elo.get_rating('UNC')
        assert 'Duke' in ncaab_elo.ratings
        assert 'UNC' in ncaab_elo.ratings

    def test_multiple_updates(self, ncaab_elo):
        for i in range(5):
            ncaab_elo.update('Duke', 'UNC', home_win=1.0)
        assert ncaab_elo.get_rating('Duke') > ncaab_elo.get_rating('UNC')


class TestMLBEloMethods:
    """More tests for MLBEloRating."""

    @pytest.fixture
    def mlb_elo(self):
        from plugins.elo import MLBEloRating
        return MLBEloRating()

    def test_ratings_dict(self, mlb_elo):
        mlb_elo.get_rating('Yankees')
        mlb_elo.get_rating('Red Sox')
        assert 'Yankees' in mlb_elo.ratings

    def test_tie_game(self, mlb_elo):
        # Test with same score
        mlb_elo.update('Team A', 'Team B', home_score=3, away_score=3)
        # Both should be close to initial
        assert abs(mlb_elo.get_rating('Team A') - 1500) < 20


class TestNFLEloMethods:
    """More tests for NFLEloRating."""

    @pytest.fixture
    def nfl_elo(self):
        from plugins.elo import NFLEloRating
        return NFLEloRating()

    def test_ratings_dict(self, nfl_elo):
        nfl_elo.get_rating('Chiefs')
        nfl_elo.get_rating('49ers')
        assert 'Chiefs' in nfl_elo.ratings

    def test_close_game(self, nfl_elo):
        nfl_elo.update('Team A', 'Team B', home_score=24, away_score=21)
        assert nfl_elo.get_rating('Team A') > 1500


class TestNBAEloMethods:
    """More tests for NBAEloRating."""

    @pytest.fixture
    def nba_elo(self):
        from plugins.elo import NBAEloRating
        return NBAEloRating()

    def test_ratings_dict(self, nba_elo):
        nba_elo.update('Lakers', 'Celtics', True)
        assert 'Lakers' in nba_elo.ratings
        assert 'Celtics' in nba_elo.ratings

    def test_expected_score_strong_favorite(self, nba_elo):
        nba_elo.ratings['Strong'] = 1700
        nba_elo.ratings['Weak'] = 1300

        score = nba_elo.expected_score(1700, 1300)
        assert score > 0.9


class TestNHLEloMethods:
    """More tests for NHLEloRating."""

    @pytest.fixture
    def nhl_elo(self):
        from plugins.elo import NHLEloRating
        return NHLEloRating()

    def test_ratings_init(self, nhl_elo):
        assert nhl_elo.ratings == {}

    def test_game_history_init(self, nhl_elo):
        assert nhl_elo.game_history == []


class TestGlicko2Methods:
    """More tests for Glicko2Rating."""

    @pytest.fixture
    def glicko(self):
        from glicko2_rating import Glicko2Rating
        return Glicko2Rating()

    def test_epsilon(self, glicko):
        assert glicko.EPSILON == 0.000001

    def test_defaultdict_behavior(self, glicko):
        # Access a new team
        rating = glicko.ratings['NewTeam']
        assert rating['rating'] == 1500
        assert rating['rd'] == 350
        assert rating['vol'] == 0.06


class TestTennisEloMethods:
    """More tests for TennisEloRating."""

    @pytest.fixture
    def tennis_elo(self):
        from plugins.elo import TennisEloRating
        return TennisEloRating()

    def test_multiple_matches(self, tennis_elo):
        # Simulate a tournament
        for _ in range(7):
            tennis_elo.update('Champion', 'Opponent')

        assert tennis_elo.get_rating('Champion') > 1600


class TestEPLEloMethods:
    """More tests for EPLEloRating."""

    @pytest.fixture
    def epl_elo(self):
        from plugins.elo import EPLEloRating
        return EPLEloRating()

    def test_predict_3way_sums_to_one(self, epl_elo):
        probs = epl_elo.predict_3way('Arsenal', 'Chelsea')
        total = probs['home'] + probs['draw'] + probs['away']
        assert abs(total - 1.0) < 0.01


class TestLigue1EloMethods:
    """More tests for Ligue1EloRating."""

    @pytest.fixture
    def ligue1_elo(self):
        from plugins.elo import Ligue1EloRating
        return Ligue1EloRating()

    def test_predict_probs_returns_dict(self, ligue1_elo):
        probs = ligue1_elo.predict_probs('PSG', 'Lyon')
        # Returns dict with 'home', 'draw', 'away' keys
        assert 'home' in probs
        assert 'draw' in probs
        assert 'away' in probs


class TestDataValidationMethods:
    """More tests for data_validation."""

    def test_report_sport(self):
        from data_validation import DataValidationReport
        report = DataValidationReport('nhl')
        assert report.sport == 'nhl'

    def test_report_stats_dict(self):
        from data_validation import DataValidationReport
        report = DataValidationReport('test')
        report.add_stat('games', 100)
        report.add_stat('teams', 30)
        assert len(report.stats) == 2


class TestDBLoaderMethods:
    """More tests for db_loader."""

    def test_import(self):
        from db_loader import NHLDatabaseLoader
        assert NHLDatabaseLoader is not None


class TestLiftGainMethods:
    """More tests for lift_gain_analysis."""

    def test_import(self):
        import lift_gain_analysis
        assert lift_gain_analysis is not None


class TestBetLoaderMethods:
    """More tests for bet_loader."""

    def test_import(self):
        from bet_loader import BetLoader
        assert BetLoader is not None


class TestBetTrackerMethods:
    """More tests for bet_tracker."""

    def test_create_bets_table(self):
        from bet_tracker import create_bets_table
        assert create_bets_table is not None


class TestKalshiMarketsMethods:
    """More tests for kalshi_markets."""

    def test_import(self):
        from kalshi_markets import KalshiAPI
        assert KalshiAPI is not None
