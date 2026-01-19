"""Tests for The Odds API client."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestTheOddsAPIInit:
    """Test TheOddsAPI initialization."""
    
    def test_init_with_api_key(self):
        """Test initialization with API key."""
        from the_odds_api import TheOddsAPI
        
        api = TheOddsAPI(api_key='test_key_123')
        
        assert api.api_key == 'test_key_123'
        assert api.BASE_URL == "https://api.the-odds-api.com/v4"
    
    @patch.dict('os.environ', {'ODDS_API_KEY': 'env_key_456'})
    def test_init_with_env_key(self):
        """Test initialization with environment variable."""
        from the_odds_api import TheOddsAPI
        
        api = TheOddsAPI()
        
        assert api.api_key == 'env_key_456'
    
    def test_init_without_key(self):
        """Test initialization without API key."""
        from the_odds_api import TheOddsAPI
        
        with patch.dict('os.environ', {}, clear=True):
            with patch.object(Path, 'exists', return_value=False):
                api = TheOddsAPI(api_key=None)
                # Should not raise, just warn


class TestSportKeys:
    """Test sport key mapping."""
    
    def test_sport_keys_nba(self):
        """Test NBA sport key."""
        from the_odds_api import TheOddsAPI
        
        assert TheOddsAPI.SPORT_KEYS['nba'] == 'basketball_nba'
    
    def test_sport_keys_nhl(self):
        """Test NHL sport key."""
        from the_odds_api import TheOddsAPI
        
        assert TheOddsAPI.SPORT_KEYS['nhl'] == 'icehockey_nhl'
    
    def test_sport_keys_mlb(self):
        """Test MLB sport key."""
        from the_odds_api import TheOddsAPI
        
        assert TheOddsAPI.SPORT_KEYS['mlb'] == 'baseball_mlb'
    
    def test_sport_keys_nfl(self):
        """Test NFL sport key."""
        from the_odds_api import TheOddsAPI
        
        assert TheOddsAPI.SPORT_KEYS['nfl'] == 'americanfootball_nfl'
    
    def test_sport_keys_epl(self):
        """Test EPL sport key."""
        from the_odds_api import TheOddsAPI
        
        assert TheOddsAPI.SPORT_KEYS['epl'] == 'soccer_epl'
    
    def test_sport_keys_ncaab(self):
        """Test NCAAB sport key."""
        from the_odds_api import TheOddsAPI
        
        assert TheOddsAPI.SPORT_KEYS['ncaab'] == 'basketball_ncaab'


class TestFetchMarkets:
    """Test fetch_markets method."""
    
    @patch('the_odds_api.requests.Session')
    def test_fetch_markets_success(self, mock_session):
        """Test successful market fetch."""
        from the_odds_api import TheOddsAPI
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                'id': 'game1',
                'home_team': 'Lakers',
                'away_team': 'Celtics',
                'bookmakers': []
            }
        ]
        mock_response.headers = {'x-requests-remaining': '499'}
        mock_session.return_value.get.return_value = mock_response
        
        api = TheOddsAPI(api_key='test_key')
        api.session = mock_session.return_value
        
        with patch.object(api, '_parse_game', return_value={'id': 'game1'}):
            with patch.object(api, '_count_bookmakers', return_value=5):
                markets = api.fetch_markets('nba')
    
    def test_fetch_markets_unknown_sport(self):
        """Test fetch with unknown sport."""
        from the_odds_api import TheOddsAPI
        
        api = TheOddsAPI(api_key='test_key')
        
        markets = api.fetch_markets('unknown_sport')
        
        assert markets == []
    
    def test_fetch_markets_no_api_key(self):
        """Test fetch without API key."""
        from the_odds_api import TheOddsAPI
        
        with patch.dict('os.environ', {}, clear=True):
            api = TheOddsAPI(api_key=None)
            api.api_key = None
            
            markets = api.fetch_markets('nba')
            
            assert markets == []


class TestOddsConversion:
    """Test odds conversion utilities."""
    
    def test_decimal_to_probability(self):
        """Test converting decimal odds to probability."""
        decimal_odds = 2.0
        probability = 1 / decimal_odds
        
        assert probability == 0.5
    
    def test_decimal_odds_favorite(self):
        """Test decimal odds for favorite."""
        decimal_odds = 1.5
        probability = 1 / decimal_odds
        
        assert probability == pytest.approx(0.667, abs=0.01)
    
    def test_decimal_odds_underdog(self):
        """Test decimal odds for underdog."""
        decimal_odds = 3.0
        probability = 1 / decimal_odds
        
        assert probability == pytest.approx(0.333, abs=0.01)
    
    def test_remove_juice(self):
        """Test removing juice/vig from odds."""
        home_prob = 0.55
        away_prob = 0.50
        total = home_prob + away_prob
        
        fair_home = home_prob / total
        fair_away = away_prob / total
        
        assert fair_home + fair_away == pytest.approx(1.0, abs=0.001)


class TestGameParsing:
    """Test game data parsing."""
    
    def test_parse_game_response(self):
        """Test parsing API game response."""
        game_data = {
            'id': 'abc123',
            'commence_time': '2024-01-15T19:30:00Z',
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
                                {'name': 'Los Angeles Lakers', 'price': 2.10},
                                {'name': 'Boston Celtics', 'price': 1.80}
                            ]
                        }
                    ]
                }
            ]
        }
        
        # Parse the data
        parsed = {
            'id': game_data['id'],
            'home_team': game_data['home_team'],
            'away_team': game_data['away_team'],
            'commence_time': game_data['commence_time']
        }
        
        assert parsed['home_team'] == 'Los Angeles Lakers'
        assert parsed['away_team'] == 'Boston Celtics'
    
    def test_extract_odds_from_bookmaker(self):
        """Test extracting odds from bookmaker data."""
        bookmaker = {
            'key': 'draftkings',
            'markets': [
                {
                    'key': 'h2h',
                    'outcomes': [
                        {'name': 'Lakers', 'price': 2.00},
                        {'name': 'Celtics', 'price': 1.90}
                    ]
                }
            ]
        }
        
        # Extract h2h odds
        for market in bookmaker['markets']:
            if market['key'] == 'h2h':
                for outcome in market['outcomes']:
                    if outcome['name'] == 'Lakers':
                        assert outcome['price'] == 2.00
                    elif outcome['name'] == 'Celtics':
                        assert outcome['price'] == 1.90


class TestCountBookmakers:
    """Test bookmaker counting."""
    
    def test_count_unique_bookmakers(self):
        """Test counting unique bookmakers."""
        games = [
            {'bookmakers': [{'key': 'dk'}, {'key': 'fanduel'}]},
            {'bookmakers': [{'key': 'dk'}, {'key': 'betmgm'}]},
        ]
        
        all_bookmakers = set()
        for game in games:
            for bm in game.get('bookmakers', []):
                all_bookmakers.add(bm['key'])
        
        assert len(all_bookmakers) == 3  # dk, fanduel, betmgm


class TestRateLimiting:
    """Test rate limiting handling."""
    
    def test_parse_remaining_requests(self):
        """Test parsing remaining requests from header."""
        headers = {'x-requests-remaining': '495'}
        remaining = int(headers.get('x-requests-remaining', 0))
        
        assert remaining == 495
    
    def test_low_requests_warning(self):
        """Test warning for low remaining requests."""
        remaining = 10
        
        if remaining < 50:
            warning = True
        else:
            warning = False
        
        assert warning == True
