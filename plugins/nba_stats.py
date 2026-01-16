#!/usr/bin/env python3
"""
NBA Stats Fetcher using official NBA Stats API.
Collects play-by-play, shot charts, player tracking, and game statistics.
"""

import requests
import json
from datetime import datetime, timedelta
from pathlib import Path
import time


class NBAStatsFetcher:
    """Fetch NBA statistics from official NBA Stats API."""
    
    BASE_URL = "https://stats.nba.com/stats"
    
    # Required headers to avoid being blocked
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.nba.com/',
        'Origin': 'https://www.nba.com',
        'Connection': 'keep-alive',
    }
    
    def __init__(self, output_dir="data/nba"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
    
    def get_scoreboard(self, date):
        """
        Get scoreboard for a specific date.
        
        Args:
            date: datetime.date or string in YYYY-MM-DD format
        
        Returns:
            dict with scoreboard data
        """
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d').date()
        
        url = f"{self.BASE_URL}/scoreboardv2"
        params = {
            'GameDate': date.strftime('%m/%d/%Y'),
            'LeagueID': '00',  # NBA
            'DayOffset': 0
        }
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def get_play_by_play(self, game_id):
        """
        Get play-by-play data for a specific game.
        
        Args:
            game_id: NBA game ID (e.g., '0022300500')
        
        Returns:
            dict with play-by-play data
        """
        url = f"{self.BASE_URL}/playbyplayv2"
        params = {
            'GameID': game_id,
            'StartPeriod': 0,
            'EndPeriod': 14  # Covers OT periods
        }
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def get_shot_chart(self, game_id, season='2023-24'):
        """
        Get shot chart detail for a game.
        Includes all shot attempts with coordinates, shooter, result, etc.
        
        Args:
            game_id: NBA game ID
            season: Season in format 'YYYY-YY' (e.g., '2023-24')
        
        Returns:
            dict with shot chart data
        """
        url = f"{self.BASE_URL}/shotchartdetail"
        params = {
            'GameID': game_id,
            'Season': season,
            'SeasonType': 'Regular Season',
            'TeamID': 0,
            'PlayerID': 0,
            'Outcome': '',
            'Location': '',
            'Month': 0,
            'SeasonSegment': '',
            'DateFrom': '',
            'DateTo': '',
            'OpponentTeamID': 0,
            'VsConference': '',
            'VsDivision': '',
            'Position': '',
            'RookieYear': '',
            'GameSegment': '',
            'Period': 0,
            'LastNGames': 0,
            'ContextMeasure': 'FGA',
        }
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def get_box_score_traditional(self, game_id):
        """
        Get traditional box score statistics.
        
        Args:
            game_id: NBA game ID
        
        Returns:
            dict with box score data
        """
        url = f"{self.BASE_URL}/boxscoretraditionalv2"
        params = {
            'GameID': game_id,
            'StartPeriod': 0,
            'EndPeriod': 14,
            'StartRange': 0,
            'EndRange': 28800,
            'RangeType': 0
        }
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def get_box_score_advanced(self, game_id):
        """
        Get advanced box score statistics.
        
        Args:
            game_id: NBA game ID
        
        Returns:
            dict with advanced stats
        """
        url = f"{self.BASE_URL}/boxscoreadvancedv2"
        params = {
            'GameID': game_id,
            'StartPeriod': 0,
            'EndPeriod': 14,
            'StartRange': 0,
            'EndRange': 28800,
            'RangeType': 0
        }
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def download_game(self, game_id, season='2023-24'):
        """
        Download all available data for a specific game.
        
        Args:
            game_id: NBA game ID
            season: Season string
        
        Returns:
            dict with all game data
        """
        print(f"Downloading NBA game {game_id}...")
        
        game_data = {
            'game_id': game_id,
            'timestamp': datetime.now().isoformat()
        }
        
        # Get play-by-play
        try:
            pbp = self.get_play_by_play(game_id)
            game_data['play_by_play'] = pbp
            
            pbp_file = self.output_dir / f"{game_id}_playbyplay.json"
            with open(pbp_file, 'w') as f:
                json.dump(pbp, f, indent=2)
            print(f"  Saved play-by-play to {pbp_file}")
            time.sleep(0.6)  # Rate limiting
        except Exception as e:
            print(f"  Error fetching play-by-play: {e}")
        
        # Get shot chart
        try:
            shot_chart = self.get_shot_chart(game_id, season)
            game_data['shot_chart'] = shot_chart
            
            shot_file = self.output_dir / f"{game_id}_shotchart.json"
            with open(shot_file, 'w') as f:
                json.dump(shot_chart, f, indent=2)
            print(f"  Saved shot chart to {shot_file}")
            time.sleep(0.6)
        except Exception as e:
            print(f"  Error fetching shot chart: {e}")
        
        # Get box score
        try:
            boxscore = self.get_box_score_traditional(game_id)
            game_data['boxscore'] = boxscore
            
            box_file = self.output_dir / f"{game_id}_boxscore.json"
            with open(box_file, 'w') as f:
                json.dump(boxscore, f, indent=2)
            print(f"  Saved boxscore to {box_file}")
            time.sleep(0.6)
        except Exception as e:
            print(f"  Error fetching boxscore: {e}")
        
        # Get advanced stats
        try:
            advanced = self.get_box_score_advanced(game_id)
            game_data['advanced'] = advanced
            
            adv_file = self.output_dir / f"{game_id}_advanced.json"
            with open(adv_file, 'w') as f:
                json.dump(advanced, f, indent=2)
            print(f"  Saved advanced stats to {adv_file}")
            time.sleep(0.6)
        except Exception as e:
            print(f"  Error fetching advanced stats: {e}")
        
        return game_data
    
    def download_daily_games(self, date=None, season='2023-24'):
        """
        Download all games for a specific date.
        
        Args:
            date: datetime.date or string (defaults to yesterday)
            season: Season string
        
        Returns:
            list of game data
        """
        if date is None:
            date = (datetime.now() - timedelta(days=1)).date()
        elif isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d').date()
        
        print(f"Fetching NBA games for {date}...")
        scoreboard = self.get_scoreboard(date)
        
        games = []
        game_header = scoreboard.get('resultSets', [{}])[0]
        rows = game_header.get('rowSet', [])
        
        if not rows:
            print(f"No games found for {date}")
            return games
        
        for row in rows:
            # Extract game info from row
            # Columns: [GAME_DATE_EST, GAME_SEQUENCE, GAME_ID, GAME_STATUS_ID, ...]
            game_id = row[2]
            game_status = row[3]
            
            # Only download finished games (status 3 = Final)
            if game_status == 3:
                try:
                    game_data = self.download_game(game_id, season)
                    games.append(game_data)
                except Exception as e:
                    print(f"Error downloading game {game_id}: {e}")
            else:
                print(f"Skipping game {game_id} (not final)")
        
        print(f"\nDownloaded {len(games)} games for {date}")
        return games
    
    def extract_shot_data(self, shot_chart):
        """
        Extract structured shot data from shot chart JSON.
        
        Args:
            shot_chart: Shot chart JSON from get_shot_chart()
        
        Returns:
            list of shot data dictionaries
        """
        shots = []
        
        result_sets = shot_chart.get('resultSets', [])
        if not result_sets:
            return shots
        
        shot_data = result_sets[0]
        headers = shot_data.get('headers', [])
        rows = shot_data.get('rowSet', [])
        
        for row in rows:
            shot = dict(zip(headers, row))
            shots.append(shot)
        
        return shots


def main():
    """Example usage and testing."""
    fetcher = NBAStatsFetcher()
    
    print("="*60)
    print("NBA Stats Fetcher Test")
    print("="*60)
    
    # Test 1: Get recent scoreboard
    print("\n1. Testing scoreboard retrieval...")
    test_date = '2024-01-15'  # Known game date
    
    try:
        scoreboard = fetcher.get_scoreboard(test_date)
        result_sets = scoreboard.get('resultSets', [])
        if result_sets:
            games = result_sets[0].get('rowSet', [])
            print(f"✓ Found {len(games)} games for {test_date}")
            
            if games:
                game = games[0]
                print(f"  Sample game ID: {game[2]}")
        else:
            print("✗ No games found")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test 2: Get play-by-play for a specific game
    print("\n2. Testing play-by-play retrieval...")
    test_game_id = '0022300500'  # Example game ID
    
    try:
        pbp = fetcher.get_play_by_play(test_game_id)
        result_sets = pbp.get('resultSets', [])
        if result_sets:
            plays = result_sets[0].get('rowSet', [])
            print(f"✓ Retrieved {len(plays)} plays for game {test_game_id}")
            if plays:
                print(f"  Sample play: {plays[0]}")
        else:
            print("  No play data available")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test 3: Get shot chart
    print("\n3. Testing shot chart retrieval...")
    try:
        shot_chart = fetcher.get_shot_chart(test_game_id)
        shots = fetcher.extract_shot_data(shot_chart)
        print(f"✓ Retrieved {len(shots)} shots for game {test_game_id}")
        if shots:
            made = sum(1 for s in shots if s.get('SHOT_MADE_FLAG') == 1)
            print(f"  Shots made: {made}/{len(shots)} ({made/len(shots)*100:.1f}%)")
            print(f"  Sample shot: {shots[0].get('PLAYER_NAME')} - " +
                  f"{shots[0].get('SHOT_TYPE')} from {shots[0].get('SHOT_DISTANCE')}ft")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n" + "="*60)
    print("Test complete!")
    print("="*60)


if __name__ == "__main__":
    main()
