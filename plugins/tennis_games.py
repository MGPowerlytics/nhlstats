import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import requests


class TennisGames:
    """Download and manage ATP/WTA tennis game data."""

    def __init__(self, data_dir: str = "data/tennis") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Years to fetch — dynamic so the pipeline never goes stale at year-end.
        # Always include the next calendar year so an early-January season opener
        # is captured the moment tennis-data.co.uk publishes it.
        current_year = datetime.now().year
        self.years = [str(y) for y in range(2021, current_year + 2)]
        self.tours = ["atp", "wta"]

    def download_games(self):
        """Download historical and current Tennis data (Excel -> CSV)."""
        success = True
        headers = {"User-Agent": "Mozilla/5.0"}

        for tour in self.tours:
            for year in self.years:
                # ATP: http://www.tennis-data.co.uk/2024/2024.xlsx
                # WTA: http://www.tennis-data.co.uk/2024w/2024.xlsx

                if tour == "atp":
                    url = f"http://www.tennis-data.co.uk/{year}/{year}.xlsx"
                else:
                    url = f"http://www.tennis-data.co.uk/{year}w/{year}.xlsx"

                xlsx_filename = self.data_dir / f"{tour}_{year}.xlsx"
                csv_filename = self.data_dir / f"{tour}_{year}.csv"

                # Skip if CSV exists and not current/future year (re-fetch only the
                # actively-played seasons so updates land daily).
                current_year = datetime.now().year
                if csv_filename.exists() and int(year) < current_year:
                    continue

                print(f"📥 Downloading {tour.upper()} data ({year}) from {url}...")
                try:
                    response = requests.get(url, headers=headers)
                    if response.status_code == 404:
                        print(f"  Note: Data for {tour} {year} not found.")
                        continue

                    response.raise_for_status()

                    # Save Excel temporarily
                    with open(xlsx_filename, "wb") as f:
                        f.write(response.content)

                    # Convert to CSV immediately
                    try:
                        df = pd.read_excel(xlsx_filename)
                        df.to_csv(csv_filename, index=False)
                        print(f"✓ Converted to {csv_filename}")
                        # Cleanup Excel file to save space? Optional.
                        # xlsx_filename.unlink()
                    except Exception as e:
                        print(f"  Error converting {xlsx_filename} to CSV: {e}")

                except Exception as e:
                    print(f"✗ Failed to download {tour} data for {year}: {e}")
                    success = False
        return success

    def _read_tennis_csv(self, csv_path: Path) -> pd.DataFrame:
        """Read tennis CSV with encoding fallbacks."""
        try:
            return pd.read_csv(csv_path, encoding="latin1")
        except Exception:
            return pd.read_csv(csv_path)

    def _standardize_tennis_data(
        self, df: pd.DataFrame, tour: str
    ) -> List[Dict[str, Any]]:
        """Standardize tennis data columns and return list of game dictionaries."""
        if "Date" not in df.columns:
            return []

        # Clean date usually DD/MM/YYYY or similar. Pandas is smart.
        # Silence warning for format %Y-%m-%d
        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message="Parsing dates in %Y-%m-%d format"
            )
            df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")

        games = []
        for _, row in df.iterrows():
            if pd.isna(row["Date"]) or pd.isna(row["Winner"]) or pd.isna(row["Loser"]):
                continue

            games.append(
                {
                    "tour": tour.upper(),
                    "date": row["Date"],
                    "tournament": row.get("Tournament"),
                    "surface": row.get("Surface"),
                    "winner": row.get("Winner"),
                    "loser": row.get("Loser"),
                    "w_rank": row.get("WRank"),
                    "l_rank": row.get("LRank"),
                    "score": row.get("Score"),  # e.g. "6-4 6-2"
                }
            )
        return games

    def load_games(self):
        """Load games into standard format."""
        self.download_games()
        all_games = []

        for tour in self.tours:
            for year in self.years:
                csv_path = self.data_dir / f"{tour}_{year}.csv"
                if not csv_path.exists():
                    continue

                try:
                    df = self._read_tennis_csv(csv_path)
                    games = self._standardize_tennis_data(df, tour)
                    all_games.extend(games)
                except Exception as e:
                    print(f"Error loading {tour} games for {year}: {e}")

        return pd.DataFrame(all_games)


if __name__ == "__main__":
    tennis = TennisGames()
    tennis.download_games()
    df = tennis.load_games()
    print(f"Loaded {len(df)} finished games.")
    if not df.empty:
        print(df.tail())
