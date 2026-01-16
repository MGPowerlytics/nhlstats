#!/usr/bin/env python3
"""
Download NHL shift data showing time on ice for each player shift.
"""

import requests
import json
import csv
from pathlib import Path


class NHLShifts:
    """Fetch shift and time on ice data for NHL games."""
    
    BASE_URL = "https://api.nhle.com/stats/rest/en/shiftcharts"
    
    def __init__(self, output_dir="data/shifts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def get_game_shifts(self, game_id):
        """
        Get shift data for a specific game.
        Returns detailed shift information for all players.
        """
        url = f"{self.BASE_URL}?cayenneExp=gameId={game_id}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    
    def download_game_shifts(self, game_id, format='json'):
        """
        Download and save shift data for a game.
        format: 'json' or 'csv'
        """
        print(f"Downloading shifts for game {game_id}...")
        
        data = self.get_game_shifts(game_id)
        shifts = data.get('data', [])
        
        if format == 'json':
            output_file = self.output_dir / f"{game_id}_shifts.json"
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)
        else:  # csv
            output_file = self.output_dir / f"{game_id}_shifts.csv"
            if shifts:
                keys = shifts[0].keys()
                with open(output_file, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writeheader()
                    writer.writerows(shifts)
        
        print(f"  Saved {len(shifts)} shifts to {output_file}")
        return data
    
    def analyze_toi(self, shifts_data):
        """Calculate time on ice statistics from shift data."""
        shifts = shifts_data.get('data', [])
        
        # Group by player
        player_toi = {}
        
        for shift in shifts:
            player_id = shift.get('playerId')
            player_name = f"{shift.get('firstName')} {shift.get('lastName')}"
            duration_str = shift.get('duration', '00:00')
            
            # Convert MM:SS duration to seconds
            if isinstance(duration_str, str) and ':' in duration_str:
                parts = duration_str.split(':')
                duration = int(parts[0]) * 60 + int(parts[1])
            else:
                duration = 0
            
            if player_id not in player_toi:
                player_toi[player_id] = {
                    'name': player_name,
                    'team': shift.get('teamAbbrev'),
                    'position': shift.get('position'),
                    'total_toi': 0,
                    'shift_count': 0,
                    'shifts': []
                }
            
            player_toi[player_id]['total_toi'] += duration
            player_toi[player_id]['shift_count'] += 1
            player_toi[player_id]['shifts'].append({
                'period': shift.get('period'),
                'start_time': shift.get('startTime'),
                'end_time': shift.get('endTime'),
                'duration': duration
            })
        
        return player_toi
    
    def download_season_shifts(self, season="20232024", game_type="02", 
                               start_game=1, end_game=10):
        """
        Download shifts for a range of games.
        Warning: Full season is 1000+ games and takes considerable time.
        """
        for game_num in range(start_game, end_game + 1):
            game_id = int(f"{season[:4]}{game_type}{game_num:05d}")
            try:
                self.download_game_shifts(game_id, format='csv')
            except Exception as e:
                print(f"  Error downloading game {game_id}: {e}")


def main():
    """Example usage."""
    fetcher = NHLShifts()
    
    # Example 1: Download shifts for a specific game
    game_id = 2023020001
    shifts_data = fetcher.download_game_shifts(game_id, format='json')
    
    # Also save as CSV
    fetcher.download_game_shifts(game_id, format='csv')
    
    # Example 2: Analyze time on ice
    toi_stats = fetcher.analyze_toi(shifts_data)
    
    print(f"\nTime on Ice Summary:")
    print(f"{'Player':<25} {'Team':<5} {'TOI (sec)':<10} {'Shifts':<8} {'Avg Shift'}")
    print("-" * 70)
    
    # Sort by TOI
    sorted_players = sorted(toi_stats.values(), 
                           key=lambda x: x['total_toi'], 
                           reverse=True)
    
    for player in sorted_players[:10]:  # Top 10
        avg_shift = player['total_toi'] / player['shift_count'] if player['shift_count'] > 0 else 0
        print(f"{player['name']:<25} {player['team']:<5} "
              f"{player['total_toi']:<10} {player['shift_count']:<8} {avg_shift:.1f}")
    
    # Example 3: Download multiple games (commented out)
    # fetcher.download_season_shifts("20232024", game_type="02", start_game=1, end_game=50)


if __name__ == "__main__":
    main()
