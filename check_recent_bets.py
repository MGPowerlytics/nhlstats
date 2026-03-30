import psycopg2
import os
import pandas as pd
from datetime import datetime, timedelta

def check_recent_bets():
    try:
        # Connect to Postgres
        conn = psycopg2.connect(
            dbname="airflow",
            user="airflow",
            password="airflow",
            host="postgres",
            port="5432"
        )

        # Query for recent bets
        query = """
        SELECT sport, COUNT(*) as bet_count, MIN(created_at) as first_bet, MAX(created_at) as last_bet
        FROM bet_recommendations
        WHERE created_at > NOW() - INTERVAL '1 hour'
        GROUP BY sport
        """

        df = pd.read_sql(query, conn)
        print("\n=== Recent Bets Summary (Last 1 Hour) ===")
        if df.empty:
            print("No bets found in the last hour.")
        else:
            print(df.to_string(index=False))

        # Check specific sports
        print("\n=== Checking specific sports ===")
        sports = ['tennis', 'cba', 'unrivaled']
        for sport in sports:
            q = f"SELECT * FROM bet_recommendations WHERE sport = '{sport}' AND created_at > NOW() - INTERVAL '1 hour' LIMIT 5"
            sport_df = pd.read_sql(q, conn)
            print(f"\n{sport.upper()} Bets:")
            if sport_df.empty:
                print("  None")
            else:
                print(sport_df[['game_id', 'team', 'recommended_bet', 'confidence', 'bookmaker']].to_string())

        conn.close()

    except Exception as e:
        print(f"Error querying database: {e}")

if __name__ == "__main__":
    check_recent_bets()
