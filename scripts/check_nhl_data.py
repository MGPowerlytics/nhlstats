import sys
import os
from sqlalchemy import text

# Add plugins to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../plugins')))

from db_manager import DBManager

db = DBManager()

try:
    with db.get_engine().connect() as conn:
        print("Connected to DB.")

        # Check current date
        query = text("SELECT CURRENT_DATE")
        res = conn.execute(query)
        print(f"Current DB Date: {res.scalar()}")

        # Check latest date for NHL games in 'games' table
        query = text("SELECT MAX(game_date) FROM games")
        res = conn.execute(query)
        latest_date = res.scalar()
        print(f"Latest NHL game date in 'games': {latest_date}")

        # Check count of games in last 7 days
        query = text("""
            SELECT COUNT(*) FROM games
            WHERE game_date > CURRENT_DATE - INTERVAL '7 days'
        """)
        res = conn.execute(query)
        recent_count = res.scalar()
        print(f"NHL games in last 7 days: {recent_count}")

        # List past games with missing scores
        query = text("""
            SELECT game_date, home_team_name, away_team_name
            FROM games
            WHERE (home_score IS NULL OR away_score IS NULL)
            AND game_date < CURRENT_DATE
            ORDER BY game_date DESC
        """)
        res = conn.execute(query)
        missing_games = res.fetchall()
        print(f"Missing scores for generic 'games' table (likely NHL):")
        for game in missing_games:
            print(f"  {game[0]}: {game[1]} vs {game[2]}")

except Exception as e:
    print(f"Error checking DB: {e}")
