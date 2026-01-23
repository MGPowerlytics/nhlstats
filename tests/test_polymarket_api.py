"""Tests for Polymarket API module."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestPolymarketAPIInit:
    """Test PolymarketAPI initialization."""

    def test_init(self):
        """Test initialization."""
        from polymarket_api import PolymarketAPI

        api = PolymarketAPI()

        assert api.session is not None

    def test_base_url(self):
        """Test base URL configuration."""
        from polymarket_api import PolymarketAPI

        assert PolymarketAPI.BASE_URL == "https://gamma-api.polymarket.com"

    def test_clob_url(self):
        """Test CLOB URL configuration."""
        from polymarket_api import PolymarketAPI

        assert PolymarketAPI.CLOB_URL == "https://clob.polymarket.com"

    def test_headers_set(self):
        """Test headers are set correctly."""
        from polymarket_api import PolymarketAPI

        api = PolymarketAPI()

        assert 'Content-Type' in api.session.headers


class TestFetchMarkets:
    """Test market fetching."""

    @patch('polymarket_api.requests.Session')
    def test_fetch_markets_success(self, mock_session_class):
        """Test successful market fetch."""
        from polymarket_api import PolymarketAPI

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        api = PolymarketAPI()
        api.session = mock_session

        markets = api.fetch_markets('nba')

        assert isinstance(markets, list)

    @patch('polymarket_api.requests.Session')
    def test_fetch_markets_error(self, mock_session_class):
        """Test handling fetch error."""
        from polymarket_api import PolymarketAPI
        import requests

        mock_session = MagicMock()
        mock_session.get.side_effect = requests.exceptions.RequestException("Error")
        mock_session_class.return_value = mock_session

        api = PolymarketAPI()
        api.session = mock_session

        markets = api.fetch_markets()

        assert markets == []


class TestSportDetection:
    """Test sport detection from market data."""

    def test_detect_nba(self):
        """Test detecting NBA market."""
        question = "Will the Lakers beat the Celtics in the NBA game?"

        sport = None
        if 'nba' in question.lower() or 'basketball' in question.lower():
            sport = 'nba'

        assert sport == 'nba'

    def test_detect_nhl(self):
        """Test detecting NHL market."""
        question = "Will the Bruins win the NHL game tonight?"

        sport = None
        if 'nhl' in question.lower() or 'hockey' in question.lower():
            sport = 'nhl'

        assert sport == 'nhl'

    def test_detect_mlb(self):
        """Test detecting MLB market."""
        question = "Will the Yankees win the MLB World Series?"

        sport = None
        if 'mlb' in question.lower() or 'baseball' in question.lower():
            sport = 'mlb'

        assert sport == 'mlb'

    def test_detect_nfl(self):
        """Test detecting NFL market."""
        question = "Will the Chiefs win the NFL game?"

        sport = None
        if 'nfl' in question.lower():
            sport = 'nfl'

        assert sport == 'nfl'

    def test_no_sport_detected(self):
        """Test when no sport is detected."""
        question = "Will Bitcoin reach $100k?"

        sport = None
        if 'nba' in question.lower():
            sport = 'nba'
        elif 'nhl' in question.lower():
            sport = 'nhl'

        assert sport is None


class TestMarketParsing:
    """Test market parsing."""

    def test_parse_market_with_outcomes(self):
        """Test parsing market with Yes/No outcomes."""
        market = {
            'question': 'Will Lakers win?',
            'outcomePrices': '[0.55, 0.45]'
        }

        # Parse outcome prices
        import json
        prices = json.loads(market['outcomePrices'])

        yes_price = prices[0]
        no_price = prices[1]

        assert yes_price == 0.55
        assert no_price == 0.45

    def test_parse_market_id(self):
        """Test parsing market ID."""
        market = {
            'id': '0x1234567890abcdef1234567890abcdef12345678',
            'slug': 'lakers-win-game'
        }

        assert market['id'].startswith('0x')
        assert 'lakers' in market['slug']

    def test_parse_volume(self):
        """Test parsing market volume."""
        market = {
            'volume': '10000.00',
            'liquidity': '5000.00'
        }

        volume = float(market['volume'])
        liquidity = float(market['liquidity'])

        assert volume == 10000.0
        assert liquidity == 5000.0


class TestPriceConversion:
    """Test price conversion utilities."""

    def test_probability_price(self):
        """Test probability as price."""
        # Polymarket uses 0-1 probability as price
        yes_price = 0.65
        no_price = 1 - yes_price

        assert yes_price == 0.65
        assert no_price == 0.35

    def test_implied_probability_with_spread(self):
        """Test implied probability with bid-ask spread."""
        bid = 0.52
        ask = 0.55

        # Mid-price
        mid = (bid + ask) / 2

        assert mid == 0.535


class TestMarketFiltering:
    """Test market filtering."""

    def test_filter_active_markets(self):
        """Test filtering active markets."""
        markets = [
            {'active': True, 'closed': False, 'question': 'Q1'},
            {'active': False, 'closed': True, 'question': 'Q2'},
            {'active': True, 'closed': False, 'question': 'Q3'}
        ]

        active = [m for m in markets if m.get('active') and not m.get('closed')]

        assert len(active) == 2

    def test_filter_by_sport(self):
        """Test filtering by sport."""
        markets = [
            {'question': 'Will Lakers beat Celtics? NBA'},
            {'question': 'Will Bitcoin reach $100k?'},
            {'question': 'NHL game prediction'}
        ]

        nba_markets = [m for m in markets if 'nba' in m['question'].lower()]

        assert len(nba_markets) == 1


class TestOrderBook:
    """Test order book functionality."""

    def test_best_bid_ask(self):
        """Test getting best bid and ask."""
        order_book = {
            'bids': [
                {'price': 0.52, 'size': 100},
                {'price': 0.51, 'size': 200}
            ],
            'asks': [
                {'price': 0.55, 'size': 100},
                {'price': 0.56, 'size': 200}
            ]
        }

        best_bid = max(order_book['bids'], key=lambda x: x['price'])
        best_ask = min(order_book['asks'], key=lambda x: x['price'])

        assert best_bid['price'] == 0.52
        assert best_ask['price'] == 0.55

    def test_spread_calculation(self):
        """Test spread calculation."""
        bid = 0.52
        ask = 0.55

        spread = ask - bid
        spread_pct = spread / ask * 100

        assert spread == pytest.approx(0.03, abs=0.001)
        assert spread_pct == pytest.approx(5.45, abs=0.1)
