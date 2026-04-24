"""
Base class for soccer data downloaders from football-data.co.uk.
"""

import pandas as pd
from pathlib import Path
import requests
from typing import List, Optional


from plugins.base_games import BaseGamesFetcher


class FootballDataCoUkGames(BaseGamesFetcher):
    """Download and manage game data from football-data.co.uk."""

    # Seasons to fetch (e.g., '2122' for 2021-2022)
    DEFAULT_SEASONS = ["2122", "2223", "2324", "2425", "2526"]

    def __init__(
        self, sport_id: str, data_dir: str, seasons: Optional[List[str]] = None
    ):
        """
        Initialize the downloader.

        Args:
            sport_id: The ID used by football-data.co.uk (e.g., 'E0' for EPL, 'F1' for Ligue 1)
            data_dir: Directory to save downloaded files
            seasons: Optional list of seasons to fetch
        """
        super().__init__(sport=sport_id, output_dir=data_dir)
        self.sport_id = sport_id
        self.seasons = seasons or self.DEFAULT_SEASONS

    def download_games(self):
        """Download historical and current season data."""
        success = True
        for season in self.seasons:
            url = (
                f"https://www.football-data.co.uk/mmz4281/{season}/{self.sport_id}.csv"
            )
            filename = self.data_dir / f"{self.sport_id}_{season}.csv"

            # Skip historical if already downloaded (keep current fresh)
            if filename.exists() and season != "2526":
                continue

            print(f"📥 Downloading {self.sport_id} data ({season}) from {url}...")
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                response = requests.get(url, headers=headers)
                response.raise_for_status()

                with open(filename, "wb") as f:
                    f.write(response.content)

                print(f"✓ Saved {self.sport_id} data to {filename}")
            except Exception as e:
                print(f"✗ Failed to download {self.sport_id} data for {season}: {e}")
                success = False
        return success

    def load_games(self) -> pd.DataFrame:
        """Load games into standard format from all downloaded files."""
        # Ensure we have data
        self.download_games()

        all_games = []

        for season in self.seasons:
            csv_path = self.data_dir / f"{self.sport_id}_{season}.csv"
            if not csv_path.exists():
                continue

            try:
                df = pd.read_csv(csv_path)

                # Standardize columns
                # CSV cols: Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR (H, D, A)

                # Parse dates (usually DD/MM/YYYY or DD/MM/YY)
                try:
                    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, format="%d/%m/%Y")
                except ValueError:
                    # Fallback for YY format
                    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, format="%d/%m/%y")

                for _, row in df.iterrows():
                    if pd.isna(row["FTHG"]):  # Skip unplayed
                        continue

                    all_games.append(
                        {
                            "Date": row["Date"].strftime("%Y-%m-%d")
                            if hasattr(row["Date"], "strftime")
                            else str(row["Date"])[:10],
                            "HomeTeam": row["HomeTeam"],
                            "AwayTeam": row["AwayTeam"],
                            "FTHG": int(row["FTHG"]),
                            "FTAG": int(row["FTAG"]),
                            "FTR": row["FTR"],
                            "date": row["Date"],
                            "home_team": row["HomeTeam"],
                            "away_team": row["AwayTeam"],
                            "home_score": int(row["FTHG"]),
                            "away_score": int(row["FTAG"]),
                            "result": row["FTR"],  # H, D, A
                        }
                    )
            except Exception as e:
                print(f"Error loading {self.sport_id} games for {season}: {e}")

        return pd.DataFrame(all_games)
