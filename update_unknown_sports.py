#!/usr/bin/env python3
"""
Update UNKNOWN sport bets with correct sport classifications.
"""

import sys
import os
import pandas as pd

# Add plugins directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'plugins'))
from db_manager import DBManager

def update_unknown_sports():
    """Update UNKNOWN bets with correct sport classifications."""
    try:
        # Create connection string for localhost
        connection_string = "postgresql+psycopg2://airflow:airflow@localhost:5432/airflow"
        db = DBManager(connection_string=connection_string)

        print("Updating UNKNOWN sport bets with correct classifications...")

        # Count UNKNOWN bets before update
        query_count = "SELECT COUNT(*) as count FROM placed_bets WHERE sport = 'UNKNOWN'"
        before_count = db.fetch_df(query_count).iloc[0]['count']
        print(f"UNKNOWN bets before update: {before_count}")

        # Update WNCAAB bets (KXNCAAWBGAME tickers)
        update_wncaab = """
        UPDATE placed_bets
        SET sport = 'WNCAAB'
        WHERE sport = 'UNKNOWN'
          AND ticker LIKE 'KXNCAAWBGAME%'
        """

        result_wncaab = db.execute(update_wncaab)
        print(f"Updated {result_wncaab.rowcount} bets to WNCAAB")

        # Update TENNIS bets (Challenger matches)
        update_tennis = """
        UPDATE placed_bets
        SET sport = 'TENNIS'
        WHERE sport = 'UNKNOWN'
          AND (ticker LIKE 'KXWTACHALLENGERMATCH%' OR ticker LIKE 'KXATPCHALLENGERMATCH%')
        """

        result_tennis = db.execute(update_tennis)
        print(f"Updated {result_tennis.rowcount} bets to TENNIS")

        # Count UNKNOWN bets after update
        after_count = db.fetch_df(query_count).iloc[0]['count']
        print(f"UNKNOWN bets after update: {after_count}")

        # Show what remains as UNKNOWN
        if after_count > 0:
            query_remaining = """
            SELECT
                ticker,
                market_title,
                COUNT(*) as count
            FROM placed_bets
            WHERE sport = 'UNKNOWN'
            GROUP BY ticker, market_title
            ORDER BY count DESC
            """

            remaining = db.fetch_df(query_remaining)
            print(f"\nRemaining UNKNOWN bets ({after_count} total):")
            for _, row in remaining.iterrows():
                print(f"  Ticker: {row['ticker']}")
                print(f"  Market: {row['market_title']}")
                print(f"  Count: {row['count']}")
                print()

        # Verify the updates
        print("\nVerifying updates...")

        # Check WNCAAB count
        query_wncaab_count = "SELECT COUNT(*) as count FROM placed_bets WHERE sport = 'WNCAAB'"
        wncaab_count = db.fetch_df(query_wncaab_count).iloc[0]['count']
        print(f"Total WNCAAB bets: {wncaab_count}")

        # Check TENNIS count
        query_tennis_count = "SELECT COUNT(*) as count FROM placed_bets WHERE sport = 'TENNIS'"
        tennis_count = db.fetch_df(query_tennis_count).iloc[0]['count']
        print(f"Total TENNIS bets: {tennis_count}")

        # Show updated sport distribution
        query_sports = """
        SELECT
            sport,
            COUNT(*) as bet_count
        FROM placed_bets
        GROUP BY sport
        ORDER BY sport
        """

        sports_dist = db.fetch_df(query_sports)
        print(f"\nUpdated sport distribution:")
        for _, row in sports_dist.iterrows():
            print(f"  {row['sport']}: {row['bet_count']} bets")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

def main():
    """Main function."""
    print("This script will update UNKNOWN sport bets in the database.")
    print("The following updates will be made:")
    print("1. KXNCAAWBGAME* tickers -> WNCAAB")
    print("2. KXWTACHALLENGERMATCH* and KXATPCHALLENGERMATCH* tickers -> TENNIS")
    print()

    response = input("Do you want to proceed? (yes/no): ")
    if response.lower() == 'yes':
        return update_unknown_sports()
    else:
        print("Update cancelled.")
        return 0

if __name__ == "__main__":
    sys.exit(main())
