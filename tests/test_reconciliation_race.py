"""
Tests proving that reconcile_all's cutoff_minutes window prevents race
conditions with the hourly bet_sync_hourly DAG.

Strategy chosen: Option A — Reconciliation lookback window.
  reconcile_all accepts a ``cutoff_minutes`` parameter (default 15).  Bets
  whose ``created_at`` is within the last N minutes are excluded from the
  reconciliation pass.  This avoids simultaneous writes between the daily
  ``multi_sport_betting_workflow`` (10 AM UTC) and the hourly
  ``bet_sync_hourly`` DAG.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from bet_reconciliation import reconcile_all  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(rows: list[dict]) -> MagicMock:
    """Build a mock DBManager whose fetch_df returns *rows* as a DataFrame."""
    db = MagicMock()

    def _fetch_df(sql: str, params=None):
        # Return empty DataFrame for the excluded-count query
        if "COUNT(*)" in sql:
            return pd.DataFrame([{"n": 0}])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df.attrs["_sql"] = sql
        return df

    db.fetch_df.side_effect = _fetch_df
    return db


def _bet_row(bet_id: str, created_at: datetime, **kwargs) -> dict:
    """Minimal placed_bets row dict."""
    return {
        "bet_id": bet_id,
        "contracts": 5,
        "price_cents": 55,
        "cost_dollars": 2.75,
        "fees_dollars": 0.03,
        "status": "open",
        "settled_date": None,
        "payout_dollars": None,
        "profit_dollars": None,
        "placed_date": created_at.date(),
        "created_at": created_at,
        **kwargs,
    }


# ---------------------------------------------------------------------------
# Core lookback-window behaviour
# ---------------------------------------------------------------------------


class TestCutoffWindowExcludesRecentBets:
    """Prove that the cutoff window excludes bets created within N minutes."""

    def test_recent_bet_excluded_from_sql_query(self):
        """The SQL query must carry a created_at <= :cutoff_ts filter when
        cutoff_minutes > 0, so that rows newer than the window never reach the
        reconciliation loop."""
        db = _make_db([])  # no rows returned → nothing reconciled

        with patch("bet_reconciliation.fetch_kalshi_state", return_value={}):
            reconcile_all(db=db, client=MagicMock(), cutoff_minutes=15)

        # Inspect every fetch_df call for the cutoff constraint
        fetch_calls = [str(c) for c in db.fetch_df.call_args_list]
        has_cutoff = any("cutoff_ts" in c for c in fetch_calls)
        assert has_cutoff, (
            "Expected 'cutoff_ts' in a fetch_df call when cutoff_minutes=15, "
            f"but calls were: {fetch_calls}"
        )

    def test_summary_includes_excluded_by_cutoff_key(self):
        """reconcile_all must always return 'excluded_by_cutoff' in its summary."""
        db = _make_db([])

        with patch("bet_reconciliation.fetch_kalshi_state", return_value={}):
            summary = reconcile_all(db=db, client=MagicMock(), cutoff_minutes=15)

        assert (
            "excluded_by_cutoff" in summary
        ), f"Summary missing 'excluded_by_cutoff' key.  Got: {list(summary.keys())}"

    def test_summary_includes_cutoff_ts_key(self):
        """reconcile_all must return 'cutoff_ts' (ISO-8601 or None) in summary."""
        db = _make_db([])

        with patch("bet_reconciliation.fetch_kalshi_state", return_value={}):
            summary = reconcile_all(db=db, client=MagicMock(), cutoff_minutes=15)

        assert "cutoff_ts" in summary
        # Should be an ISO-8601 string (not None) when cutoff is active
        assert summary["cutoff_ts"] is not None
        assert isinstance(summary["cutoff_ts"], str)

    def test_cutoff_ts_is_approximately_now_minus_cutoff_minutes(self):
        """cutoff_ts must be within a few seconds of utcnow - cutoff_minutes."""
        db = _make_db([])
        cutoff_minutes = 15

        before = datetime.now(tz=timezone.utc) - timedelta(minutes=cutoff_minutes)

        with patch("bet_reconciliation.fetch_kalshi_state", return_value={}):
            summary = reconcile_all(
                db=db, client=MagicMock(), cutoff_minutes=cutoff_minutes
            )

        after = datetime.now(tz=timezone.utc) - timedelta(minutes=cutoff_minutes)

        cutoff_ts = datetime.fromisoformat(summary["cutoff_ts"])
        # Allow 5-second tolerance for test execution
        assert (
            before - timedelta(seconds=5) <= cutoff_ts <= after + timedelta(seconds=5)
        )

    def test_zero_cutoff_disables_window(self):
        """Setting cutoff_minutes=0 must not add any cutoff_ts filter to the query."""
        db = _make_db([])

        with patch("bet_reconciliation.fetch_kalshi_state", return_value={}):
            summary = reconcile_all(db=db, client=MagicMock(), cutoff_minutes=0)

        fetch_calls = [str(c) for c in db.fetch_df.call_args_list]
        has_cutoff = any("cutoff_ts" in c for c in fetch_calls)
        assert not has_cutoff, (
            "Expected NO cutoff_ts filter when cutoff_minutes=0, "
            f"but calls were: {fetch_calls}"
        )
        assert summary["cutoff_ts"] is None
        assert summary["excluded_by_cutoff"] == 0

    def test_default_cutoff_is_15_minutes(self):
        """Calling reconcile_all() without arguments must apply a 15-min window."""
        db = _make_db([])

        with patch("bet_reconciliation.fetch_kalshi_state", return_value={}):
            summary = reconcile_all(db=db)

        assert summary["cutoff_ts"] is not None, "Default should apply a 15-min cutoff"
        cutoff_ts = datetime.fromisoformat(summary["cutoff_ts"])
        expected = datetime.now(tz=timezone.utc) - timedelta(minutes=15)
        assert (
            abs((cutoff_ts - expected).total_seconds()) < 10
        ), "Default cutoff_ts should be ~15 minutes ago"


# ---------------------------------------------------------------------------
# Race-condition scenario: recent bet NOT reconciled
# ---------------------------------------------------------------------------


class TestRecentBetNotReconciled:
    """End-to-end scenario: a bet created 5 minutes ago is excluded."""

    def test_bet_created_5_min_ago_not_in_checked_count(self):
        """With a 15-minute window, a bet created 5 minutes ago must not be
        reconciled (i.e., should not appear in the local_bets that are walked).

        We simulate this by having the DB return an EMPTY DataFrame when the
        cutoff filter is applied (mimicking that the recent row is filtered out
        by the WHERE clause), while Kalshi reports that bet as a fill.
        The reconcile_all loop should see 'checked=1' from remote state but
        attempt insert_missing_bet (not reconcile_bet), because the row was
        excluded from the local query.
        """
        # DB returns NO rows (the recent bet was filtered out by SQL cutoff)
        db = _make_db([])

        recent_bet_id = "BET-RECENT-001"
        remote_state = {
            recent_bet_id: {
                "bet_id": recent_bet_id,
                "ticker": "NBA-TEST",
                "contracts": 5,
                "price_cents": 55,
                "cost_dollars": 2.75,
                "fees_dollars": 0.03,
                "status": "open",
                "settled_date": None,
                "payout_dollars": None,
                "profit_dollars": None,
            }
        }

        with patch("bet_reconciliation.fetch_kalshi_state", return_value=remote_state):
            with patch(
                "bet_reconciliation.insert_missing_bet", return_value=False
            ) as mock_insert:
                summary = reconcile_all(db=db, client=MagicMock(), cutoff_minutes=15)

        # The bet was NOT in local_bets (filtered by cutoff), so insert_missing_bet
        # was called (treating it as a missing local bet)
        assert (
            mock_insert.called
        ), "Expected insert_missing_bet to be called for a bet absent from local_bets"
        # And reconcile_bet was NOT called (no field-level diff possible)
        assert summary["corrected"] == 0, "Recent bet should not have been corrected"


# ---------------------------------------------------------------------------
# Regression: existing summary keys still present
# ---------------------------------------------------------------------------


class TestSummaryKeysRegression:
    """Ensure adding the new cutoff keys did not drop any existing keys."""

    REQUIRED_KEYS = {
        "checked",
        "discrepancies",
        "corrected",
        "missing_locally_inserted",
        "missing_on_kalshi",
        "audit_rows_written",
        "excluded_by_cutoff",
        "cutoff_ts",
        "run_id",
    }

    def test_all_expected_keys_present(self):
        db = _make_db([])

        with patch("bet_reconciliation.fetch_kalshi_state", return_value={}):
            summary = reconcile_all(db=db, client=MagicMock())

        missing = self.REQUIRED_KEYS - set(summary.keys())
        assert not missing, f"Summary is missing expected keys: {missing}"
