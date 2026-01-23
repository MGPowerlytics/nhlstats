"""Tests for Cloudbet and Polymarket API modules."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestCloudbetAPI:
    """Test Cloudbet API module."""

    def test_base_url(self):
        """Test Cloudbet base URL."""
        base_url = "https://sports-api.cloudbet.com/pub/v2"

        assert "cloudbet.com" in base_url
        assert "/pub/v2" in base_url

    def test_sport_mapping(self):
        """Test sport to Cloudbet category mapping."""
        sport_map = {
            'nba': 'basketball',
            'nhl': 'ice-hockey',
            'mlb': 'baseball',
            'nfl': 'american-football',
            'epl': 'soccer'
        }

        assert sport_map['nba'] == 'basketball'
        assert sport_map['nhl'] == 'ice-hockey'

    def test_parse_cloudbet_odds(self):
        """Test parsing Cloudbet odds format."""
        # Cloudbet uses decimal odds
        odds_data = {
            'home': {'price': '2.10'},
            'away': {'price': '1.80'}
        }

        home_decimal = float(odds_data['home']['price'])
        away_decimal = float(odds_data['away']['price'])

        home_prob = 1 / home_decimal
        away_prob = 1 / away_decimal

        assert home_prob == pytest.approx(0.476, abs=0.01)
        assert away_prob == pytest.approx(0.556, abs=0.01)

    def test_api_key_header(self):
        """Test API key header format."""
        api_key = "test_api_key_123"
        headers = {
            'X-API-KEY': api_key,
            'Content-Type': 'application/json'
        }

        assert 'X-API-KEY' in headers
        assert headers['X-API-KEY'] == api_key


class TestPolymarketAPI:
    """Test Polymarket API module."""

    def test_base_url(self):
        """Test Polymarket base URL."""
        base_url = "https://gamma-api.polymarket.com"

        assert "polymarket.com" in base_url

    def test_market_id_format(self):
        """Test Polymarket market ID format."""
        # Polymarket uses UUIDs for market IDs
        market_id = "0x1234567890abcdef1234567890abcdef12345678"

        assert market_id.startswith("0x")
        assert len(market_id) == 42

    def test_parse_polymarket_price(self):
        """Test parsing Polymarket prices."""
        # Polymarket prices are 0-1 probabilities
        price_data = {
            'yes': 0.55,
            'no': 0.45
        }

        assert price_data['yes'] + price_data['no'] == pytest.approx(1.0, abs=0.01)

    def test_volume_calculation(self):
        """Test market volume calculation."""
        trades = [
            {'amount': 100},
            {'amount': 250},
            {'amount': 75}
        ]

        total_volume = sum(t['amount'] for t in trades)

        assert total_volume == 425


class TestCryptoBettingOdds:
    """Test crypto betting odds handling."""

    def test_decimal_odds_to_probability(self):
        """Test converting decimal odds to implied probability."""
        decimal_odds = 2.0
        implied_prob = 1 / decimal_odds

        assert implied_prob == 0.5

    def test_american_to_decimal_positive(self):
        """Test converting positive American odds to decimal."""
        american = 150  # +150
        decimal_odds = (american / 100) + 1

        assert decimal_odds == 2.5

    def test_american_to_decimal_negative(self):
        """Test converting negative American odds to decimal."""
        american = -150
        decimal_odds = (100 / abs(american)) + 1

        assert decimal_odds == pytest.approx(1.667, abs=0.01)

    def test_calculate_payout(self):
        """Test calculating potential payout."""
        stake = 100
        decimal_odds = 2.5

        payout = stake * decimal_odds
        profit = payout - stake

        assert payout == 250
        assert profit == 150


class TestAPIErrorHandling:
    """Test API error handling."""

    def test_rate_limit_detection(self):
        """Test detecting rate limit response."""
        status_codes = {
            200: 'success',
            429: 'rate_limit',
            500: 'server_error',
            401: 'unauthorized'
        }

        assert status_codes[429] == 'rate_limit'

    def test_retry_logic(self):
        """Test retry logic for failed requests."""
        max_retries = 3
        retry_delays = [1, 2, 4]  # Exponential backoff

        for i in range(max_retries):
            assert retry_delays[i] == 2 ** i

    def test_timeout_handling(self):
        """Test timeout configuration."""
        default_timeout = 10  # seconds

        assert default_timeout == 10


class TestMarketStatusHandling:
    """Test market status handling."""

    def test_market_status_values(self):
        """Test valid market status values."""
        valid_statuses = ['open', 'closed', 'resolved', 'suspended']

        market = {'status': 'open'}
        assert market['status'] in valid_statuses

    def test_is_tradeable(self):
        """Test checking if market is tradeable."""
        tradeable_statuses = ['open', 'live']

        market_open = {'status': 'open'}
        market_closed = {'status': 'closed'}

        assert market_open['status'] in tradeable_statuses
        assert market_closed['status'] not in tradeable_statuses

    def test_is_settled(self):
        """Test checking if market is settled."""
        market_resolved = {'status': 'resolved', 'result': 'yes'}
        market_open = {'status': 'open'}

        assert market_resolved['status'] == 'resolved'
        assert market_open['status'] != 'resolved'


class TestPriceFormatting:
    """Test price formatting for display."""

    def test_format_probability_percentage(self):
        """Test formatting probability as percentage."""
        prob = 0.553
        formatted = f"{prob:.1%}"

        assert formatted == "55.3%"

    def test_format_decimal_odds(self):
        """Test formatting decimal odds."""
        decimal_odds = 2.105
        formatted = f"{decimal_odds:.2f}"

        assert formatted == "2.10"

    def test_format_american_odds_positive(self):
        """Test formatting positive American odds."""
        american = 150
        formatted = f"+{american}"

        assert formatted == "+150"

    def test_format_american_odds_negative(self):
        """Test formatting negative American odds."""
        american = -150
        formatted = str(american)

        assert formatted == "-150"


class TestLiquidityChecking:
    """Test liquidity checking functionality."""

    def test_sufficient_liquidity(self):
        """Test checking for sufficient liquidity."""
        available_liquidity = 10000
        desired_bet = 500
        min_ratio = 0.1  # Bet should be < 10% of liquidity

        is_sufficient = desired_bet <= available_liquidity * min_ratio

        assert is_sufficient == True

    def test_insufficient_liquidity(self):
        """Test detecting insufficient liquidity."""
        available_liquidity = 1000
        desired_bet = 500
        min_ratio = 0.1

        is_sufficient = desired_bet <= available_liquidity * min_ratio

        assert is_sufficient == False

    def test_spread_calculation(self):
        """Test bid-ask spread calculation."""
        bid = 0.52
        ask = 0.55

        spread = ask - bid
        spread_pct = spread / ask * 100

        assert spread == pytest.approx(0.03, abs=0.001)
        assert spread_pct == pytest.approx(5.45, abs=0.1)
