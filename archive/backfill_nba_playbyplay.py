#!/usr/bin/env python3
"""
Backfill NBA play-by-play data for games that only have boxscores.
"""

import json
import time
from pathlib import Path
from nba_games import NBAGames

def find_games_missing_playbyplay(data_dir="data/nba"):
    """Find all games that have boxscores but no play-by-play."""
    data_path = Path(data_dir)
    
    boxscore_files = list(data_path.glob("*/boxscore_*.json"))
    missing = []
    
    for boxscore_file in boxscore_files:
        game_id = boxscore_file.stem.replace("boxscore_", "")
        date_folder = boxscore_file.parent
        pbp_file = date_folder / f"playbyplay_{game_id}.json"
        
        if not pbp_file.exists():
            missing.append({
                'game_id': game_id,
                'date_folder': date_folder.name,
                'boxscore_file': boxscore_file
            })
    
    return missing

def backfill_playbyplay(missing_games, batch_size=50):
    """Download play-by-play for missing games."""
    print(f"🏀 NBA Play-by-Play Backfill")
    print(f"=" * 80)
    print(f"Found {len(missing_games)} games missing play-by-play data")
    print("")
    
    success = 0
    failed = 0
    
    for i, game_info in enumerate(missing_games, 1):
        game_id = game_info['game_id']
        date_folder = game_info['date_folder']
        
        try:
            print(f"[{i}/{len(missing_games)}] Downloading play-by-play for {game_id} ({date_folder})")
            
            # Create fetcher for this date folder
            fetcher = NBAGames(output_dir=f"data/nba/{date_folder}")
            
            # Download play-by-play
            playbyplay = fetcher.get_game_playbyplay(game_id)
            
            if playbyplay:
                pbp_file = Path(f"data/nba/{date_folder}/playbyplay_{game_id}.json")
                with open(pbp_file, 'w') as f:
                    json.dump(playbyplay, f, indent=2)
                
                actions_count = len(playbyplay.get('game', {}).get('actions', []))
                print(f"  ✓ Saved {actions_count} actions")
                success += 1
            else:
                print(f"  ✗ No play-by-play data available")
                failed += 1
            
            # Rate limiting - be gentle with the API
            if i % batch_size == 0:
                print(f"\n⏸  Completed {i} games. Taking 30s break to avoid rate limits...\n")
                time.sleep(30)
            else:
                time.sleep(2)
                
        except Exception as e:
            print(f"  ✗ Error: {e}")
            failed += 1
            time.sleep(5)
    
    print("")
    print("=" * 80)
    print(f"✅ Backfill Complete!")
    print(f"   Success: {success}")
    print(f"   Failed: {failed}")
    print(f"   Total: {len(missing_games)}")
    print("=" * 80)

if __name__ == "__main__":
    print("Scanning for missing play-by-play data...")
    missing = find_games_missing_playbyplay()
    
    if not missing:
        print("✅ No missing play-by-play data found!")
    else:
        print(f"\n⚠️  Found {len(missing)} games without play-by-play")
        print("\nSample missing games:")
        for game in missing[:5]:
            print(f"  - {game['game_id']} ({game['date_folder']})")
        
        response = input(f"\nDownload play-by-play for {len(missing)} games? (y/N): ")
        
        if response.lower() == 'y':
            backfill_playbyplay(missing)
        else:
            print("Cancelled.")
