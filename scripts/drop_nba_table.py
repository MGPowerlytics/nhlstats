import sys
import os
from sqlalchemy import text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../plugins')))
from db_manager import default_db

print("Dropping nba_games table...")
try:
    with default_db.get_engine().connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS nba_games"))
        conn.commit()
    print("Success.")
except Exception as e:
    print(f"Error: {e}")
