#!/usr/bin/env python3
"""Check database for odds data."""

import sys
sys.path.insert(0, '.')

try:
    from plugins.db_manager import default_db

    # Check what tables exist
    query = """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name
    """

    tables = default_db.fetch_df(query)
    print("Database Tables:")
    print("=" * 60)
    for _, row in tables.iterrows():
        print(f"  {row['table_name']}")

    # Check for odds-related tables
    print("\nChecking for odds tables...")
    odds_tables = [t for t in tables['table_name'] if 'odds' in t.lower() or 'price' in t.lower()]
    if odds_tables:
        print(f"Found odds tables: {odds_tables}")

        # Check game_odds table
        if 'game_odds' in [t.lower() for t in odds_tables]:
            print("\nChecking game_odds table...")
            count_query = "SELECT COUNT(*) as count FROM game_odds"
            count_result = default_db.fetch_df(count_query)
            print(f"  Total rows: {count_result.iloc[0]['count'] if not count_result.empty else 0}")

            # Check recent odds
            recent_query = """
            SELECT game_id, bookmaker, market_name, price, last_update
            FROM game_odds
            ORDER BY last_update DESC
            LIMIT 5
            """
            recent = default_db.fetch_df(recent_query)
            if not recent.empty:
                print(f"  Recent odds (last 5):")
                for _, row in recent.iterrows():
                    print(f"    {row['game_id']}: {row['bookmaker']} - {row['market_name']} = {row['price']}")
            else:
                print("  No recent odds found")
    else:
        print("No odds tables found!")

except Exception as e:
    print(f"Error checking database: {e}")
    print("Make sure PostgreSQL is running and accessible")
