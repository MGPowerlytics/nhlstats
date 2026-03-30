"""Tests for compute_fill_time_analysis() — fill time / hours-before-game analysis.

TDD: Tests written first to define expected behavior before implementation.

Key insight: placed_time_utc = Kalshi fill timestamp (created_time from fills API).
"Hours before game" = hours between fill and game start = adverse selection signal.
"""

import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_fill_time_df(
    n: int = 60,
    hours_choices=None,
    seed: int = 42,
    include_sport: bool = True,
) -> pd.DataFrame:
    """Build a synthetic bets DataFrame with game_start_time_utc for fill time tests.

    Args:
        n: Number of rows to generate.
        hours_choices: List of hours-before-game values to cycle through.
        seed: RNG seed for reproducibility.
        include_sport: Whether to include a sport column.

    Returns:
        DataFrame suitable for passing to compute_fill_time_analysis().
    """
    rng = np.random.default_rng(seed)
    if hours_choices is None:
        hours_choices = [1.0, 3.0, 6.0, 12.0, 36.0]
    rows = []
    for i in range(n):
        won = rng.random() < 0.55
        hours_before = float(rng.choice(hours_choices))
        game_time = datetime(2026, 2, (i % 28) + 1, 19, 0)
        placed_time = game_time - timedelta(hours=hours_before)
        row = {
            "bet_id": f"bet_{i}",
            "placed_time_utc": placed_time,
            "game_start_time_utc": game_time,
            "profit_loss": 5.0 if won else -6.5,
            "cost_dollars": 6.5,
            "edge": float(0.08 + rng.random() * 0.06),
        }
        if include_sport:
            row["sport"] = "NBA"
        rows.append(row)
    return pd.DataFrame(rows)


# ===========================================================================
# TestComputeFillTimeAnalysis — pure function tests
# ===========================================================================


class TestComputeFillTimeAnalysis:
    """Tests for compute_fill_time_analysis() — ROI by hours-before-game buckets."""

    def test_returns_dataframe(self):
        """compute_fill_time_analysis returns a DataFrame."""
        from plugins.pnl_diagnostic import compute_fill_time_analysis

        df = _make_fill_time_df(n=60)
        result = compute_fill_time_analysis(df)
        assert isinstance(result, pd.DataFrame)

    def test_required_columns_present(self):
        """Result contains all required columns."""
        from plugins.pnl_diagnostic import compute_fill_time_analysis

        df = _make_fill_time_df(n=60)
        result = compute_fill_time_analysis(df)
        required = ["hours_bucket", "n_bets", "roi_pct", "avg_edge", "avg_hours_before_game"]
        for col in required:
            assert col in result.columns, f"Missing required column: {col}"

    def test_sport_column_included_when_present(self):
        """When input has sport column, output includes sport column."""
        from plugins.pnl_diagnostic import compute_fill_time_analysis

        df = _make_fill_time_df(n=60, include_sport=True)
        result = compute_fill_time_analysis(df)
        assert "sport" in result.columns

    def test_sport_column_absent_when_not_in_input(self):
        """When input lacks sport column, output omits sport column."""
        from plugins.pnl_diagnostic import compute_fill_time_analysis

        df = _make_fill_time_df(n=60, include_sport=False)
        result = compute_fill_time_analysis(df)
        assert "sport" not in result.columns

    def test_correct_bucket_assignment(self):
        """Bets with specific hours_before_game land in the correct bucket."""
        from plugins.pnl_diagnostic import compute_fill_time_analysis

        game_time = datetime(2026, 3, 1, 19, 0)
        test_cases = [
            (1.0, "<2hr"),
            (3.0, "2-4hr"),
            (6.0, "4-8hr"),
            (12.0, "8-24hr"),
            (36.0, "24+hr"),
        ]
        rows = []
        for hours, _expected in test_cases:
            rows.append(
                {
                    "placed_time_utc": game_time - timedelta(hours=hours),
                    "game_start_time_utc": game_time,
                    "profit_loss": 5.0,
                    "cost_dollars": 6.5,
                    "edge": 0.10,
                }
            )
        df = pd.DataFrame(rows)
        result = compute_fill_time_analysis(df)
        bucket_labels = [str(b) for b in result["hours_bucket"]]
        assert "<2hr" in bucket_labels
        assert "2-4hr" in bucket_labels
        assert "4-8hr" in bucket_labels
        assert "8-24hr" in bucket_labels
        assert "24+hr" in bucket_labels

    def test_empty_df_returns_empty_dataframe(self):
        """Empty input DataFrame returns an empty DataFrame."""
        from plugins.pnl_diagnostic import compute_fill_time_analysis

        df = pd.DataFrame(
            columns=["placed_time_utc", "game_start_time_utc", "profit_loss", "edge"]
        )
        result = compute_fill_time_analysis(df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_null_timestamps_dropped(self):
        """Rows with NULL placed_time_utc or game_start_time_utc are excluded."""
        from plugins.pnl_diagnostic import compute_fill_time_analysis

        df = _make_fill_time_df(n=20, include_sport=False)
        # Nullify rows 0-4 (placed_time) and 5-9 (game_start_time)
        df.loc[0:4, "placed_time_utc"] = None
        df.loc[5:9, "game_start_time_utc"] = None
        # Rows 10-19 are valid (10 rows)

        result = compute_fill_time_analysis(df)
        assert isinstance(result, pd.DataFrame)
        total_bets = int(result["n_bets"].sum()) if len(result) > 0 else 0
        assert total_bets <= 10, f"Expected ≤10 valid bets, got {total_bets}"

    def test_n_bets_sums_to_total_valid_rows(self):
        """Sum of n_bets across buckets equals the number of valid input rows."""
        from plugins.pnl_diagnostic import compute_fill_time_analysis

        df = _make_fill_time_df(n=60, include_sport=False)
        result = compute_fill_time_analysis(df)
        assert int(result["n_bets"].sum()) == 60

    def test_roi_pct_is_numeric(self):
        """All roi_pct values are numeric (int or float)."""
        from plugins.pnl_diagnostic import compute_fill_time_analysis

        df = _make_fill_time_df(n=60)
        result = compute_fill_time_analysis(df)
        for val in result["roi_pct"]:
            assert isinstance(val, (int, float)), f"roi_pct should be numeric, got {type(val)}"

    def test_roi_pct_calculated_correctly(self):
        """roi_pct = (sum_profit / sum_cost) * 100 for cost_dollars column present."""
        from plugins.pnl_diagnostic import compute_fill_time_analysis

        game_time = datetime(2026, 3, 1, 19, 0)
        # 10 bets all in <2hr bucket, all winning
        rows = [
            {
                "placed_time_utc": game_time - timedelta(hours=1.0),
                "game_start_time_utc": game_time,
                "profit_loss": 4.0,
                "cost_dollars": 5.0,
                "edge": 0.10,
            }
            for _ in range(10)
        ]
        df = pd.DataFrame(rows)
        result = compute_fill_time_analysis(df)
        bucket_row = result[result["hours_bucket"].astype(str) == "<2hr"]
        assert len(bucket_row) == 1
        # roi_pct = (10 * 4.0) / (10 * 5.0) * 100 = 80.0
        assert abs(float(bucket_row.iloc[0]["roi_pct"]) - 80.0) < 0.01

    def test_avg_edge_is_float(self):
        """avg_edge values are floats (or NaN when edge col absent)."""
        from plugins.pnl_diagnostic import compute_fill_time_analysis

        df = _make_fill_time_df(n=60, include_sport=False)
        result = compute_fill_time_analysis(df)
        for val in result["avg_edge"].dropna():
            assert isinstance(val, (int, float))

    def test_avg_hours_before_game_within_bucket_range(self):
        """avg_hours_before_game should be within the bucket boundaries."""
        from plugins.pnl_diagnostic import compute_fill_time_analysis

        game_time = datetime(2026, 3, 1, 19, 0)
        # Only bets in 4-8hr bucket
        rows = [
            {
                "placed_time_utc": game_time - timedelta(hours=h),
                "game_start_time_utc": game_time,
                "profit_loss": 2.0,
                "cost_dollars": 5.0,
                "edge": 0.05,
            }
            for h in [4.5, 5.0, 6.0, 7.5]
        ]
        df = pd.DataFrame(rows)
        result = compute_fill_time_analysis(df)
        row = result[result["hours_bucket"].astype(str) == "4-8hr"]
        assert len(row) == 1
        avg_h = float(row.iloc[0]["avg_hours_before_game"])
        assert 4.0 <= avg_h < 8.0

    def test_fallback_to_market_close_time_utc(self):
        """Falls back to market_close_time_utc when game_start_time_utc is absent."""
        from plugins.pnl_diagnostic import compute_fill_time_analysis

        df = _make_fill_time_df(n=20, include_sport=False)
        df = df.rename(columns={"game_start_time_utc": "market_close_time_utc"})
        result = compute_fill_time_analysis(df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0
        assert int(result["n_bets"].sum()) == 20

    def test_profit_dollars_accepted_as_alias(self):
        """Accepts profit_dollars column as alias for profit_loss."""
        from plugins.pnl_diagnostic import compute_fill_time_analysis

        df = _make_fill_time_df(n=20, include_sport=False)
        df = df.rename(columns={"profit_loss": "profit_dollars"})
        result = compute_fill_time_analysis(df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0

    def test_all_five_possible_buckets_labelled(self):
        """Result only contains valid FILL_TIME_BUCKET_LABELS values in hours_bucket."""
        from plugins.pnl_diagnostic import compute_fill_time_analysis
        from plugins.constants import FILL_TIME_BUCKET_LABELS

        df = _make_fill_time_df(n=60, include_sport=False)
        result = compute_fill_time_analysis(df)
        for bucket in result["hours_bucket"].astype(str):
            assert bucket in FILL_TIME_BUCKET_LABELS, f"Unexpected bucket: {bucket}"

    def test_all_data_null_returns_empty(self):
        """All rows have null timestamps → empty DataFrame."""
        from plugins.pnl_diagnostic import compute_fill_time_analysis

        df = _make_fill_time_df(n=10, include_sport=False)
        df["placed_time_utc"] = None
        result = compute_fill_time_analysis(df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


# ===========================================================================
# TestLoadFullBetsHoursBeforeGame — _load_full_bets adds hours_before_game
# ===========================================================================


class TestLoadFullBetsHoursBeforeGame:
    """Tests that _load_full_bets() computes and returns hours_before_game."""

    def test_hours_before_game_column_present(self):
        """_load_full_bets returns DataFrame with hours_before_game column."""
        from plugins.pnl_diagnostic import _load_full_bets

        game_time = datetime(2026, 3, 1, 19, 0)
        placed_time = datetime(2026, 3, 1, 15, 0)  # 4 hours before

        mock_df = pd.DataFrame(
            [
                {
                    "bet_id": "b1",
                    "sport": "NBA",
                    "placed_date": "2026-03-01",
                    "placed_time_utc": placed_time,
                    "home_team": "BOS",
                    "away_team": "LAL",
                    "bet_on": "home",
                    "side": "yes",
                    "cost_dollars": 6.5,
                    "profit_dollars": 5.0,
                    "elo_prob": 0.65,
                    "market_prob": 0.55,
                    "edge": 0.10,
                    "market_close_time_utc": game_time,
                    "bet_line_prob": 0.55,
                    "closing_line_prob": 0.60,
                    "clv": 0.05,
                    "status": "won",
                }
            ]
        )

        with patch("plugins.pnl_diagnostic.default_db") as mock_db:
            mock_db.fetch_df.return_value = mock_df
            result = _load_full_bets("NBA")

        assert "hours_before_game" in result.columns

    def test_hours_before_game_correct_value(self):
        """hours_before_game is computed as (market_close - placed_time) / 3600."""
        from plugins.pnl_diagnostic import _load_full_bets

        game_time = datetime(2026, 3, 1, 19, 0)
        placed_time = datetime(2026, 3, 1, 15, 0)  # 4 hours before

        mock_df = pd.DataFrame(
            [
                {
                    "bet_id": "b1",
                    "sport": "NBA",
                    "placed_date": "2026-03-01",
                    "placed_time_utc": placed_time,
                    "home_team": "BOS",
                    "away_team": "LAL",
                    "bet_on": "home",
                    "side": "yes",
                    "cost_dollars": 6.5,
                    "profit_dollars": 5.0,
                    "elo_prob": 0.65,
                    "market_prob": 0.55,
                    "edge": 0.10,
                    "market_close_time_utc": game_time,
                    "bet_line_prob": 0.55,
                    "closing_line_prob": 0.60,
                    "clv": 0.05,
                    "status": "won",
                }
            ]
        )

        with patch("plugins.pnl_diagnostic.default_db") as mock_db:
            mock_db.fetch_df.return_value = mock_df
            result = _load_full_bets("NBA")

        assert abs(float(result.iloc[0]["hours_before_game"]) - 4.0) < 0.01

    def test_null_market_close_time_handled(self):
        """Rows with NULL market_close_time_utc produce NaN for hours_before_game."""
        from plugins.pnl_diagnostic import _load_full_bets

        placed_time = datetime(2026, 3, 1, 15, 0)

        mock_df = pd.DataFrame(
            [
                {
                    "bet_id": "b1",
                    "sport": "NBA",
                    "placed_date": "2026-03-01",
                    "placed_time_utc": placed_time,
                    "home_team": "BOS",
                    "away_team": "LAL",
                    "bet_on": "home",
                    "side": "yes",
                    "cost_dollars": 6.5,
                    "profit_dollars": 5.0,
                    "elo_prob": 0.65,
                    "market_prob": 0.55,
                    "edge": 0.10,
                    "market_close_time_utc": None,  # NULL
                    "bet_line_prob": 0.55,
                    "closing_line_prob": 0.60,
                    "clv": 0.05,
                    "status": "won",
                }
            ]
        )

        with patch("plugins.pnl_diagnostic.default_db") as mock_db:
            mock_db.fetch_df.return_value = mock_df
            result = _load_full_bets("NBA")

        assert "hours_before_game" in result.columns
        assert pd.isna(result.iloc[0]["hours_before_game"])


# ===========================================================================
# TestDiagnoseSpotFillTimeIntegration — _diagnose_sport includes fill_time_analysis
# ===========================================================================


class TestDiagnoseSpotFillTimeIntegration:
    """Integration tests: _diagnose_sport includes fill_time_analysis in result."""

    def _make_mock_full_bets(self, n: int = 60) -> pd.DataFrame:
        """Build mock full bets DataFrame as returned by _load_full_bets()."""
        game_time = datetime(2026, 3, 1, 19, 0)
        rows = []
        for i in range(n):
            hours = [1.0, 3.0, 6.0, 12.0, 36.0][i % 5]
            placed_time = game_time - timedelta(hours=hours)
            rows.append(
                {
                    "bet_id": f"b{i}",
                    "sport": "NBA",
                    "placed_time_utc": placed_time,
                    "market_close_time_utc": game_time,
                    "hours_before_game": hours,
                    "cost_dollars": 6.5,
                    "profit_dollars": 5.0 if i % 2 == 0 else -6.5,
                    "elo_prob": 0.65,
                    "market_prob": 0.55,
                    "edge": 0.10,
                    "bet_line_prob": 0.55,
                    "closing_line_prob": 0.60,
                    "clv": 0.05,
                    "status": "won" if i % 2 == 0 else "lost",
                }
            )
        return pd.DataFrame(rows)

    def test_fill_time_analysis_key_in_result(self):
        """_diagnose_sport result contains fill_time_analysis key."""
        from plugins.pnl_diagnostic import _diagnose_sport

        mock_full_bets = self._make_mock_full_bets(60)

        with (
            patch(
                "plugins.pnl_diagnostic.replay_elo_ratings",
                return_value={"BOS": 1500.0},
            ),
            patch(
                "plugins.pnl_diagnostic.compare_replay_vs_csv", return_value=1.0
            ),
            patch(
                "plugins.pnl_diagnostic.recalculate_bet_metrics",
                return_value=pd.DataFrame(),
            ),
            patch(
                "plugins.pnl_diagnostic._load_full_bets", return_value=mock_full_bets
            ),
        ):
            result = _diagnose_sport("NBA", "nba")

        assert "fill_time_analysis" in result

    def test_fill_time_analysis_is_dataframe(self):
        """fill_time_analysis value is a DataFrame."""
        from plugins.pnl_diagnostic import _diagnose_sport

        mock_full_bets = self._make_mock_full_bets(60)

        with (
            patch(
                "plugins.pnl_diagnostic.replay_elo_ratings",
                return_value={"BOS": 1500.0},
            ),
            patch(
                "plugins.pnl_diagnostic.compare_replay_vs_csv", return_value=1.0
            ),
            patch(
                "plugins.pnl_diagnostic.recalculate_bet_metrics",
                return_value=pd.DataFrame(),
            ),
            patch(
                "plugins.pnl_diagnostic._load_full_bets", return_value=mock_full_bets
            ),
        ):
            result = _diagnose_sport("NBA", "nba")

        assert isinstance(result["fill_time_analysis"], pd.DataFrame)

    def test_fill_time_roi_under_2hr_in_result(self):
        """Result contains fill_time_roi_under_2hr key."""
        from plugins.pnl_diagnostic import _diagnose_sport

        mock_full_bets = self._make_mock_full_bets(60)

        with (
            patch(
                "plugins.pnl_diagnostic.replay_elo_ratings",
                return_value={"BOS": 1500.0},
            ),
            patch(
                "plugins.pnl_diagnostic.compare_replay_vs_csv", return_value=1.0
            ),
            patch(
                "plugins.pnl_diagnostic.recalculate_bet_metrics",
                return_value=pd.DataFrame(),
            ),
            patch(
                "plugins.pnl_diagnostic._load_full_bets", return_value=mock_full_bets
            ),
        ):
            result = _diagnose_sport("NBA", "nba")

        assert "fill_time_roi_under_2hr" in result

    def test_fill_time_roi_over_24hr_in_result(self):
        """Result contains fill_time_roi_over_24hr key."""
        from plugins.pnl_diagnostic import _diagnose_sport

        mock_full_bets = self._make_mock_full_bets(60)

        with (
            patch(
                "plugins.pnl_diagnostic.replay_elo_ratings",
                return_value={"BOS": 1500.0},
            ),
            patch(
                "plugins.pnl_diagnostic.compare_replay_vs_csv", return_value=1.0
            ),
            patch(
                "plugins.pnl_diagnostic.recalculate_bet_metrics",
                return_value=pd.DataFrame(),
            ),
            patch(
                "plugins.pnl_diagnostic._load_full_bets", return_value=mock_full_bets
            ),
        ):
            result = _diagnose_sport("NBA", "nba")

        assert "fill_time_roi_over_24hr" in result


# ===========================================================================
# TestPrintDiagnosticReportFillTime — report output includes fill time section
# ===========================================================================


class TestPrintDiagnosticReportFillTime:
    """Tests that print_diagnostic_report() outputs a fill time analysis section."""

    def test_fill_time_section_printed(self, capsys):
        """Print output contains '⏰ Fill Time' or 'Fill Time Analysis' header."""
        from plugins.pnl_diagnostic import print_diagnostic_report

        fill_df = pd.DataFrame(
            [
                {
                    "hours_bucket": "<2hr",
                    "n_bets": 12,
                    "roi_pct": -8.1,
                    "avg_edge": 0.04,
                    "avg_hours_before_game": 1.0,
                },
                {
                    "hours_bucket": "2-4hr",
                    "n_bets": 24,
                    "roi_pct": -2.3,
                    "avg_edge": 0.06,
                    "avg_hours_before_game": 3.0,
                },
            ]
        )
        all_results = {
            "NBA": {
                "roi": 0.05,
                "settled_bets": 60,
                "real_clv": 0.02,
                "bootstrap": {"ci_lower": 1.0, "ci_upper": 5.0},
                "elo_replay_divergence": 2.0,
                "recommendation": "CONTINUE",
                "fill_time_analysis": fill_df,
            }
        }
        print_diagnostic_report(all_results)
        captured = capsys.readouterr()
        assert "Fill Time" in captured.out, "Expected 'Fill Time' in report output"

    def test_fill_time_bucket_labels_printed(self, capsys):
        """Bucket labels (<2hr, 24+hr) appear in report output."""
        from plugins.pnl_diagnostic import print_diagnostic_report

        fill_df = pd.DataFrame(
            [
                {
                    "hours_bucket": "<2hr",
                    "n_bets": 12,
                    "roi_pct": -8.1,
                    "avg_edge": 0.04,
                    "avg_hours_before_game": 1.0,
                },
                {
                    "hours_bucket": "24+hr",
                    "n_bets": 33,
                    "roi_pct": -1.1,
                    "avg_edge": 0.05,
                    "avg_hours_before_game": 30.0,
                },
            ]
        )
        all_results = {
            "NBA": {
                "roi": 0.05,
                "settled_bets": 60,
                "real_clv": 0.02,
                "bootstrap": {"ci_lower": 1.0, "ci_upper": 5.0},
                "elo_replay_divergence": 2.0,
                "recommendation": "CONTINUE",
                "fill_time_analysis": fill_df,
            }
        }
        print_diagnostic_report(all_results)
        captured = capsys.readouterr()
        assert "<2hr" in captured.out
        assert "24+hr" in captured.out

    def test_no_fill_time_section_when_missing(self, capsys):
        """No crash when fill_time_analysis key is absent from result."""
        from plugins.pnl_diagnostic import print_diagnostic_report

        all_results = {
            "NBA": {
                "roi": 0.05,
                "settled_bets": 60,
                "real_clv": 0.02,
                "bootstrap": {"ci_lower": 1.0, "ci_upper": 5.0},
                "elo_replay_divergence": 2.0,
                "recommendation": "CONTINUE",
                # No fill_time_analysis key
            }
        }
        # Should not raise
        print_diagnostic_report(all_results)

    def test_empty_fill_time_analysis_handled(self, capsys):
        """Empty fill_time_analysis DataFrame does not crash the report."""
        from plugins.pnl_diagnostic import print_diagnostic_report

        fill_df = pd.DataFrame(
            columns=["hours_bucket", "n_bets", "roi_pct", "avg_edge", "avg_hours_before_game"]
        )
        all_results = {
            "NBA": {
                "roi": 0.05,
                "settled_bets": 60,
                "real_clv": 0.02,
                "bootstrap": {"ci_lower": 1.0, "ci_upper": 5.0},
                "elo_replay_divergence": 2.0,
                "recommendation": "CONTINUE",
                "fill_time_analysis": fill_df,
            }
        }
        # Should not raise
        print_diagnostic_report(all_results)
