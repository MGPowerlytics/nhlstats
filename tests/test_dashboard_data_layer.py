"""Integration tests for dashboard data layer functions.

Uses the test SQLite database from conftest.py.
Ensures each data function runs without error and returns expected types.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.data_layer import (
    get_portfolio_summary,
    get_calibration_data,
    get_data_quality_report,
)


class TestPortfolioSummary:
    def test_returns_dict_with_required_keys(self):
        result = get_portfolio_summary()
        assert isinstance(result, dict)
        required = ["portfolio_value", "daily_pnl", "open_bets_count",
                    "total_exposure", "win_rate", "total_bets", "settled_count"]
        for key in required:
            assert key in result, f"Missing key: {key}"

    def test_portfolio_value_is_float(self):
        result = get_portfolio_summary()
        assert isinstance(result["portfolio_value"], (int, float))

    def test_counts_are_non_negative(self):
        result = get_portfolio_summary()
        assert result["open_bets_count"] >= 0
        assert result["total_bets"] >= 0
        assert result["settled_count"] >= 0

    def test_win_rate_in_range(self):
        result = get_portfolio_summary()
        assert 0.0 <= result["win_rate"] <= 1.0


class TestCalibrationData:
    def test_returns_dict_with_required_keys(self):
        result = get_calibration_data()
        assert isinstance(result, dict)
        for key in ["bets", "buckets", "by_sport"]:
            assert key in result

    def test_bets_is_list(self):
        result = get_calibration_data()
        assert isinstance(result["bets"], list)

    def test_buckets_has_eight_entries(self):
        result = get_calibration_data()
        assert len(result["buckets"]) == 8


class TestDataQualityReport:
    def test_returns_dict_with_required_keys(self):
        result = get_data_quality_report()
        assert isinstance(result, dict)
        for key in ["overall_health", "sports"]:
            assert key in result

    def test_overall_health_is_int_between_0_and_100(self):
        result = get_data_quality_report()
        assert isinstance(result["overall_health"], int)
        assert 0 <= result["overall_health"] <= 100

    def test_sports_is_list(self):
        result = get_data_quality_report()
        assert isinstance(result["sports"], list)


class TestDashboardImports:
    """Verify all page modules import cleanly."""

    def test_import_app(self):
        from dashboard import app  # noqa: F401

    def test_import_data_layer(self):
        from dashboard import data_layer  # noqa: F401

    def test_import_bet_detail(self):
        from dashboard.pages import bet_detail  # noqa: F401

    def test_import_portfolio(self):
        from dashboard.pages import portfolio  # noqa: F401

    def test_import_live_markets(self):
        from dashboard.pages import live_markets  # noqa: F401

    def test_import_rankings(self):
        from dashboard.pages import rankings  # noqa: F401

    def test_import_calibration(self):
        from dashboard.pages import calibration  # noqa: F401

    def test_import_data_quality(self):
        from dashboard.pages import data_quality  # noqa: F401
