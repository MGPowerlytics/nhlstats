#!/usr/bin/env python3
"""
Backfill NHL data for the 2025-26 season (Oct 2025 - Jan 2026).
Downloads games and loads them into DuckDB.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add plugins to path
sys.path.insert(0, '/mnt/data2/nhlstats/plugins')

from nhl_game_events import NHLGameEvents
from db_loader import NHLDatabaseLoader


def backfill_nhl_current_season():
    """Download NHL games from Oct 2025 to today and load into DB."""
    start_date = datetime(2025, 10, 1)
    end_date = datetime.now()
    
    print(f"=" * 60)
    print(f"NHL 2025-26 Season Backfill")
    print(f"Date range: {start_date.date()} to {end_date.date()}")
    print(f"=" * 60)
    
    current_date = start_date
    total_games = 0
    dates_processed = 0
    
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        
        # Check if already downloaded
        games_dir = Path(f'data/games/{date_str}')
        if games_dir.exists() and list(games_dir.glob('*_boxscore.json')):
            print(f"[{date_str}] Already downloaded, skipping...")
            current_date += timedelta(days=1)
            continue
        
        try:
            # Create fetcher with date folder
            fetcher = NHLGameEvents(date_folder=date_str)
            
            # Get schedule for the date
            schedule = fetcher.get_schedule_by_date(date_str)
            
            game_ids = []
            for week in schedule.get('gameWeek', []):
                for game in week.get('games', []):
                    # Only download completed games
                    game_state = game.get('gameState', '')
                    if game_state in ['OFF', 'FINAL']:
                        game_ids.append(game.get('id'))
            
            if game_ids:
                print(f"[{date_str}] Found {len(game_ids)} completed games")
                for game_id in game_ids:
                    try:
                        fetcher.download_game(game_id)
                        total_games += 1
                    except Exception as e:
                        print(f"  Error downloading game {game_id}: {e}")
                dates_processed += 1
            else:
                print(f"[{date_str}] No completed games")
                
        except Exception as e:
            print(f"[{date_str}] Error: {e}")
        
        current_date += timedelta(days=1)
    
    print(f"\n" + "=" * 60)
    print(f"Download Complete!")
    print(f"  Dates processed: {dates_processed}")
    print(f"  Games downloaded: {total_games}")
    print(f"=" * 60)
    
    # Now load into DuckDB
    print(f"\nLoading games into DuckDB...")
    
    with NHLDatabaseLoader('data/nhlstats.duckdb') as loader:
        current_date = start_date
        games_loaded = 0
        
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            loaded = loader.load_date(date_str)
            games_loaded += loaded
            current_date += timedelta(days=1)
        
        print(f"\n✓ Loaded {games_loaded} games into DuckDB")
    
    return total_games


if __name__ == "__main__":
    backfill_nhl_current_season()
