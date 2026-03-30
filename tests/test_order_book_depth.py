"""Tests for order book depth analysis — get_order_book_depth() and analyze_market_impact().

TDD Red Phase: defines expected behavior before implementation.
"""

import pytest
from unittest.mock import MagicMock, patch
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_kalshi_api():
    """Return a KalshiAPI instance with a mocked markets_api."""
    from plugins.kalshi_markets import KalshiAPI

    api = object.__new__(KalshiAPI)
    api.markets_api = MagicMock()
    api._logged_market_data = True  # suppress sample log
    return api


def _make_raw_orderbook_response(yes_levels=None, no_levels=None):
    """Build a fake raw HTTP response with orderbook_fp payload."""
    yes_levels = yes_levels or []
    no_levels = no_levels or []
    payload = {
        "orderbook_fp": {
            "yes_dollars": yes_levels,
            "no_dollars": no_levels,
        }
    }
    resp = MagicMock()
    resp.raw_data = json.dumps(payload).encode()
    return resp


# ---------------------------------------------------------------------------
# Tests for KalshiAPI.get_order_book_depth()
# ---------------------------------------------------------------------------


class TestGetOrderBookDepth:
    """Tests for KalshiAPI.get_order_book_depth()."""

    def test_empty_order_book_returns_zeroed_dict(self):
        """Empty yes/no levels should produce zero depth and 0.0 prices."""
        api = _make_kalshi_api()
        api.markets_api.get_market_orderbook_with_http_info.return_value = (
            _make_raw_orderbook_response([], [])
        )

        result = api.get_order_book_depth("TEST-TICKER")

        assert result["yes_levels"] == []
        assert result["no_levels"] == []
        assert result["yes_top_of_book"] == 0.0
        assert result["no_top_of_book"] == 0.0
        assert result["total_yes_depth_usd"] == 0.0
        assert result["total_no_depth_usd"] == 0.0
        assert result["market_impact_pct"] == 0.0

    def test_full_order_book_parses_all_levels(self):
        """Multiple yes/no levels should be parsed with price descending."""
        api = _make_kalshi_api()
        # yes_dollars is ascending (lowest price first), so [-1] is the best ask
        yes_levels_raw = [["0.30", "50"], ["0.50", "100"], ["0.70", "200"]]
        no_levels_raw = [["0.20", "30"], ["0.40", "80"]]
        api.markets_api.get_market_orderbook_with_http_info.return_value = (
            _make_raw_orderbook_response(yes_levels_raw, no_levels_raw)
        )

        result = api.get_order_book_depth("TEST-TICKER")

        # Should be sorted descending by price
        assert result["yes_levels"][0]["price"] == pytest.approx(0.70)
        assert result["yes_levels"][-1]["price"] == pytest.approx(0.30)
        assert len(result["yes_levels"]) == 3

        # Top-of-book = highest price level (last in ascending raw = first after desc sort)
        assert result["yes_top_of_book"] == pytest.approx(0.70)
        assert result["no_top_of_book"] == pytest.approx(0.40)

        # Total depth: sum of (price * quantity) for each level
        # yes: 0.30*50 + 0.50*100 + 0.70*200 = 15 + 50 + 140 = 205
        assert result["total_yes_depth_usd"] == pytest.approx(205.0)
        # no: 0.20*30 + 0.40*80 = 6 + 32 = 38
        assert result["total_no_depth_usd"] == pytest.approx(38.0)

    def test_market_impact_pct_calculation(self):
        """market_impact_pct = (bet_size / total_yes_depth_usd) * 100."""
        api = _make_kalshi_api()
        # Total yes depth = 0.50 * 2000 = 1000 USD
        yes_levels_raw = [["0.50", "2000"]]
        api.markets_api.get_market_orderbook_with_http_info.return_value = (
            _make_raw_orderbook_response(yes_levels_raw, [])
        )

        result = api.get_order_book_depth("TEST-TICKER", bet_size=10.0)

        # 10 / 1000 * 100 = 1.0%
        assert result["market_impact_pct"] == pytest.approx(1.0)

    def test_api_error_returns_empty_dict(self):
        """When API raises an exception, return empty dict (graceful degradation)."""
        api = _make_kalshi_api()
        api.markets_api.get_market_orderbook_with_http_info.side_effect = Exception(
            "Network error"
        )

        result = api.get_order_book_depth("TEST-TICKER")

        assert result == {}

    def test_no_early_exit_guard(self):
        """get_order_book_depth does NOT skip when yes_ask already populated."""
        api = _make_kalshi_api()
        # Single level with data
        yes_levels_raw = [["0.60", "500"]]
        api.markets_api.get_market_orderbook_with_http_info.return_value = (
            _make_raw_orderbook_response(yes_levels_raw, [])
        )

        # Even if we had set yes_ask before, this method still calls the API
        result = api.get_order_book_depth("TEST-TICKER")

        assert api.markets_api.get_market_orderbook_with_http_info.call_count == 1
        assert result["yes_top_of_book"] == pytest.approx(0.60)

    def test_partial_levels_only_yes(self):
        """Only yes levels present; no_levels and no_top_of_book should be defaults."""
        api = _make_kalshi_api()
        yes_levels_raw = [["0.55", "300"]]
        api.markets_api.get_market_orderbook_with_http_info.return_value = (
            _make_raw_orderbook_response(yes_levels_raw, [])
        )

        result = api.get_order_book_depth("TEST-TICKER")

        assert result["no_levels"] == []
        assert result["no_top_of_book"] == 0.0
        assert result["total_no_depth_usd"] == 0.0
        assert result["yes_top_of_book"] == pytest.approx(0.55)

    def test_yes_levels_sorted_descending(self):
        """Returned yes_levels must be sorted by price descending."""
        api = _make_kalshi_api()
        yes_levels_raw = [["0.10", "10"], ["0.90", "90"], ["0.50", "50"]]
        api.markets_api.get_market_orderbook_with_http_info.return_value = (
            _make_raw_orderbook_response(yes_levels_raw, [])
        )

        result = api.get_order_book_depth("TEST-TICKER")

        prices = [lvl["price"] for lvl in result["yes_levels"]]
        assert prices == sorted(prices, reverse=True)

    def test_level_quantity_is_float(self):
        """Each level's quantity should be a float."""
        api = _make_kalshi_api()
        yes_levels_raw = [["0.40", "150"]]
        api.markets_api.get_market_orderbook_with_http_info.return_value = (
            _make_raw_orderbook_response(yes_levels_raw, [])
        )

        result = api.get_order_book_depth("TEST-TICKER")

        assert isinstance(result["yes_levels"][0]["quantity"], float)
        assert result["yes_levels"][0]["quantity"] == pytest.approx(150.0)


# ---------------------------------------------------------------------------
# Tests for analyze_market_impact()
# ---------------------------------------------------------------------------


class TestAnalyzeMarketImpact:
    """Tests for pnl_diagnostic.analyze_market_impact()."""

    def _make_depth_result(self, total_yes_usd: float, impact_pct: float) -> dict:
        return {
            "yes_levels": [],
            "no_levels": [],
            "yes_top_of_book": 0.5,
            "no_top_of_book": 0.5,
            "total_yes_depth_usd": total_yes_usd,
            "total_no_depth_usd": total_yes_usd,
            "market_impact_pct": impact_pct,
        }

    def test_negligible_verdict_when_max_impact_below_1pct(self):
        """If all tickers have impact < 1%, verdict must be NEGLIGIBLE."""
        from plugins.pnl_diagnostic import analyze_market_impact

        sample_tickers = ["T1", "T2", "T3"]
        depth_results = {
            "T1": self._make_depth_result(5000.0, 0.2),
            "T2": self._make_depth_result(3000.0, 0.33),
            "T3": self._make_depth_result(2000.0, 0.5),
        }

        def mock_depth(ticker, bet_size=10.0):
            return depth_results[ticker]

        with patch(
            "plugins.pnl_diagnostic._get_kalshi_api_instance"
        ) as mock_api_factory:
            mock_api = MagicMock()
            mock_api.get_order_book_depth.side_effect = mock_depth
            mock_api_factory.return_value = mock_api

            result = analyze_market_impact(sample_tickers=sample_tickers, bet_size=10.0)

        assert result["verdict"] == "NEGLIGIBLE"
        assert result["tickers_analyzed"] == 3

    def test_monitor_verdict_when_max_impact_between_1_and_5pct(self):
        """If max impact is between 1-5%, verdict must be MONITOR."""
        from plugins.pnl_diagnostic import analyze_market_impact

        sample_tickers = ["T1", "T2"]
        depth_results = {
            "T1": self._make_depth_result(1000.0, 1.0),
            "T2": self._make_depth_result(500.0, 2.0),
        }

        def mock_depth(ticker, bet_size=10.0):
            return depth_results[ticker]

        with patch(
            "plugins.pnl_diagnostic._get_kalshi_api_instance"
        ) as mock_api_factory:
            mock_api = MagicMock()
            mock_api.get_order_book_depth.side_effect = mock_depth
            mock_api_factory.return_value = mock_api

            result = analyze_market_impact(sample_tickers=sample_tickers, bet_size=10.0)

        assert result["verdict"] == "MONITOR"

    def test_significant_verdict_when_max_impact_above_5pct(self):
        """If max impact > 5%, verdict must be SIGNIFICANT."""
        from plugins.pnl_diagnostic import analyze_market_impact

        sample_tickers = ["T1"]
        depth_results = {
            "T1": self._make_depth_result(100.0, 10.0),
        }

        def mock_depth(ticker, bet_size=10.0):
            return depth_results[ticker]

        with patch(
            "plugins.pnl_diagnostic._get_kalshi_api_instance"
        ) as mock_api_factory:
            mock_api = MagicMock()
            mock_api.get_order_book_depth.side_effect = mock_depth
            mock_api_factory.return_value = mock_api

            result = analyze_market_impact(sample_tickers=sample_tickers, bet_size=10.0)

        assert result["verdict"] == "SIGNIFICANT"

    def test_unknown_verdict_when_api_unavailable(self):
        """When _get_kalshi_api_instance returns None, verdict should be UNKNOWN."""
        from plugins.pnl_diagnostic import analyze_market_impact

        with patch(
            "plugins.pnl_diagnostic._get_kalshi_api_instance"
        ) as mock_api_factory:
            mock_api_factory.return_value = None

            result = analyze_market_impact(sample_tickers=["T1"], bet_size=10.0)

        assert result["verdict"] == "UNKNOWN"
        assert result["median_market_impact_pct"] is None

    def test_empty_tickers_returns_unknown(self):
        """No tickers available → verdict UNKNOWN."""
        from plugins.pnl_diagnostic import analyze_market_impact

        with patch(
            "plugins.pnl_diagnostic._get_kalshi_api_instance"
        ) as mock_api_factory:
            mock_api = MagicMock()
            mock_api_factory.return_value = mock_api

            result = analyze_market_impact(sample_tickers=[], bet_size=10.0)

        assert result["verdict"] == "UNKNOWN"
        assert result["tickers_analyzed"] == 0

    def test_api_error_per_ticker_skipped_gracefully(self):
        """Tickers where get_order_book_depth returns {} should be skipped."""
        from plugins.pnl_diagnostic import analyze_market_impact

        def mock_depth(ticker, bet_size=10.0):
            if ticker == "GOOD":
                return {
                    "yes_levels": [],
                    "no_levels": [],
                    "yes_top_of_book": 0.5,
                    "no_top_of_book": 0.5,
                    "total_yes_depth_usd": 2000.0,
                    "total_no_depth_usd": 2000.0,
                    "market_impact_pct": 0.5,
                }
            return {}  # API error for BAD ticker

        with patch(
            "plugins.pnl_diagnostic._get_kalshi_api_instance"
        ) as mock_api_factory:
            mock_api = MagicMock()
            mock_api.get_order_book_depth.side_effect = mock_depth
            mock_api_factory.return_value = mock_api

            result = analyze_market_impact(
                sample_tickers=["GOOD", "BAD"], bet_size=10.0
            )

        assert result["tickers_analyzed"] == 1  # Only GOOD counted

    def test_result_keys_present(self):
        """Result dict must include all required keys."""
        from plugins.pnl_diagnostic import analyze_market_impact

        def mock_depth(ticker, bet_size=10.0):
            return {
                "yes_levels": [],
                "no_levels": [],
                "yes_top_of_book": 0.5,
                "no_top_of_book": 0.5,
                "total_yes_depth_usd": 1000.0,
                "total_no_depth_usd": 1000.0,
                "market_impact_pct": 1.0,
            }

        with patch(
            "plugins.pnl_diagnostic._get_kalshi_api_instance"
        ) as mock_api_factory:
            mock_api = MagicMock()
            mock_api.get_order_book_depth.side_effect = mock_depth
            mock_api_factory.return_value = mock_api

            result = analyze_market_impact(sample_tickers=["T1"], bet_size=10.0)

        required_keys = {
            "tickers_analyzed",
            "median_yes_depth_usd",
            "median_market_impact_pct",
            "max_market_impact_pct",
            "verdict",
            "bet_size_analyzed",
            "per_ticker",
        }
        assert required_keys.issubset(result.keys())
        assert result["bet_size_analyzed"] == 10.0

    def test_bet_size_param_forwarded_to_depth_call(self):
        """bet_size parameter must be forwarded to get_order_book_depth()."""
        from plugins.pnl_diagnostic import analyze_market_impact

        received_bet_sizes = []

        def mock_depth(ticker, bet_size=10.0):
            received_bet_sizes.append(bet_size)
            return {
                "yes_levels": [],
                "no_levels": [],
                "yes_top_of_book": 0.5,
                "no_top_of_book": 0.5,
                "total_yes_depth_usd": 500.0,
                "total_no_depth_usd": 500.0,
                "market_impact_pct": 2.0,
            }

        with patch(
            "plugins.pnl_diagnostic._get_kalshi_api_instance"
        ) as mock_api_factory:
            mock_api = MagicMock()
            mock_api.get_order_book_depth.side_effect = mock_depth
            mock_api_factory.return_value = mock_api

            analyze_market_impact(sample_tickers=["T1"], bet_size=25.0)

        assert 25.0 in received_bet_sizes


# ---------------------------------------------------------------------------
# Verdict threshold edge cases
# ---------------------------------------------------------------------------


class TestVerdictThresholds:
    """Boundary tests for NEGLIGIBLE / MONITOR / SIGNIFICANT thresholds."""

    def _run_with_impact(self, impact_pct: float) -> str:
        from plugins.pnl_diagnostic import analyze_market_impact

        def mock_depth(ticker, bet_size=10.0):
            return {
                "yes_levels": [],
                "no_levels": [],
                "yes_top_of_book": 0.5,
                "no_top_of_book": 0.5,
                "total_yes_depth_usd": 1000.0,
                "total_no_depth_usd": 1000.0,
                "market_impact_pct": impact_pct,
            }

        with patch(
            "plugins.pnl_diagnostic._get_kalshi_api_instance"
        ) as mock_api_factory:
            mock_api = MagicMock()
            mock_api.get_order_book_depth.side_effect = mock_depth
            mock_api_factory.return_value = mock_api
            result = analyze_market_impact(sample_tickers=["T1"], bet_size=10.0)

        return result["verdict"]

    def test_exactly_zero_impact_is_negligible(self):
        assert self._run_with_impact(0.0) == "NEGLIGIBLE"

    def test_just_below_1pct_is_negligible(self):
        assert self._run_with_impact(0.999) == "NEGLIGIBLE"

    def test_exactly_1pct_is_monitor(self):
        assert self._run_with_impact(1.0) == "MONITOR"

    def test_just_below_5pct_is_monitor(self):
        assert self._run_with_impact(4.999) == "MONITOR"

    def test_exactly_5pct_is_significant(self):
        assert self._run_with_impact(5.0) == "SIGNIFICANT"

    def test_above_5pct_is_significant(self):
        assert self._run_with_impact(50.0) == "SIGNIFICANT"
