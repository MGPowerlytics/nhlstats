import sys
import os
sys.path.append(os.getcwd())
from plugins.db_manager import DBManager

def check_db():
    db = DBManager()
    try:
        games_count = db.fetch_df("SELECT COUNT(*) FROM unified_games").iloc[0, 0]
        odds_count = db.fetch_df("SELECT COUNT(*) FROM game_odds").iloc[0, 0]
        print(f"unified_games count: {games_count}")
        print(f"game_odds count: {odds_count}")

        # Check recent odds
        recent_odds = db.fetch_df("SELECT COUNT(*) FROM game_odds WHERE last_update > NOW() - INTERVAL '24 hours'").iloc[0, 0]
        print(f"recent_odds (last 24h): {recent_odds}")

        # Check recent games
        recent_games = db.fetch_df("SELECT COUNT(*) FROM unified_games WHERE game_date >= CURRENT_DATE").iloc[0, 0]
        print(f"recent_games (future): {recent_games}")

    except Exception as e:
        print(f"Error checking DB: {e}")

if __name__ == "__main__":
    check_db()
