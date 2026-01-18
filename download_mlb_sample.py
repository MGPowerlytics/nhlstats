import sys
from pathlib import Path

# Add plugins to path
sys.path.append('/mnt/data2/nhlstats/plugins')
from mlb_games import MLBGames

fetcher = MLBGames()
fetcher.download_games_for_date("2021-04-01")
