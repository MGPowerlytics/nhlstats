import sys
import os
sys.path.append(os.getcwd())
try:
    from plugins.db_manager import default_db
    res = default_db.fetch_one("SELECT COUNT(*) FROM game_odds")
    print(f"Game odds count: {res[0]}")
    res = default_db.fetch_one("SELECT COUNT(DISTINCT bookmaker) FROM game_odds")
    print(f"Distinct bookmakers count: {res[0]}")

    # Try fetch_all for bookmakers if fetch_one is just single value
    # But fetch_one returns a tuple? "SELECT DISTINCT bookmaker FROM game_odds LIMIT 5" would return first row.
    # So iterate.
    import pandas as pd
    df = default_db.fetch_df("SELECT DISTINCT bookmaker FROM game_odds LIMIT 10")
    print("Sample bookmakers:")
    print(df)
except Exception as e:
    print(f"Error: {e}")
