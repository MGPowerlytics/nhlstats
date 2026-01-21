#!/usr/bin/env python3
"""
Backfill NBA games from JSON scoreboard files into PostgreSQL.

This script:
1. Scans data/nba/ directory for scoreboard JSON files
2. Parses game data from NBA Stats API format
3. Loads into unified_games table in PostgreSQL
4. Handles updates for games that already exist
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent / "plugins"))

from db_manager import default_db


def parse_scoreboard_json(file_path: Path) -> List[Dict[str, Any]]:
    """Parse NBA scoreboard JSON file and extract game data."""
    with open(file_path) as f:
        data = json.load(f)

    games = []

    # NBA API format: resultSets array with different data
    if 'resultSets' not in data:
        return games

    # Find the GameHeader and LineScore result sets
    game_header = None
    line_score = None

    for rs in data['resultSets']:
        if rs.get('name') == 'GameHeader':
            game_header = rs
        elif rs.get('name') == 'LineScore':
            line_score = rs

    if not game_header or not line_score:
        return games

    # Parse game headers
    game_header_cols = {col: idx for idx, col in enumerate(game_header['headers'])}

    for row in game_header['rowSet']:
        game_id = str(row[game_header_cols['GAME_ID']])
        game_date_str = str(row[game_header_cols['GAME_DATE_EST']])
        game_status = str(row[game_header_cols['GAME_STATUS_TEXT']])
        season = row[game_header_cols.get('SEASON', 0)]

        # Parse date (format: 2024-10-22T00:00:00)
        try:
            game_date = datetime.strptime(game_date_str[:10], '%Y-%m-%d').date()
        except:
            continue

        # Find team scores from LineScore
        line_score_cols = {col: idx for idx, col in enumerate(line_score['headers'])}

        home_team = None
        away_team = None
        home_score = None
        away_score = None

        for ls_row in line_score['rowSet']:
            if str(ls_row[line_score_cols['GAME_ID']]) == game_id:
                team_abbrev = ls_row[line_score_cols['TEAM_ABBREVIATION']]
                team_name = ls_row[line_score_cols['TEAM_CITY_NAME']] + ' ' + ls_row[line_score_cols['TEAM_NAME']]
                team_id = str(ls_row[line_score_cols['TEAM_ID']])
                pts = ls_row[line_score_cols.get('PTS', None)]

                # Home team has different indicator in different API versions
                # Typically the first team listed is the home team
                if home_team is None:
                    home_team = team_name
                    home_team_id = team_id
                    home_score = pts if pts is not None else 0
                else:
                    away_team = team_name
                    away_team_id = team_id
                    away_score = pts if pts is not None else 0

        if home_team and away_team:
            games.append({
                'game_id': f"NBA_{game_id}",
                'sport': 'NBA',
                'game_date': game_date,
                'season': season if season else None,
                'status': game_status,
                'home_team_id': home_team_id,
                'home_team_name': home_team,
                'away_team_id': away_team_id,
                'away_team_name': away_team,
                'home_score': home_score,
                'away_score': away_score,
            })

    return games


def load_games_to_db(games: List[Dict[str, Any]]) -> int:
    """Load games into PostgreSQL unified_games table."""
    loaded = 0

    for game in games:
        try:
            default_db.execute("""
                INSERT INTO unified_games (
                    game_id, sport, game_date, season, status,
                    home_team_id, home_team_name,
                    away_team_id, away_team_name,
                    home_score, away_score
                ) VALUES (
                    :game_id, :sport, :game_date, :season, :status,
                    :home_team_id, :home_team_name,
                    :away_team_id, :away_team_name,
                    :home_score, :away_score
                )
                ON CONFLICT (game_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    home_score = EXCLUDED.home_score,
                    away_score = EXCLUDED.away_score,
                    loaded_at = CURRENT_TIMESTAMP
            """, game)
            loaded += 1
        except Exception as e:
            print(f"  ✗ Error loading game {game['game_id']}: {e}")

    return loaded


def backfill_nba_games(data_dir: Path = Path("data/nba")):
    """Backfill all NBA games from JSON files."""
    print("🏀 Backfilling NBA games to PostgreSQL...")
    print(f"📂 Scanning {data_dir}")

    if not data_dir.exists():
        print(f"✗ Directory {data_dir} does not exist!")
        return

    # Find all scoreboard JSON files
    scoreboard_files = sorted(data_dir.rglob("scoreboard_*.json"))

    if not scoreboard_files:
        print("✗ No scoreboard files found!")
        return

    print(f"📄 Found {len(scoreboard_files)} scoreboard files")

    total_games = 0
    total_loaded = 0

    for file_path in scoreboard_files:
        games = parse_scoreboard_json(file_path)
        if games:
            loaded = load_games_to_db(games)
            total_games += len(games)
            total_loaded += loaded

            date_str = file_path.stem.replace('scoreboard_', '')
            print(f"  ✓ {date_str}: {loaded}/{len(games)} games loaded")

    print(f"\n✅ Backfill complete!")
    print(f"   Total games found: {total_games}")
    print(f"   Total games loaded: {total_loaded}")

    # Verify data
    result = default_db.fetch_df("""
        SELECT
            MIN(game_date) as first_game,
            MAX(game_date) as last_game,
            COUNT(*) as total_games,
            COUNT(CASE WHEN status LIKE '%Final%' THEN 1 END) as final_games
        FROM unified_games
        WHERE sport = 'NBA'
    """)

    print(f"\n📊 NBA data in database:")
    print(result.to_string(index=False))


if __name__ == "__main__":
    backfill_nba_games()
