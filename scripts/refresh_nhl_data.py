import sys
import os

# Add plugins to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../plugins")))

from nhl_game_events import NHLGameEvents
from db_loader import NHLDatabaseLoader

DATE_TO_REFRESH = "2026-01-21"

print(f"Refreshing NHL data for {DATE_TO_REFRESH}...")

# 1. Download
print("--- Downloading Games ---")
downloader = NHLGameEvents(date_folder=DATE_TO_REFRESH)
downloader.download_games_for_date(DATE_TO_REFRESH)

# 2. Load to DB
print("\n--- Loading to Database ---")
with NHLDatabaseLoader() as loader:
    count = loader.load_date(DATE_TO_REFRESH)
    print(f"Loaded {count} games.")

print("\nDone.")
