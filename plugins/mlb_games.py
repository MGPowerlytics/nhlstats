#!/usr/bin/env python3
"""
Download MLB game data from MLB Stats API.
"""

import requests
import json
import time
from pathlib import Path
from datetime import datetime


class MLBGames:
    """Fetch MLB game data from statsapi.mlb.com."""
    
    BASE_URL = "https://statsapi.mlb.com/api/v1"
    
    def __init__(self, output_dir="data/mlb", date_folder=None):
        self.output_dir = Path(output_dir)
        if date_folder:
            self.output_dir = self.output_dir / date_folder
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _make_request(self, url, params=None, max_retries=5):
        """Make HTTP request with exponential backoff for rate limits."""
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, timeout=30)
                
                # Handle rate limiting
                if response.status_code == 429:
                    wait_time = (2 ** attempt) * 3  # 3, 6, 12, 24, 48 seconds
                    print(f"Rate limited. Waiting {wait_time}s before retry {attempt+1}/{max_retries}")
                    time.sleep(wait_time)
                    continue
                
                if response.status_code == 404:
                    print(f"  Resource not found: {url}")
                    return {}
                
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = (2 ** attempt) * 3
                print(f"Request failed: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        
        raise Exception(f"Failed to fetch {url} after {max_retries} attempts")
    
    def get_schedule_for_date(self, date_str):
        """
        Get schedule for a specific date.
        Date format: YYYY-MM-DD
        """
        url = f"{self.BASE_URL}/schedule"
        params = {
            'sportId': 1,  # MLB
            'date': date_str,
            'hydrate': 'team,linescore,decisions'
        }
        
        return self._make_request(url, params)
    
    def get_game_data(self, game_id):
        """Get detailed game data including play-by-play."""
        # Use v1.1 for live feed
        url = f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live"
        return self._make_request(url)
    
    def get_game_boxscore(self, game_id):
        """Get boxscore for a specific game."""
        url = f"{self.BASE_URL}/game/{game_id}/boxscore"
        return self._make_request(url)
    
    def download_games_for_date(self, date_str):
        """Download all games for a specific date."""
        print(f"Downloading MLB games for {date_str}...")
        
        # Get schedule
        schedule = self.get_schedule_for_date(date_str)
        schedule_file = self.output_dir / f"schedule_{date_str}.json"
        with open(schedule_file, 'w') as f:
            json.dump(schedule, f, indent=2)
        print(f"  Saved schedule to {schedule_file}")
        
        # Get game IDs
        game_ids = []
        if 'dates' in schedule and len(schedule['dates']) > 0:
            for game in schedule['dates'][0].get('games', []):
                game_ids.append(game['gamePk'])
        
        print(f"  Found {len(game_ids)} games")
        
        # Download data for each game
        for i, game_id in enumerate(game_ids, 1):
            try:
                print(f"  [{i}/{len(game_ids)}] Downloading game {game_id}")
                
                # Get game feed
                game_data = self.get_game_data(game_id)
                game_file = self.output_dir / f"game_{game_id}.json"
                with open(game_file, 'w') as f:
                    json.dump(game_data, f, indent=2)
                
                # Get boxscore
                boxscore = self.get_game_boxscore(game_id)
                boxscore_file = self.output_dir / f"boxscore_{game_id}.json"
                with open(boxscore_file, 'w') as f:
                    json.dump(boxscore, f, indent=2)
                
                # Rate limiting
                if i < len(game_ids):
                    time.sleep(3)
            except Exception as e:
                print(f"  Error downloading game {game_id}: {e}")
        
        return len(game_ids)


if __name__ == "__main__":
    # Test
    fetcher = MLBGames()
    fetcher.download_games_for_date("2021-04-01")
