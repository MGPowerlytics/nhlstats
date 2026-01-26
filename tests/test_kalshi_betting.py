"""Tests for Kalshi Betting Client."""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, mock_open

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))


class TestKalshiBettingInit:
    """Test KalshiBetting initialization."""

    @patch("kalshi_betting.serialization.load_pem_private_key")
    @patch("builtins.open", mock_open(read_data=b"test_private_key"))
    def test_init_production(self, mock_load_key):
        """Test initialization in production mode."""
        from kalshi_betting import KalshiBetting

        mock_load_key.return_value = MagicMock()

        client = KalshiBetting(
            api_key_id="test_key",
            private_key_path="test.pem",
            max_bet_size=10.0,
            production=True,
        )

        assert client.api_key_id == "test_key"
        assert client.max_bet_size == 10.0
        assert client.base_url == "https://api.elections.kalshi.com"

    @patch("kalshi_betting.serialization.load_pem_private_key")
    @patch("builtins.open", mock_open(read_data=b"test_private_key"))
    def test_init_demo(self, mock_load_key):
        """Test initialization in demo mode."""
        from kalshi_betting import KalshiBetting

        mock_load_key.return_value = MagicMock()

        client = KalshiBetting(
            api_key_id="test_key", private_key_path="test.pem", production=False
        )

        assert client.base_url == "https://demo-api.kalshi.co"

    @patch("kalshi_betting.serialization.load_pem_private_key")
    @patch("builtins.open", mock_open(read_data=b"test_private_key"))
    def test_init_with_odds_api_key(self, mock_load_key):
        """Test initialization with odds API key."""
        from kalshi_betting import KalshiBetting

        mock_load_key.return_value = MagicMock()

        client = KalshiBetting(
            api_key_id="test_key",
            private_key_path="test.pem",
            odds_api_key="odds_test_key",
        )

        assert client.odds_api_key == "odds_test_key"


class TestKalshiBettingMethods:
    """Test KalshiBetting methods."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Kalshi client."""
        with patch(
            "kalshi_betting.serialization.load_pem_private_key"
        ) as mock_load_key:
            with patch("builtins.open", mock_open(read_data=b"test_private_key")):
                from kalshi_betting import KalshiBetting

                mock_load_key.return_value = MagicMock()
                client = KalshiBetting(
                    "test_key", "test.pem", odds_api_key="test_odds_key"
                )
                return client

    def test_calculate_bet_size_min(self, mock_client):
        """Test bet size calculation returns minimum."""
        size = mock_client.calculate_bet_size(confidence=0.6, edge=0.01, balance=100)
        assert size >= mock_client.min_bet_size

    def test_calculate_bet_size_max(self, mock_client):
        """Test bet size calculation caps at maximum."""
        size = mock_client.calculate_bet_size(confidence=0.99, edge=0.50, balance=1000)
        assert size <= mock_client.max_bet_size

    def test_calculate_bet_size_position_limit(self, mock_client):
        """Test bet size respects position limit."""
        size = mock_client.calculate_bet_size(confidence=0.99, edge=0.50, balance=100)
        assert size <= 100 * mock_client.max_position_pct

    def test_is_game_started_closed_market(self, mock_client):
        """Test is_game_started with closed market."""
        market = {"status": "closed"}
        assert mock_client.is_game_started(market)

    def test_is_game_started_settled_market(self, mock_client):
        """Test is_game_started with settled market."""
        market = {"status": "settled"}
        assert mock_client.is_game_started(market)

    def test_is_game_started_active_market(self, mock_client):
        """Test is_game_started with active market (no close_time)."""
        market = {"status": "active"}
        assert not mock_client.is_game_started(market)

    def test_is_game_started_future_close_time(self, mock_client):
        """Test is_game_started with future close time."""
        future_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        market = {"status": "active", "close_time": future_time}
        assert not mock_client.is_game_started(market)

    def test_is_game_started_past_close_time(self, mock_client):
        """Test is_game_started with past close time."""
        past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        market = {"status": "active", "close_time": past_time}
        assert mock_client.is_game_started(market)

    @patch("kalshi_betting.requests.get")
    def test_verify_game_not_started_no_api_key(self, mock_get, mock_client):
        """Test verify_game_not_started without API key."""
        mock_client.odds_api_key = None
        result = mock_client.verify_game_not_started("Lakers", "Celtics", "NBA")
        assert result  # Should return True when no API key
        mock_get.assert_not_called()

    @patch("kalshi_betting.requests.get")
    def test_verify_game_not_started_unknown_sport(self, mock_get, mock_client):
        """Test verify_game_not_started with unknown sport."""
        result = mock_client.verify_game_not_started(
            "Team A", "Team B", "UNKNOWN_SPORT"
        )
        assert result
        mock_get.assert_not_called()

    @patch("kalshi_betting.requests.get")
    def test_verify_game_not_started_game_started(self, mock_get, mock_client):
        """Test verify_game_not_started when game has started."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "home_team": "Los Angeles Lakers",
                "away_team": "Boston Celtics",
                "scores": [{"name": "Lakers", "score": "50"}],
                "commence_time": "2024-01-01T00:00:00Z",
            }
        ]
        mock_get.return_value = mock_response

        result = mock_client.verify_game_not_started("Lakers", "Celtics", "NBA")
        assert not result

    @patch("kalshi_betting.requests.get")
    def test_verify_game_not_started_game_not_found(self, mock_get, mock_client):
        """Test verify_game_not_started when game not in started games."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        result = mock_client.verify_game_not_started("Lakers", "Celtics", "NBA")
        assert result

    @patch("kalshi_betting.requests.get")
    def test_verify_game_not_started_api_error(self, mock_get, mock_client):
        """Test verify_game_not_started handles API error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = mock_client.verify_game_not_started("Lakers", "Celtics", "NBA")
        assert result  # Should fail open

    @patch("kalshi_betting.requests.get")
    def test_verify_game_not_started_timeout(self, mock_get, mock_client):
        """Test verify_game_not_started handles timeout."""
        mock_get.side_effect = Exception("Timeout")

        result = mock_client.verify_game_not_started("Lakers", "Celtics", "NBA")
        assert result  # Should fail open


class TestProcessBetRecommendations:
    """Test process_bet_recommendations method."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Kalshi client."""
        with patch(
            "kalshi_betting.serialization.load_pem_private_key"
        ) as mock_load_key:
            with patch("builtins.open", mock_open(read_data=b"test_private_key")):
                from kalshi_betting import KalshiBetting

                mock_load_key.return_value = MagicMock()
                client = KalshiBetting(
                    "test_key", "test.pem", odds_api_key="test_odds_key"
                )
                client.get_balance = MagicMock(return_value=(100.0, 100.0))
                client.get_market_details = MagicMock(
                    return_value={"status": "active", "yes_ask": 50}
                )
                client.verify_game_not_started = MagicMock(return_value=True)
                client.is_game_started = MagicMock(return_value=False)
                client.place_bet = MagicMock(return_value={"order_id": "123"})
                return client

    def test_empty_recommendations(self, mock_client):
        """Test with empty recommendations list."""
        result = mock_client.process_bet_recommendations([])
        assert result["placed"] == []
        assert result["skipped"] == []
        assert result["errors"] == []

    def test_low_confidence_skipped(self, mock_client):
        """Test that low confidence bets are skipped."""
        recs = [
            {
                "sport": "NBA",
                "elo_prob": 0.60,  # Below 0.75 threshold
                "edge": 0.10,
                "ticker": "TEST-123",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "bet_on": "home",
            }
        ]

        result = mock_client.process_bet_recommendations(recs, min_confidence=0.75)
        assert len(result["skipped"]) == 1
        assert result["skipped"][0]["reason"] == "Low confidence"

    def test_low_edge_skipped(self, mock_client):
        """Test that low edge bets are skipped."""
        recs = [
            {
                "sport": "NBA",
                "elo_prob": 0.80,
                "edge": 0.02,  # Below 0.05 threshold
                "ticker": "TEST-123",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "bet_on": "home",
            }
        ]

        result = mock_client.process_bet_recommendations(recs, min_edge=0.05)
        assert len(result["skipped"]) == 1
        assert result["skipped"][0]["reason"] == "Low edge"

    def test_no_ticker_error(self, mock_client):
        """Test that missing ticker causes error."""
        recs = [
            {
                "sport": "NBA",
                "elo_prob": 0.80,
                "edge": 0.10,
                "home_team": "Lakers",
                "away_team": "Celtics",
                "bet_on": "home",
                # No ticker
            }
        ]

        result = mock_client.process_bet_recommendations(recs)
        assert len(result["errors"]) == 1

    def test_sport_filter(self, mock_client):
        """Test sport filter skips non-matching sports."""
        recs = [
            {
                "sport": "NHL",
                "elo_prob": 0.80,
                "edge": 0.10,
                "ticker": "TEST-123",
                "home_team": "Leafs",
                "away_team": "Bruins",
                "bet_on": "home",
            }
        ]

        result = mock_client.process_bet_recommendations(recs, sport_filter=["NBA"])
        assert len(result["skipped"]) == 1
        assert result["skipped"][0]["reason"] == "Sport filter"

    def test_tennis_sport_case_insensitive(self, mock_client):
        """Test that tennis detection is case-insensitive."""
        recs = [
            {
                "sport": "TENNIS",  # Uppercase
                "elo_prob": 0.80,
                "edge": 0.10,
                "ticker": "KXATPMATCH-26JAN17-PLAYER",
                "bet_on": "Djokovic",
                "matchup": "Djokovic vs Nadal",
            }
        ]

        # Should not raise KeyError for home_team/away_team
        result = mock_client.process_bet_recommendations(
            recs, sport_filter=["TENNIS"], dry_run=True
        )
        # If it gets past the tennis check without error, the case-insensitive fix works
        assert "skipped" in result

    def test_dry_run_mode(self, mock_client):
        """Test dry run doesn't place actual bets."""
        recs = [
            {
                "sport": "NBA",
                "elo_prob": 0.80,
                "edge": 0.10,
                "ticker": "TEST-123",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "bet_on": "home",
            }
        ]

        result = mock_client.process_bet_recommendations(recs, dry_run=True)
        mock_client.place_bet.assert_not_called()
        assert len(result["placed"]) == 1
        assert result["placed"][0]["dry_run"]

    def test_game_already_started_skipped(self, mock_client):
        """Test that started games are skipped."""
        mock_client.verify_game_not_started = MagicMock(return_value=False)

        recs = [
            {
                "sport": "NBA",
                "elo_prob": 0.80,
                "edge": 0.10,
                "ticker": "TEST-123",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "bet_on": "home",
            }
        ]

        result = mock_client.process_bet_recommendations(recs)
        assert len(result["skipped"]) == 1
        assert result["skipped"][0]["reason"] == "Game already started"

    def test_market_closed_skipped(self, mock_client):
        """Test that closed markets are skipped."""
        mock_client.is_game_started = MagicMock(return_value=True)

        recs = [
            {
                "sport": "NBA",
                "elo_prob": 0.80,
                "edge": 0.10,
                "ticker": "TEST-123",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "bet_on": "home",
            }
        ]

        result = mock_client.process_bet_recommendations(recs)
        assert len(result["skipped"]) == 1
        assert result["skipped"][0]["reason"] == "Market closed"

    def test_home_bet_uses_yes_side(self, mock_client):
        """Test that betting on home uses YES side."""
        recs = [
            {
                "sport": "NBA",
                "elo_prob": 0.80,
                "edge": 0.10,
                "ticker": "TEST-123",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "bet_on": "home",
            }
        ]

        result = mock_client.process_bet_recommendations(recs, dry_run=True)
        assert result["placed"][0]["side"] == "yes"

    def test_away_bet_uses_no_side(self, mock_client):
        """Test that betting on away uses NO side."""
        recs = [
            {
                "sport": "NBA",
                "elo_prob": 0.80,
                "edge": 0.10,
                "ticker": "TEST-123",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "bet_on": "away",
            }
        ]

        result = mock_client.process_bet_recommendations(recs, dry_run=True)
        assert result["placed"][0]["side"] == "no"


class TestSignatureCreation:
    """Test signature creation for API authentication."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Kalshi client."""
        with patch(
            "kalshi_betting.serialization.load_pem_private_key"
        ) as mock_load_key:
            with patch("builtins.open", mock_open(read_data=b"test_private_key")):
                from kalshi_betting import KalshiBetting

                mock_key = MagicMock()
                mock_key.sign.return_value = b"test_signature"
                mock_load_key.return_value = mock_key
                client = KalshiBetting("test_key", "test.pem")
                return client

    def test_signature_strips_query_params(self, mock_client):
        """Test that signature creation strips query parameters."""
        mock_client._create_signature("12345", "GET", "/api/markets?limit=10")
        # The signature should be created without the query params
        mock_client.private_key.sign.assert_called_once()
        call_args = mock_client.private_key.sign.call_args[0]
        assert b"?" not in call_args[0]

    def test_get_headers_includes_required_fields(self, mock_client):
        """Test that headers include all required fields."""
        headers = mock_client._get_headers("GET", "/api/test")

        assert "KALSHI-ACCESS-KEY" in headers
        assert "KALSHI-ACCESS-SIGNATURE" in headers
        assert "KALSHI-ACCESS-TIMESTAMP" in headers
        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"
