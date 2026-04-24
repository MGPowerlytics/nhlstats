
import os
import sys
from pathlib import Path

# Add plugins directory to path
sys.path.insert(0, os.path.join(os.getcwd(), "plugins"))

from db_manager import DBManager
from csv_history_loader import CSVHistoryLoader

def backfill_ligue1():
    db = DBManager()
    loader = CSVHistoryLoader(db)

    print("🚀 Starting Ligue 1 backfill...")

    # Load all seasons from data/ligue1/
    # Config in CSVHistoryLoader for Ligue1:
    # "data_dir": Path("data/ligue1"),
    # "pattern": "F1_*.csv",

    try:
        loader.load_csv_history("Ligue1")
        print("✅ Ligue 1 backfill complete!")
    except Exception as e:
        print(f"❌ Error during backfill: {e}")

if __name__ == "__main__":
    backfill_ligue1()
