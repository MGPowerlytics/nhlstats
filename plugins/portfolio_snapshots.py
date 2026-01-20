"""DuckDB-backed portfolio value snapshots.

This module stores hourly (or more frequent) snapshots of Kalshi portfolio values
in DuckDB so the Streamlit dashboard can render a historical time series.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import duckdb


DEFAULT_DB_PATH = "data/nhlstats.duckdb"


@dataclass(frozen=True)
class PortfolioSnapshot:
    """A single portfolio snapshot."""

    snapshot_hour_utc: datetime
    balance_dollars: float
    portfolio_value_dollars: float
    created_at_utc: datetime


def _ensure_parent_dir(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)


def ensure_portfolio_snapshots_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the portfolio snapshots table if needed.

    Args:
        conn: Open DuckDB connection.
    """

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS portfolio_value_snapshots (
            snapshot_hour_utc TIMESTAMP PRIMARY KEY,
            balance_dollars DOUBLE,
            portfolio_value_dollars DOUBLE,
            created_at_utc TIMESTAMP DEFAULT (now())
        )
        """
    )

    # Lightweight schema migration if the table pre-existed.
    conn.execute(
        """ALTER TABLE portfolio_value_snapshots
        ADD COLUMN IF NOT EXISTS balance_dollars DOUBLE"""
    )
    conn.execute(
        """ALTER TABLE portfolio_value_snapshots
        ADD COLUMN IF NOT EXISTS portfolio_value_dollars DOUBLE"""
    )
    conn.execute(
        """ALTER TABLE portfolio_value_snapshots
        ADD COLUMN IF NOT EXISTS created_at_utc TIMESTAMP"""
    )


def _floor_to_hour_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    ts = ts.astimezone(timezone.utc)
    return ts.replace(minute=0, second=0, microsecond=0)


def _as_naive_utc(ts: datetime) -> datetime:
    """Convert a datetime to naive UTC for DuckDB TIMESTAMP storage."""

    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).replace(tzinfo=None)


def _as_aware_utc(ts: datetime) -> datetime:
    """Interpret a DuckDB-returned TIMESTAMP as UTC and make it tz-aware."""

    return ts.replace(tzinfo=timezone.utc)


def upsert_hourly_snapshot(
    *,
    db_path: str = DEFAULT_DB_PATH,
    observed_at_utc: Optional[datetime] = None,
    balance_dollars: float,
    portfolio_value_dollars: float,
) -> PortfolioSnapshot:
    """Upsert a portfolio snapshot keyed by UTC hour.

    Args:
        db_path: DuckDB path.
        observed_at_utc: When the values were observed. Defaults to now (UTC).
        balance_dollars: Cash balance in dollars.
        portfolio_value_dollars: Total portfolio value in dollars.

    Returns:
        The upserted snapshot (hour-bucketed).
    """

    _ensure_parent_dir(db_path)

    now_utc = datetime.now(tz=timezone.utc)
    observed = observed_at_utc or now_utc
    snapshot_hour = _floor_to_hour_utc(observed)

    snapshot_hour_db = _as_naive_utc(snapshot_hour)
    created_at_db = _as_naive_utc(now_utc)

    conn = duckdb.connect(db_path)
    try:
        ensure_portfolio_snapshots_table(conn)
        conn.execute(
            """
            INSERT INTO portfolio_value_snapshots (
                snapshot_hour_utc,
                balance_dollars,
                portfolio_value_dollars,
                created_at_utc
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(snapshot_hour_utc) DO UPDATE SET
                balance_dollars = excluded.balance_dollars,
                portfolio_value_dollars = excluded.portfolio_value_dollars,
                created_at_utc = excluded.created_at_utc
            """,
            [snapshot_hour_db, balance_dollars, portfolio_value_dollars, created_at_db],
        )

        row = conn.execute(
            """
            SELECT snapshot_hour_utc, balance_dollars, portfolio_value_dollars, created_at_utc
            FROM portfolio_value_snapshots
            WHERE snapshot_hour_utc = ?
            """,
            [snapshot_hour_db],
        ).fetchone()
    finally:
        conn.close()

    return PortfolioSnapshot(
        snapshot_hour_utc=_as_aware_utc(row[0]),
        balance_dollars=float(row[1] or 0.0),
        portfolio_value_dollars=float(row[2] or 0.0),
        created_at_utc=_as_aware_utc(row[3]),
    )


def load_latest_snapshot(db_path: str = DEFAULT_DB_PATH) -> Optional[PortfolioSnapshot]:
    """Load the most recent snapshot."""

    if not Path(db_path).exists():
        return None

    conn = duckdb.connect(db_path, read_only=True)
    try:
        tables = {str(t[0]) for t in conn.execute("SHOW TABLES").fetchall()}
        if "portfolio_value_snapshots" not in tables:
            return None

        row = conn.execute(
            """
            SELECT snapshot_hour_utc, balance_dollars, portfolio_value_dollars, created_at_utc
            FROM portfolio_value_snapshots
            ORDER BY snapshot_hour_utc DESC
            LIMIT 1
            """
        ).fetchone()
        if not row:
            return None
        return PortfolioSnapshot(
            snapshot_hour_utc=_as_aware_utc(row[0]),
            balance_dollars=float(row[1] or 0.0),
            portfolio_value_dollars=float(row[2] or 0.0),
            created_at_utc=_as_aware_utc(row[3]),
        )
    finally:
        conn.close()


def load_snapshots_since(
    *,
    db_path: str = DEFAULT_DB_PATH,
    since_utc: datetime,
):
    """Load snapshots since a UTC timestamp as a DataFrame."""

    import pandas as pd

    if not Path(db_path).exists():
        return pd.DataFrame()

    conn = duckdb.connect(db_path, read_only=True)
    try:
        tables = {str(t[0]) for t in conn.execute("SHOW TABLES").fetchall()}
        if "portfolio_value_snapshots" not in tables:
            return pd.DataFrame()

        if since_utc.tzinfo is None:
            since_utc = since_utc.replace(tzinfo=timezone.utc)
        since_utc = since_utc.astimezone(timezone.utc)
        since_db = since_utc.replace(tzinfo=None)

        df = conn.execute(
            """
            SELECT snapshot_hour_utc, balance_dollars, portfolio_value_dollars
            FROM portfolio_value_snapshots
            WHERE snapshot_hour_utc >= ?
            ORDER BY snapshot_hour_utc ASC
            """,
            [since_db],
        ).fetchdf()
        return df
    finally:
        conn.close()
