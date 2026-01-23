"""
Ligue 1 (French Soccer) game data downloader.

Downloads historical match results from football-data.co.uk (free CSV source).
"""

import pandas as pd
from pathlib import Path
import requests
from datetime import datetime

class Ligue1Games:
    """Download and manage Ligue 1 game data."""

    def __init__(self, data_dir='data/ligue1'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Seasons to fetch (e.g., '2122' for 2021-2022)
        self.seasons = ['2122', '2223', '2324', '2425', '2526']

    def download_games(self):
        """Download historical and current Ligue 1 data."""
        success = True
        for season in self.seasons:
            url = f"https://www.football-data.co.uk/mmz4281/{season}/F1.csv"
            filename = self.data_dir / f"F1_{season}.csv"

            # Skip historical if already downloaded (keep current fresh)
            if filename.exists() and season != '2526':
                continue

            print(f"📥 Downloading Ligue 1 data ({season}) from {url}...")
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(url, headers=headers)
                response.raise_for_status()

                with open(filename, 'wb') as f:
                    f.write(response.content)

                print(f"✓ Saved Ligue 1 data to {filename}")
            except Exception as e:
                print(f"✗ Failed to download Ligue 1 data for {season}: {e}")
                success = False
        return success

    def load_games(self):
        """Load games into standard format from all downloaded files."""
        # Ensure we have data
        self.download_games()

        all_games = []

        for season in self.seasons:
            csv_path = self.data_dir / f"F1_{season}.csv"
            if not csv_path.exists():
                continue

            try:
                df = pd.read_csv(csv_path)

                # Standardize columns
                # CSV cols: Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR (H, D, A)

                # Parse dates (usually DD/MM/YYYY)
                df['Date'] = pd.to_datetime(df['Date'], dayfirst=True)

                for _, row in df.iterrows():
                    if pd.isna(row['FTHG']):  # Skip unplayed
                        continue

                    all_games.append({
                        'date': row['Date'],
                        'home_team': row['HomeTeam'],
                        'away_team': row['AwayTeam'],
                        'home_score': int(row['FTHG']),
                        'away_score': int(row['FTAG']),
                        'result': row['FTR']  # H, D, A
                    })
            except Exception as e:
                print(f"Error loading Ligue 1 games for {season}: {e}")

        return pd.DataFrame(all_games)

    def get_team_mapping(self):
        """Map between different team name formats used in CSV vs Kalshi.

        Returns:
            Dictionary mapping various name formats to canonical names
        """
        return {
            'Paris Saint-Germain': 'PSG',
            'Paris Saint Germain': 'PSG',
            'Olympique de Marseille': 'Marseille',
            'Olympique Marseille': 'Marseille',
            'Olympique Lyonnais': 'Lyon',
            'AS Monaco FC': 'Monaco',
            'AS Monaco': 'Monaco',
            'Lille OSC': 'Lille',
            'OGC Nice': 'Nice',
            'Stade Rennais FC': 'Rennes',
            'Stade Rennais': 'Rennes',
            'RC Lens': 'Lens',
            'Stade de Reims': 'Reims',
            'Montpellier HSC': 'Montpellier',
            'FC Nantes': 'Nantes',
            'AJ Auxerre': 'Auxerre',
            'Le Havre AC': 'Le Havre',
            'FC Lorient': 'Lorient',
            'Toulouse FC': 'Toulouse',
            'Angers SCO': 'Angers',
            'Brest': 'Brest',
            'RC Strasbourg': 'Strasbourg',
        }


if __name__ == "__main__":
    ligue1 = Ligue1Games()
    ligue1.download_games()
    df = ligue1.load_games()
    print(f"Loaded {len(df)} finished games.")
    print(df.tail())
