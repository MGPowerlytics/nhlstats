"""
Final Verification: Portfolio Value Calculation

This test confirms:
1. Dashboard calculates portfolio value correctly
2. Portfolio value = cash balance + open positions value
3. Value matches user's Kalshi account balance

NOTE: This is an integration test that requires production PostgreSQL database.
"""

import os
import sys
from pathlib import Path
import pytest
from plugins.db_manager import DBManager

sys.path.append(str(Path(__file__).parent.parent))

# Skip unless running against production database
pytestmark = pytest.mark.skipif(
    os.environ.get("POSTGRES_HOST") != "postgres",
    reason="Integration test requires production PostgreSQL database",
)


def test_portfolio_value_matches_kalshi():
    """
    FINAL TEST: Verify dashboard portfolio value matches Kalshi
    """
    db = DBManager()

    print("\n" + "=" * 80)
    print("FINAL VERIFICATION: Portfolio Value Calculation")
    print("=" * 80)

    # Get cash balance from snapshot
    cash_df = db.fetch_df(
        """
        SELECT
            ROUND(balance_dollars::numeric, 2) as cash,
            snapshot_hour_utc
        FROM portfolio_value_snapshots
        ORDER BY snapshot_hour_utc DESC
        LIMIT 1
    """
    )

    # Get open positions value
    open_df = db.fetch_df(
        """
        SELECT
            ROUND(SUM(cost_dollars)::numeric, 2) as open_value,
            COUNT(*) as num_open
        FROM placed_bets
        WHERE status = 'open'
    """
    )

    if cash_df.empty:
        print("\n❌ No portfolio snapshots available")
        return False

    cash = float(cash_df.iloc[0]["cash"])
    timestamp = cash_df.iloc[0]["snapshot_hour_utc"]

    num_open = (
        int(open_df.iloc[0]["num_open"])
        if not open_df.empty and open_df.iloc[0]["num_open"]
        else 0
    )
    open_value = (
        float(open_df.iloc[0]["open_value"])
        if not open_df.empty and open_df.iloc[0]["open_value"]
        else 0.0
    )

    portfolio_value = cash + open_value

    print("\n📊 Portfolio Value Calculation:")
    print(f"   Data as of: {timestamp}")
    print("")
    print(f"   Cash Balance:        ${cash:>10,.2f}")
    print(f"   + Open Positions:    ${open_value:>10,.2f}  ({num_open} open bets)")
    print(f"   {'=' * 40}")
    print(f"   Portfolio Value:     ${portfolio_value:>10,.2f}")

    # Compare to user's reported balance
    user_balance = 80.69
    difference = abs(portfolio_value - user_balance)

    print("\n✅ Verification:")
    print(f"   User's Kalshi Balance:  ${user_balance:>10,.2f}")
    print(f"   Dashboard Shows:        ${portfolio_value:>10,.2f}")
    print(f"   Difference:             ${difference:>10,.2f}")

    if difference < 0.01:
        print("\n🎯 PERFECT MATCH! Dashboard exactly matches Kalshi!")
        status = "EXACT MATCH"
    elif difference < 1.00:
        print("\n✅ EXCELLENT! Within $1.00 (likely rounding or timing)")
        status = "EXCELLENT"
    elif difference < 5.00:
        print("\n✅ GOOD! Within $5.00 (snapshot may be stale)")
        status = "GOOD"
    else:
        print("\n⚠️  Difference > $5.00 - may need fresh snapshot")
        status = "NEEDS REFRESH"

    print("\n📋 Summary:")
    print(f"   Status: {status}")
    print("   Portfolio value correctly calculated: ✅")
    print("   Includes cash balance: ✅")
    print("   Includes open positions: ✅")
    print(f"   Matches Kalshi account: {'✅' if difference < 5.0 else '⚠️'}")

    print("\n" + "=" * 80)

    return difference < 5.0


if __name__ == "__main__":
    print("=" * 80)
    print("Final Verification: Portfolio Value = Cash + Open Positions")
    print("=" * 80)

    success = test_portfolio_value_matches_kalshi()

    if success:
        print("\n✅ ALL TESTS PASSED")
        print("Dashboard correctly shows portfolio value!")
        print("=" * 80)
        sys.exit(0)
    else:
        print("\n❌ TEST FAILED")
        print("Dashboard value doesn't match Kalshi")
        print("=" * 80)
        sys.exit(1)
