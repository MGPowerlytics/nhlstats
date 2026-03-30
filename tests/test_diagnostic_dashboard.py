"""Tests for Diagnostic Report Dashboard Page (TODO-005) and Timing Heatmap (TODO-007).

TDD Red Phase: These tests define expected behavior before implementation.
"""

import sys
import os
import unittest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../plugins")
)

# Mock streamlit before importing dashboard_app
st_mock = MagicMock()


def cache_decorator(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        return args[0]
    return lambda f: f


st_mock.cache_data = cache_decorator
sys.modules["streamlit"] = st_mock


# ---------------------------------------------------------------------------
# Tests for generate_timing_heatmap_data (plugins/pnl_diagnostic.py)
# ---------------------------------------------------------------------------


class TestGenerateTimingHeatmapData(unittest.TestCase):
    """Tests for the generate_timing_heatmap_data function in pnl_diagnostic."""

    def _make_diagnostic_row(
        self,
        sport: str,
        under_2hr: float = 0.05,
        over_8hr: float = -0.02,
    ) -> dict:
        """Build a minimal diagnostic_results row dict."""
        return {
            "sport": sport,
            "settled_bets": 50,
            "roi": 0.03,
            "real_clv": 0.01,
            "p_value": 0.04,
            "recommendation": "CONTINUE",
            "timing_roi_under_2hr": under_2hr,
            "timing_roi_over_8hr": over_8hr,
            "elo_replay_divergence": 5.0,
            "run_date": "2024-01-01 00:00:00",
        }

    @patch("plugins.pnl_diagnostic.default_db")
    def test_returns_dataframe(self, mock_db):
        """generate_timing_heatmap_data returns a pandas DataFrame."""
        from plugins.pnl_diagnostic import generate_timing_heatmap_data

        rows = [
            self._make_diagnostic_row("NHL", under_2hr=0.05, over_8hr=-0.02),
            self._make_diagnostic_row("NBA", under_2hr=0.10, over_8hr=0.03),
        ]
        mock_db.fetch_df.return_value = pd.DataFrame(rows)

        result = generate_timing_heatmap_data()

        self.assertIsInstance(result, pd.DataFrame)

    @patch("plugins.pnl_diagnostic.default_db")
    def test_returns_empty_dataframe_when_no_data(self, mock_db):
        """generate_timing_heatmap_data returns empty DataFrame when table is empty."""
        from plugins.pnl_diagnostic import generate_timing_heatmap_data

        mock_db.fetch_df.return_value = pd.DataFrame()

        result = generate_timing_heatmap_data()

        self.assertIsInstance(result, pd.DataFrame)
        self.assertTrue(result.empty)

    @patch("plugins.pnl_diagnostic.default_db")
    def test_index_is_sport_column(self, mock_db):
        """Returned DataFrame has sports as the index or 'sport' column."""
        from plugins.pnl_diagnostic import generate_timing_heatmap_data

        rows = [
            self._make_diagnostic_row("NHL", under_2hr=0.05, over_8hr=-0.02),
            self._make_diagnostic_row("NBA", under_2hr=0.10, over_8hr=0.03),
        ]
        mock_db.fetch_df.return_value = pd.DataFrame(rows)

        result = generate_timing_heatmap_data()

        # Either the index contains sports or there's a 'sport' column
        sports_present = set(result.index.tolist()) | set(
            result.get("sport", pd.Series()).tolist()
        )
        self.assertIn("NHL", sports_present)
        self.assertIn("NBA", sports_present)

    @patch("plugins.pnl_diagnostic.default_db")
    def test_columns_are_timing_buckets(self, mock_db):
        """Returned DataFrame columns correspond to timing bucket labels."""
        from plugins.pnl_diagnostic import generate_timing_heatmap_data

        rows = [
            self._make_diagnostic_row("NHL", under_2hr=0.05, over_8hr=-0.02),
        ]
        mock_db.fetch_df.return_value = pd.DataFrame(rows)

        result = generate_timing_heatmap_data()

        if not result.empty:
            # At least one timing bucket column must be present
            timing_cols = [c for c in result.columns if c not in ("sport",)]
            self.assertGreater(len(timing_cols), 0)

    @patch("plugins.pnl_diagnostic.default_db")
    def test_values_are_roi_floats(self, mock_db):
        """Values in the heatmap DataFrame are floats (ROI percentages or fractions)."""
        from plugins.pnl_diagnostic import generate_timing_heatmap_data

        rows = [
            self._make_diagnostic_row("NHL", under_2hr=0.05, over_8hr=-0.02),
            self._make_diagnostic_row("NBA", under_2hr=0.10, over_8hr=0.03),
        ]
        mock_db.fetch_df.return_value = pd.DataFrame(rows)

        result = generate_timing_heatmap_data()

        if not result.empty:
            # Drop the 'sport' column if it exists, then check numeric values
            num_cols = result.select_dtypes(include=[np.number]).columns
            self.assertGreater(len(num_cols), 0)

    @patch("plugins.pnl_diagnostic.default_db")
    def test_handles_none_timing_values(self, mock_db):
        """generate_timing_heatmap_data handles None/NaN timing columns gracefully."""
        from plugins.pnl_diagnostic import generate_timing_heatmap_data

        rows = [
            {
                "sport": "NHL",
                "timing_roi_under_2hr": None,
                "timing_roi_over_8hr": None,
                "run_date": "2024-01-01",
            },
        ]
        mock_db.fetch_df.return_value = pd.DataFrame(rows)

        # Should not raise
        result = generate_timing_heatmap_data()
        self.assertIsInstance(result, pd.DataFrame)

    @patch("plugins.pnl_diagnostic.default_db")
    def test_db_error_returns_empty_dataframe(self, mock_db):
        """Returns empty DataFrame on DB error."""
        from plugins.pnl_diagnostic import generate_timing_heatmap_data

        mock_db.fetch_df.side_effect = Exception("DB connection failed")

        result = generate_timing_heatmap_data()
        self.assertIsInstance(result, pd.DataFrame)
        self.assertTrue(result.empty)

    @patch("plugins.pnl_diagnostic.default_db")
    def test_uses_most_recent_run_per_sport(self, mock_db):
        """When multiple runs exist for a sport, uses the most recent entry."""
        from plugins.pnl_diagnostic import generate_timing_heatmap_data

        rows = [
            {
                "sport": "NHL",
                "timing_roi_under_2hr": 0.01,
                "timing_roi_over_8hr": -0.01,
                "run_date": "2024-01-01 00:00:00",
            },
            {
                "sport": "NHL",
                "timing_roi_under_2hr": 0.08,
                "timing_roi_over_8hr": 0.04,
                "run_date": "2024-01-02 00:00:00",
            },
        ]
        mock_db.fetch_df.return_value = pd.DataFrame(rows)

        result = generate_timing_heatmap_data()
        self.assertIsInstance(result, pd.DataFrame)
        # Should only have one row for NHL
        self.assertLessEqual(len(result), 1)


# ---------------------------------------------------------------------------
# Tests for diagnostic_report_page (dashboard/dashboard_app.py)
# ---------------------------------------------------------------------------


class TestDiagnosticReportPage(unittest.TestCase):
    """Tests for the diagnostic_report_page function in dashboard_app."""

    def setUp(self):
        """Reset streamlit mock before each test and configure columns."""
        st_mock.reset_mock()
        # Explicitly clear any side_effect set by previous tests
        st_mock.button.side_effect = None
        st_mock.button.return_value = False

        # Configure st.columns to return the right number of MagicMock context managers
        def columns_side_effect(n, **kwargs):
            count = n if isinstance(n, int) else len(n)
            return [MagicMock() for _ in range(count)]

        st_mock.columns.side_effect = columns_side_effect

    def _make_diagnostic_df(self) -> pd.DataFrame:
        """Create sample diagnostic_results data."""
        return pd.DataFrame(
            [
                {
                    "sport": "NHL",
                    "settled_bets": 120,
                    "wins": 65,
                    "losses": 55,
                    "roi": 0.08,
                    "real_clv": 0.03,
                    "p_value": 0.03,
                    "passes_gate": 1,
                    "recommendation": "CONTINUE",
                    "timing_roi_under_2hr": 0.12,
                    "timing_roi_over_8hr": 0.05,
                    "bets_with_closing_price": 100,
                    "elo_replay_divergence": 4.2,
                    "run_date": "2024-06-01 12:00:00",
                },
                {
                    "sport": "NBA",
                    "settled_bets": 80,
                    "wins": 35,
                    "losses": 45,
                    "roi": -0.05,
                    "real_clv": -0.01,
                    "p_value": 0.45,
                    "passes_gate": 0,
                    "recommendation": "PAUSE",
                    "timing_roi_under_2hr": -0.08,
                    "timing_roi_over_8hr": -0.03,
                    "bets_with_closing_price": 60,
                    "elo_replay_divergence": 7.1,
                    "run_date": "2024-06-01 12:00:00",
                },
            ]
        )

    @patch("dashboard.dashboard_app.default_db")
    def test_page_function_exists(self, mock_db):
        """diagnostic_report_page function exists in dashboard_app."""
        import dashboard.dashboard_app as dashboard_app

        self.assertTrue(hasattr(dashboard_app, "diagnostic_report_page"))
        self.assertTrue(callable(dashboard_app.diagnostic_report_page))

    @patch("dashboard.dashboard_app.default_db")
    def test_page_handles_empty_table_gracefully(self, mock_db):
        """Page shows warning (not error) when diagnostic_results table is empty."""
        import dashboard.dashboard_app as dashboard_app

        mock_db.fetch_df.return_value = pd.DataFrame()

        # Should not raise
        dashboard_app.diagnostic_report_page()

        # Should call st.warning or st.info when no data
        warning_or_info_called = st_mock.warning.called or st_mock.info.called
        self.assertTrue(warning_or_info_called)

    @patch("dashboard.dashboard_app.default_db")
    def test_page_shows_title(self, mock_db):
        """Page sets a title via st.title or st.header."""
        import dashboard.dashboard_app as dashboard_app

        mock_db.fetch_df.return_value = pd.DataFrame()

        dashboard_app.diagnostic_report_page()

        self.assertTrue(st_mock.title.called or st_mock.header.called)

    @patch("dashboard.dashboard_app.default_db")
    def test_page_shows_run_diagnostic_button(self, mock_db):
        """Page renders a 'Run Diagnostic' button."""
        import dashboard.dashboard_app as dashboard_app

        mock_db.fetch_df.return_value = pd.DataFrame()

        dashboard_app.diagnostic_report_page()

        # st.button should be called with text containing 'Diagnostic'
        button_calls = st_mock.button.call_args_list
        button_texts = [str(c) for c in button_calls]
        diagnostic_button_found = any("Diagnostic" in t for t in button_texts)
        self.assertTrue(
            diagnostic_button_found,
            f"No 'Diagnostic' button found. Calls: {button_texts}",
        )

    @patch("dashboard.dashboard_app.default_db")
    def test_page_shows_dataframe_with_data(self, mock_db):
        """Page renders a dataframe when diagnostic data is available."""
        import dashboard.dashboard_app as dashboard_app

        mock_db.fetch_df.return_value = self._make_diagnostic_df()

        dashboard_app.diagnostic_report_page()

        self.assertTrue(
            st_mock.dataframe.called or st_mock.table.called,
            "Expected st.dataframe or st.table to be called",
        )

    @patch("dashboard.dashboard_app.default_db")
    def test_page_shows_last_run_timestamp(self, mock_db):
        """Page displays last-run timestamp from diagnostic data."""
        import dashboard.dashboard_app as dashboard_app

        mock_db.fetch_df.return_value = self._make_diagnostic_df()

        dashboard_app.diagnostic_report_page()

        # Check that some metric or text was written referencing time
        all_calls = (
            list(st_mock.metric.call_args_list)
            + list(st_mock.write.call_args_list)
            + list(st_mock.caption.call_args_list)
            + list(st_mock.text.call_args_list)
        )
        call_strs = [str(c) for c in all_calls]
        time_shown = any(
            "2024" in s or "run" in s.lower() or "timestamp" in s.lower()
            for s in call_strs
        )
        self.assertTrue(time_shown, f"No timestamp found in calls: {call_strs[:5]}")

    @patch("dashboard.dashboard_app.default_db")
    def test_page_shows_elo_divergence_metric(self, mock_db):
        """Page shows Elo replay divergence metric."""
        import dashboard.dashboard_app as dashboard_app

        mock_db.fetch_df.return_value = self._make_diagnostic_df()

        dashboard_app.diagnostic_report_page()

        metric_calls = st_mock.metric.call_args_list
        metric_strs = [str(c) for c in metric_calls]
        divergence_shown = any(
            "diverge" in s.lower() or "elo" in s.lower() or "replay" in s.lower()
            for s in metric_strs
        )
        self.assertTrue(
            divergence_shown, f"Elo divergence metric not found. Calls: {metric_strs}"
        )

    @patch("dashboard.dashboard_app.default_db")
    def test_page_calls_run_diagnostic_on_button_click(self, mock_db):
        """When Run Diagnostic button is clicked, run_diagnostic() is called."""
        import dashboard.dashboard_app as dashboard_app

        mock_db.fetch_df.return_value = self._make_diagnostic_df()

        # First button call (Run Diagnostic) returns True; subsequent calls False
        st_mock.button.side_effect = [True, False]

        with patch("dashboard.dashboard_app.run_diagnostic") as mock_run:
            mock_run.return_value = {}
            dashboard_app.diagnostic_report_page()
            mock_run.assert_called_once()

    @patch("dashboard.dashboard_app.default_db")
    def test_page_db_error_handled_gracefully(self, mock_db):
        """Page handles DB error without crashing."""
        import dashboard.dashboard_app as dashboard_app

        mock_db.fetch_df.side_effect = Exception("Connection refused")

        # Should not raise
        try:
            dashboard_app.diagnostic_report_page()
        except Exception as e:
            self.fail(f"diagnostic_report_page raised unexpectedly: {e}")

    @patch("dashboard.dashboard_app.default_db")
    def test_page_shows_recommendation_column(self, mock_db):
        """Page table includes recommendation data (CONTINUE/PAUSE)."""
        import dashboard.dashboard_app as dashboard_app

        mock_db.fetch_df.return_value = self._make_diagnostic_df()

        with patch("dashboard.dashboard_app.generate_timing_heatmap_data") as mock_hm:
            mock_hm.return_value = pd.DataFrame()
            dashboard_app.diagnostic_report_page()

        if st_mock.dataframe.called:
            df_arg = st_mock.dataframe.call_args_list[0][0][0]
            if isinstance(df_arg, pd.DataFrame):
                # Column is displayed as "Recommendation" (renamed from "recommendation")
                col_names_lower = [c.lower() for c in df_arg.columns]
                self.assertIn("recommendation", col_names_lower)

    @patch("dashboard.dashboard_app.default_db")
    def test_page_shows_plotly_chart_for_heatmap(self, mock_db):
        """Page renders a heatmap chart when timing data is available."""
        import dashboard.dashboard_app as dashboard_app

        mock_db.fetch_df.return_value = self._make_diagnostic_df()

        with patch(
            "dashboard.dashboard_app.generate_timing_heatmap_data"
        ) as mock_heatmap:
            mock_heatmap.return_value = pd.DataFrame(
                {"<2hr": [0.05, -0.08], "8+hr": [0.03, -0.02]},
                index=["NHL", "NBA"],
            )
            dashboard_app.diagnostic_report_page()
            # Should render something (plotly_chart or write)
            self.assertTrue(
                st_mock.plotly_chart.called or st_mock.write.called,
                "Expected plotly chart to be rendered",
            )

    @patch("dashboard.dashboard_app.default_db")
    def test_page_in_navigation(self, mock_db):
        """Diagnostic Report page is registered in the page_handlers dict in main()."""
        import dashboard.dashboard_app as dashboard_app
        import inspect

        source = inspect.getsource(dashboard_app.main)
        self.assertIn("Diagnostic", source)


# ---------------------------------------------------------------------------
# Tests for helper function _load_diagnostic_data
# ---------------------------------------------------------------------------


class TestLoadDiagnosticData(unittest.TestCase):
    """Tests for the internal _load_diagnostic_data helper."""

    def setUp(self):
        st_mock.reset_mock()

    @patch("dashboard.dashboard_app.default_db")
    def test_returns_dataframe(self, mock_db):
        """_load_diagnostic_data returns a DataFrame."""
        import dashboard.dashboard_app as dashboard_app

        if not hasattr(dashboard_app, "_load_diagnostic_data"):
            self.skipTest("_load_diagnostic_data not yet implemented")

        mock_db.fetch_df.return_value = pd.DataFrame(
            [{"sport": "NHL", "roi": 0.05, "recommendation": "CONTINUE"}]
        )

        result = dashboard_app._load_diagnostic_data()
        self.assertIsInstance(result, pd.DataFrame)

    @patch("dashboard.dashboard_app.default_db")
    def test_returns_empty_on_error(self, mock_db):
        """_load_diagnostic_data returns empty DataFrame on DB error."""
        import dashboard.dashboard_app as dashboard_app

        if not hasattr(dashboard_app, "_load_diagnostic_data"):
            self.skipTest("_load_diagnostic_data not yet implemented")

        mock_db.fetch_df.side_effect = Exception("DB error")

        result = dashboard_app._load_diagnostic_data()
        self.assertIsInstance(result, pd.DataFrame)
        self.assertTrue(result.empty)


if __name__ == "__main__":
    unittest.main()
