import sys
import os
import logging

# Add plugins to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../plugins')))

from nba_games import NBAGames

logging.basicConfig(level=logging.INFO)

print("Testing NBA download for TODAY (2026-01-22)...")
try:
    game_date = "2026-01-22"
    downloader = NBAGames(date_folder=game_date)
    downloader.download_games_for_date(game_date)
    print("Download triggered.")

    # Check if files exist
    import glob
    files = glob.glob(f"data/nba/{game_date}/*.json")
    print(f"Found {len(files)} JSON files in data/nba/{game_date}")

except Exception as e:
    print(f"Error: {e}")
