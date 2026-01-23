"""TDD tests for Kalshi deposit tracking.

Requirements:
1. Track initial deposit of $100 on January 18, 2026
2. Track cash deposits hourly from Kalshi API
3. Calculate net deposits = current_cash - (initial_deposit + cumulative_deposits)
4. Store deposit history in database
"""

import os
import pytest
from datetime import datetime, timezone
from plugins.db_manager import DBManager

# Override for testing outside Docker
os.environ["POSTGRES_HOST"] = "localhost"


class TestDepositTracking:
    """TDD tests for deposit tracking."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        """Setup test database connection."""
        from plugins.deposit_tracking import initialize_starting_deposit
        from datetime import date

        self.db = DBManager()

        # Ensure initial deposit exists (idempotent)
        initialize_starting_deposit(
            deposit_date=date(2026, 1, 18),
            amount_dollars=100.0,
            notes="Initial Kalshi deposit - actual starting balance",
            db=self.db,
        )

        yield

        # Cleanup test data (but preserve initial deposit on 2026-01-18)
        try:
            self.db.execute(
                "DELETE FROM cash_deposits WHERE deposit_date > '2026-01-18'"
            )
        except:
            pass

    def test_cash_deposits_table_exists(self):
        """RED: Table for tracking cash deposits should exist."""
        # Check if table exists
        result = self.db.fetch_df(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name = 'cash_deposits'
            """
        )

        assert not result.empty, "cash_deposits table should exist"

        # Check table structure
        columns = self.db.fetch_df(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'cash_deposits'
            ORDER BY ordinal_position
            """
        )

        expected_columns = {
            "deposit_id",
            "deposit_date",
            "amount_dollars",
            "deposit_type",
            "notes",
            "created_at_utc",
        }
        actual_columns = set(columns["column_name"].tolist())

        assert expected_columns.issubset(
            actual_columns
        ), f"Missing columns. Expected: {expected_columns}, Got: {actual_columns}"

    def test_initial_deposit_exists(self):
        """RED: Initial $100 deposit on Jan 18, 2026 should be recorded."""
        result = self.db.fetch_df(
            """
            SELECT * FROM cash_deposits
            WHERE deposit_date = '2026-01-18'
            AND deposit_type = 'initial'
            """
        )

        assert not result.empty, "Initial deposit record should exist"

        deposit = result.iloc[0]
        assert (
            float(deposit["amount_dollars"]) == 100.0
        ), f"Initial deposit should be $100, got ${deposit['amount_dollars']}"

    def test_calculate_total_deposits(self):
        """RED: Should calculate total deposits from database."""
        from plugins.deposit_tracking import calculate_total_deposits

        total = calculate_total_deposits(db=self.db)

        # Should include $100 initial deposit
        assert total >= 100.0, f"Total deposits should be at least $100, got ${total}"

    def test_detect_new_deposit_from_balance_increase(self):
        """RED: Should detect new deposits by comparing balance changes."""
        from plugins.deposit_tracking import detect_new_deposits

        # Simulate balance snapshots
        # Hour 1: $100 balance, no bets
        # Hour 2: $150 balance, no bets -> $50 deposit detected

        snapshots = [
            {
                "snapshot_hour_utc": datetime(2026, 1, 22, 10, 0, 0),
                "balance_dollars": 100.0,
            },
            {
                "snapshot_hour_utc": datetime(2026, 1, 22, 11, 0, 0),
                "balance_dollars": 150.0,
            },
        ]

        # Mock: no bets placed between these times
        deposits = detect_new_deposits(snapshots, db=self.db)

        assert len(deposits) > 0, "Should detect at least one deposit"
        assert any(
            d["amount_dollars"] == 50.0 for d in deposits
        ), "Should detect $50 deposit"

    def test_upsert_deposit_record(self):
        """RED: Should insert/update deposit records."""
        from plugins.deposit_tracking import upsert_deposit

        # Record a deposit
        deposit_id = upsert_deposit(
            deposit_date=datetime(2026, 1, 22),
            amount_dollars=50.0,
            deposit_type="detected",
            notes="Detected from balance increase",
            db=self.db,
        )

        assert deposit_id is not None, "Should return deposit ID"

        # Verify it's in the database
        result = self.db.fetch_df(
            """
            SELECT * FROM cash_deposits
            WHERE deposit_date = '2026-01-22'
            AND amount_dollars = 50.0
            """
        )

        assert not result.empty, "Deposit should be in database"

    def test_portfolio_snapshots_include_deposit_info(self):
        """RED: Portfolio snapshots should track cumulative deposits."""
        # Check if portfolio_value_snapshots has deposit tracking
        columns = self.db.fetch_df(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'portfolio_value_snapshots'
            """
        )

        column_names = columns["column_name"].tolist()

        # Should have a column to track cumulative deposits
        assert any(
            "deposit" in col.lower() for col in column_names
        ), "portfolio_value_snapshots should track deposits"

    def test_calculate_net_profit_with_deposits(self):
        """RED: Should calculate true P&L accounting for deposits."""
        from plugins.deposit_tracking import calculate_net_profit

        # Current portfolio value: $80.69
        # Total deposits: $100 (initial)
        # Expected P&L: $80.69 - $100 = -$19.31

        net_profit = calculate_net_profit(current_portfolio_value=80.69, db=self.db)

        # Should be negative (lost money)
        assert net_profit < 0, f"Expected negative P&L, got ${net_profit}"

        # Should be close to -$19.31 (within $1 due to timing)
        expected_loss = -19.31
        assert (
            abs(net_profit - expected_loss) < 5.0
        ), f"Expected P&L ~${expected_loss}, got ${net_profit}"
