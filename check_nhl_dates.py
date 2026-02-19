#!/usr/bin/env python3
"""
Check date ranges for NHL bets.
"""

import sys
import os
import pandas as pd

# Add plugins directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'plugins'))
from db_manager import DBManager

def main():
    """Check NHL bet dates."""
    try:
        # Create connection string for localhost
        connection_string = "postgresql+psycopg2://airflow:airflow@localhost:5432/airflow"
        db = DBManager(connection_string=connection_string)

        print("Checking NHL bet dates...")

        # Check date range of all NHL bets
        query = """
        SELECT
            MIN(placed_date) as first_date,
            MAX(placed_date) as last_date,
            COUNT(*) as bet_count
        FROM placed_bets
        WHERE sport = 'NHL'
        """

        result = db.fetch_df(query)
        print("\nNHL Bets Overall Date Range:")
        print(f"First bet: {result.iloc[0]['first_date']}")
        print(f"Last bet: {result.iloc[0]['last_date']}")
        print(f"Total NHL bets: {result.iloc[0]['bet_count']}")

        # Check NHL bets since Feb 6, 2025
        query2 = """
        SELECT
            COUNT(*) as bet_count,
            MIN(placed_date) as first_date,
            MAX(placed_date) as last_date
        FROM placed_bets
        WHERE sport = 'NHL'
          AND placed_date >= '2025-02-06'
        """

        result2 = db.fetch_df(query2)
        print(f"\nNHL bets since Feb 6, 2025: {result2.iloc[0]['bet_count']}")
        if result2.iloc[0]['first_date']:
            print(f"Date range: {result2.iloc[0]['first_date']} to {result2.iloc[0]['last_date']}")
        else:
            print("No NHL bets since Feb 6, 2025")

        # Check all bets since Feb 6, 2025 by sport
        query3 = """
        SELECT
            sport,
            COUNT(*) as bet_count,
            MIN(placed_date) as first_date,
            MAX(placed_date) as last_date
        FROM placed_bets
        WHERE placed_date >= '2025-02-06'
        GROUP BY sport
        ORDER BY sport
        """

        result3 = db.fetch_df(query3)
        print("\nAll bets since Feb 6, 2025 by sport:")
        for _, row in result3.iterrows():
            print(f"{row['sport']}: {row['bet_count']} bets, {row['first_date']} to {row['last_date']}")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
