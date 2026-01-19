"""
Ligue 1 (French Soccer) game data downloader.

Downloads historical match results to build Elo ratings.
"""

import requests
from datetime import datetime
from typing import List, Dict

class Ligue1GameDownloader:
    """Download Ligue 1 match results."""
    
    def __init__(self):
        # Using a free soccer API - football-data.org
        # For production, may need API key
        self.base_url = "https://api.football-data.org/v4"
        self.headers = {}
        # Ligue 1 competition ID: 2015 (FL1)
        self.competition_id = 2015
    
    def download_season_games(self, season: str = "2023") -> List[Dict]:
        """
        Download games for a season.
        
        Args:
            season: Season year (e.g., "2023" for 2023/24 season)
            
        Returns:
            List of match dictionaries
        """
        url = f"{self.base_url}/competitions/{self.competition_id}/matches"
        params = {'season': season}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                matches = data.get('matches', [])
                
                games = []
                for match in matches:
                    if match['status'] == 'FINISHED':
                        score = match.get('score', {}).get('fullTime', {})
                        home_score = score.get('home')
                        away_score = score.get('away')
                        
                        if home_score is not None and away_score is not None:
                            # Determine outcome
                            if home_score > away_score:
                                outcome = 'home'
                            elif away_score > home_score:
                                outcome = 'away'
                            else:
                                outcome = 'draw'
                            
                            games.append({
                                'date': match['utcDate'],
                                'home_team': match['homeTeam']['name'],
                                'away_team': match['awayTeam']['name'],
                                'home_score': home_score,
                                'away_score': away_score,
                                'outcome': outcome
                            })
                
                print(f"  ✓ Downloaded {len(games)} Ligue 1 matches for {season}")
                return games
            else:
                print(f"  ⚠️  API returned status {response.status_code}")
                return []
                
        except Exception as e:
            print(f"  ❌ Error downloading Ligue 1 games: {e}")
            return []
    
    def get_team_mapping(self) -> Dict[str, str]:
        """
        Map between different team name formats.
        
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


def download_ligue1_history():
    """Download multiple seasons of Ligue 1 history."""
    downloader = Ligue1GameDownloader()
    
    print("📥 Downloading Ligue 1 historical data...\n")
    
    all_games = []
    # Download last 3 seasons
    for season in ['2021', '2022', '2023']:
        games = downloader.download_season_games(season)
        all_games.extend(games)
    
    print(f"\n✓ Total games downloaded: {len(all_games)}")
    return all_games


if __name__ == '__main__':
    games = download_ligue1_history()
    
    if games:
        print(f"\n📊 Sample games:")
        for game in games[:5]:
            print(f"  {game['date']}: {game['away_team']} @ {game['home_team']} "
                  f"({game['away_score']}-{game['home_score']}) - {game['outcome'].upper()}")
