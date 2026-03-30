#!/usr/bin/env python3
"""
Check actual bets placed by querying database inside Docker container.
"""

import os
import sys
import pandas as pd

# Add path for imports
sys.path.insert(0, "/opt/airflow")

from plugins.db_manager import DBManager


def check_placed_bets():
    """Check placed_bets table for March 10-11 bets."""
    print("Checking placed_bets table in PostgreSQL...")

    db = DBManager()

    # Check if table exists
    if not db.table_exists("placed_bets"):
        print("❌ placed_bets table does not exist!")
        return

    # Query for bets placed on March 10-11
    query = """
    SELECT
        bet_id,
        game_id,
        market_id,
        bookmaker,
        outcome,
        stake,
        odds,
        potential_payout,
        status,
        result,
        placed_time_utc,
        market_title
    FROM placed_bets
    WHERE DATE(placed_time_utc) >= '2026-03-10'
    ORDER BY placed_time_utc DESC
    LIMIT 20
    """

    try:
        df = db.fetch_df(query)

        if df.empty:
            print("⚠️ No bets found for March 10-11 in database")
        else:
            print(f"✅ Found {len(df)} bets placed March 10-11")
            print("\nRecent bets:")
            for _, row in df.iterrows():
                print(f"  {row['placed_time_utc']}: {row['market_title']}")
                print(
                    f"    Stake: ${row['stake']:.2f}, Status: {row['status']}, Result: ${row.get('result', 0):.2f}"
                )
                print()

    except Exception as e:
        print(f"❌ Error querying database: {e}")
        import traceback

        traceback.print_exc()


def check_betting_results_files():
    """Check betting_results JSON files."""
    print("\nChecking betting_results JSON files...")

    import json
    import glob

    results_dir = "/opt/airflow/data/portfolio"

    if not os.path.exists(results_dir):
        print(f"❌ Directory not found: {results_dir}")
        return

    # Find recent betting_results files
    result_files = glob.glob(
        os.path.join(results_dir, "betting_results_2026-03-*.json")
    )
    result_files.sort(reverse=True)

    for filepath in result_files[:3]:  # Last 3 days
        date_str = (
            os.path.basename(filepath)
            .replace("betting_results_", "")
            .replace(".json", "")
        )

        with open(filepath, "r") as f:
            data = json.load(f)

        placed = len(data.get("placed_bets", []))
        errors = len(data.get("errors", []))
        skipped = len(data.get("skipped_bets", []))

        print(f"{date_str}: {placed} bets placed, {errors} errors, {skipped} skipped")

        if errors > 0:
            print(f"  Errors:")
            for error in data.get("errors", [])[:3]:
                print(f"    {error.get('ticker')}: {error.get('error')}")


def check_order_locks():
    """Check order lock files."""
    print("\nChecking order lock files...")

    import glob

    lock_dir = "/opt/airflow/data/order_dedup"

    if not os.path.exists(lock_dir):
        print(f"❌ Lock directory not found: {lock_dir}")
        return

    # Count lock files by date
    lock_files = glob.glob(os.path.join(lock_dir, "*_yes.lock"))

    print(f"Total lock files: {len(lock_files)}")

    # Count recent locks
    recent_locks = [f for f in lock_files if "2026-03-10" in f or "2026-03-11" in f]
    print(f"March 10-11 lock files: {len(recent_locks)}")

    # Show some recent locks
    for lock_file in recent_locks[:5]:
        print(f"  {os.path.basename(lock_file)}")


def main():
    print("=" * 80)
    print("ACTUAL BET PLACEMENT VERIFICATION - DOCKER CONTAINER")
    print("=" * 80)

    check_placed_bets()
    check_betting_results_files()
    check_order_locks()

    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)

    print("\nCompare with portfolio reports:")
    print("- If database shows bets placed but JSON files show 0: Data inconsistency")
    print("- If both show 0 but locks exist: Bets attempted but failed")
    print("- If bankroll changed without bets: Manual intervention or stale data")


if __name__ == "__main__":
    main()
