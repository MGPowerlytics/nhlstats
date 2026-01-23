import sys
import os
from sqlalchemy import text

# Add plugins to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../plugins')))

from db_manager import DBManager

db = DBManager()

def check_sport(sport_name, table_name, date_col='game_date'):
    print(f"\n--- Checking {sport_name} ({table_name}) ---")
    try:
        with db.get_engine().connect() as conn:
            # Check latest date
            query = text(f"SELECT MAX({date_col}) FROM {table_name}")
            res = conn.execute(query)
            latest_date = res.scalar()
            print(f"Latest game date: {latest_date}")

            # Check games in last 7 days
            query = text(f"""
                SELECT COUNT(*) FROM {table_name}
                WHERE {date_col} > CURRENT_DATE - INTERVAL '7 days'
            """)
            res = conn.execute(query)
            recent_count = res.scalar()
            print(f"Games in last 7 days: {recent_count}")

            # Check for today's games (scheduled)
            query = text(f"""
                SELECT COUNT(*) FROM {table_name}
                WHERE {date_col} = CURRENT_DATE
            """)
            res = conn.execute(query)
            today_count = res.scalar()
            print(f"Games scheduled for today (in DB): {today_count}")

    except Exception as e:
        print(f"Error checking {sport_name}: {e}")

if __name__ == "__main__":
    check_sport("NBA", "nba_games")
    # check_sport("NCAAB", "ncaab_games")
    # check_sport("NCAA Women's", "wncaab_games")

    print("\n--- Unified Games ---")
    try:
        with db.get_engine().connect() as conn:
            query = text("SELECT COUNT(*), MIN(game_date), MAX(game_date) FROM unified_games WHERE sport IN ('NBA', 'NCAAB', 'WNCAAB') AND game_date >= CURRENT_DATE")
            res = conn.execute(query).fetchone()
            print(f"Upcoming NBA/NCAAB/WNCAAB games in Unified: {res}")

            query = text("SELECT * FROM unified_games WHERE sport='NBA' AND game_date >= CURRENT_DATE LIMIT 5")
            res = conn.execute(query).fetchall()
            print("\nNBA Sample:")
            for row in res:
                print(row)
    except Exception as e:
        print(f"Unified Check Error: {e}")
