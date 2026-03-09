import unittest
import pandas as pd
from unittest.mock import MagicMock, patch
import sys
import os
from datetime import datetime

# Add parent directory to path to import dashboard_app
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "../dashboard"))

# Mock streamlit before importing dashboard_app
st = MagicMock()


def cache_decorator(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        return args[0]
    return lambda f: f


st.cache_data = cache_decorator
sys.modules["streamlit"] = st

import dashboard.dashboard_app as dashboard_app


class TestDashboardPortfolio(unittest.TestCase):
    def setUp(self):
        # Reset the mock from dashboard_app
        dashboard_app.st.reset_mock()

    @patch("dashboard.dashboard_app.default_db")
    def test_get_latest_cash_snapshot(self, mock_db):
        mock_df = pd.DataFrame(
            {"cash_balance": [1000.50], "snapshot_hour_utc": ["2026-03-02 09:00:00"]}
        )
        mock_db.fetch_df.return_value = mock_df

        result = dashboard_app._get_latest_cash_snapshot()

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["cash_balance"], 1000.50)
        mock_db.fetch_df.assert_called_once()

    @patch("dashboard.dashboard_app.default_db")
    def test_get_open_positions_value(self, mock_db):
        mock_df = pd.DataFrame({"open_positions_value": [500.25]})
        mock_db.fetch_df.return_value = mock_df

        result = dashboard_app._get_open_positions_value()

        self.assertEqual(result, 500.25)
        mock_db.fetch_df.assert_called_once()

    @patch("dashboard.dashboard_app.default_db")
    def test_get_open_positions_value_empty(self, mock_db):
        mock_df = pd.DataFrame({"open_positions_value": [None]})
        mock_db.fetch_df.return_value = mock_df

        result = dashboard_app._get_open_positions_value()

        self.assertEqual(result, 0.0)

    @patch("dashboard.dashboard_app._get_latest_cash_snapshot")
    @patch("dashboard.dashboard_app._get_open_positions_value")
    def test_calculate_portfolio_value_success(self, mock_open_val, mock_cash_snap):
        mock_cash_snap.return_value = pd.DataFrame(
            {
                "cash_balance": [1000.00],
                "snapshot_hour_utc": [datetime(2026, 3, 2, 9, 0)],
            }
        )
        mock_open_val.return_value = 500.00

        result = dashboard_app._calculate_portfolio_value()

        self.assertTrue(result["success"])
        self.assertEqual(result["kalshi_balance"], 1500.00)
        self.assertEqual(result["cash_balance"], 1000.00)
        self.assertEqual(result["open_value"], 500.00)
        self.assertIn("2026-03-02 09:00 AM", result["balance_timestamp"])

    @patch("dashboard.dashboard_app._get_latest_cash_snapshot")
    @patch("dashboard.dashboard_app._get_open_positions_value")
    def test_calculate_portfolio_value_no_cash(self, mock_open_val, mock_cash_snap):
        mock_cash_snap.return_value = pd.DataFrame()
        mock_open_val.return_value = 500.00

        result = dashboard_app._calculate_portfolio_value()

        self.assertFalse(result["success"])
        self.assertIsNone(result["kalshi_balance"])


if __name__ == "__main__":
    unittest.main()
