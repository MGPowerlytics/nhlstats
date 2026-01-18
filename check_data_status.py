#!/usr/bin/env python3
"""Check current data status for all leagues."""

import duckdb
from pathlib import Path
from datetime import datetime
import json

print("=== CURRENT DATA STATUS FOR ALL LEAGUES ===\n")

# NHL - from DuckDB
print("📊 NHL (DuckDB)")
conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)
result = conn.execute("""
    SELECT 
        COUNT(*) as total_games,
        MIN(game_date) as oldest_game,
        MAX(game_date) as newest_game,
        COUNT(CASE WHEN game_date >= '2024-10-01' THEN 1 END) as current_season_games
    FROM games 
    WHERE game_state IN ('OFF', 'FINAL')
""").fetchone()
print(f"   Total completed games: {result[0]:,}")
print(f"   Date range: {result[1]} to {result[2]}")
print(f"   2024-25 season games: {result[3]:,}")
conn.close()

# NBA - from JSON files
print("\n📊 NBA (JSON files)")
nba_path = Path('data/nba')
if nba_path.exists():
    date_folders = sorted([d for d in nba_path.iterdir() if d.is_dir()])
    if date_folders:
        # Count games from scoreboards
        total_games = 0
        for folder in date_folders:
            scoreboard = folder / f"scoreboard_{folder.name}.json"
            if scoreboard.exists():
                with open(scoreboard) as f:
                    data = json.load(f)
                    for rs in data.get('resultSets', []):
                        if rs['name'] == 'GameHeader':
                            total_games += len(rs['rowSet'])
        print(f"   Total game dates with data: {len(date_folders)}")
        print(f"   Total games: {total_games:,}")
        print(f"   Date range: {date_folders[0].name} to {date_folders[-1].name}")
        
        # Count current season
        current_season = [d for d in date_folders if d.name >= '2024-10-22']
        print(f"   2024-25 season dates: {len(current_season)}")
else:
    print("   No NBA data directory found")

# MLB - from DuckDB
print("\n📊 MLB (DuckDB)")
conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)
try:
    result = conn.execute("""
        SELECT 
            COUNT(*) as total_games,
            MIN(game_date) as oldest_game,
            MAX(game_date) as newest_game,
            COUNT(CASE WHEN game_date >= '2024-03-28' THEN 1 END) as current_season_games
        FROM mlb_games 
        WHERE status = 'Final'
    """).fetchone()
    print(f"   Total completed games: {result[0]:,}")
    print(f"   Date range: {result[1]} to {result[2]}")
    print(f"   2024 season games: {result[3]:,}")
except Exception as e:
    print(f"   Error: {e}")
conn.close()

# NFL - from DuckDB
print("\n📊 NFL (DuckDB)")
conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)
try:
    result = conn.execute("""
        SELECT 
            COUNT(*) as total_games,
            MIN(gameday) as oldest_game,
            MAX(gameday) as newest_game,
            COUNT(CASE WHEN gameday >= '2024-09-05' THEN 1 END) as current_season_games
        FROM nfl_games 
        WHERE home_score IS NOT NULL
    """).fetchone()
    print(f"   Total completed games: {result[0]:,}")
    print(f"   Date range: {result[1]} to {result[2]}")
    print(f"   2024 season games: {result[3]:,}")
except Exception as e:
    print(f"   Error: {e}")
conn.close()

print(f"\n📅 Today's date: {datetime.now().strftime('%Y-%m-%d')}")
