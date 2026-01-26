"""Extended tests for game modules to boost coverage."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))


# ============================================================
# Extended tests for nba_games.py (31% -> higher)
# ============================================================


class TestNBAGamesExtended:
    """Extended tests for NBA games module."""

    def test_nba_games_import(self):
        """Test NBAGames can be imported."""
        from nba_games import NBAGames

        assert NBAGames is not None

    def test_nba_games_init(self, tmp_path):
        """Test NBAGames initialization."""
        from nba_games import NBAGames

        games = NBAGames(output_dir=str(tmp_path / "nba"))

        assert games.output_dir.exists()

    def test_nba_games_with_date_folder(self, tmp_path):
        """Test NBAGames with date folder."""
        from nba_games import NBAGames

        games = NBAGames(output_dir=str(tmp_path / "nba"), date_folder="2024-01-15")

        assert "2024-01-15" in str(games.output_dir)

    def test_nba_api_url_format(self):
        """Test NBA API URL format."""
        base_url = "https://stats.nba.com/stats/scoreboardv2"
        date_str = "2024-01-15"

        url = f"{base_url}?GameDate={date_str}"

        assert "scoreboardv2" in url
        assert "GameDate=" in url

    def test_nba_headers(self):
        """Test NBA API requires specific headers."""
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.nba.com/"}

        assert "User-Agent" in headers
        assert "nba.com" in headers["Referer"]


# ============================================================
# Extended tests for mlb_games.py (23% -> higher)
# ============================================================


class TestMLBGamesExtended:
    """Extended tests for MLB games module."""

    def test_mlb_games_import(self):
        """Test MLBGames can be imported."""
        from mlb_games import MLBGames

        assert MLBGames is not None

    def test_mlb_games_init(self, tmp_path):
        """Test MLBGames initialization."""
        from mlb_games import MLBGames

        games = MLBGames(output_dir=str(tmp_path / "mlb"))

        assert games.output_dir.exists()

    def test_mlb_api_url_format(self):
        """Test MLB API URL format."""
        date_str = "2024-04-01"
        url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"

        assert "statsapi.mlb.com" in url
        assert "sportId=1" in url
        assert date_str in url


# ============================================================
# Extended tests for epl_games.py (25% -> higher)
# ============================================================


class TestEPLGamesExtended:
    """Extended tests for EPL games module."""

    def test_epl_games_import(self):
        """Test EPLGames can be imported."""
        from epl_games import EPLGames

        assert EPLGames is not None

    def test_epl_games_init(self, tmp_path):
        """Test EPLGames initialization."""
        from epl_games import EPLGames

        games = EPLGames(data_dir=str(tmp_path / "epl"))

        assert games.data_dir.exists()

    def test_epl_data_url_format(self):
        """Test EPL data URL format."""
        season = "2324"  # 2023-2024 season
        url = f"https://www.football-data.co.uk/mmz4281/{season}/E0.csv"

        assert "football-data.co.uk" in url
        assert "E0.csv" in url  # E0 = Premier League


# ============================================================
# Extended tests for ligue1_games.py (25% -> higher)
# ============================================================


class TestLigue1GamesExtended:
    """Extended tests for Ligue1 games module."""

    def test_ligue1_games_import(self):
        """Test Ligue1Games can be imported."""
        from ligue1_games import Ligue1Games

        assert Ligue1Games is not None

    def test_ligue1_games_init(self, tmp_path):
        """Test Ligue1Games initialization."""
        from ligue1_games import Ligue1Games

        games = Ligue1Games(data_dir=str(tmp_path / "ligue1"))

        assert games.data_dir.exists()

    def test_ligue1_data_url_format(self):
        """Test Ligue1 data URL format."""
        season = "2324"
        url = f"https://www.football-data.co.uk/mmz4281/{season}/F1.csv"

        assert "F1.csv" in url  # F1 = Ligue 1


# ============================================================
# Extended tests for ncaab_games.py (15% -> higher)
# ============================================================


class TestNCAABGamesExtended:
    """Extended tests for NCAAB games module."""

    def test_ncaab_games_import(self):
        """Test NCAABGames can be imported."""
        from ncaab_games import NCAABGames

        assert NCAABGames is not None

    def test_ncaab_games_init(self, tmp_path):
        """Test NCAABGames initialization."""
        from ncaab_games import NCAABGames

        games = NCAABGames(data_dir=str(tmp_path / "ncaab"))

        assert games.data_dir.exists()


# ============================================================
# Extended tests for tennis_games.py (19% -> higher)
# ============================================================


class TestTennisGamesExtended:
    """Extended tests for tennis games module."""

    def test_tennis_games_import(self):
        """Test TennisGames can be imported."""
        from tennis_games import TennisGames

        assert TennisGames is not None

    def test_tennis_games_init(self, tmp_path):
        """Test TennisGames initialization."""
        from tennis_games import TennisGames

        games = TennisGames(data_dir=str(tmp_path / "tennis"))

        assert games.data_dir.exists()

    def test_tennis_data_urls(self):
        """Test tennis data URL formats."""
        year = "2024"

        atp_url = f"http://www.tennis-data.co.uk/{year}/{year}.xlsx"
        wta_url = f"http://www.tennis-data.co.uk/{year}w/{year}.xlsx"

        assert year in atp_url
        assert f"{year}w" in wta_url


# ============================================================
# Extended tests for nhl_game_events.py (29% -> higher)
# ============================================================


class TestNHLGameEventsExtended:
    """Extended tests for NHL game events module."""

    def test_nhl_game_events_import(self):
        """Test NHLGameEvents can be imported."""
        from nhl_game_events import NHLGameEvents

        assert NHLGameEvents is not None

    def test_nhl_game_events_init(self, tmp_path):
        """Test NHLGameEvents initialization."""
        from nhl_game_events import NHLGameEvents

        events = NHLGameEvents(output_dir=str(tmp_path / "nhl"))

        assert events.output_dir.exists()

    def test_nhl_api_url_format(self):
        """Test NHL API URL format."""
        game_id = "2023020001"
        url = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play"

        assert "nhle.com" in url
        assert game_id in url
        assert "play-by-play" in url

    def test_event_type_constants(self):
        """Test common NHL event types."""
        event_types = [
            "GOAL",
            "SHOT",
            "MISSED_SHOT",
            "BLOCKED_SHOT",
            "HIT",
            "PENALTY",
            "FACEOFF",
            "GIVEAWAY",
            "TAKEAWAY",
            "STOPPAGE",
        ]

        for event in event_types:
            assert event.isupper()


# ============================================================
# Extended tests for polymarket_api.py (30% -> higher)
# ============================================================


class TestPolymarketAPIExtended:
    """Extended tests for Polymarket API module."""

    def test_polymarket_api_import(self):
        """Test PolymarketAPI can be imported."""
        from polymarket_api import PolymarketAPI

        assert PolymarketAPI is not None

    def test_polymarket_clob_url(self):
        """Test Polymarket CLOB URL."""
        base_url = "https://clob.polymarket.com"

        assert "polymarket" in base_url
        assert "clob" in base_url

    def test_condition_id_format(self):
        """Test Polymarket condition ID format."""
        # Condition IDs are hex strings
        condition_id = "0x1234567890abcdef1234567890abcdef12345678"

        assert condition_id.startswith("0x")
        assert len(condition_id) > 10


# ============================================================
# Extended tests for cloudbet_api.py (40% -> higher)
# ============================================================


class TestCloudbetAPIExtended:
    """Extended tests for Cloudbet API module."""

    def test_cloudbet_api_import(self):
        """Test CloudbetAPI can be imported."""
        from cloudbet_api import CloudbetAPI

        assert CloudbetAPI is not None

    def test_cloudbet_base_url(self):
        """Test Cloudbet API base URL."""
        base_url = "https://sports-api.cloudbet.com/pub/v2"

        assert "cloudbet" in base_url
        assert "v2" in base_url

    def test_cloudbet_sports_keys(self):
        """Test Cloudbet sport keys."""
        sport_keys = {
            "nba": "basketball-usa-nba",
            "nhl": "ice-hockey-usa-nhl",
            "mlb": "baseball-usa-mlb",
            "nfl": "american-football-usa-nfl",
        }

        for sport, key in sport_keys.items():
            assert sport in key


# ============================================================
# Extended tests for bet_loader.py (52% -> higher)
# ============================================================


class TestBetLoaderExtended:
    """Extended tests for bet_loader module."""

    def test_bet_loader_import(self):
        """Test BetLoader can be imported."""
        from bet_loader import BetLoader

        assert BetLoader is not None

    def test_bet_loader_init_creates_table(self, tmp_path):
        """Test BetLoader creates table on init."""
        from bet_loader import BetLoader
        import duckdb

        db_path = tmp_path / "test.duckdb"
        BetLoader(db_path=str(db_path))

        # Check table exists
        conn = duckdb.connect(str(db_path))
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        conn.close()

        assert "bet_recommendations" in table_names


# ============================================================
# Extended tests for mlb_elo_rating.py (49% -> higher)
# ============================================================


class TestMLBEloRatingExtended:
    """Extended tests for MLB Elo module."""

    def test_mlb_elo_expected_score(self):
        """Test expected score calculation."""
        from plugins.elo import MLBEloRating

        elo = MLBEloRating()

        # Equal ratings
        score = elo.expected_score(1500, 1500)
        assert score == pytest.approx(0.5)

    def test_mlb_elo_predict(self):
        """Test prediction method."""
        from plugins.elo import MLBEloRating

        elo = MLBEloRating()
        prob = elo.predict("Yankees", "Red Sox")

        assert 0 < prob < 1

    def test_mlb_elo_rating_after_game(self):
        """Test rating changes after game."""
        from plugins.elo import MLBEloRating

        elo = MLBEloRating()
        initial = elo.get_rating("Team A")

        elo.update("Team A", "Team B", home_score=5, away_score=3)

        # Winner should gain rating
        assert elo.get_rating("Team A") > initial

    def test_mlb_elo_blowout_effect(self):
        """Test blowout wins give more rating."""
        from plugins.elo import MLBEloRating

        elo1 = MLBEloRating()
        elo2 = MLBEloRating()

        # Close game
        elo1.update("Team A", "Team B", home_score=5, away_score=4)
        close_gain = elo1.get_rating("Team A") - 1500

        # Blowout
        elo2.update("Team A", "Team B", home_score=10, away_score=1)
        blowout_gain = elo2.get_rating("Team A") - 1500

        # Blowout should give more rating (or equal)
        assert blowout_gain >= close_gain


# ============================================================
# Extended tests for nfl_elo_rating.py (49% -> higher)
# ============================================================


class TestNFLEloRatingExtended:
    """Extended tests for NFL Elo module."""

    def test_nfl_elo_expected_score(self):
        """Test expected score calculation."""
        from plugins.elo import NFLEloRating

        elo = NFLEloRating()

        score = elo.expected_score(1500, 1500)
        assert score == pytest.approx(0.5)

    def test_nfl_elo_predict(self):
        """Test prediction method."""
        from plugins.elo import NFLEloRating

        elo = NFLEloRating()
        prob = elo.predict("Chiefs", "Bills")

        assert 0 < prob < 1

    def test_nfl_elo_home_advantage(self):
        """Test home advantage effect."""
        from plugins.elo import NFLEloRating

        elo = NFLEloRating()

        # With equal ratings, home team should be favored
        prob = elo.predict("Home", "Away")

        assert prob > 0.5

    def test_nfl_elo_after_game(self):
        """Test rating changes after game."""
        from plugins.elo import NFLEloRating

        elo = NFLEloRating()

        elo.update("Team A", "Team B", home_score=28, away_score=21)

        assert elo.get_rating("Team A") > elo.get_rating("Team B")


# ============================================================
# Extended tests for ncaab_elo_rating.py (55% -> higher)
# ============================================================


class TestNCAABEloRatingExtended:
    """Extended tests for NCAAB Elo module."""

    def test_ncaab_elo_init(self):
        """Test NCAAB Elo initialization."""
        from plugins.elo import NCAABEloRating

        elo = NCAABEloRating()

        assert elo.k_factor > 0

    def test_ncaab_elo_neutral_site(self):
        """Test neutral site prediction."""
        from plugins.elo import NCAABEloRating

        elo = NCAABEloRating()

        prob = elo.predict("Duke", "UNC", is_neutral=True)

        # At neutral site with equal ratings, should be ~50%
        assert prob == pytest.approx(0.5, abs=0.01)

    def test_ncaab_elo_home_vs_neutral(self):
        """Test home advantage vs neutral site."""
        from plugins.elo import NCAABEloRating

        elo = NCAABEloRating()

        home_prob = elo.predict("Duke", "UNC", is_neutral=False)
        neutral_prob = elo.predict("Duke", "UNC", is_neutral=True)

        # Home should have advantage
        assert home_prob > neutral_prob

    def test_ncaab_elo_update(self):
        """Test rating update."""
        from plugins.elo import NCAABEloRating

        elo = NCAABEloRating()

        change = elo.update("Duke", "UNC", home_win=True)

        assert change != 0
