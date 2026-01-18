#!/usr/bin/env python3
"""
Download NFL game data using nfl-data-py library.
"""

import nfl_data_py as nfl
import json
import time
from pathlib import Path
from datetime import datetime
import pandas as pd


class NFLGames:
    """Fetch NFL game data using nfl-data-py."""
    
    def __init__(self, output_dir="data/nfl", date_folder=None):
        self.output_dir = Path(output_dir)
        if date_folder:
            self.output_dir = self.output_dir / date_folder
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def download_games_for_date(self, date_str):
        """
        Download games for a specific date.
        Date format: YYYY-MM-DD
        """
        print(f"Downloading NFL games for {date_str}...")
        
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        
        # Determine NFL season year (season starts in September)
        if date_obj.month >= 9:
            season_year = date_obj.year
        else:
            season_year = date_obj.year - 1
        
        try:
            # Get schedule for the season
            schedule = nfl.import_schedules([season_year])
            
            # Filter games for the specific date
            schedule['gameday'] = pd.to_datetime(schedule['gameday'])
            date_games = schedule[schedule['gameday'].dt.date == date_obj.date()]
            
            if len(date_games) == 0:
                print(f"  No NFL games found for {date_str}")
                return 0
            
            print(f"  Found {len(date_games)} games for {date_str}")
            
            # Save schedule for this date
            schedule_file = self.output_dir / f"schedule_{date_str}.json"
            date_games.to_json(schedule_file, orient='records', indent=2)
            print(f"  Saved schedule to {schedule_file}")
            
            # Get game IDs
            game_ids = date_games['game_id'].tolist()
            
            # Download play-by-play data for these games
            print(f"  Downloading play-by-play data...")
            try:
                pbp = nfl.import_pbp_data([season_year], downcast=False)
                
                # Filter to just these games
                date_pbp = pbp[pbp['game_id'].isin(game_ids)]
                
                if len(date_pbp) > 0:
                    pbp_file = self.output_dir / f"pbp_{date_str}.json"
                    date_pbp.to_json(pbp_file, orient='records', indent=2)
                    print(f"  Saved play-by-play to {pbp_file}")
            except Exception as pbp_error:
                # Play-by-play data may not be available yet for recent/future games
                error_msg = str(pbp_error)
                if "404" in error_msg or "Not Found" in error_msg or "name 'Error' is not defined" in error_msg:
                    print(f"  Play-by-play data not available for {season_year} season")
                else:
                    raise
            
            # Get weekly data for the week of these games
            # Weekly data is player-level, not game-level, so filter by season/week
            if len(date_games) > 0:
                try:
                    week = date_games.iloc[0]['week']
                    weekly = nfl.import_weekly_data([season_year])
                    date_weekly = weekly[(weekly['season'] == season_year) & (weekly['week'] == week)]
                    
                    if len(date_weekly) > 0:
                        weekly_file = self.output_dir / f"weekly_{date_str}.json"
                        date_weekly.to_json(weekly_file, orient='records', indent=2)
                        print(f"  Saved weekly stats to {weekly_file}")
                except Exception as weekly_error:
                    print(f"  Weekly stats not available for {season_year} season: {weekly_error}")
            
            return len(date_games)
            
        except Exception as e:
            print(f"Error downloading NFL data for {date_str}: {e}")
            raise


if __name__ == "__main__":
    # Test with a date that has games
    fetcher = NFLGames()
    fetcher.download_games_for_date("2021-09-09")

