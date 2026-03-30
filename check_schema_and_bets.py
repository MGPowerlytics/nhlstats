#!/usr/bin/env python3
"""
Check database schema and actual bets placed.
"""

import os
import sys
import json
import pandas as pd

sys.path.insert(0, "/opt/airflow")
from plugins.db_manager import DBManager


def check_table_schema():
    """Check placed_bets table schema."""
    print("Checking placed_bets table schema...")

    db = DBManager()

    if not db.table_exists("placed_bets"):
        print("❌ placed_bets table does not exist!")
        return

    # Get table columns
    query = """
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'placed_bets'
    ORDER BY ordinal_position
    """

    try:
        df = db.fetch_df(query)
        print(f"✅ placed_bets table exists with {len(df)} columns:")
        for _, row in df.iterrows():
            print(
                f"  {row['column_name']} ({row['data_type']}, nullable: {row['is_nullable']})"
            )
        return df
    except Exception as e:
        print(f"❌ Error checking schema: {e}")
        return None


def check_recent_bets():
    """Check recent bets using correct schema."""
    print("\nChecking recent bets...")

    db = DBManager()

    # First get correct column names
    query_columns = """
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'placed_bets'
    ORDER BY ordinal_position
    """

    try:
        columns_df = db.fetch_df(query_columns)
        columns = [row["column_name"] for row in columns_df.itertuples()]

        print(f"Available columns: {', '.join(columns)}")

        # Build query with available columns
        select_cols = []
        for col in columns:
            select_cols.append(col)

        query = f"""
        SELECT {", ".join(select_cols)}
        FROM placed_bets
        WHERE placed_time_utc >= '2026-03-10'
        ORDER BY placed_time_utc DESC
        LIMIT 20
        """

        df = db.fetch_df(query)

        if df.empty:
            print("⚠️ No bets found for March 10+ in database")
            return df
        else:
            print(f"✅ Found {len(df)} bets placed March 10+")
            print("\nRecent bets:")

            # Try to display relevant info
            for _, row in df.iterrows():
                placed_time = row.get("placed_time_utc", "Unknown")
                ticker = row.get("ticker", row.get("market_id", "Unknown"))
                stake = row.get("stake", row.get("amount", 0))
                status = row.get("status", "Unknown")

                print(f"  {placed_time}: {ticker}")
                print(f"    Stake: ${stake:.2f}, Status: {status}")

                if "result" in df.columns:
                    result = row.get("result")
                    if result is not None:
                        print(f"    Result: ${result:.2f}")
                print()

            return df

    except Exception as e:
        print(f"❌ Error querying bets: {e}")
        import traceback

        traceback.print_exc()
        return None


def check_portfolio_snapshots():
    """Check portfolio snapshot history."""
    print("\nChecking portfolio snapshots...")

    db = DBManager()

    if not db.table_exists("portfolio_snapshots"):
        print("❌ portfolio_snapshots table does not exist!")
        return

    query = """
    SELECT snapshot_time, total_value, cash_balance, invested_amount, realized_pnl
    FROM portfolio_snapshots
    ORDER BY snapshot_time DESC
    LIMIT 10
    """

    try:
        df = db.fetch_df(query)

        if df.empty:
            print("⚠️ No portfolio snapshots found")
        else:
            print(f"✅ Found {len(df)} portfolio snapshots")
            print("\nRecent snapshots:")
            for _, row in df.iterrows():
                time_str = row["snapshot_time"].strftime("%Y-%m-%d %H:%M")
                print(
                    f"  {time_str}: Total: ${row['total_value']:.2f}, "
                    f"Cash: ${row['cash_balance']:.2f}, "
                    f"Realized P&L: ${row['realized_pnl']:.2f}"
                )

    except Exception as e:
        print(f"❌ Error checking portfolio: {e}")


def check_kalshi_balance():
    """Check if we can get Kalshi balance via API."""
    print("\nAttempting to check Kalshi API...")

    try:
        from plugins.kalshi_betting import KalshiBetting, KalshiConfig

        config = KalshiConfig.from_kalshkey("/opt/airflow/kalshkey")
        client = KalshiBetting(config=config)

        portfolio = client.get_portfolio()
        if portfolio:
            balance = portfolio.get("balance", {})
            cash = balance.get("cash_balance", "Unknown")
            total = portfolio.get("total_value", "Unknown")

            print(f"✅ Kalshi API accessible")
            print(f"   Cash balance: ${cash}")
            print(f"   Total value: ${total}")

            # Check open positions
            positions = client.get_open_positions()
            print(f"   Open positions: {len(positions)}")

            # Check open orders
            orders = client.get_open_orders()
            print(f"   Open orders: {len(orders)}")

            return True
        else:
            print("❌ Could not get portfolio from Kalshi API")
            return False

    except Exception as e:
        print(f"❌ Kalshi API error: {e}")
        return False


def main():
    print("=" * 80)
    print("DOCKER CONTAINER - REAL BET PLACEMENT ANALYSIS")
    print("=" * 80)

    # Check schema first
    schema_df = check_table_schema()

    # Check actual bets
    bets_df = check_recent_bets()

    # Check portfolio
    check_portfolio_snapshots()

    # Try Kalshi API
    # check_kalshi_balance()  # Commented out as it might fail

    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)

    print("\nBased on the JSON files in data/portfolio/:")
    print("  March 9-11: 0 bets placed, multiple 'Failed to place bet' errors")
    print("  Yet lock files exist for March 10-11 (bets were attempted)")

    print("\nKey questions:")
    print("1. Are bets actually in database but not in JSON files?")
    print("2. Did manual bets get placed outside the system?")
    print("3. Is the portfolio data stale/corrupted?")
    print("4. Why do lock files exist if bets failed?")


if __name__ == "__main__":
    main()
