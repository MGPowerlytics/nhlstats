#!/usr/bin/env python3
"""
Batch load all NBA data from JSON files into DuckDB.
"""

from pathlib import Path
from nba_db_loader import NBADatabaseLoader
import sys

def load_all_nba_data():
    """Load all NBA data from all date directories."""
    nba_dir = Path('data/nba')
    
    if not nba_dir.exists():
        print(f"NBA data directory not found: {nba_dir}")
        return
    
    # Get all date directories
    date_dirs = sorted([d.name for d in nba_dir.iterdir() if d.is_dir()])
    
    print(f"Found {len(date_dirs)} date directories to process")
    print(f"Date range: {date_dirs[0]} to {date_dirs[-1]}")
    
    loaded_count = 0
    skipped_count = 0
    
    with NBADatabaseLoader() as loader:
        for i, date_str in enumerate(date_dirs):
            try:
                count = loader.load_date(date_str)
                if count > 0:
                    loaded_count += count
                    if (i + 1) % 100 == 0:
                        print(f"  Processed {i+1}/{len(date_dirs)} dates... ({loaded_count} games loaded)")
                else:
                    skipped_count += 1
            except Exception as e:
                print(f"  Error loading {date_str}: {e}")
                skipped_count += 1
                continue
        
        print(f"\n✅ Loading complete!")
        print(f"   Loaded: {loaded_count} games")
        print(f"   Skipped: {skipped_count} dates")
        
        # Show summary
        print("\n=== DATABASE SUMMARY ===")
        result = loader.conn.execute("""
            SELECT 
                COUNT(*) as total_games,
                MIN(game_date) as earliest,
                MAX(game_date) as latest
            FROM games
            WHERE home_score IS NOT NULL
        """).fetchone()
        
        print(f"Completed games: {result[0]}")
        if result[1]:
            print(f"Date range: {result[1]} to {result[2]}")

if __name__ == '__main__':
    load_all_nba_data()
