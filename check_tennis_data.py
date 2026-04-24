import os
from plugins.db_manager import DBManager

def check_tennis():
    # Force use of localhost instead of postgres container
    os.environ['POSTGRES_HOST'] = 'localhost'
    os.environ['POSTGRES_USER'] = 'airflow'
    os.environ['POSTGRES_PASSWORD'] = 'airflow'
    os.environ['POSTGRES_DB'] = 'airflow'

    db = DBManager()

    # Check sports available
    df_sports = db.fetch_df("SELECT sport, COUNT(*) FROM unified_games GROUP BY sport")
    print("Games by sport in unified_games:")
    print(df_sports)

    # Check tennis games by year
    df_tennis = db.fetch_df("""
        SELECT EXTRACT(YEAR FROM game_date) as year, COUNT(*)
        FROM unified_games
        WHERE sport = 'tennis'
        GROUP BY year
        ORDER BY year
    """)
    print("\nTennis games by year in unified_games:")
    print(df_tennis)

if __name__ == "__main__":
    check_tennis()
