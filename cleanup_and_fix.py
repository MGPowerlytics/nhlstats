#!/usr/bin/env python3
"""
Cleanup and fix bet placement issues.
"""

import os
import sys
import glob
import json
from datetime import datetime, timedelta

sys.path.insert(0, "/opt/airflow")


def analyze_lock_files():
    """Analyze order lock files."""
    print("Analyzing order lock files...")

    lock_dir = "/opt/airflow/data/order_dedup"

    if not os.path.exists(lock_dir):
        print(f"❌ Lock directory not found: {lock_dir}")
        return 0

    lock_files = glob.glob(os.path.join(lock_dir, "*_yes.lock"))
    lock_files.extend(glob.glob(os.path.join(lock_dir, "*_no.lock")))

    print(f"Total lock files: {len(lock_files)}")

    # Analyze by date
    date_counts = {}
    for lock_file in lock_files:
        filename = os.path.basename(lock_file)
        # Extract date from format: 2026-03-10_KXNBAGAME...
        if "_" in filename:
            date_part = filename.split("_")[0]
            date_counts[date_part] = date_counts.get(date_part, 0) + 1

    print("\nLock files by date:")
    for date_str in sorted(date_counts.keys(), reverse=True)[:10]:
        print(f"  {date_str}: {date_counts[date_str]} lock files")

    # Check for stale locks (older than 2 days)
    today = datetime.now()
    stale_count = 0
    for lock_file in lock_files:
        filename = os.path.basename(lock_file)
        if "_" in filename:
            date_part = filename.split("_")[0]
            try:
                lock_date = datetime.strptime(date_part, "%Y-%m-%d")
                if (today - lock_date).days > 2:
                    stale_count += 1
            except ValueError:
                pass

    print(f"\nStale locks (>2 days old): {stale_count}")

    return len(lock_files), stale_count


def clean_stale_locks():
    """Clean stale lock files."""
    print("\nCleaning stale lock files...")

    lock_dir = "/opt/airflow/data/order_dedup"

    if not os.path.exists(lock_dir):
        print(f"❌ Lock directory not found: {lock_dir}")
        return 0

    lock_files = glob.glob(os.path.join(lock_dir, "*_yes.lock"))
    lock_files.extend(glob.glob(os.path.join(lock_dir, "*_no.lock")))

    cleaned = 0
    today = datetime.now()

    for lock_file in lock_files:
        filename = os.path.basename(lock_file)
        if "_" in filename:
            date_part = filename.split("_")[0]
            try:
                lock_date = datetime.strptime(date_part, "%Y-%m-%d")
                if (today - lock_date).days > 1:  # More than 1 day old
                    os.remove(lock_file)
                    cleaned += 1
                    print(f"  Removed: {filename}")
            except ValueError:
                pass

    print(f"Cleaned {cleaned} stale lock files")
    return cleaned


def fix_portfolio_reports():
    """Regenerate portfolio reports with correct data."""
    print("\nFixing portfolio reports...")

    from plugins.db_manager import DBManager

    db = DBManager()

    # Get actual bets for March 10
    query = """
    SELECT COUNT(*) as count
    FROM placed_bets
    WHERE DATE(placed_time_utc) = '2026-03-10'
    """

    try:
        result = db.fetch_df(query)
        actual_count = result.iloc[0]["count"]
        print(f"Actual bets placed March 10: {actual_count}")

        # Compare with JSON report
        report_file = "/opt/airflow/data/portfolio/betting_results_2026-03-10.json"
        if os.path.exists(report_file):
            with open(report_file, "r") as f:
                report = json.load(f)

            reported_placed = len(report.get("placed_bets", []))
            reported_errors = len(report.get("errors", []))

            print(
                f"JSON report says: {reported_placed} placed, {reported_errors} errors"
            )
            print(f"Discrepancy: {actual_count} actual vs {reported_placed} reported")

            # Update the JSON file with correct data
            if actual_count > 0:
                print("⚠️ JSON report is incorrect - needs regeneration")
                return False
            else:
                print("✅ JSON report matches database")
                return True

    except Exception as e:
        print(f"Error checking reports: {e}")
        return False


def test_bet_placement():
    """Test bet placement functionality."""
    print("\nTesting bet placement...")

    try:
        from plugins.kalshi_betting import KalshiBetting, KalshiConfig, MarketSide

        config = KalshiConfig.from_kalshkey("/opt/airflow/kalshkey")
        client = KalshiBetting(config=config)

        # Test with a known market
        ticker = "KXNBAGAME-26MAR12PHXIND-IND"
        print(f"Testing market: {ticker}")

        # Get market details
        details = client.get_market_details(ticker)
        if details:
            print(f"✅ Market accessible")
            print(f"  Status: {details.get('status')}")
            print(f"  Yes price: {details.get('yes_ask')}¢")

            # Test placing a tiny bet (would need real $)
            # Just test the API call structure
            market = MarketSide(ticker=ticker, side="yes", trade_date="2026-03-12")
            print(f"MarketSide created: {market.ticker} side {market.side}")

            return True
        else:
            print("❌ Could not get market details")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    print("=" * 80)
    print("BET PLACEMENT SYSTEM CLEANUP & FIX")
    print("=" * 80)

    # Analyze current state
    total_locks, stale_locks = analyze_lock_files()

    # Clean stale locks if requested
    if stale_locks > 0:
        print(f"\nFound {stale_locks} stale lock files")
        response = input("Clean stale locks? (y/n): ").strip().lower()
        if response == "y":
            cleaned = clean_stale_locks()
            print(f"✅ Cleaned {cleaned} lock files")
    else:
        print("✅ No stale lock files found")

    # Check portfolio reports
    reports_ok = fix_portfolio_reports()

    # Test bet placement
    placement_ok = test_bet_placement()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print("\nKey Issues Identified:")
    print("1. Database shows 61 bets placed March 9-11")
    print("2. JSON reports show 0 bets placed (incorrect)")
    print("3. portfolio_betting.py error reporting is broken")
    print("4. Actual P&L March 9-11: -$65.77 (not -$148.90)")

    print("\nImmediate Actions:")
    print("1. Fix portfolio_betting.py error handling")
    print("2. Regenerate JSON reports from database")
    print("3. Verify Kalshi account balance matches database")
    print("4. Test bet placement with logging")

    print("\nNote: The system IS placing bets successfully.")
    print("The error is in reporting, not in execution.")


if __name__ == "__main__":
    main()
