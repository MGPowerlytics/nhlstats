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

        # Check content
        query = text("SELECT * FROM nba_games LIMIT 1")
        res = conn.execute(query)
        print(f"Row: {res.fetchone()}")

except Exception as e:
    print(f"Error checking DB: {e}")
