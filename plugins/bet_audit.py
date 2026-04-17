"""
Bet Audit Helpers
=================

Provides parameterized-query helpers for writing to and reading from the
``bet_reconciliation_audit`` table.  All writes use INSERT statements with
named placeholders so no string interpolation touches user-supplied values.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


def insert_audit_row(
    db: Any,
    bet_id: str,
    field_changed: str,
    old_value: Any,
    new_value: Any,
    source: str,
    reason: Optional[str] = None,
    run_id: Optional[str] = None,
) -> None:
    """Insert a single immutable audit row into ``bet_reconciliation_audit``.

    Uses a parameterized INSERT so no user-supplied value is ever interpolated
    into the SQL string.

    Args:
        db: A ``DBManager`` (or compatible) instance that exposes ``execute(sql, params)``.
        bet_id: The primary key of the bet being audited.
        field_changed: The column name that was changed (e.g. ``"status"``).
        old_value: The value before the change.  Converted to ``str`` for storage.
        new_value: The value after the change.  Converted to ``str`` for storage.
        source: Origin of the change (e.g. ``"kalshi_reconciliation"``,
            ``"kalshi_discovered"``).
        reason: Optional human-readable explanation for the change.
        run_id: Optional UUID identifying the reconciliation run that triggered
            this audit entry.
    """
    sql = """
        INSERT INTO bet_reconciliation_audit
            (bet_id, field_changed, old_value, new_value, source, reason, run_id)
        VALUES
            (:bet_id, :field_changed, :old_value, :new_value, :source, :reason, :run_id)
    """
    params = {
        "bet_id": str(bet_id),
        "field_changed": str(field_changed),
        "old_value": None if old_value is None else str(old_value),
        "new_value": None if new_value is None else str(new_value),
        "source": str(source),
        "reason": reason,
        "run_id": run_id,
    }
    db.execute(sql, params)
    logger.debug("Audit row inserted: bet_id=%s field=%s", bet_id, field_changed)


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


def get_audit_history(
    db: Any,
    bet_id: Optional[str] = None,
    since: Optional[date] = None,
) -> list[dict]:
    """Return audit rows from ``bet_reconciliation_audit``.

    Both filters are optional.  When neither is supplied all rows are returned
    (use with care on large datasets).

    Args:
        db: A ``DBManager`` (or compatible) instance that exposes ``fetch_df(sql, params)``.
        bet_id: When provided, limit results to this bet.
        since: When provided, only return rows with ``reconciled_at >= since``.

    Returns:
        A list of dicts, one per audit row, with keys matching column names.
        Returns an empty list when no rows match.
    """
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if bet_id is not None:
        conditions.append("bet_id = :bet_id")
        params["bet_id"] = str(bet_id)

    if since is not None:
        conditions.append("reconciled_at >= :since")
        # Accept both date and datetime; cast to datetime for the query
        if isinstance(since, datetime):
            params["since"] = since
        else:
            params["since"] = datetime(since.year, since.month, since.day)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"""
        SELECT
            audit_id, bet_id, field_changed, old_value, new_value,
            source, reconciled_at, reason, discrepancy_type, run_id
        FROM bet_reconciliation_audit
        {where_clause}
        ORDER BY reconciled_at DESC, audit_id DESC
    """

    try:
        df = db.fetch_df(sql, params if params else None)
        if df.empty:
            return []
        return df.to_dict(orient="records")
    except Exception as exc:  # pragma: no cover
        logger.error("get_audit_history failed: %s", exc)
        raise
