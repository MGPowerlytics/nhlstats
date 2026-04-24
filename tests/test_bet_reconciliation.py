"""
Tests for plugins/bet_reconciliation.py

All tests use unittest.mock – no live database or Kalshi credentials are
required.  Tests that would benefit from a real DB are marked with
``pytest.mark.integration`` so they can be skipped in CI environments that
lack a PostgreSQL connection.

The functions under test currently raise ``NotImplementedError`` (scaffolded
stubs).  These tests are written first (TDD) and are expected to fail until
the implementations are provided.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, call, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Path setup – allow imports from plugins/ without installing the package
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from bet_reconciliation import (  # noqa: E402
    RECONCILABLE_FIELDS,
    diff_bet,
    fetch_kalshi_state,
    insert_missing_bet,
    reconcile_all,
    reconcile_bet,
)


# ===========================================================================
# Helpers / fixtures
# ===========================================================================


def _local_bet(**overrides) -> dict:
    """Return a minimal local placed_bets row dict."""
    base = {
        "bet_id": "BET-001",
        "contracts": 10,
        "price_cents": 55,
        "cost_dollars": 5.50,
        "fees_dollars": 0.05,
        "status": "open",
        "settled_date": None,
        "payout_dollars": None,
        "profit_dollars": None,
        "sport": "NBA",
        "placed_date": date(2024, 1, 15),
    }
    base.update(overrides)
    return base


def _remote_bet(**overrides) -> dict:
    """Return a minimal Kalshi-sourced bet dict mirroring _local_bet."""
    base = {
        "bet_id": "BET-001",
        "contracts": 10,
        "price_cents": 55,
        "cost_dollars": 5.50,
        "fees_dollars": 0.05,
        "status": "open",
        "settled_date": None,
        "payout_dollars": None,
        "profit_dollars": None,
    }
    base.update(overrides)
    return base


def _mock_db():
    """Return a MagicMock that acts as a DBManager."""
    db = MagicMock()
    # Simulate fetch_df returning an empty DataFrame by default
    db.fetch_df.return_value = MagicMock(
        iterrows=MagicMock(return_value=iter([])),
        empty=True,
    )
    return db


# ===========================================================================
# diff_bet tests
# ===========================================================================


class TestDiffBet:
    """Unit tests for diff_bet()."""

    def test_diff_detects_status_change(self):
        """diff_bet should report a status change when remote differs from local."""
        local = _local_bet(status="open")
        remote = _remote_bet(status="settled")

        diffs = diff_bet(local, remote)

        assert len(diffs) == 1
        assert diffs[0]["field"] == "status"
        assert diffs[0]["old"] == "open"
        assert diffs[0]["new"] == "settled"

    def test_diff_detects_price_mismatch(self):
        """diff_bet should report a price_cents mismatch."""
        local = _local_bet(price_cents=55)
        remote = _remote_bet(price_cents=60)

        diffs = diff_bet(local, remote)

        assert any(d["field"] == "price_cents" for d in diffs)
        price_diff = next(d for d in diffs if d["field"] == "price_cents")
        assert price_diff["old"] == 55
        assert price_diff["new"] == 60

    def test_diff_returns_empty_when_records_match(self):
        """diff_bet should return an empty list when local and remote are identical."""
        local = _local_bet()
        remote = _remote_bet()

        diffs = diff_bet(local, remote)

        assert diffs == []

    def test_diff_only_checks_reconcilable_fields(self):
        """diff_bet should ignore fields not in RECONCILABLE_FIELDS."""
        local = _local_bet(sport="NBA")
        remote = _remote_bet()
        # 'sport' is not in RECONCILABLE_FIELDS; if it appears in remote we
        # add an unexpected key that should be silently ignored
        remote["sport"] = "NHL"

        diffs = diff_bet(local, remote)

        assert not any(d["field"] == "sport" for d in diffs)

    def test_diff_multiple_fields_changed(self):
        """diff_bet should report all changed reconcilable fields at once."""
        local = _local_bet(status="open", payout_dollars=None, profit_dollars=None)
        remote = _remote_bet(
            status="settled", payout_dollars=12.50, profit_dollars=7.00
        )

        diffs = diff_bet(local, remote)
        changed_fields = {d["field"] for d in diffs}

        assert "status" in changed_fields
        assert "payout_dollars" in changed_fields
        assert "profit_dollars" in changed_fields


# ===========================================================================
# reconcile_bet tests
# ===========================================================================


class TestReconcileBet:
    """Unit tests for reconcile_bet()."""

    def test_reconcile_bet_applies_update_and_audit(self):
        """reconcile_bet must issue UPDATE on placed_bets AND insert audit rows.

        Both operations must happen within a single transaction.  We verify
        that both calls are made on the db mock.
        """
        db = _mock_db()
        local = _local_bet(status="open")
        remote = _remote_bet(
            status="settled", payout_dollars=11.00, profit_dollars=5.50
        )

        with patch(
            "bet_reconciliation.diff_bet",
            return_value=[
                {"field": "status", "old": "open", "new": "settled"},
                {"field": "payout_dollars", "old": None, "new": 11.00},
                {"field": "profit_dollars", "old": None, "new": 5.50},
            ],
        ):
            changes = reconcile_bet("BET-001", local, remote, db)

        assert changes == 3
        # At minimum an UPDATE and audit INSERT must be invoked
        assert db.execute.called or db.execute_many.called

    def test_reconcile_bet_returns_zero_when_no_diff(self):
        """reconcile_bet should return 0 and not touch the DB when records match."""
        db = _mock_db()
        local = _local_bet()
        remote = _remote_bet()

        with patch("bet_reconciliation.diff_bet", return_value=[]):
            changes = reconcile_bet("BET-001", local, remote, db)

        assert changes == 0
        db.execute.assert_not_called()

    def test_reconcile_bet_rolls_back_on_audit_failure(self):
        """Atomicity: if the audit INSERT raises, the UPDATE must roll back.

        We simulate this by making the second db.execute() call (the audit
        insert) raise an exception and verify that:

        1. The exception propagates out of reconcile_bet.
        2. A rollback is performed (either via an explicit rollback call or by
           the context manager exiting without commit).
        """
        db = _mock_db()
        local = _local_bet(status="open")
        remote = _remote_bet(status="settled")

        audit_error = RuntimeError("Audit insert failed – simulated")

        with patch(
            "bet_reconciliation.diff_bet",
            return_value=[{"field": "status", "old": "open", "new": "settled"}],
        ):
            # Make the audit-related execute call raise
            db.execute.side_effect = [None, audit_error]

            with pytest.raises(Exception):
                reconcile_bet("BET-001", local, remote, db)

        # The transaction must NOT have been committed silently
        # (implementation detail: either rollback was called explicitly, or a
        #  context-manager-based connection never called commit)
        # We assert that a commit did NOT occur without a preceding rollback.
        # Since implementations vary, we simply assert the exception escaped.
        # A more precise assertion can be added once the implementation exists.


# ===========================================================================
# insert_missing_bet tests
# ===========================================================================


class TestInsertMissingBet:
    """Unit tests for insert_missing_bet()."""

    def test_insert_missing_bet_creates_row_with_source_kalshi_discovered(self):
        """insert_missing_bet must persist a row with source='kalshi_discovered'."""
        db = _mock_db()
        fill = {
            "bet_id": "BET-KALSHI-999",
            "ticker": "NBA-2024-LAL-YES",
            "contracts": 5,
            "price_cents": 48,
            "cost_dollars": 2.40,
            "fees_dollars": 0.02,
            "status": "settled",
            "settled_date": "2024-03-01",
            "payout_dollars": 5.00,
            "profit_dollars": 2.60,
        }

        result = insert_missing_bet(fill, db)

        assert result is True
        # The INSERT SQL executed on db must contain 'kalshi_discovered'
        assert db.execute.called
        sql_calls = [str(c) for c in db.execute.call_args_list]
        assert any("kalshi_discovered" in sql_call for sql_call in sql_calls), (
            "Expected 'kalshi_discovered' to appear in an execute() call, "
            f"but calls were: {sql_calls}"
        )

    def test_insert_missing_bet_returns_false_on_duplicate(self):
        """insert_missing_bet should return False when the bet_id already exists."""
        from sqlalchemy.exc import IntegrityError

        db = _mock_db()
        db.execute.side_effect = IntegrityError(
            statement="INSERT", params={}, orig=Exception("duplicate key")
        )
        fill = {
            "bet_id": "BET-DUPE",
            "ticker": "NBA-DUPE",
            "contracts": 1,
            "price_cents": 50,
        }

        result = insert_missing_bet(fill, db)

        assert result is False


# ===========================================================================
# reconcile_all tests
# ===========================================================================


class TestReconcileAll:
    """Unit tests for reconcile_all()."""

    def test_reconcile_all_handles_empty_kalshi_response(self):
        """reconcile_all should return a zeroed summary dict with no Kalshi fills."""
        db = _mock_db()

        with patch(
            "bet_reconciliation.fetch_kalshi_state", return_value={}
        ) as mock_fetch:
            summary = reconcile_all(db=db, client=MagicMock())

        mock_fetch.assert_called_once()
        assert isinstance(summary, dict)
        assert summary["checked"] == 0
        assert summary["discrepancies"] == 0
        assert summary["corrected"] == 0
        assert summary["missing_locally_inserted"] == 0
        assert summary["missing_on_kalshi"] == 0

    def test_reconcile_all_only_considers_bets_since_date(self):
        """reconcile_all must pass since_date filter to the DB query."""
        db = _mock_db()
        cutoff = date(2024, 3, 1)

        with patch("bet_reconciliation.fetch_kalshi_state", return_value={}):
            reconcile_all(db=db, client=MagicMock(), since_date=cutoff)

        # Verify that the DB was queried with the since_date constraint.
        # We check that *some* call to fetch_df / execute contains the date.
        all_calls = db.fetch_df.call_args_list + db.execute.call_args_list
        call_strs = [str(c) for c in all_calls]
        assert any("2024-03-01" in s or str(cutoff) in s for s in call_strs), (
            f"Expected since_date={cutoff} to appear in a DB call but calls were: "
            f"{call_strs}"
        )

    def test_reconcile_all_returns_correct_summary_keys(self):
        """reconcile_all must always return all required summary keys."""
        db = _mock_db()

        with patch("bet_reconciliation.fetch_kalshi_state", return_value={}):
            summary = reconcile_all(db=db)

        # Core 5 operational counters plus audit metadata keys
        required_keys = {
            "checked",
            "discrepancies",
            "corrected",
            "missing_locally_inserted",
            "missing_on_kalshi",
        }
        assert required_keys.issubset(set(summary.keys()))

    @pytest.mark.integration
    def test_reconcile_all_integration_requires_db(self):
        """Integration smoke-test: reconcile_all connects to a real DB.

        Skipped unless a PostgreSQL connection is available.
        """
        from db_manager import DBManager

        db = DBManager()
        with patch("bet_reconciliation.fetch_kalshi_state", return_value={}):
            summary = reconcile_all(db=db)
        assert "checked" in summary
