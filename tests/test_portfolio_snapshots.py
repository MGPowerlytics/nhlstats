from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from plugins.portfolio_snapshots import (
    load_latest_snapshot,
    load_snapshots_since,
    upsert_hourly_snapshot,
)


def test_upsert_and_load_latest_snapshot(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.duckdb")

    t1 = datetime(2026, 1, 20, 12, 34, tzinfo=timezone.utc)
    snap1 = upsert_hourly_snapshot(
        db_path=db_path,
        observed_at_utc=t1,
        balance_dollars=10.0,
        portfolio_value_dollars=25.5,
    )
    assert snap1.snapshot_hour_utc == datetime(2026, 1, 20, 12, 0, tzinfo=timezone.utc)

    # Upsert same hour should overwrite values.
    snap2 = upsert_hourly_snapshot(
        db_path=db_path,
        observed_at_utc=datetime(2026, 1, 20, 12, 59, tzinfo=timezone.utc),
        balance_dollars=11.0,
        portfolio_value_dollars=30.0,
    )
    assert snap2.snapshot_hour_utc == snap1.snapshot_hour_utc

    latest = load_latest_snapshot(db_path=db_path)
    assert latest is not None
    assert latest.snapshot_hour_utc == snap1.snapshot_hour_utc
    assert latest.balance_dollars == 11.0
    assert latest.portfolio_value_dollars == 30.0


def test_load_snapshots_since(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.duckdb")

    upsert_hourly_snapshot(
        db_path=db_path,
        observed_at_utc=datetime(2026, 1, 20, 10, 5, tzinfo=timezone.utc),
        balance_dollars=1.0,
        portfolio_value_dollars=2.0,
    )
    upsert_hourly_snapshot(
        db_path=db_path,
        observed_at_utc=datetime(2026, 1, 20, 11, 5, tzinfo=timezone.utc),
        balance_dollars=3.0,
        portfolio_value_dollars=4.0,
    )

    df = load_snapshots_since(
        db_path=db_path,
        since_utc=datetime(2026, 1, 20, 11, 0, tzinfo=timezone.utc),
    )
    assert len(df) == 1
    assert float(df.iloc[0]["portfolio_value_dollars"]) == 4.0
