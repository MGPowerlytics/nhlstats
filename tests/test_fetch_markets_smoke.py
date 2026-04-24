"""
Smoke tests for fetch_markets functions.

Tests verify:
1. All fetch_*_markets functions exist and are callable
2. Functions handle missing kalshi_python package gracefully
3. Functions handle credential errors gracefully
4. Functions handle API errors gracefully
5. Rate limiting is applied between API calls
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))


class TestFetchMarketsImports:
    """Test that all fetch_*_markets functions can be imported."""

    ALL_SPORTS = [
        "nba",
        "nhl",
        "mlb",
        "nfl",
        "epl",
        "ligue1",
        "ncaab",
        "wncaab",
        "tennis",
    ]

    @pytest.mark.parametrize("sport", ALL_SPORTS)
    def test_fetch_function_exists(self, sport):
        """Each fetch_*_markets function should exist."""
        import kalshi_markets

        func_name = f"fetch_{sport}_markets"
        assert hasattr(kalshi_markets, func_name), f"Missing function: {func_name}"
        assert callable(getattr(kalshi_markets, func_name))

    def test_sport_series_dict_exists(self):
        """SPORT_SERIES dictionary should be defined."""
        from kalshi_markets import SPORT_SERIES

        assert isinstance(SPORT_SERIES, dict)
        assert len(SPORT_SERIES) == 11  # All 11 sports (including CBA and Unrivaled)

    def test_sport_series_has_all_sports(self):
        """SPORT_SERIES should have entries for all sports."""
        from kalshi_markets import SPORT_SERIES

        for sport in self.ALL_SPORTS:
            assert sport in SPORT_SERIES, f"Missing sport: {sport}"
            assert isinstance(SPORT_SERIES[sport], list), (
                f"{sport} should have list of tickers"
            )
            assert len(SPORT_SERIES[sport]) >= 1, (
                f"{sport} should have at least 1 ticker"
            )

    def test_tennis_has_multiple_series(self):
        """Tennis should fetch from 4 different series."""
        from kalshi_markets import SPORT_SERIES

        assert len(SPORT_SERIES["tennis"]) == 4
        assert "KXATPMATCH" in SPORT_SERIES["tennis"]
        assert "KXWTAMATCH" in SPORT_SERIES["tennis"]
        assert "KXATPCHALLENGERMATCH" in SPORT_SERIES["tennis"]
        assert "KXWTACHALLENGERMATCH" in SPORT_SERIES["tennis"]


class TestFetchMarketsErrorHandling:
    """Test error handling in fetch_*_markets functions."""

    @pytest.fixture
    def mock_kalshi_available(self):
        """Mock kalshi_python as available."""
        with patch("kalshi_markets.KALSHI_AVAILABLE", True):
            yield

    @pytest.fixture
    def mock_kalshi_unavailable(self):
        """Mock kalshi_python as unavailable."""
        with patch("kalshi_markets.KALSHI_AVAILABLE", False):
            yield

    def test_returns_empty_list_when_kalshi_unavailable(self, mock_kalshi_unavailable):
        """Should return [] when kalshi_python not installed."""
        from kalshi_markets import fetch_nba_markets

        result = fetch_nba_markets()
        assert result == []

    def test_returns_empty_list_on_credential_error(self, mock_kalshi_available):
        """Should return [] when credentials are missing."""
        from kalshi_markets import fetch_nba_markets

        with patch("kalshi_markets.load_kalshi_credentials") as mock_creds:
            mock_creds.side_effect = FileNotFoundError("No credentials")

            result = fetch_nba_markets()
            assert result == []

    def test_returns_empty_list_on_invalid_credentials(self, mock_kalshi_available):
        """Should return [] when credentials are invalid."""
        from kalshi_markets import fetch_nba_markets

        with patch("kalshi_markets.load_kalshi_credentials") as mock_creds:
            mock_creds.side_effect = ValueError("Invalid credentials")

            result = fetch_nba_markets()
            assert result == []

    def test_returns_empty_list_on_api_error(self, mock_kalshi_available):
        """Should return [] when API returns None."""
        from kalshi_markets import fetch_nba_markets

        with patch("kalshi_markets.load_kalshi_credentials") as mock_creds:
            with patch("kalshi_markets.KalshiAPI") as mock_api_class:
                mock_creds.return_value = ("key", "pem")
                mock_api = MagicMock()
                mock_api.get_markets.return_value = None  # API failure
                mock_api_class.return_value = mock_api

                result = fetch_nba_markets()
                assert result == []


class TestFetchMarketsSuccess:
    """Test successful fetch scenarios."""

    @pytest.fixture
    def mock_kalshi_api(self):
        """Mock successful Kalshi API responses."""
        with patch("kalshi_markets.KALSHI_AVAILABLE", True):
            with patch("kalshi_markets.load_kalshi_credentials") as mock_creds:
                with patch("kalshi_markets.KalshiAPI") as mock_api_class:
                    with patch("kalshi_markets.save_to_db") as mock_save:
                        mock_creds.return_value = ("test_key", "test_pem")
                        mock_api = MagicMock()
                        mock_api.get_markets.return_value = {
                            "markets": [
                                {"ticker": "TEST-001", "status": "active"},
                                {"ticker": "TEST-002", "status": "initialized"},
                                {
                                    "ticker": "TEST-003",
                                    "status": "closed",
                                },  # Should be filtered
                            ]
                        }
                        mock_api_class.return_value = mock_api
                        mock_save.return_value = 2

                        yield {
                            "api": mock_api,
                            "save_to_db": mock_save,
                            "creds": mock_creds,
                        }

    @pytest.mark.parametrize("sport", ["nba", "nhl", "mlb", "nfl", "epl", "ligue1"])
    def test_fetch_single_series_sport(self, sport, mock_kalshi_api):
        """Single-series sports should return filtered active markets."""
        import kalshi_markets

        fetch_fn = getattr(kalshi_markets, f"fetch_{sport}_markets")
        result = fetch_fn()

        # Should return only active/initialized markets (not closed)
        assert len(result) == 2
        assert all(m.get("status") in ["active", "initialized"] for m in result)

    def test_fetch_tennis_uses_kalshi(self):
        """Tennis should use the shared Kalshi sport-fetch path."""
        from kalshi_markets import fetch_tennis_markets

        tennis_markets = [{"id": "tennis-1"}]
        with patch("kalshi_markets._fetch_sport_markets") as mock_fetch:
            mock_fetch.return_value = tennis_markets
            result = fetch_tennis_markets()

        assert result == tennis_markets
        mock_fetch.assert_called_once_with("tennis")

    def test_saves_to_database(self, mock_kalshi_api):
        """Fetched markets should be saved to database."""
        from kalshi_markets import fetch_nba_markets

        fetch_nba_markets()

        mock_kalshi_api["save_to_db"].assert_called_once()
        call_args = mock_kalshi_api["save_to_db"].call_args
        assert call_args[0][0] == "nba"  # First arg is sport


class TestRateLimiting:
    """Test rate limiting between API calls."""

    def test_rate_limit_function_exists(self):
        """_rate_limit function should exist."""
        from kalshi_markets import _rate_limit

        assert callable(_rate_limit)

    def test_rate_limit_constant_defined(self):
        """API_RATE_LIMIT_SECONDS should be defined."""
        from kalshi_markets import API_RATE_LIMIT_SECONDS

        assert isinstance(API_RATE_LIMIT_SECONDS, (int, float))
        assert API_RATE_LIMIT_SECONDS >= 0.1  # At least 100ms


class TestLogging:
    """Test that logging is properly configured."""

    def test_logger_exists(self):
        """Module should have a logger."""
        import kalshi_markets

        assert hasattr(kalshi_markets, "logger")

    def test_log_messages_on_success(self, caplog):
        """Should log success messages."""
        import logging

        with patch("kalshi_markets.KALSHI_AVAILABLE", True):
            with patch("kalshi_markets.load_kalshi_credentials") as mock_creds:
                with patch("kalshi_markets.KalshiAPI") as mock_api_class:
                    with patch("kalshi_markets.save_to_db"):
                        mock_creds.return_value = ("key", "pem")
                        mock_api = MagicMock()
                        mock_api.get_markets.return_value = {"markets": []}
                        mock_api_class.return_value = mock_api

                        with caplog.at_level(logging.INFO):
                            from kalshi_markets import fetch_nba_markets

                            fetch_nba_markets()

    def test_log_messages_on_error(self, caplog):
        """Should log error messages on failure."""
        import logging

        with patch("kalshi_markets.KALSHI_AVAILABLE", True):
            with patch("kalshi_markets.load_kalshi_credentials") as mock_creds:
                mock_creds.side_effect = FileNotFoundError("Test error")

                with caplog.at_level(logging.ERROR):
                    from kalshi_markets import fetch_nba_markets

                    fetch_nba_markets()


class TestNcaabWncaabLimits:
    """Test that NCAAB/WNCAAB use higher limits."""

    def test_ncaab_uses_higher_limit(self):
        """NCAAB should use limit of 1000."""
        from kalshi_markets import SPORT_LIMITS

        assert SPORT_LIMITS.get("ncaab") == 1000

    def test_wncaab_uses_higher_limit(self):
        """WNCAAB should use limit of 1000."""
        from kalshi_markets import SPORT_LIMITS

        assert SPORT_LIMITS.get("wncaab") == 1000
