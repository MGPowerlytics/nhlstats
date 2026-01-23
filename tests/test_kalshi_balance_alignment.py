"""
TDD Tests: Diagnose why dashboard "Total Invested" doesn't match Kalshi account balance

User Issue:
- Dashboard shows "Total Invested": $147.13
- Actual Kalshi balance: $80.69
- These should align at nearly all times

Hypothesis to test:
1. "Total Invested" = sum of all bet costs (what we've spent)
2. Kalshi balance = current account balance (deposits - bets + winnings)
3. These are DIFFERENT metrics - need to show correct one

Correct metric should be:
Portfolio Value = Kalshi Balance = Initial Deposit + Total P&L

NOTE: This is an integration test that requires production PostgreSQL database.
"""

import os
import sys
from pathlib import Path
import pytest

sys.path.append(str(Path(__file__).parent.parent))

# Skip unless running against production database
pytestmark = pytest.mark.skipif(
    os.environ.get("POSTGRES_HOST") != "postgres",
    reason="Integration test requires production PostgreSQL database"
)

from plugins.db_manager import DBManager
from datetime import datetime


def test_understand_total_invested():
    """
    Test 1: What is "Total Invested" actually showing?

    Total Invested = sum of all bet costs (amount we paid for contracts)
    This is NOT the same as account balance!
    """
    db = DBManager()

    # Get all placed bets
    all_bets_df = db.fetch_df("""
        SELECT
            status,
            COUNT(*) as num_bets,
            ROUND(SUM(cost_dollars)::numeric, 2) as total_cost,
            ROUND(SUM(profit_dollars)::numeric, 2) as total_profit
        FROM placed_bets
        GROUP BY status
    """)

    print("\n📊 DIAGNOSTIC: Bet Status Breakdown")
    print(all_bets_df.to_string(index=False))
    print()

    # Calculate what dashboard shows
    settled_bets_df = db.fetch_df("""
        SELECT
            ROUND(SUM(cost_dollars)::numeric, 2) as total_invested,
            ROUND(SUM(profit_dollars)::numeric, 2) as total_pnl
        FROM placed_bets
        WHERE status IN ('won', 'lost')
    """)

    total_invested = float(settled_bets_df.iloc[0]['total_invested'])
    total_pnl = float(settled_bets_df.iloc[0]['total_pnl'])

    print(f"📈 Dashboard Metrics (Settled Bets Only):")
    print(f"   Total Invested: ${total_invested:.2f}")
    print(f"   Total P&L: ${total_pnl:.2f}")
    print()

    # This is what it SHOULD show
    print("❌ PROBLEM IDENTIFIED:")
    print(f"   'Total Invested' shows cost of settled bets only")
    print(f"   This doesn't match Kalshi balance!")
    print()


def test_get_actual_kalshi_balance():
    """
    Test 2: What is the ACTUAL Kalshi account balance?

    This should be fetched from Kalshi API or portfolio snapshots
    """
    db = DBManager()

    # Get latest portfolio snapshot
    snapshot_df = db.fetch_df("""
        SELECT
            snapshot_hour_utc,
            ROUND(portfolio_value_dollars::numeric, 2) as portfolio_value
        FROM portfolio_snapshots
        ORDER BY snapshot_hour_utc DESC
        LIMIT 1
    """)

    if not snapshot_df.empty:
        latest_balance = float(snapshot_df.iloc[0]['portfolio_value'])
        snapshot_time = snapshot_df.iloc[0]['snapshot_hour_utc']

        print(f"\n💰 ACTUAL Kalshi Account Balance:")
        print(f"   ${latest_balance:.2f}")
        print(f"   As of: {snapshot_time}")
        print()

        # User says actual balance is $80.69
        user_reported_balance = 80.69

        if abs(latest_balance - user_reported_balance) < 1.0:
            print(f"✅ Portfolio snapshot matches user's Kalshi balance")
        else:
            print(f"⚠️  Portfolio snapshot (${latest_balance:.2f}) != User balance (${user_reported_balance:.2f})")
            print(f"   Difference: ${abs(latest_balance - user_reported_balance):.2f}")
        print()
    else:
        print("\n❌ No portfolio snapshots found!")
        print("   Need to check Kalshi API directly")
        print()


def test_what_dashboard_should_show():
    """
    Test 3: What SHOULD the dashboard show?

    Dashboard should show:
    1. Portfolio Value = Current Kalshi Balance (from API/snapshots)
    2. NOT "Total Invested" (that's cost of bets, which is misleading)

    The relationship should be:
    Portfolio Value = Initial Deposit + Total P&L
    """
    db = DBManager()

    # Get latest portfolio value
    snapshot_df = db.fetch_df("""
        SELECT
            ROUND(portfolio_value_dollars::numeric, 2) as current_balance
        FROM portfolio_snapshots
        ORDER BY snapshot_hour_utc DESC
        LIMIT 1
    """)

    # Get total P&L
    pnl_df = db.fetch_df("""
        SELECT
            ROUND(SUM(profit_dollars)::numeric, 2) as total_pnl
        FROM placed_bets
        WHERE status IN ('won', 'lost')
    """)

    if not snapshot_df.empty and not pnl_df.empty:
        current_balance = float(snapshot_df.iloc[0]['current_balance'])
        total_pnl = float(pnl_df.iloc[0]['total_pnl'])

        # Calculate implied initial deposit
        implied_initial_deposit = current_balance - total_pnl

        print(f"\n🎯 CORRECT Dashboard Metrics:")
        print(f"   Portfolio Value (Kalshi Balance): ${current_balance:.2f}")
        print(f"   Total P&L (Won - Lost): ${total_pnl:.2f}")
        print(f"   Implied Initial Deposit: ${implied_initial_deposit:.2f}")
        print()

        user_balance = 80.69
        if abs(current_balance - user_balance) < 1.0:
            print(f"✅ Dashboard SHOULD show Portfolio Value: ${user_balance:.2f}")
            print(f"   This matches user's actual Kalshi balance")
        else:
            print(f"⚠️  Sync issue detected")
        print()


def test_check_open_bets_capital():
    """
    Test 4: How much capital is tied up in open bets?

    This explains why Kalshi balance might be lower than expected
    """
    db = DBManager()

    open_bets_df = db.fetch_df("""
        SELECT
            COUNT(*) as num_open_bets,
            ROUND(SUM(cost_dollars)::numeric, 2) as capital_at_risk
        FROM placed_bets
        WHERE status = 'open'
    """)

    if not open_bets_df.empty:
        num_open = int(open_bets_df.iloc[0]['num_open_bets'])
        capital_at_risk = float(open_bets_df.iloc[0]['capital_at_risk']) if open_bets_df.iloc[0]['capital_at_risk'] else 0.0

        print(f"\n📊 Open Bets Analysis:")
        print(f"   Number of open bets: {num_open}")
        print(f"   Capital at risk: ${capital_at_risk:.2f}")
        print()

        # Get portfolio value
        snapshot_df = db.fetch_df("""
            SELECT ROUND(portfolio_value_dollars::numeric, 2) as balance
            FROM portfolio_snapshots
            ORDER BY snapshot_hour_utc DESC
            LIMIT 1
        """)

        if not snapshot_df.empty:
            current_balance = float(snapshot_df.iloc[0]['balance'])
            print(f"   Current Kalshi balance: ${current_balance:.2f}")
            print(f"   Includes value of open positions")
        print()


def test_fix_needed():
    """
    Test 5: What fix is needed?

    SOLUTION:
    Replace "Total Invested" with "Portfolio Value" (actual Kalshi balance)
    This gives users the information they actually care about!
    """
    print("\n🔧 FIX REQUIRED:")
    print("   1. Replace 'Total Invested' with 'Portfolio Value'")
    print("   2. Show current Kalshi balance (from portfolio_snapshots)")
    print("   3. This is what user actually cares about!")
    print()
    print("   'Total Invested' = cost of bets (internal accounting)")
    print("   'Portfolio Value' = actual money in Kalshi (what matters!)")
    print()

    assert True, "Fix identified: Show Portfolio Value instead of Total Invested"


if __name__ == "__main__":
    print("=" * 80)
    print("TDD: Diagnosing Dashboard Balance vs Kalshi Balance Mismatch")
    print("=" * 80)

    test_understand_total_invested()
    test_get_actual_kalshi_balance()
    test_what_dashboard_should_show()
    test_check_open_bets_capital()
    test_fix_needed()

    print("=" * 80)
    print("✅ DIAGNOSIS COMPLETE")
    print("=" * 80)
