"""
Tests for plugins/bet_audit.py

All tests use unittest.mock – no live database or Kalshi credentials are
required.  Integration tests (requiring real PostgreSQL) are marked with
``pytest.mark.integration``.
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, call

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from bet_audit import get_audit_history, insert_audit_row  # noqa: E402


# ===========================================================================
# Helpers
# ===========================================================================


def _mock_db() -> MagicMock:
    """Return a MagicMock that behaves like DBManager."""
    db = MagicMock()
    # Use a genuinely empty DataFrame (empty is a read-only property on DataFrame)
    empty_df = pd.DataFrame(
        columns=[
            "audit_id",
            "bet_id",
            "field_changed",
            "old_value",
            "new_value",
            "source",
            "reconciled_at",
            "reason",
            "discrepancy_type",
            "run_id",
        ]
    )
    # empty_df.empty is True because no rows → no assignment needed
    db.fetch_df.return_value = empty_df
    return db


# ===========================================================================
# insert_audit_row tests
# ===========================================================================


class TestInsertAuditRow:
    """Unit tests for insert_audit_row()."""

    def test_insert_calls_db_execute(self):
        """insert_audit_row must call db.execute exactly once."""
        db = _mock_db()
        insert_audit_row(
            db, "BET-1", "status", "open", "settled", "kalshi_reconciliation"
        )
        assert db.execute.call_count == 1

    def test_insert_passes_parameterized_sql(self):
        """insert_audit_row must pass named-param dict, not raw string values."""
        db = _mock_db()
        insert_audit_row(
            db,
            bet_id="BET-2",
            field_changed="price_cents",
            old_value=55,
            new_value=60,
            source="kalshi_reconciliation",
            reason="price corrected by kalshi",
            run_id="run-uuid-123",
        )
        _sql, params = db.execute.call_args[0]
        assert params["bet_id"] == "BET-2"
        assert params["field_changed"] == "price_cents"
        assert params["old_value"] == "55"
        assert params["new_value"] == "60"
        assert params["source"] == "kalshi_reconciliation"
        assert params["reason"] == "price corrected by kalshi"
        assert params["run_id"] == "run-uuid-123"

    def test_insert_handles_none_old_and_new(self):
        """None values must be stored as None (not the string 'None')."""
        db = _mock_db()
        insert_audit_row(db, "BET-3", "payout_dollars", None, None, "kalshi_discovered")
        _sql, params = db.execute.call_args[0]
        assert params["old_value"] is None
        assert params["new_value"] is None

    def test_insert_without_optional_reason_and_run_id(self):
        """Optional args reason and run_id default to None without error."""
        db = _mock_db()
        insert_audit_row(
            db, "BET-4", "status", "open", "settled", "kalshi_reconciliation"
        )
        _sql, params = db.execute.call_args[0]
        assert params["reason"] is None
        assert params["run_id"] is None

    def test_insert_converts_numeric_values_to_str(self):
        """Numeric old/new values are converted to str for TEXT column."""
        db = _mock_db()
        insert_audit_row(db, "BET-5", "contracts", 10, 12, "kalshi_reconciliation")
        _sql, params = db.execute.call_args[0]
        assert params["old_value"] == "10"
        assert params["new_value"] == "12"

    def test_sql_uses_named_placeholders(self):
        """The SQL string must use named placeholders, not raw values."""
        db = _mock_db()
        insert_audit_row(db, "BET-6", "status", "open", "settled", "test_source")
        sql = db.execute.call_args[0][0]
        # Check that the SQL uses :param style placeholders
        assert ":bet_id" in sql
        assert ":field_changed" in sql
        assert ":old_value" in sql
        assert ":new_value" in sql
        assert ":source" in sql
        # No raw values injected into SQL string
        assert "BET-6" not in sql
        assert "settled" not in sql


# ===========================================================================
# get_audit_history tests
# ===========================================================================


class TestGetAuditHistory:
    """Unit tests for get_audit_history()."""

    def test_returns_empty_list_when_no_rows(self):
        """get_audit_history returns [] when fetch_df returns empty DataFrame."""
        db = _mock_db()
        result = get_audit_history(db)
        assert result == []

    def test_no_filters_queries_without_where_clause(self):
        """When called with no filters, SQL has no WHERE clause."""
        db = _mock_db()
        get_audit_history(db)
        sql = db.fetch_df.call_args[0][0]
        assert "WHERE" not in sql.upper()

    def test_bet_id_filter_appends_where_clause(self):
        """bet_id filter adds WHERE bet_id = :bet_id to SQL."""
        db = _mock_db()
        get_audit_history(db, bet_id="BET-007")
        sql, params = db.fetch_df.call_args[0]
        assert "bet_id" in sql.lower()
        assert params["bet_id"] == "BET-007"

    def test_since_date_filter_appends_where_clause(self):
        """since filter adds reconciled_at >= :since to SQL."""
        db = _mock_db()
        get_audit_history(db, since=date(2024, 1, 1))
        sql, params = db.fetch_df.call_args[0]
        assert "reconciled_at" in sql.lower()
        assert "since" in params

    def test_both_filters_combined(self):
        """Both bet_id and since filters produce a combined WHERE clause."""
        db = _mock_db()
        get_audit_history(db, bet_id="BET-X", since=date(2024, 6, 1))
        sql, params = db.fetch_df.call_args[0]
        assert "bet_id" in sql.lower()
        assert "reconciled_at" in sql.lower()
        assert params["bet_id"] == "BET-X"

    def test_returns_list_of_dicts(self):
        """get_audit_history returns list[dict] when rows are present."""
        db = _mock_db()
        sample_df = pd.DataFrame(
            [
                {
                    "audit_id": 1,
                    "bet_id": "BET-1",
                    "field_changed": "status",
                    "old_value": "open",
                    "new_value": "settled",
                    "source": "kalshi_reconciliation",
                    "reconciled_at": datetime(2024, 3, 1),
                    "reason": None,
                    "discrepancy_type": None,
                    "run_id": "run-abc",
                }
            ]
        )
        db.fetch_df.return_value = sample_df
        result = get_audit_history(db, bet_id="BET-1")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["bet_id"] == "BET-1"
        assert result[0]["field_changed"] == "status"

    def test_since_accepts_datetime(self):
        """since parameter can be a datetime object as well as a date."""
        db = _mock_db()
        dt = datetime(2024, 6, 15, 12, 0, 0)
        get_audit_history(db, since=dt)
        _sql, params = db.fetch_df.call_args[0]
        assert params["since"] == dt
