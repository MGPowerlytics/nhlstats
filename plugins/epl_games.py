import pandas as pd
from pathlib import Path
import requests
from plugins.football_data_co_uk import FootballDataCoUkGames


class EPLGames(FootballDataCoUkGames):
    """Download and manage EPL game data."""

    def __init__(self, data_dir="data/epl"):
        super().__init__(sport_id="E0", data_dir=data_dir)


if __name__ == "__main__":
    epl = EPLGames()
    epl.download_games()
    df = epl.load_games()
    print(f"Loaded {len(df)} finished games.")
    print(df.tail())


if __name__ == "__main__":
    epl = EPLGames()
    epl.download_games()
    df = epl.load_games()
    print(f"Loaded {len(df)} finished games.")
    print(df.tail())
