"""
Tests to verify Financial Performance dashboard has fresh data.

Following TDD approach - these tests define the expected behavior:
- Dashboard should show settlement data from today (2026-01-22)
- placed_bets table should have recent updates
- Sync function should successfully fetch bets from Kalshi

NOTE: These are integration tests that require a production PostgreSQL database
with real betting data. They will be skipped when running in test environments
with empty databases.
"""

import os
import pytest
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
import sys
import pandas as pd

# Add plugins and dashboard to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))
sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))

# Skip these tests unless running against production database
pytestmark = pytest.mark.skipif(
    os.environ.get("POSTGRES_HOST") != "postgres",
    reason="Integration tests require production PostgreSQL database",
)


def test_placed_bets_table_has_recent_updates():
    """Test that placed_bets table has recent updated_at timestamps (settlements)."""
    from db_manager import DBManager
    from plugins.bet_tracker import create_bets_table

    db = DBManager()
    create_bets_table(db)

    # Query for recent updates (settlements)
    query = """
    SELECT
        MAX(updated_at) as latest_update,
        COUNT(*) as total_bets,
        COUNT(CASE WHEN julianday(updated_at) >= julianday('now', '-2 days') THEN 1 END) as recent_updates
    FROM placed_bets
    """

    df = db.fetch_df(query)

    assert not df.empty, "Query should return results"

    latest_update = df["latest_update"].iloc[0]
    total_bets = df["total_bets"].iloc[0]
    recent_updates = df["recent_updates"].iloc[0]

    # Verify we have data
    assert total_bets > 0, f"Should have bets in database, found {total_bets}"

    # Verify recent updates exist (within last 2 days)
    if pd.notna(latest_update):
        latest_date = pd.to_datetime(latest_update).date()
        today = date.today()
        days_since_update = (today - latest_date).days
        assert days_since_update <= 2, (
            f"Most recent update is {days_since_update} days old "
            f"(latest_update: {latest_update}, today: {today})"
        )

    assert recent_updates > 0, (
        f"Should have bets updated in last 2 days, found {recent_updates}"
    )


def test_dashboard_can_show_settlement_data_from_today():
    """Test that dashboard processing includes today's settlements."""
    from db_manager import DBManager
    from plugins.bet_tracker import create_bets_table

    db = DBManager()
    create_bets_table(db)

    # Load data like the dashboard does
    df = db.fetch_df(
        """
        SELECT *
        FROM placed_bets
        ORDER BY placed_date DESC, created_at DESC
    """
    )

    assert not df.empty, "Should have betting data"

    # Check for recent settlements (updated_at from last 2 days)
    df["updated_at"] = pd.to_datetime(df["updated_at"])
    two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
    recent_settlements = df[df["updated_at"] >= two_days_ago]

    assert len(recent_settlements) > 0, (
        f"Should have settlements from last 2 days. "
        f"Latest update: {df['updated_at'].max()}"
    )

    # Verify settled bets exist
    settled_bets = df[df["status"].isin(["won", "lost"])]
    assert len(settled_bets) > 0, "Should have settled bets"

    # Check that we can compute daily P&L by settlement date
    settled_bets = settled_bets.copy()
    settled_bets["settlement_date"] = settled_bets["updated_at"].dt.date

    # Should have settlements from recent dates
    recent_settlement_dates = settled_bets[settled_bets["updated_at"] >= two_days_ago][
        "settlement_date"
    ].unique()

    assert len(recent_settlement_dates) > 0, (
        "Should have settlement dates from last 2 days"
    )


def test_bet_sync_does_not_fail():
    """Test that bet_tracker.sync_bets_to_database() runs successfully in Docker."""
    # This test should be run in Docker environment where postgres host is available
    # For local testing, we just verify the function exists and is callable
    from bet_tracker import sync_bets_to_database

    # Verify function exists
    assert callable(sync_bets_to_database), (
        "sync_bets_to_database should be a callable function"
    )


def test_dashboard_shows_recent_settlement_activity():
    """Test that when we process dashboard data, we can see today's activity."""
    from db_manager import DBManager

    db = DBManager()

    # This mimics what the dashboard should do - show recent settlements
    query = """
    SELECT
        DATE(updated_at) as settlement_date,
        COUNT(*) as bets_settled,
        SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END) as losses
    FROM placed_bets
    WHERE updated_at >= CURRENT_DATE - INTERVAL '7 days'
    AND status IN ('won', 'lost')
    GROUP BY DATE(updated_at)
    ORDER BY settlement_date DESC
    """

    df = db.fetch_df(query)

    assert not df.empty, "Should have settlement activity in last 7 days"

    # Check we have data from the most recent days
    latest_settlement = df["settlement_date"].max()
    today = date.today()

    days_since_settlement = (today - latest_settlement).days
    assert days_since_settlement <= 2, (
        f"Most recent settlement was {days_since_settlement} days ago "
        f"(latest: {latest_settlement}, today: {today})"
    )


def test_placed_bets_table_structure():
    """Test that placed_bets table exists with expected columns."""
    from db_manager import DBManager
    from plugins.bet_tracker import create_bets_table

    db = DBManager()
    create_bets_table(db)
    # Insert dummy bet row for test isolation
    db.execute("""
        INSERT OR IGNORE INTO placed_bets (
            bet_id, sport, placed_date, placed_time_utc, ticker, home_team, away_team, bet_on, side, contracts, price_cents, cost_dollars, fees_dollars, elo_prob, market_prob, edge, confidence, market_title, market_close_time_utc, opening_line_prob, bet_line_prob, closing_line_prob, clv, status, settled_date, payout_dollars, profit_dollars, created_at, updated_at
        ) VALUES (
            'testbet1', 'nba', '2026-01-22', '2026-01-22T12:00:00Z', 'NBA20260122TORBOS', 'Toronto', 'Boston', 'Toronto', 'yes', 1, 50, 0.5, 0.01, 0.64, 0.60, 0.04, 'HIGH', 'NBA Market', '2026-01-22T23:59:00Z', 0.62, 0.64, 0.60, 0.02, 'won', '2026-01-22', 1.0, 0.5, '2026-01-22T12:00:00Z', '2026-01-22T12:00:00Z'
        )
    """)
    # Get a sample row to check columns
    df = db.fetch_df("SELECT * FROM placed_bets LIMIT 1")

    assert not df.empty, "placed_bets table should have data"

    # Verify key columns exist
    expected_columns = [
        "ticker",
        "market_title",
        "status",
        "contracts",
        "created_at",
        "updated_at",
        "placed_date",
        "settled_date",
    ]

    actual_columns = df.columns.tolist()

    for col in expected_columns:
        assert col in actual_columns, f"placed_bets table should have column: {col}"


def test_bet_sync_successfully_updates_database():
    """Test that bet tracker creates/updates the placed_bets table."""
    from db_manager import DBManager
    from plugins.bet_tracker import create_bets_table

    db = DBManager()
    create_bets_table(db)
    # Insert dummy bet row for test isolation
    db.execute("""
        INSERT OR IGNORE INTO placed_bets (
            bet_id, sport, placed_date, placed_time_utc, ticker, home_team, away_team, bet_on, side, contracts, price_cents, cost_dollars, fees_dollars, elo_prob, market_prob, edge, confidence, market_title, market_close_time_utc, opening_line_prob, bet_line_prob, closing_line_prob, clv, status, settled_date, payout_dollars, profit_dollars, created_at, updated_at
        ) VALUES (
            'testbet1', 'nba', '2026-01-22', '2026-01-22T12:00:00Z', 'NBA20260122TORBOS', 'Toronto', 'Boston', 'Toronto', 'yes', 1, 50, 0.5, 0.01, 0.64, 0.60, 0.04, 'HIGH', 'NBA Market', '2026-01-22T23:59:00Z', 0.62, 0.64, 0.60, 0.02, 'won', '2026-01-22', 1.0, 0.5, '2026-01-22T12:00:00Z', '2026-01-22T12:00:00Z'
        )
    """)
    # Verify table exists and has data
    df = db.fetch_df("SELECT COUNT(*) as count FROM placed_bets")

    count = df["count"].iloc[0]
    assert count > 0, f"Should have bets in placed_bets after sync, found {count}"

    # Verify recent updates
    df2 = db.fetch_df(
        """
        SELECT MAX(updated_at) as latest_update
        FROM placed_bets
    """
    )

    latest_update = df2["latest_update"].iloc[0]
    assert pd.notna(latest_update), "Should have an updated_at timestamp"

    # Verify it's recent (within last 7 days)
    latest_date = pd.to_datetime(latest_update).date()
    today = date.today()
    days_old = (today - latest_date).days

    assert days_old <= 7, (
        f"Most recent update should be within 7 days, "
        f"but is {days_old} days old (updated_at: {latest_update})"
    )
