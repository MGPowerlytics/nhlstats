"""Provider contract tests for the PortfolioSnapshots boundary.

Validates that ``upsert_hourly_snapshot()``, ``load_latest_snapshot()``, and
``load_snapshots_since()`` produce outputs that conform to the portfolio
snapshots contract schema. Uses mock DB dependencies to avoid requiring
a live PostgreSQL instance.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from jsonschema import Draft202012Validator, ValidationError

from plugins.portfolio_snapshots import (
    PortfolioSnapshot,
    upsert_hourly_snapshot,
    load_latest_snapshot,
    load_snapshots_since,
)

SCHEMA_PATH = (
    Path(__file__).parent / "schemas" / "portfolio_snapshots_contract_v1.json"
)

# ---------------------------------------------------------------------------
# Deterministic test values
# ---------------------------------------------------------------------------

SNAPSHOT_HOUR = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
BALANCE_DOLLARS = 8500.00
PORTFOLIO_VALUE_DOLLARS = 12500.00
CUMULATIVE_DEPOSITS = 5000.00


def _make_snapshot_row_df(
    snapshot_hour_utc: datetime | str = SNAPSHOT_HOUR,
    balance_dollars: float = BALANCE_DOLLARS,
    portfolio_value_dollars: float = PORTFOLIO_VALUE_DOLLARS,
    created_at_utc: datetime | str | None = None,
) -> pd.DataFrame:
    """Build a deterministic DataFrame matching the shape returned by
    portfolio_snapshots queries."""
    if created_at_utc is None:
        created_at_utc = SNAPSHOT_HOUR
    return pd.DataFrame([
        {
            "snapshot_hour_utc": snapshot_hour_utc,
            "balance_dollars": balance_dollars,
            "portfolio_value_dollars": portfolio_value_dollars,
            "created_at_utc": created_at_utc,
        }
    ])


def _build_snapshot_result_from_snapshot(
    snapshot: PortfolioSnapshot,
) -> dict[str, Any]:
    """Convert a PortfolioSnapshot dataclass into a contract-conformant
    ``portfolio_snapshot_result`` dict.

    Derives fields from the available dataclass fields:
    - date_str from snapshot_hour_utc
    - total_value from portfolio_value_dollars
    - cash_balance from balance_dollars
    - positions_value as portfolio_value_dollars - balance_dollars (approx)
    - unrealized_pnl as portfolio_value_dollars - cumulative_deposits_dollars
    - realized_pnl as 0 (not tracked in the dataclass)
    - position_count as 0 (not tracked in the dataclass)
    """
    snapshot_hour = snapshot.snapshot_hour_utc
    if snapshot_hour.tzinfo is not None:
        date_str = snapshot_hour.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        date_str = snapshot_hour.isoformat()

    total_value = snapshot.portfolio_value_dollars
    cash_balance = snapshot.balance_dollars
    positions_value = total_value - cash_balance
    # Approximate PnL: current value minus cumulative deposits
    unrealized_pnl = total_value - snapshot.cumulative_deposits_dollars

    return {
        "date_str": date_str,
        "total_value": total_value,
        "cash_balance": cash_balance,
        "positions_value": max(0.0, positions_value),
        "unrealized_pnl": unrealized_pnl,
        "realized_pnl": 0.0,
        "position_count": 0,
    }


def _build_summary_from_snapshots(
    snapshots: list[PortfolioSnapshot],
) -> dict[str, Any]:
    """Build a ``snapshot_summary`` dict from a list of PortfolioSnapshot
    dataclass instances."""
    if not snapshots:
        return {
            "start_date": "N/A",
            "end_date": "N/A",
            "snapshot_count": 0,
            "total_return": 0.0,
            "avg_daily_return": 0.0,
        }

    dates = [s.snapshot_hour_utc for s in snapshots]
    start_date = min(dates)
    end_date = max(dates)

    first_value = snapshots[0].portfolio_value_dollars
    last_value = snapshots[-1].portfolio_value_dollars
    total_return = last_value - first_value

    days_diff = max((end_date - start_date).days, 1)
    avg_daily_return = total_return / days_diff

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    return {
        "start_date": start_str,
        "end_date": end_str,
        "snapshot_count": len(snapshots),
        "total_return": total_return,
        "avg_daily_return": avg_daily_return,
    }


def _build_combined_payload(
    snapshot_result: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    """Combine a portfolio_snapshot_result and snapshot_summary into the
    top-level contract payload."""
    return {
        "portfolio_snapshot_result": snapshot_result,
        "snapshot_summary": summary,
    }


# ---------------------------------------------------------------------------
# Mock DB helpers
# ---------------------------------------------------------------------------


def _make_mock_db() -> MagicMock:
    """Create a mock DBManager that returns empty results by default."""
    mock_db = MagicMock()
    mock_db.table_exists.return_value = True
    return mock_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def snapshots_schema() -> dict[str, Any]:
    """Load the portfolio snapshots schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate(schema: dict[str, Any], payload: dict[str, Any]) -> None:
    Draft202012Validator(schema).validate(payload)


# ---------------------------------------------------------------------------
# Provider tests: upsert_hourly_snapshot
# ---------------------------------------------------------------------------


class TestUpsertHourlySnapshot:
    """``upsert_hourly_snapshot()`` output must conform to the contract schema."""

    @patch("plugins.portfolio_snapshots.default_db")
    def test_upsert_returns_portfolio_snapshot_dataclass(
        self, mock_db: MagicMock, snapshots_schema: dict[str, Any]
    ) -> None:
        """The upsert function must return a PortfolioSnapshot dataclass, and
        its serialized form must validate against the contract schema after
        transformation."""
        mock_db.table_exists.return_value = True
        mock_db.fetch_df.side_effect = [
            pd.DataFrame(),  # first call handled internally
            _make_snapshot_row_df(),  # return the upserted row
        ]

        snapshot = upsert_hourly_snapshot(
            balance_dollars=BALANCE_DOLLARS,
            portfolio_value_dollars=PORTFOLIO_VALUE_DOLLARS,
            observed_at_utc=SNAPSHOT_HOUR,
            db=mock_db,
        )

        assert isinstance(snapshot, PortfolioSnapshot)
        assert snapshot.balance_dollars == BALANCE_DOLLARS
        assert snapshot.portfolio_value_dollars == PORTFOLIO_VALUE_DOLLARS

        # Build the contract payload from the dataclass
        result = _build_snapshot_result_from_snapshot(snapshot)
        summary = {
            "start_date": SNAPSHOT_HOUR.strftime("%Y-%m-%d"),
            "end_date": SNAPSHOT_HOUR.strftime("%Y-%m-%d"),
            "snapshot_count": 1,
            "total_return": 0.0,
            "avg_daily_return": 0.0,
        }
        payload = _build_combined_payload(result, summary)
        _validate(snapshots_schema, payload)

    @patch("plugins.portfolio_snapshots.default_db")
    def test_upsert_balance_dollars_is_non_negative(
        self, mock_db: MagicMock, snapshots_schema: dict[str, Any]
    ) -> None:
        mock_db.table_exists.return_value = True
        mock_db.fetch_df.side_effect = [
            pd.DataFrame(),
            _make_snapshot_row_df(),
        ]

        snapshot = upsert_hourly_snapshot(
            balance_dollars=0.0,
            portfolio_value_dollars=5000.0,
            observed_at_utc=SNAPSHOT_HOUR,
            db=mock_db,
        )

        assert snapshot.balance_dollars >= 0

    @patch("plugins.portfolio_snapshots.default_db")
    def test_upsert_portfolio_value_dollars_matches_input(
        self, mock_db: MagicMock, snapshots_schema: dict[str, Any]
    ) -> None:
        mock_db.table_exists.return_value = True
        mock_db.fetch_df.side_effect = [
            pd.DataFrame(),
            _make_snapshot_row_df(portfolio_value_dollars=20000.0),
        ]

        snapshot = upsert_hourly_snapshot(
            balance_dollars=10000.0,
            portfolio_value_dollars=20000.0,
            observed_at_utc=SNAPSHOT_HOUR,
            db=mock_db,
        )

        assert snapshot.portfolio_value_dollars == pytest.approx(20000.0)

    @patch("plugins.portfolio_snapshots.default_db")
    def test_upsert_snapshot_hour_is_rounded_to_hour(
        self, mock_db: MagicMock, snapshots_schema: dict[str, Any]
    ) -> None:
        mock_db.table_exists.return_value = True
        mock_db.fetch_df.side_effect = [
            pd.DataFrame(),
            _make_snapshot_row_df(
                snapshot_hour_utc=datetime(2026, 1, 15, 10, 0, 0)
            ),
        ]

        odd_minute = datetime(2026, 1, 15, 10, 37, 42, tzinfo=timezone.utc)
        snapshot = upsert_hourly_snapshot(
            balance_dollars=BALANCE_DOLLARS,
            portfolio_value_dollars=PORTFOLIO_VALUE_DOLLARS,
            observed_at_utc=odd_minute,
            db=mock_db,
        )

        assert snapshot.snapshot_hour_utc.hour == 10
        assert snapshot.snapshot_hour_utc.minute == 0

    @patch("plugins.portfolio_snapshots.default_db")
    def test_upsert_produces_schema_compliant_result(
        self, mock_db: MagicMock, snapshots_schema: dict[str, Any]
    ) -> None:
        mock_db.table_exists.return_value = True
        mock_db.fetch_df.side_effect = [
            pd.DataFrame(),
            _make_snapshot_row_df(),
        ]

        snapshot = upsert_hourly_snapshot(
            balance_dollars=BALANCE_DOLLARS,
            portfolio_value_dollars=PORTFOLIO_VALUE_DOLLARS,
            observed_at_utc=SNAPSHOT_HOUR,
            db=mock_db,
        )

        result = _build_snapshot_result_from_snapshot(snapshot)
        summary = {
            "start_date": SNAPSHOT_HOUR.strftime("%Y-%m-%d"),
            "end_date": SNAPSHOT_HOUR.strftime("%Y-%m-%d"),
            "snapshot_count": 1,
            "total_return": 0.0,
            "avg_daily_return": 0.0,
        }
        payload = _build_combined_payload(result, summary)
        _validate(snapshots_schema, payload)


# ---------------------------------------------------------------------------
# Provider tests: load_latest_snapshot
# ---------------------------------------------------------------------------


class TestLoadLatestSnapshot:
    """``load_latest_snapshot()`` output must conform to the contract schema."""

    @patch("plugins.portfolio_snapshots.default_db")
    def test_load_latest_returns_portfolio_snapshot(
        self, mock_db: MagicMock, snapshots_schema: dict[str, Any]
    ) -> None:
        mock_db.table_exists.return_value = True
        mock_db.fetch_df.return_value = _make_snapshot_row_df()

        snapshot = load_latest_snapshot(db=mock_db)

        assert isinstance(snapshot, PortfolioSnapshot)
        assert snapshot.portfolio_value_dollars == PORTFOLIO_VALUE_DOLLARS
        assert snapshot.balance_dollars == BALANCE_DOLLARS

    @patch("plugins.portfolio_snapshots.default_db")
    def test_load_latest_returns_none_when_table_missing(
        self, mock_db: MagicMock
    ) -> None:
        mock_db.table_exists.return_value = False
        snapshot = load_latest_snapshot(db=mock_db)
        assert snapshot is None

    @patch("plugins.portfolio_snapshots.default_db")
    def test_load_latest_returns_none_when_no_data(
        self, mock_db: MagicMock
    ) -> None:
        mock_db.table_exists.return_value = True
        mock_db.fetch_df.return_value = pd.DataFrame()

        snapshot = load_latest_snapshot(db=mock_db)
        assert snapshot is None

    @patch("plugins.portfolio_snapshots.default_db")
    def test_load_latest_output_validates_against_schema(
        self, mock_db: MagicMock, snapshots_schema: dict[str, Any]
    ) -> None:
        mock_db.table_exists.return_value = True
        mock_db.fetch_df.return_value = _make_snapshot_row_df()

        snapshot = load_latest_snapshot(db=mock_db)
        assert snapshot is not None

        result = _build_snapshot_result_from_snapshot(snapshot)
        summary = {
            "start_date": SNAPSHOT_HOUR.strftime("%Y-%m-%d"),
            "end_date": SNAPSHOT_HOUR.strftime("%Y-%m-%d"),
            "snapshot_count": 1,
            "total_return": 0.0,
            "avg_daily_return": 0.0,
        }
        payload = _build_combined_payload(result, summary)
        _validate(snapshots_schema, payload)

    @patch("plugins.portfolio_snapshots.default_db")
    def test_load_latest_balance_dollars_non_negative(
        self, mock_db: MagicMock
    ) -> None:
        mock_db.table_exists.return_value = True
        mock_db.fetch_df.return_value = _make_snapshot_row_df(
            balance_dollars=0.0
        )

        snapshot = load_latest_snapshot(db=mock_db)
        assert snapshot is not None
        assert snapshot.balance_dollars >= 0


# ---------------------------------------------------------------------------
# Provider tests: load_snapshots_since
# ---------------------------------------------------------------------------


class TestLoadSnapshotsSince:
    """``load_snapshots_since()`` output must enable contract-conformant summaries."""

    @patch("plugins.portfolio_snapshots.default_db")
    def test_load_snapshots_since_returns_dataframe(
        self, mock_db: MagicMock, snapshots_schema: dict[str, Any]
    ) -> None:
        mock_db.table_exists.return_value = True
        mock_db.fetch_df.return_value = pd.DataFrame([
            {
                "snapshot_hour_utc": datetime(2026, 1, 15, 10, 0, 0),
                "balance_dollars": 8500.0,
                "portfolio_value_dollars": 12500.0,
            },
            {
                "snapshot_hour_utc": datetime(2026, 1, 15, 11, 0, 0),
                "balance_dollars": 8600.0,
                "portfolio_value_dollars": 12600.0,
            },
        ])

        df = load_snapshots_since(
            since_utc=datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
            db=mock_db,
        )

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

        # Build PortfolioSnapshot objects from the DataFrame
        snapshots: list[PortfolioSnapshot] = []
        for _, row in df.iterrows():
            snapshots.append(
                PortfolioSnapshot(
                    snapshot_hour_utc=pd.to_datetime(
                        row["snapshot_hour_utc"]
                    ).replace(tzinfo=timezone.utc),
                    balance_dollars=float(row["balance_dollars"] or 0.0),
                    portfolio_value_dollars=float(
                        row["portfolio_value_dollars"] or 0.0
                    ),
                    created_at_utc=datetime.now(timezone.utc),
                )
            )

        # Validate the first snapshot result
        result = _build_snapshot_result_from_snapshot(snapshots[0])
        summary = _build_summary_from_snapshots(snapshots)
        payload = _build_combined_payload(result, summary)
        _validate(snapshots_schema, payload)

    @patch("plugins.portfolio_snapshots.default_db")
    def test_load_snapshots_since_empty_data(
        self, mock_db: MagicMock
    ) -> None:
        mock_db.table_exists.return_value = True
        mock_db.fetch_df.return_value = pd.DataFrame()

        df = load_snapshots_since(
            since_utc=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            db=mock_db,
        )

        assert isinstance(df, pd.DataFrame)
        assert df.empty

    @patch("plugins.portfolio_snapshots.default_db")
    def test_load_snapshots_since_missing_table(
        self, mock_db: MagicMock
    ) -> None:
        mock_db.table_exists.return_value = False

        df = load_snapshots_since(
            since_utc=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            db=mock_db,
        )

        assert isinstance(df, pd.DataFrame)
        assert df.empty

    @patch("plugins.portfolio_snapshots.default_db")
    def test_load_snapshots_since_produces_valid_summary(
        self, mock_db: MagicMock, snapshots_schema: dict[str, Any]
    ) -> None:
        """Summary built from multiple snapshots must validate."""
        mock_db.table_exists.return_value = True
        mock_db.fetch_df.return_value = pd.DataFrame([
            {
                "snapshot_hour_utc": datetime(2026, 1, 1, 10, 0, 0),
                "balance_dollars": 8000.0,
                "portfolio_value_dollars": 10000.0,
            },
            {
                "snapshot_hour_utc": datetime(2026, 1, 8, 10, 0, 0),
                "balance_dollars": 8500.0,
                "portfolio_value_dollars": 12000.0,
            },
            {
                "snapshot_hour_utc": datetime(2026, 1, 15, 10, 0, 0),
                "balance_dollars": 9000.0,
                "portfolio_value_dollars": 15000.0,
            },
        ])

        df = load_snapshots_since(
            since_utc=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            db=mock_db,
        )

        snapshots: list[PortfolioSnapshot] = []
        for _, row in df.iterrows():
            snapshots.append(
                PortfolioSnapshot(
                    snapshot_hour_utc=pd.to_datetime(
                        row["snapshot_hour_utc"]
                    ).replace(tzinfo=timezone.utc),
                    balance_dollars=float(row["balance_dollars"] or 0.0),
                    portfolio_value_dollars=float(
                        row["portfolio_value_dollars"] or 0.0
                    ),
                    created_at_utc=datetime.now(timezone.utc),
                )
            )

        summary = _build_summary_from_snapshots(snapshots)
        assert summary["snapshot_count"] == 3
        # start=10000, end=15000, total_return=5000
        assert summary["total_return"] == pytest.approx(5000.0, abs=0.01)
        # 14 days diff → 5000/14 ≈ 357.14
        assert summary["avg_daily_return"] == pytest.approx(357.14, abs=0.1)

        # Validate the combined payload
        result = _build_snapshot_result_from_snapshot(snapshots[0])
        payload = _build_combined_payload(result, summary)
        _validate(snapshots_schema, payload)

    @patch("plugins.portfolio_snapshots.default_db")
    def test_load_snapshots_since_with_loss_scenario(
        self, mock_db: MagicMock, snapshots_schema: dict[str, Any]
    ) -> None:
        """Negative total_return must still validate against the schema."""
        mock_db.table_exists.return_value = True
        mock_db.fetch_df.return_value = pd.DataFrame([
            {
                "snapshot_hour_utc": datetime(2026, 1, 1, 10, 0, 0),
                "balance_dollars": 10000.0,
                "portfolio_value_dollars": 10000.0,
            },
            {
                "snapshot_hour_utc": datetime(2026, 1, 15, 10, 0, 0),
                "balance_dollars": 8000.0,
                "portfolio_value_dollars": 9500.0,
            },
        ])

        df = load_snapshots_since(
            since_utc=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            db=mock_db,
        )

        snapshots: list[PortfolioSnapshot] = []
        for _, row in df.iterrows():
            snapshots.append(
                PortfolioSnapshot(
                    snapshot_hour_utc=pd.to_datetime(
                        row["snapshot_hour_utc"]
                    ).replace(tzinfo=timezone.utc),
                    balance_dollars=float(row["balance_dollars"] or 0.0),
                    portfolio_value_dollars=float(
                        row["portfolio_value_dollars"] or 0.0
                    ),
                    created_at_utc=datetime.now(timezone.utc),
                )
            )

        summary = _build_summary_from_snapshots(snapshots)
        assert summary["total_return"] < 0  # Negative return

        result = _build_snapshot_result_from_snapshot(snapshots[0])
        payload = _build_combined_payload(result, summary)
        _validate(snapshots_schema, payload)


# ---------------------------------------------------------------------------
# Schema conformance: schema-level rejection tests
# ---------------------------------------------------------------------------


class TestPortfolioSnapshotsSchemaRejection:
    """Schema must reject invalid payloads at the contract level."""

    def test_schema_rejects_missing_portfolio_snapshot_result(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = {
            "snapshot_summary": {
                "start_date": "2026-01-01",
                "end_date": "2026-01-15",
                "snapshot_count": 15,
                "total_return": 2500.0,
                "avg_daily_return": 166.67,
            }
        }
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_schema_rejects_missing_snapshot_summary(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = {
            "portfolio_snapshot_result": {
                "date_str": "2026-01-15",
                "total_value": 12500.0,
                "cash_balance": 8500.0,
                "positions_value": 4000.0,
                "unrealized_pnl": 250.0,
                "realized_pnl": 120.0,
                "position_count": 3,
            }
        }
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_schema_rejects_negative_cash_balance(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = {
            "portfolio_snapshot_result": {
                "date_str": "2026-01-15",
                "total_value": 12500.0,
                "cash_balance": -100.0,
                "positions_value": 4000.0,
                "unrealized_pnl": 250.0,
                "realized_pnl": 120.0,
                "position_count": 3,
            },
            "snapshot_summary": {
                "start_date": "2026-01-01",
                "end_date": "2026-01-15",
                "snapshot_count": 15,
                "total_return": 2500.0,
                "avg_daily_return": 166.67,
            },
        }
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_schema_rejects_negative_position_count(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = {
            "portfolio_snapshot_result": {
                "date_str": "2026-01-15",
                "total_value": 12500.0,
                "cash_balance": 8500.0,
                "positions_value": 4000.0,
                "unrealized_pnl": 250.0,
                "realized_pnl": 120.0,
                "position_count": -1,
            },
            "snapshot_summary": {
                "start_date": "2026-01-01",
                "end_date": "2026-01-15",
                "snapshot_count": 15,
                "total_return": 2500.0,
                "avg_daily_return": 166.67,
            },
        }
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_schema_rejects_zero_snapshot_count(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = {
            "portfolio_snapshot_result": {
                "date_str": "2026-01-15",
                "total_value": 12500.0,
                "cash_balance": 8500.0,
                "positions_value": 4000.0,
                "unrealized_pnl": 250.0,
                "realized_pnl": 120.0,
                "position_count": 3,
            },
            "snapshot_summary": {
                "start_date": "2026-01-01",
                "end_date": "2026-01-15",
                "snapshot_count": 0,
                "total_return": 2500.0,
                "avg_daily_return": 166.67,
            },
        }
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_schema_rejects_extra_top_level_field(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = {
            "portfolio_snapshot_result": {
                "date_str": "2026-01-15",
                "total_value": 12500.0,
                "cash_balance": 8500.0,
                "positions_value": 4000.0,
                "unrealized_pnl": 250.0,
                "realized_pnl": 120.0,
                "position_count": 3,
            },
            "snapshot_summary": {
                "start_date": "2026-01-01",
                "end_date": "2026-01-15",
                "snapshot_count": 15,
                "total_return": 2500.0,
                "avg_daily_return": 166.67,
            },
            "extra_field": "should_not_exist",
        }
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_schema_rejects_extra_field_in_snapshot_result(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = {
            "portfolio_snapshot_result": {
                "date_str": "2026-01-15",
                "total_value": 12500.0,
                "cash_balance": 8500.0,
                "positions_value": 4000.0,
                "unrealized_pnl": 250.0,
                "realized_pnl": 120.0,
                "position_count": 3,
                "extra_field": "x",
            },
            "snapshot_summary": {
                "start_date": "2026-01-01",
                "end_date": "2026-01-15",
                "snapshot_count": 15,
                "total_return": 2500.0,
                "avg_daily_return": 166.67,
            },
        }
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)

    def test_schema_rejects_extra_field_in_summary(
        self, snapshots_schema: dict[str, Any]
    ) -> None:
        payload = {
            "portfolio_snapshot_result": {
                "date_str": "2026-01-15",
                "total_value": 12500.0,
                "cash_balance": 8500.0,
                "positions_value": 4000.0,
                "unrealized_pnl": 250.0,
                "realized_pnl": 120.0,
                "position_count": 3,
            },
            "snapshot_summary": {
                "start_date": "2026-01-01",
                "end_date": "2026-01-15",
                "snapshot_count": 15,
                "total_return": 2500.0,
                "avg_daily_return": 166.67,
                "extra_field": "y",
            },
        }
        with pytest.raises(ValidationError):
            _validate(snapshots_schema, payload)
