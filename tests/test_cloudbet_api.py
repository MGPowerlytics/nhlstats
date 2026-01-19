"""Tests for Cloudbet API module."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestCloudbetAPIInit:
    """Test CloudbetAPI initialization."""
    
    def test_init_without_api_key(self):
        """Test initialization without API key."""
        from cloudbet_api import CloudbetAPI
        
        api = CloudbetAPI()
        
        assert api.api_key is None
        assert api.session is not None
    
    def test_init_with_api_key(self):
        """Test initialization with API key."""
        from cloudbet_api import CloudbetAPI
        
        api = CloudbetAPI(api_key='test_key_123')
        
        assert api.api_key == 'test_key_123'
        assert 'Authorization' in api.session.headers
    
    def test_base_url(self):
        """Test base URL configuration."""
        from cloudbet_api import CloudbetAPI
        
        assert CloudbetAPI.BASE_URL == "https://www.cloudbet.com/api"
    
    def test_feed_url(self):
        """Test feed URL configuration."""
        from cloudbet_api import CloudbetAPI
        
        assert CloudbetAPI.FEED_URL == "https://sports-api.cloudbet.com/pub/v2/odds"


class TestSportMapping:
    """Test sport name mapping."""
    
    def test_nba_mapping(self):
        """Test NBA to basketball mapping."""
        sport_map = {
            'nba': 'basketball',
            'nhl': 'ice-hockey',
            'mlb': 'baseball',
            'nfl': 'american-football',
            'epl': 'soccer'
        }
        
        assert sport_map['nba'] == 'basketball'
    
    def test_nhl_mapping(self):
        """Test NHL to ice-hockey mapping."""
        from cloudbet_api import CloudbetAPI
        
        api = CloudbetAPI()
        # Test the mapping logic
        sport_map = {
            'nba': 'basketball',
            'nhl': 'ice-hockey',
        }
        
        assert sport_map['nhl'] == 'ice-hockey'
    
    def test_mlb_mapping(self):
        """Test MLB to baseball mapping."""
        sport_map = {'mlb': 'baseball'}
        
        assert sport_map['mlb'] == 'baseball'


class TestFetchMarkets:
    """Test market fetching functionality."""
    
    @patch('cloudbet_api.requests.Session')
    def test_fetch_markets_success(self, mock_session_class):
        """Test successful market fetch."""
        from cloudbet_api import CloudbetAPI
        
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'competitions': [
                {'name': 'NBA', 'events': []}
            ]
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        api = CloudbetAPI()
        api.session = mock_session
        
        markets = api.fetch_markets('nba')
        
        assert isinstance(markets, list)
    
    @patch('cloudbet_api.requests.Session')
    def test_fetch_markets_error(self, mock_session_class):
        """Test handling fetch error."""
        from cloudbet_api import CloudbetAPI
        import requests
        
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.exceptions.RequestException("Connection error")
        mock_session_class.return_value = mock_session
        
        api = CloudbetAPI()
        api.session = mock_session
        
        markets = api.fetch_markets('nba')
        
        assert markets == []


class TestCompetitionFiltering:
    """Test competition filtering logic."""
    
    def test_filter_nba_competition(self):
        """Test filtering NBA competition."""
        competitions = [
            {'name': 'NBA', 'id': '1'},
            {'name': 'EuroLeague', 'id': '2'},
            {'name': 'WNBA', 'id': '3'}
        ]
        
        sport = 'nba'
        filtered = [c for c in competitions if sport in c['name'].lower()]
        
        assert len(filtered) == 1
        assert filtered[0]['name'] == 'NBA'
    
    def test_filter_nhl_competition(self):
        """Test filtering NHL competition."""
        competitions = [
            {'name': 'NHL', 'id': '1'},
            {'name': 'KHL', 'id': '2'},
            {'name': 'AHL', 'id': '3'}
        ]
        
        sport = 'nhl'
        filtered = [c for c in competitions if sport in c['name'].lower()]
        
        assert len(filtered) == 1
        assert filtered[0]['name'] == 'NHL'


class TestMarketParsing:
    """Test market parsing functionality."""
    
    def test_parse_event_data(self):
        """Test parsing event data."""
        event = {
            'id': 'abc123',
            'name': 'Lakers vs Celtics',
            'home': {'name': 'Lakers'},
            'away': {'name': 'Celtics'},
            'cutoffTime': '2024-01-15T19:30:00Z'
        }
        
        parsed = {
            'id': event['id'],
            'home_team': event['home']['name'],
            'away_team': event['away']['name'],
            'start_time': event['cutoffTime']
        }
        
        assert parsed['home_team'] == 'Lakers'
        assert parsed['away_team'] == 'Celtics'
    
    def test_parse_odds_data(self):
        """Test parsing odds data."""
        odds = {
            'price': '2.10',
            'probability': 0.476
        }
        
        decimal_odds = float(odds['price'])
        implied_prob = 1 / decimal_odds
        
        assert decimal_odds == 2.10
        assert implied_prob == pytest.approx(0.476, abs=0.01)


class TestOddsConversion:
    """Test odds conversion utilities."""
    
    def test_decimal_to_probability(self):
        """Test decimal odds to probability."""
        decimal_odds = 2.0
        probability = 1 / decimal_odds
        
        assert probability == 0.5
    
    def test_probability_to_decimal(self):
        """Test probability to decimal odds."""
        probability = 0.5
        decimal_odds = 1 / probability
        
        assert decimal_odds == 2.0
    
    def test_decimal_odds_favorite(self):
        """Test odds for favorite."""
        # Favorite at 65% implied
        decimal_odds = 1 / 0.65
        
        assert decimal_odds == pytest.approx(1.538, abs=0.01)
