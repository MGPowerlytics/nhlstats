import unittest
import pandas as pd
from unittest.mock import MagicMock
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "../dashboard"))

st = MagicMock()


def cache_decorator(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        return args[0]
    return lambda f: f


st.cache_data = cache_decorator
sys.modules["streamlit"] = st

import dashboard.dashboard_app as dashboard_app


class TestDashboardBetSummaries(unittest.TestCase):
    def test_summarize_market_outcomes_uses_market_level_counts(self):
        df = pd.DataFrame(
            {
                "ticker": ["A", "A", "B", "B", "C", "D"],
                "status": ["won", "lost", "open", "open", "lost", "won"],
                "profit_dollars": [2.0, -0.5, 0.0, 0.0, -1.0, 3.0],
            }
        )

        summary = dashboard_app._summarize_market_outcomes(df)
        counts = dict(zip(summary["Status"], summary["Count"]))

        self.assertEqual(counts["Won"], 2)
        self.assertEqual(counts["Lost"], 1)
        self.assertEqual(counts["Open"], 1)

    def test_count_settled_markets_counts_unique_tickers(self):
        df = pd.DataFrame(
            {
                "ticker": ["A", "A", "B", "C"],
                "status": ["won", "lost", "won", "lost"],
            }
        )

        self.assertEqual(dashboard_app._count_settled_markets(df), 3)


if __name__ == "__main__":
    unittest.main()
