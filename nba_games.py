#!/usr/bin/env python3
"""
Download NBA game data from NBA Stats API.
"""

import requests
import json
import time
from pathlib import Path
from datetime import datetime


class NBAGames:
    """Fetch NBA game data from stats.nba.com."""
    
    BASE_URL = "https://stats.nba.com/stats"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.nba.com/',
        'Origin': 'https://www.nba.com'
    }
    
    def __init__(self, output_dir="data/nba", date_folder=None):
        self.output_dir = Path(output_dir)
        if date_folder:
            self.output_dir = self.output_dir / date_folder
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _make_request(self, url, params=None, max_retries=5):
        """Make HTTP request with exponential backoff for rate limits."""
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=self.HEADERS, params=params, timeout=30)
                
                # Handle rate limiting
                if response.status_code == 429:
                    wait_time = (2 ** attempt) * 3  # 3, 6, 12, 24, 48 seconds
                    print(f"Rate limited. Waiting {wait_time}s before retry {attempt+1}/{max_retries}")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = (2 ** attempt) * 3
                print(f"Request failed: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        
        raise Exception(f"Failed to fetch {url} after {max_retries} attempts")
    
    def get_games_for_date(self, date_str):
        """
        Get games for a specific date.
        Date format: YYYY-MM-DD
        """
        # Convert date format for NBA API (MM/DD/YYYY)
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        nba_date = date_obj.strftime('%m/%d/%Y')
        
        url = f"{self.BASE_URL}/scoreboardv2"
        params = {
            'GameDate': nba_date,
            'LeagueID': '00',  # NBA
            'DayOffset': 0
        }
        
        return self._make_request(url, params)
    
    def get_game_boxscore(self, game_id):
        """Get boxscore for a specific game."""
        url = f"{self.BASE_URL}/boxscoretraditionalv2"
        params = {
            'GameID': game_id,
            'StartPeriod': 0,
            'EndPeriod': 10,
            'StartRange': 0,
            'EndRange': 28800,
            'RangeType': 2
        }
        
        return self._make_request(url, params)
    
    def get_game_playbyplay(self, game_id):
        """Get play-by-play data for a specific game from NBA CDN."""
        url = f"https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{game_id}.json"
        
        try:
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"    Warning: Could not fetch play-by-play for {game_id}: {e}")
            return None
    
    def download_games_for_date(self, date_str):
        """Download all games for a specific date."""
        print(f"Downloading NBA games for {date_str}...")
        
        # Get scoreboard
        scoreboard = self.get_games_for_date(date_str)
        scoreboard_file = self.output_dir / f"scoreboard_{date_str}.json"
        with open(scoreboard_file, 'w') as f:
            json.dump(scoreboard, f, indent=2)
        print(f"  Saved scoreboard to {scoreboard_file}")
        
        # Get game IDs
        game_ids = []
        if 'resultSets' in scoreboard:
            for result_set in scoreboard['resultSets']:
                if result_set['name'] == 'GameHeader':
                    headers = result_set['headers']
                    game_id_idx = headers.index('GAME_ID') if 'GAME_ID' in headers else 2
                    for row in result_set['rowSet']:
                        game_ids.append(row[game_id_idx])
        
        print(f"  Found {len(game_ids)} games")
        
        # Download boxscore and play-by-play for each game
        for i, game_id in enumerate(game_ids, 1):
            try:
                # Download boxscore (skip if exists)
                boxscore_file = self.output_dir / f"boxscore_{game_id}.json"
                if not boxscore_file.exists():
                    print(f"  [{i}/{len(game_ids)}] Downloading boxscore for game {game_id}")
                    boxscore = self.get_game_boxscore(game_id)
                    with open(boxscore_file, 'w') as f:
                        json.dump(boxscore, f, indent=2)
                else:
                    print(f"  [{i}/{len(game_ids)}] Boxscore exists for game {game_id}")
                
                # Download play-by-play (always check if missing)
                pbp_file = self.output_dir / f"playbyplay_{game_id}.json"
                if not pbp_file.exists():
                    print(f"  [{i}/{len(game_ids)}] Downloading play-by-play for game {game_id}")
                    playbyplay = self.get_game_playbyplay(game_id)
                    if playbyplay:
                        with open(pbp_file, 'w') as f:
                            json.dump(playbyplay, f, indent=2)
                        actions_count = len(playbyplay.get('game', {}).get('actions', []))
                        print(f"    ✓ Saved {actions_count} actions")
                else:
                    print(f"  [{i}/{len(game_ids)}] Play-by-play exists for game {game_id}")
                
                # Rate limiting
                if i < len(game_ids):
                    time.sleep(3)
            except Exception as e:
                print(f"  Error downloading data for {game_id}: {e}")
        
        return len(game_ids)


if __name__ == "__main__":
    # Test
    fetcher = NBAGames()
    fetcher.download_games_for_date("2021-10-19")
