
"""
Backfill script for soccer (EPL, Ligue 1) stats.
Populates unified_games, team_game_stats, and soccer_team_game_stats_ext from historical CSVs.
"""

import os
import sys
from pathlib import Path

# Add plugins to path
sys.path.insert(0, os.path.join(os.getcwd(), "plugins"))

from db_manager import DBManager
from csv_history_loader import CSVHistoryLoader

def backfill_soccer():
    # Use internal postgres host
    db = DBManager(connection_string="postgresql+psycopg2://airflow:airflow@postgres:5432/airflow")
    loader = CSVHistoryLoader(db)

    print("🚀 Starting Soccer Stats Backfill...")

    for sport in ["Ligue1", "EPL"]:
        print(f"\n📊 Backfilling {sport}...")
        try:
            loader.load_csv_history(sport)
            print(f"✅ {sport} backfill complete!")
        except Exception as e:
            print(f"❌ Error during {sport} backfill: {e}")

if __name__ == "__main__":
    backfill_soccer()
