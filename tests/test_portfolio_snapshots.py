from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pytest

from plugins.portfolio_snapshots import (
    load_latest_snapshot,
    load_snapshots_since,
    upsert_hourly_snapshot,
    ensure_portfolio_snapshots_table,
)
from db_manager import default_db


@pytest.fixture(autouse=True)
def clean_portfolio_table():
    """Clean portfolio snapshots table before each test."""
    # Ensure the table exists
    ensure_portfolio_snapshots_table()
    # Clean the table
    try:
        default_db.execute("DELETE FROM portfolio_value_snapshots WHERE snapshot_hour_utc >= '2026-01-20'")
    except:
        pass
    yield


def test_upsert_and_load_latest_snapshot(tmp_path: Path) -> None:
    t1 = datetime(2026, 1, 20, 12, 34, tzinfo=timezone.utc)
    snap1 = upsert_hourly_snapshot(
        observed_at_utc=t1,
        balance_dollars=10.0,
        portfolio_value_dollars=25.5,
    )
    assert snap1.snapshot_hour_utc == datetime(2026, 1, 20, 12, 0, tzinfo=timezone.utc)

    # Upsert same hour should overwrite values.
    snap2 = upsert_hourly_snapshot(
        observed_at_utc=datetime(2026, 1, 20, 12, 59, tzinfo=timezone.utc),
        balance_dollars=11.0,
        portfolio_value_dollars=30.0,
    )
    assert snap2.snapshot_hour_utc == snap1.snapshot_hour_utc

    latest = load_latest_snapshot()
    assert latest is not None
    assert latest.snapshot_hour_utc == snap1.snapshot_hour_utc
    assert latest.balance_dollars == 11.0
    assert latest.portfolio_value_dollars == 30.0


def test_load_snapshots_since(tmp_path: Path) -> None:
    upsert_hourly_snapshot(
        observed_at_utc=datetime(2026, 1, 20, 10, 5, tzinfo=timezone.utc),
        balance_dollars=1.0,
        portfolio_value_dollars=2.0,
    )
    upsert_hourly_snapshot(
        observed_at_utc=datetime(2026, 1, 20, 11, 5, tzinfo=timezone.utc),
        balance_dollars=3.0,
        portfolio_value_dollars=4.0,
    )

    df = load_snapshots_since(
        since_utc=datetime(2026, 1, 20, 11, 0, tzinfo=timezone.utc),
    )
    assert len(df) == 1
    assert float(df.iloc[0]["portfolio_value_dollars"]) == 4.0
