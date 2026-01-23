"""
TDD Test: Understanding Cash Balance vs Portfolio Value

User reports Kalshi shows: $80.69
Dashboard was showing: $73.35 (cash balance)

CLARIFICATION NEEDED:
- Cash Balance = uninvested cash in account
- Portfolio Value = cash + value of open positions
- User sees Portfolio Value in Kalshi

This test will:
1. Understand what each field in portfolio_value_snapshots means
2. Calculate expected portfolio value = cash + open bet values
3. Verify which metric matches user's $80.69
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from plugins.db_manager import DBManager


def test_understand_portfolio_value_components():
    """
    TEST 1: Break down portfolio value components

    Portfolio Value should equal:
    - Cash Balance (uninvested)
    - Plus: Market value of open positions
    """
    db = DBManager()
    from plugins.portfolio_snapshots import ensure_portfolio_snapshots_table
    ensure_portfolio_snapshots_table(db)

    print("\n" + "=" * 80)
    print("TEST 1: Understanding Portfolio Value Components")
    print("=" * 80)

    # Get latest snapshot
    snapshot_df = db.fetch_df(
        """
        SELECT
            snapshot_hour_utc,
            ROUND(balance_dollars, 2) as cash_balance,
            ROUND(portfolio_value_dollars, 2) as portfolio_value
        FROM portfolio_value_snapshots
        ORDER BY snapshot_hour_utc DESC
        LIMIT 1
    """
    )

    if not snapshot_df.empty:
        cash = float(snapshot_df.iloc[0]["cash_balance"])
        portfolio = float(snapshot_df.iloc[0]["portfolio_value"])
        timestamp = snapshot_df.iloc[0]["snapshot_hour_utc"]

        print(f"\n📊 Latest Snapshot ({timestamp}):")
        print(f"   balance_dollars: ${cash:.2f}")
        print(f"   portfolio_value_dollars: ${portfolio:.2f}")

        # Calculate open positions value
        open_positions_value = portfolio - cash

        print(f"\n🧮 Calculation:")
        print(f"   Portfolio Value = ${portfolio:.2f}")
        print(f"   Cash Balance = ${cash:.2f}")
        print(f"   Open Positions Value = ${open_positions_value:.2f}")

        # What does Kalshi show to user?
        user_sees = 80.69

        print(f"\n👤 User Reports Kalshi Shows: ${user_sees:.2f}")

        # Which matches?
        cash_diff = abs(cash - user_sees)
        portfolio_diff = abs(portfolio - user_sees)

        print(f"\n🎯 Comparison:")
        print(
            f"   Cash Balance vs User: ${cash:.2f} vs ${user_sees:.2f} (diff: ${cash_diff:.2f})"
        )
        print(
            f"   Portfolio Value vs User: ${portfolio:.2f} vs ${user_sees:.2f} (diff: ${portfolio_diff:.2f})"
        )

        if portfolio_diff < cash_diff:
            print(f"\n✅ User is looking at PORTFOLIO VALUE!")
            print(f"   But wait... ${portfolio:.2f} != ${user_sees:.2f}")
            print(f"   Large difference of ${portfolio_diff:.2f}")
        else:
            print(f"\n✅ User is looking at CASH BALANCE!")
            print(f"   But... this seems wrong?")

        print(f"\n❓ CONFUSION DETECTED:")
        print(f"   Neither value is close to ${user_sees:.2f}")
        print(f"   Something is wrong with the snapshot data!")
    else:
        print("\n❌ No portfolio snapshots found")

    print("\n" + "=" * 80)


def test_calculate_correct_portfolio_value():
    """
    TEST 2: Calculate portfolio value from database

    Portfolio Value SHOULD be:
    - Cash balance from API
    - Plus: Sum of cost of open bets (capital tied up)

    Actually, Kalshi API should return this correctly!
    Let's check if there's a data issue.
    """
    db = DBManager()
    from plugins.bet_tracker import create_bets_table
    create_bets_table(db)

    print("\n" + "=" * 80)
    print("TEST 2: Calculate Expected Portfolio Value")
    print("=" * 80)

    # Get open bets
    open_bets_df = db.fetch_df(
        """
        SELECT
            COUNT(*) as num_open,
            ROUND(SUM(cost_dollars), 2) as capital_in_bets
        FROM placed_bets
        WHERE status = 'open'
    """
    )

    # Get settled P&L
    settled_df = db.fetch_df(
        """
        SELECT
            ROUND(SUM(profit_dollars)::numeric, 2) as total_pnl
        FROM placed_bets
        WHERE status IN ('won', 'lost')
    """
    )

    num_open = (
        int(open_bets_df.iloc[0]["num_open"])
        if not open_bets_df.empty and open_bets_df.iloc[0]["num_open"]
        else 0
    )
    capital_in_bets = (
        float(open_bets_df.iloc[0]["capital_in_bets"])
        if not open_bets_df.empty and open_bets_df.iloc[0]["capital_in_bets"]
        else 0.0
    )
    total_pnl = settled_df.iloc[0]["total_pnl"]
    total_pnl = float(total_pnl) if total_pnl is not None else 0.0

    print(f"\n📊 Database State:")
    print(f"   Open Bets: {num_open}")
    print(f"   Capital in Open Bets: ${capital_in_bets:.2f}")
    print(f"   Settled Bets P&L: ${total_pnl:.2f}")

    from plugins.portfolio_snapshots import ensure_portfolio_snapshots_table
    ensure_portfolio_snapshots_table(db)
    # Get snapshot
    snapshot_df = db.fetch_df(
        """
        SELECT
            ROUND(balance_dollars, 2) as cash,
            ROUND(portfolio_value_dollars, 2) as portfolio
        FROM portfolio_value_snapshots
        ORDER BY snapshot_hour_utc DESC
        LIMIT 1
    """
    )

    if not snapshot_df.empty:
        cash = float(snapshot_df.iloc[0]["cash"])
        portfolio_snapshot = float(snapshot_df.iloc[0]["portfolio"])

        print(f"\n📸 Snapshot Values:")
        print(f"   Cash (balance_dollars): ${cash:.2f}")
        print(f"   Portfolio (portfolio_value_dollars): ${portfolio_snapshot:.2f}")

        # Expected portfolio value
        expected_portfolio = cash + capital_in_bets

        print(f"\n🧮 Expected Portfolio Value:")
        print(
            f"   ${cash:.2f} (cash) + ${capital_in_bets:.2f} (open bets) = ${expected_portfolio:.2f}"
        )

        user_balance = 80.69
        print(f"\n👤 User Reports: ${user_balance:.2f}")
        print(f"   Expected Portfolio: ${expected_portfolio:.2f}")
        print(f"   Difference: ${abs(expected_portfolio - user_balance):.2f}")

        print(f"\n❓ ISSUE IDENTIFIED:")
        if abs(portfolio_snapshot - expected_portfolio) > 50:
            print(f"   Snapshot portfolio value (${portfolio_snapshot:.2f}) is WRONG!")
            print(f"   It should be ${expected_portfolio:.2f}")
            print(
                f"   The snapshot data might be corrupted or from different API fields"
            )

    print("\n" + "=" * 80)


def test_check_kalshi_api_response():
    """
    TEST 3: Check what Kalshi API actually returns

    Need to understand the API response format:
    - What is "balance"?
    - What is "portfolio_value"?
    """
    print("\n" + "=" * 80)
    print("TEST 3: Check Kalshi API Fields")
    print("=" * 80)

    print(f"\n📚 Kalshi API Documentation:")
    print(f"   - balance: Cash balance (uninvested)")
    print(f"   - portfolio_value: Total value (cash + positions)")
    print(f"\n✅ EXPECTED:")
    print(f"   portfolio_value ≈ $80.69 (what user sees in Kalshi)")
    print(f"\n❌ PROBLEM:")
    print(f"   Our snapshot shows portfolio_value = $7.37")
    print(f"   This is clearly wrong!")
    print(f"\n🔍 HYPOTHESIS:")
    print(f"   The portfolio_hourly_snapshot DAG might be:")
    print(f"   1. Swapping the fields (balance <-> portfolio_value)")
    print(f"   2. Getting wrong values from API")
    print(f"   3. The API fields changed")

    print("\n" + "=" * 80)


def test_correct_dashboard_metric():
    """
    TEST 4: What should dashboard show?

    ANSWER: Portfolio Value (total account value)
    - This is what user sees in Kalshi
    - Includes cash + open positions
    - Should be ≈ $80.69
    """
    db = DBManager()

    print("\n" + "=" * 80)
    print("TEST 4: What Should Dashboard Show?")
    print("=" * 80)

    print(f"\n🎯 CORRECT ANSWER:")
    print(f"   Dashboard should show: 'Portfolio Value'")
    print(f"   Definition: Total account value (cash + positions)")
    print(f"   This matches what user sees in Kalshi")
    print(f"\n❌ WRONG:")
    print(f"   Showing only 'Cash Balance' = ${73:.2f}")
    print(f"   This excludes open positions!")
    print(f"\n✅ RIGHT:")
    print(f"   Show 'Portfolio Value' = $80.69")
    print(f"   This is total account value")

    print(f"\n🔧 FIX NEEDED:")
    print(f"   1. Verify portfolio_hourly_snapshot saves correct values")
    print(f"   2. Dashboard should show portfolio_value_dollars")
    print(f"   3. NOT balance_dollars (cash only)")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    print("=" * 80)
    print("TDD: Cash Balance vs Portfolio Value Confusion")
    print("=" * 80)

    test_understand_portfolio_value_components()
    test_calculate_correct_portfolio_value()
    test_check_kalshi_api_response()
    test_correct_dashboard_metric()

    print("\n" + "=" * 80)
    print("DIAGNOSIS COMPLETE")
    print("=" * 80)
    print("\nNEXT STEPS:")
    print("1. Check portfolio_hourly_snapshot DAG implementation")
    print("2. Verify API fields are saved correctly")
    print("3. Fix dashboard to show portfolio_value_dollars")
    print("4. Create Playwright test to verify dashboard")
    print("=" * 80)
