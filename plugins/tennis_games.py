import pandas as pd
from pathlib import Path
import requests
from datetime import datetime

class TennisGames:
    """Download and manage ATP/WTA tennis game data."""

    def __init__(self, data_dir='data/tennis'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Years to fetch (e.g., '2021', '2022'...)
        self.years = ['2021', '2022', '2023', '2024', '2025', '2026']
        self.tours = ['atp', 'wta']

    def download_games(self):
        """Download historical and current Tennis data (Excel -> CSV)."""
        success = True
        headers = {'User-Agent': 'Mozilla/5.0'}

        for tour in self.tours:
            for year in self.years:
                # ATP: http://www.tennis-data.co.uk/2024/2024.xlsx
                # WTA: http://www.tennis-data.co.uk/2024w/2024.xlsx

                if tour == 'atp':
                    url = f"http://www.tennis-data.co.uk/{year}/{year}.xlsx"
                else:
                    url = f"http://www.tennis-data.co.uk/{year}w/{year}.xlsx"

                xlsx_filename = self.data_dir / f"{tour}_{year}.xlsx"
                csv_filename = self.data_dir / f"{tour}_{year}.csv"

                # Skip if CSV exists and not current/future year
                if csv_filename.exists() and year not in ['2025', '2026']:
                    continue

                print(f"📥 Downloading {tour.upper()} data ({year}) from {url}...")
                try:
                    response = requests.get(url, headers=headers)
                    if response.status_code == 404:
                         print(f"  Note: Data for {tour} {year} not found.")
                         continue

                    response.raise_for_status()

                    # Save Excel temporarily
                    with open(xlsx_filename, 'wb') as f:
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
                    # Tennis CSVs can have encoding issues
                    try:
                        df = pd.read_csv(csv_path, encoding='latin1')
                    except:
                        df = pd.read_csv(csv_path)

                    # Standardize columns
                    # Common cols: Date, Tournament, Surface, Winner, Loser, WRank, LRank, WSets, LSets

                    if 'Date' not in df.columns:
                        continue

                    # Clean date
                    # Usually DD/MM/YYYY or similar. Pandas is smart.
                    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')

                    for _, row in df.iterrows():
                        if pd.isna(row['Date']) or pd.isna(row['Winner']) or pd.isna(row['Loser']):
                            continue

                        all_games.append({
                            'tour': tour.upper(),
                            'date': row['Date'],
                            'tournament': row.get('Tournament'),
                            'surface': row.get('Surface'),
                            'winner': row.get('Winner'),
                            'loser': row.get('Loser'),
                            'w_rank': row.get('WRank'),
                            'l_rank': row.get('LRank'),
                            'score': row.get('Score') # e.g. "6-4 6-2"
                        })
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
