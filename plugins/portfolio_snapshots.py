"""PostgreSQL-backed portfolio value snapshots.

This module stores hourly (or more frequent) snapshots of Kalshi portfolio values
in PostgreSQL so the Streamlit dashboard can render a historical time series.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import pandas as pd
from plugins.db_manager import DBManager, default_db


@dataclass(frozen=True)
class PortfolioSnapshot:
    """A single portfolio snapshot."""

    snapshot_hour_utc: datetime
    balance_dollars: float
    portfolio_value_dollars: float
    created_at_utc: datetime
    cumulative_deposits_dollars: float = 0.0
    drawdown_gate_active: bool = False
    drawdown_gate_reason_code: Optional[str] = None
    drawdown_gate_reason_detail: Optional[str] = None


def ensure_portfolio_snapshots_table(db: DBManager = default_db) -> None:
    """Create the portfolio snapshots table if needed."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS portfolio_value_snapshots (
            snapshot_hour_utc TIMESTAMP PRIMARY KEY,
            balance_dollars DOUBLE PRECISION,
            portfolio_value_dollars DOUBLE PRECISION,
            cumulative_deposits_dollars DOUBLE PRECISION DEFAULT 0.0,
            drawdown_gate_active BOOLEAN DEFAULT FALSE,
            drawdown_gate_reason_code VARCHAR,
            drawdown_gate_reason_detail VARCHAR,
            created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Add cumulative_deposits_dollars column if it doesn't exist (for existing tables)
    try:
        db.execute(
            """
            ALTER TABLE portfolio_value_snapshots
            ADD COLUMN IF NOT EXISTS cumulative_deposits_dollars DOUBLE PRECISION DEFAULT 0.0
            """
        )
    except Exception:
        pass

    db.execute(
        """
        ALTER TABLE portfolio_value_snapshots
        ADD COLUMN IF NOT EXISTS drawdown_gate_active BOOLEAN DEFAULT FALSE
        """
    )
    db.execute(
        """
        ALTER TABLE portfolio_value_snapshots
        ADD COLUMN IF NOT EXISTS drawdown_gate_reason_code VARCHAR
        """
    )
    db.execute(
        """
        ALTER TABLE portfolio_value_snapshots
        ADD COLUMN IF NOT EXISTS drawdown_gate_reason_detail VARCHAR
        """
    )


def _floor_to_hour_utc(ts: datetime) -> datetime:
    """Floor a datetime to the hour in naive UTC."""
    if ts.tzinfo is not None:
        ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
    return ts.replace(minute=0, second=0, microsecond=0)


def _optional_float(value: object, default: float = 0.0) -> float:
    """Return a nullable numeric database value as a float."""
    if value is None or pd.isna(value):
        return default
    return float(value)


def _optional_bool(value: object, default: bool = False) -> bool:
    """Return a nullable database value as a boolean."""
    if value is None or pd.isna(value):
        return default
    return bool(value)


def _optional_str(value: object) -> Optional[str]:
    """Return a nullable database value as a string."""
    if value is None or pd.isna(value):
        return None
    text = str(value)
    return text or None


def upsert_hourly_snapshot(
    *,
    db_path: Optional[str] = None,
    db: DBManager = default_db,
    observed_at_utc: Optional[datetime] = None,
    balance_dollars: float,
    portfolio_value_dollars: float,
    drawdown_gate_active: bool = False,
    drawdown_gate_reason_code: Optional[str] = None,
    drawdown_gate_reason_detail: Optional[str] = None,
) -> PortfolioSnapshot:
    """Upsert a portfolio snapshot keyed by UTC hour."""
    # Ignore db_path
    now_utc = datetime.now(tz=timezone.utc)
    observed = observed_at_utc or now_utc
    snapshot_hour = _floor_to_hour_utc(observed)

    ensure_portfolio_snapshots_table(db)

    # Calculate cumulative deposits up to this snapshot hour
    try:
        from plugins.deposit_tracking import calculate_total_deposits

        cumulative_deposits = calculate_total_deposits(up_to_date=snapshot_hour, db=db)
    except Exception:
        # If deposit tracking not available, default to 0
        cumulative_deposits = 0.0

    params = {
        "snapshot_hour": snapshot_hour,
        "balance": balance_dollars,
        "portfolio_value": portfolio_value_dollars,
        "cumulative_deposits": cumulative_deposits,
        "drawdown_gate_active": drawdown_gate_active,
        "drawdown_gate_reason_code": drawdown_gate_reason_code,
        "drawdown_gate_reason_detail": drawdown_gate_reason_detail,
        "created_at": now_utc.replace(tzinfo=None),
    }

    db.execute(
        """
        INSERT INTO portfolio_value_snapshots (
            snapshot_hour_utc,
            balance_dollars,
            portfolio_value_dollars,
            cumulative_deposits_dollars,
            drawdown_gate_active,
            drawdown_gate_reason_code,
            drawdown_gate_reason_detail,
            created_at_utc
        ) VALUES (
            :snapshot_hour,
            :balance,
            :portfolio_value,
            :cumulative_deposits,
            :drawdown_gate_active,
            :drawdown_gate_reason_code,
            :drawdown_gate_reason_detail,
            :created_at
        )
        ON CONFLICT(snapshot_hour_utc) DO UPDATE SET
            balance_dollars = EXCLUDED.balance_dollars,
            portfolio_value_dollars = EXCLUDED.portfolio_value_dollars,
            cumulative_deposits_dollars = EXCLUDED.cumulative_deposits_dollars,
            drawdown_gate_active = EXCLUDED.drawdown_gate_active,
            drawdown_gate_reason_code = EXCLUDED.drawdown_gate_reason_code,
            drawdown_gate_reason_detail = EXCLUDED.drawdown_gate_reason_detail,
            created_at_utc = EXCLUDED.created_at_utc
        """,
        params,
    )

    df = db.fetch_df(
        """
        SELECT
            snapshot_hour_utc,
            balance_dollars,
            portfolio_value_dollars,
            cumulative_deposits_dollars,
            drawdown_gate_active,
            drawdown_gate_reason_code,
            drawdown_gate_reason_detail,
            created_at_utc
        FROM portfolio_value_snapshots
        WHERE snapshot_hour_utc = :snapshot_hour
        """,
        {"snapshot_hour": snapshot_hour},
    )

    if df.empty:
        raise RuntimeError("Failed to retrieve upserted row")

    row = df.iloc[0]
    return PortfolioSnapshot(
        snapshot_hour_utc=pd.to_datetime(row["snapshot_hour_utc"]).replace(
            tzinfo=timezone.utc
        ),
        balance_dollars=_optional_float(row["balance_dollars"]),
        portfolio_value_dollars=_optional_float(row["portfolio_value_dollars"]),
        cumulative_deposits_dollars=_optional_float(
            row.get("cumulative_deposits_dollars")
        ),
        drawdown_gate_active=_optional_bool(row.get("drawdown_gate_active")),
        drawdown_gate_reason_code=_optional_str(row.get("drawdown_gate_reason_code")),
        drawdown_gate_reason_detail=_optional_str(
            row.get("drawdown_gate_reason_detail")
        ),
        created_at_utc=pd.to_datetime(row["created_at_utc"]).replace(
            tzinfo=timezone.utc
        ),
    )


def load_latest_snapshot(
    db_path: Optional[str] = None, db: DBManager = default_db
) -> Optional[PortfolioSnapshot]:
    """Load the most recent snapshot."""
    # Ignore db_path
    if not db.table_exists("portfolio_value_snapshots"):
        return None

    df = db.fetch_df(
        """
        SELECT
            snapshot_hour_utc,
            balance_dollars,
            portfolio_value_dollars,
            cumulative_deposits_dollars,
            drawdown_gate_active,
            drawdown_gate_reason_code,
            drawdown_gate_reason_detail,
            created_at_utc
        FROM portfolio_value_snapshots
        ORDER BY snapshot_hour_utc DESC
        LIMIT 1
        """
    )

    if df.empty:
        return None

    row = df.iloc[0]
    return PortfolioSnapshot(
        snapshot_hour_utc=pd.to_datetime(row["snapshot_hour_utc"]).replace(
            tzinfo=timezone.utc
        ),
        balance_dollars=_optional_float(row["balance_dollars"]),
        portfolio_value_dollars=_optional_float(row["portfolio_value_dollars"]),
        cumulative_deposits_dollars=_optional_float(
            row.get("cumulative_deposits_dollars")
        ),
        drawdown_gate_active=_optional_bool(row.get("drawdown_gate_active")),
        drawdown_gate_reason_code=_optional_str(row.get("drawdown_gate_reason_code")),
        drawdown_gate_reason_detail=_optional_str(
            row.get("drawdown_gate_reason_detail")
        ),
        created_at_utc=pd.to_datetime(row["created_at_utc"]).replace(
            tzinfo=timezone.utc
        ),
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

    # Convert to naive UTC for compatibility with SQLite (column is naive UTC)
    if since_utc.tzinfo is not None:
        since_utc_naive = since_utc.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        since_utc_naive = since_utc

    df = db.fetch_df(
        """
        SELECT
            snapshot_hour_utc,
            balance_dollars,
            portfolio_value_dollars,
            cumulative_deposits_dollars,
            drawdown_gate_active,
            drawdown_gate_reason_code,
            drawdown_gate_reason_detail
        FROM portfolio_value_snapshots
        WHERE snapshot_hour_utc >= :since_utc
        ORDER BY snapshot_hour_utc ASC
        """,
        {"since_utc": since_utc_naive},
    )
    return df
