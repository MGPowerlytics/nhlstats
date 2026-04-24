
import os
import sys
from sqlalchemy import text

# Add plugins directory to path
sys.path.insert(0, os.path.join(os.getcwd(), "plugins"))

from db_manager import DBManager

def check_ligue1_stats():
    db = DBManager()

    # Check if team_game_stats table exists
    if not db.table_exists("team_game_stats"):
        print("❌ 'team_game_stats' table does not exist.")
        return

    # Count Ligue 1 stats
    print("Available sports in 'team_game_stats' table:")
    sports = db.fetch_df("SELECT DISTINCT sport FROM team_game_stats")
    print(sports)

    # Check for 'Ligue1' (case might be different)
    query = """
    SELECT
        EXTRACT(YEAR FROM game_date) as year,
        COUNT(*) / 2 as game_count
    FROM team_game_stats
    WHERE sport ILIKE 'Ligue1'
    GROUP BY year
    ORDER BY year
    """

    df = db.fetch_df(query)
    print("\nLigue 1 stats by year (game count approx):")
    print(df)

if __name__ == "__main__":
    check_ligue1_stats()
