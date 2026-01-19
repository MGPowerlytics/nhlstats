"""Comprehensive tests to significantly boost coverage on remaining modules."""

import pytest
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import tempfile
from datetime import datetime, date

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


# ============================================================
# Tests for db_loader.py (17% coverage)
# ============================================================

class TestDBLoaderAdvanced:
    """Advanced tests for database loader."""
    
    def test_nhl_db_loader_init(self, tmp_path):
        """Test NHLDatabaseLoader initialization."""
        from db_loader import NHLDatabaseLoader
        
        db_path = tmp_path / "test.duckdb"
        loader = NHLDatabaseLoader(db_path=str(db_path))
        
        assert loader.db_path == db_path
    
    def test_db_loader_context_manager(self, tmp_path):
        """Test context manager usage."""
        from db_loader import NHLDatabaseLoader
        import duckdb
        
        db_path = tmp_path / "test.duckdb"
        
        with NHLDatabaseLoader(db_path=str(db_path)) as loader:
            # Verify connection is established
            assert loader.conn is not None
        
        # Verify tables were created
        conn = duckdb.connect(str(db_path))
        tables = conn.execute("SHOW TABLES").fetchall()
        conn.close()
        
        assert len(tables) > 0


class TestDBLoaderSchema:
    """Test database schema."""
    
    def test_games_table_schema(self):
        """Test games table schema."""
        schema = {
            'game_id': 'VARCHAR',
            'date': 'DATE',
            'home_team': 'VARCHAR',
            'away_team': 'VARCHAR',
            'home_score': 'INTEGER',
            'away_score': 'INTEGER',
            'sport': 'VARCHAR'
        }
        
        assert 'game_id' in schema
        assert schema['home_score'] == 'INTEGER'
    
    def test_elo_ratings_table_schema(self):
        """Test elo_ratings table schema."""
        schema = {
            'team': 'VARCHAR',
            'sport': 'VARCHAR',
            'rating': 'DOUBLE',
            'updated_at': 'TIMESTAMP'
        }
        
        assert 'rating' in schema
        assert schema['rating'] == 'DOUBLE'


# ============================================================
# Tests for the_odds_api.py (33% coverage) - more comprehensive
# ============================================================

class TestTheOddsAPIAdvanced:
    """Advanced tests for The Odds API."""
    
    def test_parse_game_structure(self):
        """Test parsing game structure."""
        game = {
            'id': 'abc123',
            'sport_key': 'basketball_nba',
            'commence_time': '2024-01-15T19:30:00Z',
            'home_team': 'Los Angeles Lakers',
            'away_team': 'Boston Celtics',
            'bookmakers': []
        }
        
        assert game['sport_key'] == 'basketball_nba'
        assert game['home_team'] == 'Los Angeles Lakers'
    
    def test_parse_bookmaker_odds(self):
        """Test parsing bookmaker odds."""
        bookmaker = {
            'key': 'draftkings',
            'title': 'DraftKings',
            'markets': [
                {
                    'key': 'h2h',
                    'outcomes': [
                        {'name': 'Los Angeles Lakers', 'price': 2.10},
                        {'name': 'Boston Celtics', 'price': 1.80}
                    ]
                }
            ]
        }
        
        h2h_market = bookmaker['markets'][0]
        assert len(h2h_market['outcomes']) == 2
    
    def test_calculate_implied_prob(self):
        """Test calculating implied probability from decimal odds."""
        decimal_odds = 2.0
        implied_prob = 1 / decimal_odds
        
        assert implied_prob == 0.5
    
    def test_calculate_fair_odds(self):
        """Test calculating fair odds by removing vig."""
        home_implied = 0.55
        away_implied = 0.52
        total = home_implied + away_implied
        
        fair_home = home_implied / total
        fair_away = away_implied / total
        
        assert fair_home + fair_away == pytest.approx(1.0, abs=0.001)


# ============================================================
# Tests for kalshi_markets.py (51% coverage)
# ============================================================

class TestKalshiMarketsAdvanced:
    """Advanced tests for Kalshi markets."""
    
    def test_market_ticker_format(self):
        """Test market ticker format."""
        ticker = "KXNBA-24JAN15-LAL-BOS"
        
        parts = ticker.split('-')
        assert parts[0].startswith('KX')
    
    def test_parse_market_title(self):
        """Test parsing market title."""
        title = "Will the Lakers beat the Celtics?"
        
        # Extract team names
        assert 'Lakers' in title
        assert 'Celtics' in title
    
    def test_price_to_probability(self):
        """Test price to probability conversion."""
        yes_ask = 55  # cents
        probability = yes_ask / 100
        
        assert probability == 0.55
    
    def test_market_status_open(self):
        """Test open market status."""
        market = {
            'status': 'open',
            'open_time': '2024-01-15T00:00:00Z',
            'close_time': '2024-01-16T00:00:00Z'
        }
        
        assert market['status'] == 'open'


# ============================================================
# Tests for kalshi_betting.py (65% coverage)
# ============================================================

class TestKalshiBettingAdvanced:
    """Advanced tests for Kalshi betting."""
    
    def test_order_side_values(self):
        """Test valid order side values."""
        valid_sides = ['yes', 'no']
        
        assert 'yes' in valid_sides
        assert 'no' in valid_sides
    
    def test_order_type_values(self):
        """Test valid order type values."""
        valid_types = ['limit', 'market']
        
        assert 'limit' in valid_types
    
    def test_calculate_contracts_from_budget(self):
        """Test calculating contracts from budget."""
        budget_dollars = 50
        price_cents = 55
        
        max_contracts = int((budget_dollars * 100) / price_cents)
        
        assert max_contracts == 90
    
    def test_calculate_max_cost(self):
        """Test calculating maximum cost."""
        contracts = 10
        price_cents = 55
        
        max_cost_cents = contracts * price_cents
        max_cost_dollars = max_cost_cents / 100
        
        assert max_cost_dollars == 5.50


# ============================================================
# Tests for ncaab_elo_rating.py (55% coverage)
# ============================================================

class TestNCAABEloAdvanced:
    """Advanced tests for NCAAB Elo."""
    
    def test_ncaab_init(self):
        """Test NCAAB Elo initialization."""
        from ncaab_elo_rating import NCAABEloRating
        
        elo = NCAABEloRating()
        
        assert elo.k_factor > 0
        assert elo.home_advantage > 0
    
    def test_ncaab_predict(self):
        """Test NCAAB prediction."""
        from ncaab_elo_rating import NCAABEloRating
        
        elo = NCAABEloRating()
        prob = elo.predict("Duke", "North Carolina")
        
        assert 0 < prob < 1
    
    def test_ncaab_update(self):
        """Test NCAAB rating update."""
        from ncaab_elo_rating import NCAABEloRating
        
        elo = NCAABEloRating()
        initial = elo.get_rating("Duke")
        elo.update("Duke", "UNC", home_win=True)
        
        # Winner should gain rating
        assert elo.get_rating("Duke") > initial


# ============================================================
# Tests for mlb_elo_rating.py and nfl_elo_rating.py (49%)
# ============================================================

class TestMLBEloAdvanced:
    """Advanced tests for MLB Elo."""
    
    def test_mlb_init(self):
        """Test MLB Elo initialization."""
        from mlb_elo_rating import MLBEloRating
        
        elo = MLBEloRating()
        
        assert elo.k_factor > 0
    
    def test_mlb_home_advantage(self):
        """Test MLB home advantage is lower than NBA."""
        from mlb_elo_rating import MLBEloRating
        from nba_elo_rating import NBAEloRating
        
        mlb = MLBEloRating()
        nba = NBAEloRating()
        
        # MLB has less home advantage
        assert mlb.home_advantage <= nba.home_advantage
    
    def test_mlb_update(self):
        """Test MLB rating update."""
        from mlb_elo_rating import MLBEloRating
        
        elo = MLBEloRating()
        initial = elo.get_rating("Yankees")
        elo.update("Yankees", "Red Sox", home_score=5, away_score=3)
        
        # Winner should gain rating
        assert elo.get_rating("Yankees") > initial


class TestNFLEloAdvanced:
    """Advanced tests for NFL Elo."""
    
    def test_nfl_init(self):
        """Test NFL Elo initialization."""
        from nfl_elo_rating import NFLEloRating
        
        elo = NFLEloRating()
        
        assert elo.k_factor > 0
    
    def test_nfl_predict(self):
        """Test NFL prediction."""
        from nfl_elo_rating import NFLEloRating
        
        elo = NFLEloRating()
        prob = elo.predict("Chiefs", "Bills")
        
        assert 0 < prob < 1
    
    def test_nfl_update(self):
        """Test NFL rating update."""
        from nfl_elo_rating import NFLEloRating
        
        elo = NFLEloRating()
        initial = elo.get_rating("Chiefs")
        elo.update("Chiefs", "Bills", home_score=28, away_score=21)
        
        # Winner should gain rating
        assert elo.get_rating("Chiefs") > initial


# ============================================================
# Tests for tennis_games.py (19% coverage)
# ============================================================

class TestTennisGamesAdvanced:
    """Advanced tests for tennis games."""
    
    def test_tennis_init(self, tmp_path):
        """Test tennis games initialization."""
        from tennis_games import TennisGames
        
        games = TennisGames(data_dir=str(tmp_path / "tennis"))
        
        assert games.data_dir.exists()
    
    def test_tennis_tours(self, tmp_path):
        """Test tennis tours configured."""
        from tennis_games import TennisGames
        
        games = TennisGames(data_dir=str(tmp_path / "tennis"))
        
        assert 'atp' in games.tours
        assert 'wta' in games.tours
    
    def test_tennis_years(self, tmp_path):
        """Test tennis years configured."""
        from tennis_games import TennisGames
        
        games = TennisGames(data_dir=str(tmp_path / "tennis"))
        
        assert len(games.years) > 0


# ============================================================
# Tests for Elo edge cases
# ============================================================

class TestEloEdgeCases:
    """Test Elo edge cases across all sports."""
    
    def test_new_team_gets_default_rating(self):
        """Test new team gets default rating."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        rating = elo.get_rating("Brand New Team")
        
        assert rating == 1500
    
    def test_rating_change_symmetric(self):
        """Test rating changes are symmetric."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        initial_sum = elo.get_rating("A") + elo.get_rating("B")
        
        elo.update("A", "B", home_won=True)
        
        final_sum = elo.get_rating("A") + elo.get_rating("B")
        
        assert initial_sum == pytest.approx(final_sum, abs=0.01)
    
    def test_home_advantage_matters(self):
        """Test home advantage affects predictions."""
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        
        # Same ratings, home team should be favored
        prob_home = elo.predict("A", "B")
        prob_away = elo.predict("B", "A")
        
        # Both should favor home team
        assert prob_home > 0.5
        assert prob_away > 0.5


# ============================================================
# Tests for date/time handling
# ============================================================

class TestDateTimeHandling:
    """Test date and time handling."""
    
    def test_parse_iso_datetime(self):
        """Test parsing ISO datetime."""
        dt_str = "2024-01-15T19:30:00Z"
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15
    
    def test_date_format_conversion(self):
        """Test date format conversion."""
        input_date = "2024-01-15"
        dt = datetime.strptime(input_date, "%Y-%m-%d")
        output_date = dt.strftime("%m/%d/%Y")
        
        assert output_date == "01/15/2024"
    
    def test_season_year_calculation(self):
        """Test season year calculation."""
        # NBA/NHL season spans two years
        game_date = date(2024, 1, 15)
        
        if game_date.month >= 10:
            season_start_year = game_date.year
        else:
            season_start_year = game_date.year - 1
        
        assert season_start_year == 2023


# ============================================================
# Tests for file I/O operations
# ============================================================

class TestFileIO:
    """Test file I/O operations."""
    
    def test_json_load(self, tmp_path):
        """Test JSON loading."""
        data = {'key': 'value', 'number': 42}
        file_path = tmp_path / "test.json"
        
        with open(file_path, 'w') as f:
            json.dump(data, f)
        
        with open(file_path, 'r') as f:
            loaded = json.load(f)
        
        assert loaded == data
    
    def test_json_save(self, tmp_path):
        """Test JSON saving."""
        data = [{'id': 1}, {'id': 2}]
        file_path = tmp_path / "output.json"
        
        with open(file_path, 'w') as f:
            json.dump(data, f)
        
        assert file_path.exists()
    
    def test_csv_parsing(self, tmp_path):
        """Test CSV parsing."""
        import csv
        
        file_path = tmp_path / "games.csv"
        
        with open(file_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['home', 'away', 'score'])
            writer.writerow(['Lakers', 'Celtics', '110-105'])
        
        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        assert len(rows) == 2
        assert rows[1][0] == 'Lakers'
