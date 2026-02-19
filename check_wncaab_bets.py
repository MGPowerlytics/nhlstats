#!/usr/bin/env python3
"""
Check WNCAAB bets in the database.
"""

import sys
import os
import pandas as pd

# Add plugins directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'plugins'))
from db_manager import DBManager

def main():
    """Check WNCAAB bets."""
    try:
        # Create connection string for localhost
        connection_string = "postgresql+psycopg2://airflow:airflow@localhost:5432/airflow"
        db = DBManager(connection_string=connection_string)

        print("Checking WNCAAB bets in database...")

        # Check if WNCAAB exists as a sport
        query = """
        SELECT
            sport,
            COUNT(*) as bet_count,
            MIN(placed_date) as first_date,
            MAX(placed_date) as last_date
        FROM placed_bets
        WHERE sport = 'WNCAAB'
        GROUP BY sport
        """

        wncaab_bets = db.fetch_df(query)

        if len(wncaab_bets) > 0:
            print(f"\nWNCAAB bets found: {wncaab_bets.iloc[0]['bet_count']}")
            print(f"Date range: {wncaab_bets.iloc[0]['first_date']} to {wncaab_bets.iloc[0]['last_date']}")
        else:
            print("\nNo WNCAAB bets found with sport='WNCAAB'")

        # Check all sports in database
        query2 = """
        SELECT
            sport,
            COUNT(*) as bet_count
        FROM placed_bets
        GROUP BY sport
        ORDER BY sport
        """

        all_sports = db.fetch_df(query2)
        print(f"\nAll sports in database:")
        for _, row in all_sports.iterrows():
            print(f"  {row['sport']}: {row['bet_count']} bets")

        # Check if we should update UNKNOWN bets to correct sports
        print(f"\nChecking if UNKNOWN bets should be reclassified...")

        # Get a sample of UNKNOWN bets with WNCAAB tickers
        query3 = """
        SELECT
            bet_id,
            ticker,
            market_title,
            confidence,
            status,
            profit_dollars
        FROM placed_bets
        WHERE sport = 'UNKNOWN'
          AND ticker LIKE 'KXNCAAWBGAME%'
        LIMIT 5
        """

        sample = db.fetch_df(query3)
        print(f"\nSample UNKNOWN bets with WNCAAB tickers:")
        for _, row in sample.iterrows():
            print(f"  Ticker: {row['ticker']}")
            print(f"  Market: {row['market_title']}")
            print(f"  Confidence: {row['confidence']}, Status: {row['status']}, Profit: ${row['profit_dollars']:.2f}")
            print()

        # Check if there are any bets with sport='WNCAAB' to compare
        query4 = """
        SELECT
            COUNT(*) as count,
            AVG(profit_dollars) as avg_profit
        FROM placed_bets
        WHERE sport = 'WNCAAB'
          AND status IN ('won', 'lost')
        """

        wncaab_stats = db.fetch_df(query4)
        if len(wncaab_stats) > 0 and wncaab_stats.iloc[0]['count'] > 0:
            print(f"\nExisting WNCAAB settled bets: {wncaab_stats.iloc[0]['count']}")
            print(f"Average profit: ${wncaab_stats.iloc[0]['avg_profit']:.2f}")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
