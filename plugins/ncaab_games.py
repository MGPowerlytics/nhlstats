import pandas as pd
from pathlib import Path
import requests
from datetime import datetime
import io

class NCAABGames:
    """Download and manage NCAA Basketball game data from Massey Ratings."""
    
    def __init__(self, data_dir='data/ncaab'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # 2021 to 2026
        self.seasons = [2021, 2022, 2023, 2024, 2025, 2026]
        
    def download_games(self):
        """Download historical and current NCAAB data."""
        success = True
        for season in self.seasons:
            # Format 2 = CSV
            url = f"https://masseyratings.com/scores.php?s=cb&S={season}&all=1&mode=3&format=2"
            filename = self.data_dir / f"massey_ncaab_{season}.csv"
            
            # Skip historical if already downloaded (keep current fresh)
            if filename.exists() and season != 2026:
                continue
                
            print(f"📥 Downloading NCAAB data ({season}) from {url}...")
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                
                # Check for empty response
                if len(response.content) < 100:
                    print(f"⚠️  Small content for {season}, skipping...")
                    continue

                with open(filename, 'wb') as f:
                    f.write(response.content)
                    
                print(f"✓ Saved NCAAB data to {filename}")
            except Exception as e:
                print(f"✗ Failed to download NCAAB data for {season}: {e}")
                success = False
        return success
            
    def load_games(self):
        """Load games into standard format from all downloaded files."""
        self.download_games()
            
        all_games = []
        
        for season in self.seasons:
            csv_path = self.data_dir / f"massey_ncaab_{season}.csv"
            if not csv_path.exists():
                continue
                
            try:
                # Massey CSV Format:
                # Date (YYYYMMDD), Team1, Score1, Team2, Score2, @ (if team 2 home)
                # No headers usually
                
                # Let's read first few lines to debug format if needed, but standard is usually reliable
                # Example: 20201125, Austin Peay, 70, Abilene Chr, 80, @
                
                df = pd.read_csv(csv_path, header=None, names=['DateStr', 'Team1', 'Score1', 'Team2', 'Score2', 'Loc'])
                
                for _, row in df.iterrows():
                    date_str = str(row['DateStr']).strip()
                    try:
                        date = datetime.strptime(date_str, '%Y%m%d')
                    except:
                        continue
                        
                    team1 = row['Team1'].strip()
                    score1 = int(row['Score1'])
                    team2 = row['Team2'].strip()
                    score2 = int(row['Score2'])
                    loc = str(row['Loc']).strip()
                    
                    # Determine home/away
                    # @ denotes Team2 is home. N matches are neutral.
                    # Usually: Team 1 vs Team 2 @
                    
                    if loc == '@':
                        home_team = team2
                        home_score = score2
                        away_team = team1
                        away_score = score1
                        is_neutral = False
                    else:
                        # Assumption: Neutral or Team1 Home? 
                        # Massey usually puts @ for home. If empty, usually neutral or unknown.
                        # For betting, treating as Neutral reduces Home Advantage
                        home_team = team2 # Arbitrary if neutral
                        home_score = score2
                        away_team = team1
                        away_score = score1
                        is_neutral = True # Treat as neutral if no @
                    
                    # Store
                    all_games.append({
                        'date': date,
                        'home_team': home_team,
                        'away_team': away_team,
                        'home_score': home_score,
                        'away_score': away_score,
                        'is_neutral': is_neutral,
                        'season': season
                    })
                        
            except Exception as e:
                print(f"Error loading NCAAB games for {season}: {e}")
                
        return pd.DataFrame(all_games)

if __name__ == "__main__":
    ncaab = NCAABGames()
    df = ncaab.load_games()
    print(f"Loaded {len(df)} games.")
    print(df.tail())
