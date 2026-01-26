import sys
import os

# Add plugins to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../plugins")))

from ncaab_games import NCAABGames

print("Testing NCAAB download...")
try:
    downloader = NCAABGames()
    # Force only 2026
    downloader.seasons = [2026]
    downloader.download_games()
    print("Download finished.")

    # Check file size
    import glob
    import pandas as pd

    files = glob.glob("data/ncaab/games_2026.csv")
    if files:
        size = os.path.getsize(files[0])
        print(f"File {files[0]} exists. Size: {size} bytes")

        # Read with pandas to see max date
        df = pd.read_csv(files[0], header=None)
        # col 1 is date YYYYMMDD
        max_date = df[1].max()
        print(f"Max date in CSV: {max_date}")
    else:
        print("File games_2026.csv NOT found.")

    files_t = glob.glob("data/ncaab/teams_2026.csv")
    if files_t:
        size = os.path.getsize(files_t[0])
        print(f"File {files_t[0]} exists. Size: {size} bytes")
    else:
        print("File teams_2026.csv NOT found.")

except Exception as e:
    print(f"Error: {e}")
