import sys
import os
from pathlib import Path

# Add plugins to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../plugins')))

from db_loader import NHLDatabaseLoader

DATE_TO_REFRESH = "2026-01-22"

print(f"Loading NBA data for {DATE_TO_REFRESH} into DB...")
with NHLDatabaseLoader() as loader:
    count = loader.load_date(DATE_TO_REFRESH)
    print(f"Loader finished.")

print("\nVerifying DB...")
from db_manager import DBManager, default_db
from sqlalchemy import text
with default_db.get_engine().connect() as conn:
    res = conn.execute(text(f"SELECT COUNT(*) FROM nba_games WHERE game_date = '{DATE_TO_REFRESH}'"))
    print(f"NBA Games in DB for {DATE_TO_REFRESH}: {res.scalar()}")
