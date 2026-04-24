import unittest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path to import dashboard_app
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "../dashboard"))

# Mock streamlit before importing dashboard_app
st = MagicMock()


# Handle both @st.cache_data and @st.cache_data(...)
def cache_decorator(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        return args[0]
    return lambda f: f


st.cache_data = cache_decorator
sys.modules["streamlit"] = st

import dashboard.dashboard_app as dashboard_app


class TestDashboardFunctions(unittest.TestCase):
    def setUp(self):
        self.sample_games = pd.DataFrame(
            {
                "home_team": ["Team A", "Team B"],
                "away_team": ["Team C", "Team D"],
                "home_win": [1, 0],
                "home_score": [10, 5],
                "away_score": [5, 10],
                "game_date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            }
        )

    def test_get_elo_class_for_league(self):
        self.assertIsNotNone(dashboard_app._get_rating_class_for_league("NHL", "Elo"))
        self.assertIsNotNone(dashboard_app._get_rating_class_for_league("NBA", "Elo"))
        self.assertIsNone(dashboard_app._get_rating_class_for_league("INVALID", "Elo"))

    def test_get_glicko2_class_for_league(self):
        self.assertIsNotNone(
            dashboard_app._get_rating_class_for_league("NHL", "Glicko-2")
        )
        self.assertIsNotNone(
            dashboard_app._get_rating_class_for_league("NBA", "Glicko-2")
        )
        self.assertIsNone(
            dashboard_app._get_rating_class_for_league("INVALID", "Glicko-2")
        )

    @patch("dashboard.dashboard_app._get_rating_class_for_league")
    def test_run_glicko2_simulation_empty(self, mock_get_class):
        df = pd.DataFrame()
        config = dashboard_app.SimulationConfig(league="NHL", home_adv=100.0, tau=0.5)
        result = dashboard_app.run_glicko2_simulation(df, config)
        self.assertTrue(result.empty)
        mock_get_class.assert_not_called()

    @patch("dashboard.dashboard_app._get_rating_class_for_league")
    def test_run_glicko2_simulation_invalid_league(self, mock_get_class):
        mock_get_class.return_value = None
        config = dashboard_app.SimulationConfig(
            league="INVALID", home_adv=100.0, tau=0.5
        )
        result = dashboard_app.run_glicko2_simulation(self.sample_games, config)
        self.assertEqual(len(result), len(self.sample_games))
        self.assertNotIn("glicko2_prob", result.columns)

    def test_run_glicko2_simulation_real(self):
        # This will test the actual integration if the classes are available
        # If imports failed, they will be None and _get_rating_class_for_league will return None
        config = dashboard_app.SimulationConfig(league="NHL", home_adv=100.0, tau=0.5)
        result = dashboard_app.run_glicko2_simulation(self.sample_games, config)

        # Check if glicko2_prob was added (it should be if NHLGlicko2Rating is available)
        if dashboard_app.NHLGlicko2Rating:
            self.assertIn("glicko2_prob", result.columns)
            self.assertEqual(len(result["glicko2_prob"]), 2)
            self.assertTrue(all(0 <= p <= 1 for p in result["glicko2_prob"]))
        else:
            self.assertNotIn("glicko2_prob", result.columns)

    def test_assign_deciles(self):
        df = pd.DataFrame(
            {"elo_prob": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]}
        )
        result = dashboard_app._assign_deciles(df)
        self.assertIn("decile", result.columns)
        self.assertEqual(len(result["decile"].unique()), 10)

    def test_calculate_deciles(self):
        df = pd.DataFrame({"elo_prob": [0.1, 0.9], "home_win": [0, 1]})
        result = dashboard_app.calculate_deciles(df)
        self.assertFalse(result.empty)
        self.assertEqual(len(result), 2)
        self.assertIn("Decile", result.columns)
        self.assertIn("ROI (-110)", result.columns)

    def test_calculate_decile_probability_roi_matrix(self):
        df = pd.DataFrame({"elo_prob": [0.1, 0.9], "home_win": [0, 1]})
        result = dashboard_app.calculate_decile_probability_roi_matrix(df)
        self.assertFalse(result.empty)
        self.assertIn("50¢", result.columns)
        self.assertEqual(len(result), 2)

    @patch("dashboard.dashboard_app.default_db")
    def test_load_data(self, mock_db):
        mock_db.fetch_df.return_value = self.sample_games
        result = dashboard_app.load_data("NHL")
        self.assertFalse(result.empty)
        self.assertEqual(len(result), 2)
        mock_db.fetch_df.assert_called_once()


if __name__ == "__main__":
    unittest.main()
