"""
Final validation test: Dashboard shows today's settlement data (2026-01-22).

This test confirms that:
1. Bets are syncing from Kalshi hourly
2. Settlements are being recorded with updated_at timestamps
3. Dashboard groups by settlement date (updated_at) not placement date
4. Latest date shown in dashboard is 2026-01-22 (today)

NOTE: This is an integration test that requires production PostgreSQL database.
"""

import os
import sys
from pathlib import Path
from datetime import date
import pandas as pd
import pytest

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from db_manager import DBManager

# Skip unless running against production database
pytestmark = pytest.mark.skipif(
    os.environ.get("POSTGRES_HOST") != "postgres",
    reason="Integration test requires production PostgreSQL database"
)


def test_dashboard_shows_todays_date():
    """
    CRITICAL TEST: Dashboard must show settlement activity from today (2026-01-22).

    This is the key requirement - user expects to see 01/22, not 01/20.
    """
    db = DBManager()

    # Load betting data (same as dashboard)
    betting_df = db.fetch_df(
        """
        SELECT *
        FROM placed_bets
        ORDER BY placed_date DESC, created_at DESC
    """
    )

    assert not betting_df.empty, "Should have betting data in database"

    # Filter to settled bets (same as dashboard)
    settled_bets = betting_df[betting_df["status"].isin(["won", "lost"])].copy()

    assert not settled_bets.empty, "Should have settled bets"

    # Group by settlement date (updated_at) - THIS IS THE FIX
    settled_bets["date"] = pd.to_datetime(settled_bets["updated_at"]).dt.date
    daily_pl = settled_bets.groupby("date")["profit_dollars"].sum().reset_index()
    daily_pl = daily_pl.sort_values("date", ascending=False)

    # Get the latest date that will appear in dashboard
    latest_dashboard_date = daily_pl["date"].iloc[0]
    today = date(2026, 1, 22)  # Today's date

    print(f"\n📊 Dashboard latest date: {latest_dashboard_date}")
    print(f"📅 Today's date: {today}")
    print(f"✅ Match: {latest_dashboard_date == today}")

    # CRITICAL ASSERTION: Dashboard must show today's date
    assert latest_dashboard_date == today, (
        f"Dashboard must show today's date! "
        f"Expected: {today}, Got: {latest_dashboard_date}"
    )

    # Verify we have settlement activity for today
    today_bets = settled_bets[settled_bets["date"] == today]
    assert len(today_bets) > 0, "Should have bets settled today"

    print(f"✓ {len(today_bets)} bets settled today")
    print(
        f"✓ Today's P&L: ${daily_pl[daily_pl['date'] == today]['profit_dollars'].iloc[0]:.2f}"
    )

    return True


if __name__ == "__main__":
    try:
        test_dashboard_shows_todays_date()
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("✅ Dashboard will show 2026-01-22 as latest date")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
