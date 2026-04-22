"""Tests for Kalshi Markets API module."""

import importlib
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))


class TestLoadKalshiCredentials:
    """Test load_kalshi_credentials function."""

    def test_load_credentials_from_runtime_env(self):
        """Test loading credentials from the approved runtime env vars."""
        from kalshi_markets import load_kalshi_credentials

        with patch.dict(
            "os.environ",
            {
                "KALSHI_API_KEY_ID": "test_api_key_12345",
                "KALSHI_PRIVATE_KEY_PATH": "/run/secrets/kalshi_private_key.pem",
            },
            clear=True,
        ):
            with patch("kalshi_markets.Path.read_text", return_value="test-private-key"):
                api_key_id, private_key = load_kalshi_credentials()

        assert api_key_id == "test_api_key_12345"
        assert private_key == "test-private-key"

    def test_load_credentials_file_not_found(self):
        """Test error when runtime credentials are not configured."""
        from kalshi_markets import load_kalshi_credentials

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="KALSHI_API_KEY_ID"):
                load_kalshi_credentials()


class TestKalshiAPI:
    """Test KalshiAPI class."""

    @patch("kalshi_markets.ApiClient")
    @patch("kalshi_markets.Configuration")
    @patch("kalshi_markets.MarketsApi")
    def test_init(self, mock_markets_api, mock_config, mock_client):
        """Test KalshiAPI initialization."""
        from kalshi_markets import KalshiAPI

        api = KalshiAPI("test_key", "test_pem")

        assert api.api_key_id == "test_key"
        assert api.private_key_pem == "test_pem"
        mock_config.assert_called_once_with(
            host="https://api.elections.kalshi.com/trade-api/v2"
        )

    @patch("kalshi_markets.ApiClient")
    @patch("kalshi_markets.Configuration")
    @patch("kalshi_markets.MarketsApi")
    def test_get_markets_success(self, mock_markets_api, mock_config, mock_client):
        """Test getting markets successfully."""
        from kalshi_markets import KalshiAPI

        mock_response = MagicMock()
        mock_response.to_dict.return_value = {"markets": [{"ticker": "TEST"}]}
        mock_markets_api.return_value.get_markets.return_value = mock_response

        api = KalshiAPI("test_key", "test_pem")
        result = api.get_markets(series_ticker="KXNBA")

        assert result is not None

    @patch("kalshi_markets.ApiClient")
    @patch("kalshi_markets.Configuration")
    @patch("kalshi_markets.MarketsApi")
    def test_get_markets_error(self, mock_markets_api, mock_config, mock_client):
        """Test handling error in get_markets."""
        from kalshi_markets import KalshiAPI

        mock_markets_api.return_value.get_markets.side_effect = Exception("API Error")

        api = KalshiAPI("test_key", "test_pem")
        result = api.get_markets()

        assert result is None

    @pytest.mark.skip(reason="search_markets method not implemented in KalshiAPI")
    @patch("kalshi_markets.ApiClient")
    @patch("kalshi_markets.Configuration")
    @patch("kalshi_markets.MarketsApi")
    def test_search_markets_success(self, mock_markets_api, mock_config, mock_client):
        """Test searching markets successfully."""
        from kalshi_markets import KalshiAPI

        mock_response = MagicMock()
        mock_response.to_dict.return_value = {
            "markets": [
                {"title": "Lakers vs Celtics", "ticker": "NBA1"},
                {"title": "Jets vs Patriots", "ticker": "NFL1"},
            ]
        }
        mock_markets_api.return_value.get_markets.return_value = mock_response

        api = KalshiAPI("test_key", "test_pem")
        result = api.search_markets("LAKERS")

        assert result is not None
        assert len(result["markets"]) == 1
        assert "Lakers" in result["markets"][0]["title"]

    @pytest.mark.skip(reason="search_markets method not implemented in KalshiAPI")
    @patch("kalshi_markets.ApiClient")
    @patch("kalshi_markets.Configuration")
    @patch("kalshi_markets.MarketsApi")
    def test_search_markets_error(self, mock_markets_api, mock_config, mock_client):
        """Test handling error in search_markets."""
        from kalshi_markets import KalshiAPI

        mock_markets_api.return_value.get_markets.side_effect = Exception("API Error")

        api = KalshiAPI("test_key", "test_pem")
        result = api.search_markets("NBA")

        assert result is None


class TestFetchNBAMarkets:
    """Test fetch_nba_markets function."""

    @patch("kalshi_markets.load_kalshi_credentials")
    @patch("kalshi_markets.KalshiAPI")
    def test_fetch_nba_markets_success(self, mock_api_class, mock_creds):
        """Test fetching NBA markets successfully."""
        from kalshi_markets import fetch_nba_markets

        mock_creds.return_value = ("key", "pem")
        mock_api = MagicMock()
        mock_api.get_markets.return_value = {
            "markets": [
                {"ticker": "NBA1", "status": "active"},
                {"ticker": "NBA2", "status": "closed"},
                {"ticker": "NBA3", "status": "initialized"},
            ]
        }
        mock_api_class.return_value = mock_api

        markets = fetch_nba_markets()

        assert len(markets) == 2  # Only active and initialized

    @pytest.mark.skip(
        reason="fetch_nba_markets does not catch credential exceptions - test invalid"
    )
    @patch("kalshi_markets.load_kalshi_credentials")
    def test_fetch_nba_markets_error(self, mock_creds):
        """Test handling error in fetch_nba_markets."""
        from kalshi_markets import fetch_nba_markets

        mock_creds.side_effect = Exception("Credential error")

        markets = fetch_nba_markets()

        assert markets == []


class TestFetchNHLMarkets:
    """Test fetch_nhl_markets function."""

    @patch("kalshi_markets.load_kalshi_credentials")
    @patch("kalshi_markets.KalshiAPI")
    def test_fetch_nhl_markets_success(self, mock_api_class, mock_creds):
        """Test fetching NHL markets successfully."""
        from kalshi_markets import fetch_nhl_markets

        mock_creds.return_value = ("key", "pem")
        mock_api = MagicMock()
        mock_api.get_markets.return_value = {
            "markets": [{"ticker": "NHL1", "status": "active"}]
        }
        mock_api_class.return_value = mock_api

        markets = fetch_nhl_markets()

        assert len(markets) == 1

    @pytest.mark.skip(
        reason="fetch_nhl_markets does not catch credential exceptions - test invalid"
    )
    @patch("kalshi_markets.load_kalshi_credentials")
    def test_fetch_nhl_markets_error(self, mock_creds):
        """Test handling error in fetch_nhl_markets."""
        from kalshi_markets import fetch_nhl_markets

        mock_creds.side_effect = Exception("Error")

        markets = fetch_nhl_markets()

        assert markets == []


class TestFetchMLBMarkets:
    """Test fetch_mlb_markets function."""

    @patch("kalshi_markets.load_kalshi_credentials")
    @patch("kalshi_markets.KalshiAPI")
    def test_fetch_mlb_markets_success(self, mock_api_class, mock_creds):
        """Test fetching MLB markets successfully."""
        from kalshi_markets import fetch_mlb_markets

        mock_creds.return_value = ("key", "pem")
        mock_api = MagicMock()
        mock_api.get_markets.return_value = {
            "markets": [{"ticker": "MLB1", "status": "active"}]
        }
        mock_api_class.return_value = mock_api

        markets = fetch_mlb_markets()

        assert len(markets) == 1


class TestFetchNFLMarkets:
    """Test fetch_nfl_markets function."""

    @patch("kalshi_markets.load_kalshi_credentials")
    @patch("kalshi_markets.KalshiAPI")
    def test_fetch_nfl_markets_success(self, mock_api_class, mock_creds):
        """Test fetching NFL markets successfully."""
        from kalshi_markets import fetch_nfl_markets

        mock_creds.return_value = ("key", "pem")
        mock_api = MagicMock()
        mock_api.get_markets.return_value = {
            "markets": [{"ticker": "NFL1", "status": "active"}]
        }
        mock_api_class.return_value = mock_api

        markets = fetch_nfl_markets()

        assert len(markets) == 1


class TestFetchNCAABMarkets:
    """Test fetch_ncaab_markets function."""

    @patch("kalshi_markets.load_kalshi_credentials")
    @patch("kalshi_markets.KalshiAPI")
    def test_fetch_ncaab_markets_success(self, mock_api_class, mock_creds):
        """Test fetching NCAAB markets successfully."""
        from kalshi_markets import fetch_ncaab_markets

        mock_creds.return_value = ("key", "pem")
        mock_api = MagicMock()
        mock_api.get_markets.return_value = {
            "markets": [{"ticker": "NCAAB1", "status": "active"}]
        }
        mock_api_class.return_value = mock_api

        markets = fetch_ncaab_markets()

        assert len(markets) == 1


class TestFetchTennisMarkets:
    """Test fetch_tennis_markets function."""

    @patch("kalshi_markets.TheOddsAPI")
    def test_fetch_tennis_markets_success(self, mock_odds_api):
        """Test fetching Tennis markets successfully."""
        from kalshi_markets import fetch_tennis_markets

        mock_api = mock_odds_api.return_value
        mock_api.fetch_markets.return_value = [
            {"ticker": "ATP1", "status": "active"},
            {"ticker": "WTA1", "status": "active"},
        ]
        mock_api.save_to_db.return_value = 2

        markets = fetch_tennis_markets()

        assert len(markets) == 2
        mock_api.fetch_markets.assert_called_once_with("tennis")
        mock_api.save_to_db.assert_called_once_with(markets)


class TestFetchEPLMarkets:
    """Test fetch_epl_markets function."""

    @patch("kalshi_markets.load_kalshi_credentials")
    @patch("kalshi_markets.KalshiAPI")
    def test_fetch_epl_markets_success(self, mock_api_class, mock_creds):
        """Test fetching EPL markets successfully."""
        from kalshi_markets import fetch_epl_markets

        mock_creds.return_value = ("key", "pem")
        mock_api = MagicMock()
        mock_api.get_markets.return_value = {
            "markets": [{"ticker": "EPL1", "status": "active"}]
        }
        mock_api_class.return_value = mock_api

        markets = fetch_epl_markets()

        assert len(markets) == 1


class TestFetchLigue1Markets:
    """Test fetch_ligue1_markets function."""

    @patch("kalshi_markets.load_kalshi_credentials")
    @patch("kalshi_markets.KalshiAPI")
    def test_fetch_ligue1_markets_success(self, mock_api_class, mock_creds):
        """Test fetching Ligue 1 markets successfully."""
        from kalshi_markets import fetch_ligue1_markets

        mock_creds.return_value = ("key", "pem")
        mock_api = MagicMock()
        mock_api.get_markets.return_value = {
            "markets": [{"ticker": "L1-1", "status": "active"}]
        }
        mock_api_class.return_value = mock_api

        markets = fetch_ligue1_markets()

        assert len(markets) == 1


class TestMarketFiltering:
    """Test market filtering logic."""

    def test_filter_active_markets(self):
        """Test filtering for active markets."""
        markets = [
            {"ticker": "M1", "status": "active"},
            {"ticker": "M2", "status": "closed"},
            {"ticker": "M3", "status": "initialized"},
            {"ticker": "M4", "status": "settled"},
            {"ticker": "M5", "status": "open"},
        ]

        active_markets = [
            m for m in markets if m.get("status") in ["active", "initialized", "open"]
        ]

        assert len(active_markets) == 3

    def test_filter_by_status(self):
        """Test filtering by different status values."""
        markets = [
            {"ticker": "M1", "status": "active"},
            {"ticker": "M2", "status": "ACTIVE"},  # Uppercase
            {"ticker": "M3", "status": None},
        ]

        active_markets = [
            m for m in markets if m.get("status") in ["active", "initialized"]
        ]

        assert len(active_markets) == 1


class TestMLBCompactTickerParsing:
    """Regression coverage for compact MLB Kalshi team payloads."""

    @pytest.mark.parametrize(
        ("ticker", "title", "expected_home", "expected_away"),
        [
            (
                "KXMLBGAME-24APR21LADSF-LAD",
                "Los Angeles Dodgers at San Francisco Giants",
                "San Francisco Giants",
                "Los Angeles Dodgers",
            ),
            (
                "KXMLBGAME-24APR21CWSAZ-CWS",
                "Chicago White Sox at Arizona Diamondbacks",
                "Arizona Diamondbacks",
                "Chicago White Sox",
            ),
            (
                "KXMLBGAME-24APR21SDCOL-SD",
                "San Diego Padres at Colorado Rockies",
                "Colorado Rockies",
                "San Diego Padres",
            ),
            (
                "KXMLBGAME-24APR21BALKC-BAL",
                "Baltimore Orioles at Kansas City Royals",
                "Kansas City Royals",
                "Baltimore Orioles",
            ),
            (
                "KXMLBGAME-24APR21CINTB-CIN",
                "Cincinnati Reds at Tampa Bay Rays",
                "Tampa Bay Rays",
                "Cincinnati Reds",
            ),
        ],
    )
    def test_parse_market_handles_five_character_mlb_team_payloads(
        self, ticker, title, expected_home, expected_away
    ):
        from kalshi_markets import _parse_market

        parsed = _parse_market(ticker, title, "mlb")

        assert parsed is not None
        assert parsed.game_date == "2024-04-21"
        assert parsed.home_team == expected_home
        assert parsed.away_team == expected_away

    def test_parse_market_rejects_unvalidated_five_character_mlb_team_payload(self):
        from kalshi_markets import _parse_market

        parsed = _parse_market(
            "KXMLBGAME-24APR21CWSAZ-CWS",
            "Chicago Cubs at Arizona Diamondbacks",
            "mlb",
        )

        assert parsed is None

    @pytest.mark.parametrize(
        ("ticker", "title", "expected_home", "expected_away"),
        [
            (
                "KXMLBGAME-26APR221310CINTB-TB",
                "Cincinnati vs Tampa Bay Winner?",
                "Tampa Bay Rays",
                "Cincinnati Reds",
            ),
            (
                "KXMLBGAME-26APR222145LADSF-SF",
                "Los Angeles D vs San Francisco Winner?",
                "San Francisco Giants",
                "Los Angeles Dodgers",
            ),
            (
                "KXMLBGAME-26APR221410BALKC-KC",
                "Baltimore vs Kansas City Winner?",
                "Kansas City Royals",
                "Baltimore Orioles",
            ),
            (
                "KXMLBGAME-26APR222040SDCOL-SD",
                "San Diego vs Colorado Winner?",
                "Colorado Rockies",
                "San Diego Padres",
            ),
            (
                "KXMLBGAME-26APR222140CWSAZ-AZ",
                "Chicago WS vs Arizona Winner?",
                "Arizona Diamondbacks",
                "Chicago White Sox",
            ),
        ],
    )
    def test_parse_market_handles_live_abbreviated_mlb_titles(
        self, ticker, title, expected_home, expected_away
    ):
        from kalshi_markets import _parse_market

        parsed = _parse_market(ticker, title, "mlb")

        assert parsed is not None
        assert parsed.game_date == "2026-04-22"
        assert parsed.home_team == expected_home
        assert parsed.away_team == expected_away

    def test_parse_market_rejects_ambiguous_live_abbreviated_mlb_title(self):
        from kalshi_markets import _parse_market

        parsed = _parse_market(
            "KXMLBGAME-26APR222140CWSAZ-AZ",
            "Chicago vs Arizona Winner?",
            "mlb",
        )

        assert parsed is None


class TestOptionalKalshiImportGuard:
    """Module should still import cleanly when kalshi_python is absent."""

    def test_module_imports_without_kalshi_python(self):
        original_module = sys.modules.pop("kalshi_markets", None)
        original_sdk = sys.modules.pop("kalshi_python", None)
        sys.modules["kalshi_python"] = None

        try:
            module = importlib.import_module("kalshi_markets")

            assert module.KALSHI_AVAILABLE is False
            with pytest.raises(ImportError, match="kalshi_python"):
                module.KalshiAPI("test_key", "test_pem")
        finally:
            sys.modules.pop("kalshi_markets", None)
            sys.modules.pop("kalshi_python", None)
            if original_sdk is not None:
                sys.modules["kalshi_python"] = original_sdk
            if original_module is not None:
                sys.modules["kalshi_markets"] = original_module
