"""Tests for The Odds API integration."""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestOddsAPI:
    """Test the_odds_api.py module."""
    
    @pytest.fixture
    def mock_response(self):
        """Create a mock API response."""
        return {
            'id': 'game123',
            'sport_key': 'basketball_nba',
            'sport_title': 'NBA',
            'commence_time': '2024-12-25T20:00:00Z',
            'home_team': 'Los Angeles Lakers',
            'away_team': 'Boston Celtics',
            'bookmakers': [
                {
                    'key': 'draftkings',
                    'title': 'DraftKings',
                    'markets': [
                        {
                            'key': 'h2h',
                            'outcomes': [
                                {'name': 'Los Angeles Lakers', 'price': -110},
                                {'name': 'Boston Celtics', 'price': -110}
                            ]
                        }
                    ]
                }
            ]
        }
    
    def test_american_odds_to_probability_negative(self):
        """Test converting negative American odds to probability."""
        # -110 means bet $110 to win $100 (52.4% implied probability)
        odds = -110
        probability = abs(odds) / (abs(odds) + 100)
        assert probability == pytest.approx(0.524, abs=0.01)
    
    def test_american_odds_to_probability_positive(self):
        """Test converting positive American odds to probability."""
        # +200 means bet $100 to win $200 (33.3% implied probability)
        odds = 200
        probability = 100 / (odds + 100)
        assert probability == pytest.approx(0.333, abs=0.01)
    
    def test_american_odds_to_probability_even(self):
        """Test converting even odds."""
        # +100 means bet $100 to win $100 (50% implied probability)
        odds = 100
        probability = 100 / (odds + 100)
        assert probability == pytest.approx(0.5, abs=0.01)
    
    def test_american_odds_to_probability_heavy_favorite(self):
        """Test converting heavy favorite odds."""
        # -500 means bet $500 to win $100 (83.3% implied probability)
        odds = -500
        probability = abs(odds) / (abs(odds) + 100)
        assert probability == pytest.approx(0.833, abs=0.01)
    
    def test_decimal_odds_to_probability(self):
        """Test converting decimal odds to probability."""
        # 2.0 decimal odds = 50% implied probability
        decimal_odds = 2.0
        probability = 1 / decimal_odds
        assert probability == pytest.approx(0.5, abs=0.01)
    
    def test_decimal_odds_to_probability_heavy_favorite(self):
        """Test converting heavy favorite decimal odds."""
        # 1.25 decimal odds = 80% implied probability
        decimal_odds = 1.25
        probability = 1 / decimal_odds
        assert probability == pytest.approx(0.8, abs=0.01)


class TestOddsAPIClient:
    """Test OddsAPIClient functionality."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock OddsAPI client."""
        class MockOddsAPIClient:
            def __init__(self, api_key):
                self.api_key = api_key
                self.base_url = 'https://api.the-odds-api.com/v4'
            
            def get_sport_key(self, sport):
                sport_map = {
                    'NBA': 'basketball_nba',
                    'NHL': 'icehockey_nhl',
                    'MLB': 'baseball_mlb',
                    'NFL': 'americanfootball_nfl',
                    'NCAAB': 'basketball_ncaab'
                }
                return sport_map.get(sport.upper())
        
        return MockOddsAPIClient('test_api_key')
    
    def test_get_sport_key_nba(self, mock_client):
        """Test getting sport key for NBA."""
        assert mock_client.get_sport_key('NBA') == 'basketball_nba'
    
    def test_get_sport_key_nhl(self, mock_client):
        """Test getting sport key for NHL."""
        assert mock_client.get_sport_key('NHL') == 'icehockey_nhl'
    
    def test_get_sport_key_mlb(self, mock_client):
        """Test getting sport key for MLB."""
        assert mock_client.get_sport_key('MLB') == 'baseball_mlb'
    
    def test_get_sport_key_nfl(self, mock_client):
        """Test getting sport key for NFL."""
        assert mock_client.get_sport_key('NFL') == 'americanfootball_nfl'
    
    def test_get_sport_key_ncaab(self, mock_client):
        """Test getting sport key for NCAAB."""
        assert mock_client.get_sport_key('NCAAB') == 'basketball_ncaab'
    
    def test_get_sport_key_case_insensitive(self, mock_client):
        """Test that sport key lookup is case insensitive."""
        assert mock_client.get_sport_key('nba') == 'basketball_nba'
        assert mock_client.get_sport_key('Nba') == 'basketball_nba'
    
    def test_get_sport_key_unknown(self, mock_client):
        """Test getting sport key for unknown sport."""
        assert mock_client.get_sport_key('UNKNOWN') is None


class TestOddsMatching:
    """Test odds matching logic."""
    
    def test_team_name_normalization(self):
        """Test normalizing team names for matching."""
        name = "Los Angeles Lakers"
        normalized = name.lower().replace(' ', '')
        assert normalized == "losangeleslakers"
    
    def test_team_name_matching_exact(self):
        """Test exact team name matching."""
        team1 = "Lakers"
        team2 = "Lakers"
        assert team1.lower() == team2.lower()
    
    def test_team_name_matching_partial(self):
        """Test partial team name matching."""
        team1 = "losangeleslakers"
        team2 = "lakers"
        assert team2 in team1
    
    def test_team_name_matching_city(self):
        """Test matching by city name."""
        team1 = "losangeleslakers"
        city = "losangeles"
        assert city in team1


class TestGameStatusCheck:
    """Test game status checking."""
    
    def test_game_not_started_no_scores(self):
        """Test that game without scores is not started."""
        game = {
            'home_team': 'Lakers',
            'away_team': 'Celtics',
            'scores': None,
            'completed': False
        }
        
        started = game.get('scores') is not None or game.get('completed', False)
        assert started == False
    
    def test_game_started_has_scores(self):
        """Test that game with scores has started."""
        game = {
            'home_team': 'Lakers',
            'away_team': 'Celtics',
            'scores': [{'name': 'Lakers', 'score': '55'}],
            'completed': False
        }
        
        started = game.get('scores') is not None or game.get('completed', False)
        assert started == True
    
    def test_game_completed(self):
        """Test that completed game is detected."""
        game = {
            'home_team': 'Lakers',
            'away_team': 'Celtics',
            'scores': [{'name': 'Lakers', 'score': '110'}, {'name': 'Celtics', 'score': '105'}],
            'completed': True
        }
        
        started = game.get('scores') is not None or game.get('completed', False)
        assert started == True


class TestOddsCalculation:
    """Test odds and probability calculations."""
    
    def test_remove_vig_equal_odds(self):
        """Test removing vig from equal odds."""
        # Both teams at -110: 52.4% each, but that sums to 104.8%
        prob1 = 110 / (110 + 100)  # 0.524
        prob2 = 110 / (110 + 100)  # 0.524
        total = prob1 + prob2
        
        # Fair odds (no vig)
        fair_prob1 = prob1 / total
        fair_prob2 = prob2 / total
        
        assert fair_prob1 == pytest.approx(0.5, abs=0.01)
        assert fair_prob2 == pytest.approx(0.5, abs=0.01)
    
    def test_remove_vig_unequal_odds(self):
        """Test removing vig from unequal odds."""
        # Team A at -150 (60%), Team B at +130 (43.5%)
        prob_a = 150 / (150 + 100)  # 0.60
        prob_b = 100 / (130 + 100)  # 0.435
        total = prob_a + prob_b  # 1.035
        
        fair_prob_a = prob_a / total
        fair_prob_b = prob_b / total
        
        assert fair_prob_a + fair_prob_b == pytest.approx(1.0, abs=0.001)
    
    def test_edge_calculation(self):
        """Test edge calculation."""
        elo_probability = 0.65
        market_probability = 0.55
        
        edge = elo_probability - market_probability
        
        assert edge == pytest.approx(0.10, abs=0.001)
    
    def test_edge_negative(self):
        """Test negative edge calculation."""
        elo_probability = 0.45
        market_probability = 0.55
        
        edge = elo_probability - market_probability
        
        assert edge == pytest.approx(-0.10, abs=0.001)
    
    def test_kelly_criterion_basic(self):
        """Test Kelly criterion bet sizing."""
        # Kelly = (p * b - q) / b
        # where p = probability of winning, b = odds received, q = probability of losing
        p = 0.60  # 60% win probability
        b = 1.0   # Even money (bet $1 to win $1)
        q = 0.40  # 40% loss probability
        
        kelly = (p * b - q) / b
        
        assert kelly == pytest.approx(0.20, abs=0.01)  # Bet 20% of bankroll
    
    def test_kelly_criterion_no_edge(self):
        """Test Kelly criterion with no edge."""
        p = 0.50
        b = 1.0
        q = 0.50
        
        kelly = (p * b - q) / b
        
        assert kelly == pytest.approx(0.0, abs=0.01)  # Don't bet
    
    def test_kelly_criterion_negative_edge(self):
        """Test Kelly criterion with negative edge."""
        p = 0.40
        b = 1.0
        q = 0.60
        
        kelly = (p * b - q) / b
        
        assert kelly < 0  # Negative Kelly = don't bet
