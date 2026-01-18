import sys
import json
import requests
import time
from pathlib import Path
from datetime import datetime

# Add plugins to path
sys.path.append('/mnt/data2/nhlstats/plugins')
from mlb_games import MLBGames

def download_season_schedule(year):
    print(f"Downloading MLB schedule for {year}...")
    
    # MLB API allows fetching a range of dates
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        'sportId': 1,
        'startDate': start_date,
        'endDate': end_date,
        'hydrate': 'team,linescore'  # removed decisions to keep it lighter
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Save by date to match existing structure
        output_dir = Path("data/mlb")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        total_games = 0
        dates_count = 0
        
        if 'dates' in data:
            for date_info in data['dates']:
                date_str = date_info['date']
                
                # Construct daily schedule object
                daily_schedule = {
                    "copyright": data.get("copyright"),
                    "totalItems": date_info.get("totalItems"),
                    "totalEvents": date_info.get("totalEvents"),
                    "totalGames": date_info.get("totalGames"),
                    "totalGamesInProgress": date_info.get("totalGamesInProgress"),
                    "dates": [date_info]
                }
                
                # Save to file
                date_file = output_dir / f"schedule_{date_str}.json"
                with open(date_file, 'w') as f:
                    json.dump(daily_schedule, f, indent=2)
                
                total_games += date_info.get("totalGames", 0)
                dates_count += 1
                
        print(f"✓ Processed {year}: {total_games} games across {dates_count} days")
        
    except Exception as e:
        print(f"✗ Error downloading {year}: {e}")

if __name__ == "__main__":
    for year in range(2021, 2026):
        download_season_schedule(year)
