import unittest
import pandas as pd
from unittest.mock import MagicMock, patch
import sys
import os

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


class TestDashboardHelpers(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        # Reset the mock from dashboard_app
        dashboard_app.st.reset_mock()

    def test_render_plotly_chart_histogram(self):
        with patch("plotly.express.histogram") as mock_hist:
            mock_fig = MagicMock()
            mock_hist.return_value = mock_fig

            dashboard_app._render_plotly_chart(
                df=self.df,
                config=dashboard_app.ChartConfig(
                    chart_type="histogram",
                    chart_kwargs={"x": "x"},
                    title="Test Histogram",
                ),
            )

            dashboard_app.st.subheader.assert_called_with("Test Histogram")
            mock_hist.assert_called_once()
            dashboard_app.st.plotly_chart.assert_called_once_with(
                mock_fig, use_container_width=True
            )

    def test_render_plotly_chart_empty_df(self):
        empty_df = pd.DataFrame()
        dashboard_app._render_plotly_chart(
            df=empty_df,
            config=dashboard_app.ChartConfig(
                chart_type="line", chart_kwargs={}, title="Empty Chart"
            ),
        )
        dashboard_app.st.plotly_chart.assert_not_called()

    @patch("dashboard.dashboard_app.default_db")
    def test_render_query_chart(self, mock_db):
        mock_db.fetch_df.return_value = self.df

        with patch("dashboard.dashboard_app._render_plotly_chart") as mock_render:
            config = dashboard_app.ChartConfig(
                chart_type="bar", chart_kwargs={"x": "x", "y": "y"}, title="Query Chart"
            )
            dashboard_app._render_query_chart(query="SELECT * FROM test", config=config)

            mock_db.fetch_df.assert_called_once_with("SELECT * FROM test")
            mock_render.assert_called_once_with(self.df, config)


if __name__ == "__main__":
    unittest.main()
