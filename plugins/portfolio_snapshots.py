"""PostgreSQL-backed portfolio value snapshots.

This module stores hourly (or more frequent) snapshots of Kalshi portfolio values
in PostgreSQL so the Streamlit dashboard can render a historical time series.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import pandas as pd
from db_manager import DBManager, default_db


@dataclass(frozen=True)
class PortfolioSnapshot:
    """A single portfolio snapshot."""

    snapshot_hour_utc: datetime
    balance_dollars: float
    portfolio_value_dollars: float
    created_at_utc: datetime


def ensure_portfolio_snapshots_table(db: DBManager = default_db) -> None:
    """Create the portfolio snapshots table if needed."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS portfolio_value_snapshots (
            snapshot_hour_utc TIMESTAMP PRIMARY KEY,
            balance_dollars DOUBLE PRECISION,
            portfolio_value_dollars DOUBLE PRECISION,
            created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # Add explicit constraint if needed (for cases where PRIMARY KEY wasn't picked up correctly in earlier runs)
    try:
        db.execute("ALTER TABLE portfolio_value_snapshots ADD CONSTRAINT pk_snapshot_hour PRIMARY KEY (snapshot_hour_utc)")
    except:
        pass


def _floor_to_hour_utc(ts: datetime) -> datetime:
    """Floor a datetime to the hour in naive UTC."""
    if ts.tzinfo is not None:
        ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
    return ts.replace(minute=0, second=0, microsecond=0)


def upsert_hourly_snapshot(
    *,
    db_path: Optional[str] = None,
    db: DBManager = default_db,
    observed_at_utc: Optional[datetime] = None,
    balance_dollars: float,
    portfolio_value_dollars: float,
) -> PortfolioSnapshot:
    """Upsert a portfolio snapshot keyed by UTC hour."""
    # Ignore db_path
    now_utc = datetime.now(tz=timezone.utc)
    observed = observed_at_utc or now_utc
    snapshot_hour = _floor_to_hour_utc(observed)

    ensure_portfolio_snapshots_table(db)

    params = {
        'snapshot_hour': snapshot_hour,
        'balance': balance_dollars,
        'portfolio_value': portfolio_value_dollars,
        'created_at': now_utc.replace(tzinfo=None)
    }

    db.execute(
        """
        INSERT INTO portfolio_value_snapshots (
            snapshot_hour_utc,
            balance_dollars,
            portfolio_value_dollars,
            created_at_utc
        ) VALUES (:snapshot_hour, :balance, :portfolio_value, :created_at)
        ON CONFLICT(snapshot_hour_utc) DO UPDATE SET
            balance_dollars = EXCLUDED.balance_dollars,
            portfolio_value_dollars = EXCLUDED.portfolio_value_dollars,
            created_at_utc = EXCLUDED.created_at_utc
        """,
        params
    )

    df = db.fetch_df(
        """
        SELECT snapshot_hour_utc, balance_dollars, portfolio_value_dollars, created_at_utc
        FROM portfolio_value_snapshots
        WHERE snapshot_hour_utc = :snapshot_hour
        """,
        {'snapshot_hour': snapshot_hour}
    )

    if df.empty:
        raise RuntimeError("Failed to retrieve upserted row")

    row = df.iloc[0]
    return PortfolioSnapshot(
        snapshot_hour_utc=pd.to_datetime(row['snapshot_hour_utc']).replace(tzinfo=timezone.utc),
        balance_dollars=float(row['balance_dollars'] or 0.0),
        portfolio_value_dollars=float(row['portfolio_value_dollars'] or 0.0),
        created_at_utc=pd.to_datetime(row['created_at_utc']).replace(tzinfo=timezone.utc),
    )


def load_latest_snapshot(db_path: Optional[str] = None, db: DBManager = default_db) -> Optional[PortfolioSnapshot]:
    """Load the most recent snapshot."""
    # Ignore db_path
    if not db.table_exists("portfolio_value_snapshots"):
        return None

    df = db.fetch_df(
        """
        SELECT snapshot_hour_utc, balance_dollars, portfolio_value_dollars, created_at_utc
        FROM portfolio_value_snapshots
        ORDER BY snapshot_hour_utc DESC
        LIMIT 1
        """
    )

    if df.empty:
        return None

    row = df.iloc[0]
    return PortfolioSnapshot(
        snapshot_hour_utc=pd.to_datetime(row['snapshot_hour_utc']).replace(tzinfo=timezone.utc),
        balance_dollars=float(row['balance_dollars'] or 0.0),
        portfolio_value_dollars=float(row['portfolio_value_dollars'] or 0.0),
        created_at_utc=pd.to_datetime(row['created_at_utc']).replace(tzinfo=timezone.utc),
    )


def load_snapshots_since(
    *,
    db_path: Optional[str] = None,
    db: DBManager = default_db,
    since_utc: datetime,
):
    """Load snapshots since a UTC timestamp as a DataFrame."""
    # Ignore db_path
    if not db.table_exists("portfolio_value_snapshots"):
        return pd.DataFrame()

    if since_utc.tzinfo is None:
        since_utc = since_utc.replace(tzinfo=timezone.utc)

    return db.fetch_df(
        """
        SELECT snapshot_hour_utc, balance_dollars, portfolio_value_dollars
        FROM portfolio_value_snapshots
        WHERE snapshot_hour_utc >= :since_utc
        ORDER BY snapshot_hour_utc ASC
        """,
        {'since_utc': since_utc}
    )
