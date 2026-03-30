#!/usr/bin/env python3
"""
Simple database check for placed bets.
"""

import sys

sys.path.insert(0, "/opt/airflow")

from plugins.db_manager import DBManager


def main():
    print("Checking placed_bets table for March 10-11...")

    db = DBManager()

    # Simple query to count bets
    count_query = "SELECT COUNT(*) as count FROM placed_bets WHERE placed_time_utc >= '2026-03-10'"

    try:
        count_result = db.fetch_df(count_query)
        count = count_result.iloc[0]["count"]
        print(f"Total bets placed March 10+: {count}")

        if count > 0:
            # Get actual bets
            query = """
            SELECT
                bet_id,
                ticker,
                home_team,
                away_team,
                bet_on,
                side,
                cost_dollars,
                price_cents,
                status,
                profit_dollars,
                placed_time_utc,
                market_title
            FROM placed_bets
            WHERE placed_time_utc >= '2026-03-10'
            ORDER BY placed_time_utc DESC
            LIMIT 20
            """

            df = db.fetch_df(query)
            print("\nRecent bets:")
            for idx, row in df.iterrows():
                print(f"\n{idx + 1}. {row['placed_time_utc']}")
                print(f"   Market: {row.get('market_title', row['ticker'])}")
                print(f"   Bet on: {row['bet_on']} ({row['side']})")
                print(f"   Cost: ${row['cost_dollars']:.2f} @ {row['price_cents']}¢")
                print(
                    f"   Status: {row['status']}, Profit: ${row.get('profit_dollars', 0):.2f}"
                )

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()

        # Try to see what's in the table
        try:
            query = "SELECT * FROM placed_bets ORDER BY placed_time_utc DESC LIMIT 5"
            df = db.fetch_df(query)
            print(f"\nTable shape: {df.shape}")
            print(f"Columns: {list(df.columns)}")
            print("\nFirst row sample:")
            if not df.empty:
                print(df.iloc[0].to_dict())
        except Exception as e2:
            print(f"Could not sample table: {e2}")


if __name__ == "__main__":
    main()
