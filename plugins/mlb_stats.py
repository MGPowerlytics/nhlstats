#!/usr/bin/env python3
"""
MLB Stats Fetcher using official MLB Stats API and Baseball Savant.
Collects play-by-play, pitch-by-pitch data, and Statcast metrics.
"""

import requests
import json
from datetime import datetime, timedelta
from pathlib import Path
import time


class MLBStatsFetcher:
    """Fetch MLB statistics from official MLB Stats API."""
    
    STATS_API = "https://statsapi.mlb.com/api/v1.1"
    STATCAST_API = "https://baseballsavant.mlb.com"
    
    def __init__(self, output_dir="data/mlb"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_schedule(self, date):
        """
        Get games scheduled for a specific date.
        
        Args:
            date: datetime.date or string in YYYY-MM-DD format
        
        Returns:
            dict with schedule information
        """
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d').date()
        
        url = f"{self.STATS_API}/schedule"
        params = {
            'sportId': 1,  # MLB
            'date': date.strftime('%Y-%m-%d'),
            'hydrate': 'team,linescore'
        }
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def get_game_play_by_play(self, game_pk):
        """
        Get detailed play-by-play data for a specific game.
        
        Args:
            game_pk: MLB game ID (game_pk)
        
        Returns:
            dict with complete play-by-play data
        """
        url = f"{self.STATS_API}/game/{game_pk}/playByPlay"
        
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def get_game_feed(self, game_pk):
        """
        Get live game feed with all available data.
        Includes boxscore, linescore, plays, players, etc.
        
        Args:
            game_pk: MLB game ID
        
        Returns:
            dict with comprehensive game data
        """
        url = f"{self.STATS_API}/game/{game_pk}/feed/live"
        
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def get_game_boxscore(self, game_pk):
        """
        Get game boxscore with player statistics.
        
        Args:
            game_pk: MLB game ID
        
        Returns:
            dict with boxscore data
        """
        url = f"{self.STATS_API}/game/{game_pk}/boxscore"
        
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def download_game(self, game_pk):
        """
        Download all available data for a specific game.
        
        Args:
            game_pk: MLB game ID
        
        Returns:
            dict with all game data
        """
        print(f"Downloading MLB game {game_pk}...")
        
        game_data = {
            'game_pk': game_pk,
            'timestamp': datetime.now().isoformat()
        }
        
        # Get play-by-play
        try:
            pbp = self.get_game_play_by_play(game_pk)
            game_data['play_by_play'] = pbp
            
            pbp_file = self.output_dir / f"{game_pk}_playbyplay.json"
            with open(pbp_file, 'w') as f:
                json.dump(pbp, f, indent=2)
            print(f"  Saved play-by-play to {pbp_file}")
        except Exception as e:
            print(f"  Error fetching play-by-play: {e}")
        
        # Get live feed (includes everything)
        try:
            feed = self.get_game_feed(game_pk)
            game_data['feed'] = feed
            
            feed_file = self.output_dir / f"{game_pk}_feed.json"
            with open(feed_file, 'w') as f:
                json.dump(feed, f, indent=2)
            print(f"  Saved game feed to {feed_file}")
        except Exception as e:
            print(f"  Error fetching game feed: {e}")
        
        # Get boxscore
        try:
            boxscore = self.get_game_boxscore(game_pk)
            game_data['boxscore'] = boxscore
            
            box_file = self.output_dir / f"{game_pk}_boxscore.json"
            with open(box_file, 'w') as f:
                json.dump(boxscore, f, indent=2)
            print(f"  Saved boxscore to {box_file}")
        except Exception as e:
            print(f"  Error fetching boxscore: {e}")
        
        return game_data
    
    def download_daily_games(self, date=None):
        """
        Download all games for a specific date.
        
        Args:
            date: datetime.date or string (defaults to yesterday)
        
        Returns:
            list of game data
        """
        if date is None:
            date = (datetime.now() - timedelta(days=1)).date()
        elif isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d').date()
        
        print(f"Fetching MLB games for {date}...")
        schedule = self.get_schedule(date)
        
        games = []
        dates = schedule.get('dates', [])
        
        if not dates:
            print(f"No games scheduled for {date}")
            return games
        
        for date_entry in dates:
            for game in date_entry.get('games', []):
                game_pk = game.get('gamePk')
                status = game.get('status', {}).get('detailedState')
                
                # Only download completed/final games
                if status in ['Final', 'Completed Early']:
                    try:
                        game_data = self.download_game(game_pk)
                        games.append(game_data)
                        time.sleep(1)  # Rate limiting
                    except Exception as e:
                        print(f"Error downloading game {game_pk}: {e}")
                else:
                    print(f"Skipping game {game_pk} (status: {status})")
        
        print(f"\nDownloaded {len(games)} games for {date}")
        return games
    
    def extract_pitch_data(self, game_feed):
        """
        Extract pitch-by-pitch data from game feed.
        
        Args:
            game_feed: Game feed JSON from get_game_feed()
        
        Returns:
            list of pitch data dictionaries
        """
        pitches = []
        
        live_data = game_feed.get('liveData', {})
        plays = live_data.get('plays', {}).get('allPlays', [])
        
        for play in plays:
            play_events = play.get('playEvents', [])
            
            for event in play_events:
                if event.get('isPitch'):
                    pitch_data = {
                        'game_pk': game_feed.get('gamePk'),
                        'at_bat_index': play.get('atBatIndex'),
                        'play_id': play.get('playId'),
                        'inning': play.get('about', {}).get('inning'),
                        'half_inning': play.get('about', {}).get('halfInning'),
                        'batter': play.get('matchup', {}).get('batter', {}).get('id'),
                        'pitcher': play.get('matchup', {}).get('pitcher', {}).get('id'),
                        'pitch_number': event.get('pitchNumber'),
                        'pitch_type': event.get('details', {}).get('type', {}).get('code'),
                        'pitch_description': event.get('details', {}).get('description'),
                        'call_code': event.get('details', {}).get('call', {}).get('code'),
                        'call_description': event.get('details', {}).get('call', {}).get('description'),
                        'balls': event.get('count', {}).get('balls'),
                        'strikes': event.get('count', {}).get('strikes'),
                        'outs': event.get('count', {}).get('outs'),
                    }
                    
                    # Add pitch data if available
                    pitch_data_obj = event.get('pitchData', {})
                    if pitch_data_obj:
                        pitch_data.update({
                            'start_speed': pitch_data_obj.get('startSpeed'),
                            'end_speed': pitch_data_obj.get('endSpeed'),
                            'zone': pitch_data_obj.get('zone'),
                            'type_confidence': pitch_data_obj.get('typeConfidence'),
                            'plate_time': pitch_data_obj.get('plateTime'),
                            'extension': pitch_data_obj.get('extension'),
                        })
                        
                        # Coordinates
                        coords = pitch_data_obj.get('coordinates', {})
                        pitch_data.update({
                            'x': coords.get('x'),
                            'y': coords.get('y'),
                            'pX': coords.get('pX'),
                            'pZ': coords.get('pZ'),
                        })
                        
                        # Breaks
                        breaks = pitch_data_obj.get('breaks', {})
                        pitch_data.update({
                            'break_angle': breaks.get('breakAngle'),
                            'break_length': breaks.get('breakLength'),
                            'break_y': breaks.get('breakY'),
                            'spin_rate': breaks.get('spinRate'),
                            'spin_direction': breaks.get('spinDirection'),
                        })
                    
                    pitches.append(pitch_data)
        
        return pitches


def main():
    """Example usage and testing."""
    fetcher = MLBStatsFetcher()
    
    print("="*60)
    print("MLB Stats Fetcher Test")
    print("="*60)
    
    # Test 1: Get yesterday's schedule
    print("\n1. Testing schedule retrieval...")
    yesterday = (datetime.now() - timedelta(days=1)).date()
    try:
        schedule = fetcher.get_schedule(yesterday)
        games_count = sum(len(d.get('games', [])) for d in schedule.get('dates', []))
        print(f"✓ Found {games_count} games for {yesterday}")
        
        if games_count > 0:
            first_game = schedule['dates'][0]['games'][0]
            print(f"  Sample: {first_game.get('teams', {}).get('away', {}).get('team', {}).get('name')} @ " +
                  f"{first_game.get('teams', {}).get('home', {}).get('team', {}).get('name')}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test 2: Get a specific game (if available)
    print("\n2. Testing game data retrieval...")
    # Using Opening Day 2024 game as example
    test_game_pk = 745391  # Dodgers vs Padres, March 20, 2024
    
    try:
        game_feed = fetcher.get_game_feed(test_game_pk)
        game_data = game_feed.get('gameData', {})
        teams = game_data.get('teams', {})
        
        print(f"✓ Retrieved game {test_game_pk}")
        print(f"  Away: {teams.get('away', {}).get('name')}")
        print(f"  Home: {teams.get('home', {}).get('name')}")
        print(f"  Venue: {game_data.get('venue', {}).get('name')}")
        
        # Extract pitch data
        pitches = fetcher.extract_pitch_data(game_feed)
        print(f"  Pitches: {len(pitches)}")
        if pitches:
            print(f"  Sample pitch: {pitches[0].get('pitch_type')} at {pitches[0].get('start_speed')} mph")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n" + "="*60)
    print("Test complete!")
    print("="*60)


if __name__ == "__main__":
    main()
