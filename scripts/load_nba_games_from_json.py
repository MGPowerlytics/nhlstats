#!/usr/bin/env python3
"""Load NBA games from JSON scoreboard files into DuckDB."""

import json
import duckdb
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


def parse_scoreboard_json(file_path: Path) -> List[Dict[str, Any]]:
    """Parse NBA scoreboard JSON file and extract game data."""
    with open(file_path) as f:
        data = json.load(f)

    games = []

    # NBA API format: resultSets array with different data
    if "resultSets" not in data:
        return games

    # Find the GameHeader and LineScore result sets
    game_header = None
    line_score = None

    for rs in data["resultSets"]:
        if rs.get("name") == "GameHeader":
            game_header = rs
        elif rs.get("name") == "LineScore":
            line_score = rs

    if not game_header or not line_score:
        return games

    # Parse game headers
    game_header_cols = {col: idx for idx, col in enumerate(game_header["headers"])}

    for row in game_header["rowSet"]:
        game_id = str(row[game_header_cols["GAME_ID"]])
        game_date_str = str(row[game_header_cols["GAME_DATE_EST"]])
        game_status = str(row[game_header_cols["GAME_STATUS_TEXT"]])

        # Parse date (format: 2024-10-22T00:00:00)
        try:
            game_date = datetime.strptime(game_date_str[:10], "%Y-%m-%d").date()
        except Exception:
            continue

        # Find team scores from LineScore
        line_score_cols = {col: idx for idx, col in enumerate(line_score["headers"])}
        team_scores = []

        for ls_row in line_score["rowSet"]:
            if str(ls_row[line_score_cols["GAME_ID"]]) == game_id:
                team_scores.append(
                    {
                        "team_id": ls_row[line_score_cols["TEAM_ID"]],
                        "team_abbr": ls_row[line_score_cols["TEAM_ABBREVIATION"]],
                        "team_name": ls_row[line_score_cols["TEAM_CITY_NAME"]]
                        + " "
                        + ls_row[line_score_cols["TEAM_NAME"]],
                        "pts": ls_row[line_score_cols["PTS"]],
                    }
                )

        if len(team_scores) == 2:
            # First team is usually away, second is home
            away_team = team_scores[0]
            home_team = team_scores[1]

            games.append(
                {
                    "game_id": game_id,
                    "game_date": game_date,
                    "season": f"{game_date.year}-{game_date.year + 1}"
                    if game_date.month >= 10
                    else f"{game_date.year - 1}-{game_date.year}",
                    "game_status": game_status,
                    "home_team_id": home_team["team_id"],
                    "away_team_id": away_team["team_id"],
                    "home_team_name": home_team["team_name"],
                    "away_team_name": away_team["team_name"],
                    "home_score": home_team["pts"],
                    "away_score": away_team["pts"],
                }
            )

    return games


def load_nba_games_to_duckdb(
    nba_data_dir: str = "data/nba",
    db_path: str = "data/nhlstats.duckdb",
    start_date: str = None,
    end_date: str = None,
):
    """
    Load NBA games from JSON files into DuckDB.

    Args:
        nba_data_dir: Directory containing date folders with scoreboard JSON files
        db_path: Path to DuckDB database
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)
    """
    nba_dir = Path(nba_data_dir)

    if not nba_dir.exists():
        print(f"❌ NBA data directory not found: {nba_dir}")
        return

    all_games = []

    # Find all date directories
    import re

    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    date_dirs = [
        d for d in nba_dir.iterdir() if d.is_dir() and date_pattern.match(d.name)
    ]
    date_dirs.sort()

    # Filter by date range if specified
    if start_date:
        date_dirs = [d for d in date_dirs if d.name >= start_date]
    if end_date:
        date_dirs = [d for d in date_dirs if d.name <= end_date]

    print(f"📥 Loading NBA games from {len(date_dirs)} dates...")

    for date_dir in date_dirs:
        # Find scoreboard JSON file
        scoreboard_files = list(date_dir.glob("scoreboard_*.json"))

        if not scoreboard_files:
            continue

        for scoreboard_file in scoreboard_files:
            try:
                games = parse_scoreboard_json(scoreboard_file)
                all_games.extend(games)
            except Exception as e:
                print(f"⚠️  Error parsing {scoreboard_file}: {e}")
                continue

    if not all_games:
        print("❌ No games found")
        return

    print(f"✅ Parsed {len(all_games)} games")

    # Load into DuckDB
    con = duckdb.connect(db_path)

    # Drop and recreate table
    con.execute("DROP TABLE IF EXISTS nba_games")
    con.execute("""
        CREATE TABLE nba_games (
            game_id VARCHAR PRIMARY KEY,
            game_date DATE,
            season VARCHAR,
            game_status VARCHAR,
            home_team_id INTEGER,
            away_team_id INTEGER,
            home_team_name VARCHAR,
            away_team_name VARCHAR,
            home_score INTEGER,
            away_score INTEGER
        )
    """)

    # Insert games
    con.executemany(
        """
        INSERT INTO nba_games VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        [
            (
                g["game_id"],
                g["game_date"],
                g["season"],
                g["game_status"],
                g["home_team_id"],
                g["away_team_id"],
                g["home_team_name"],
                g["away_team_name"],
                g["home_score"],
                g["away_score"],
            )
            for g in all_games
        ],
    )

    con.close()

    print(f"✅ Loaded {len(all_games)} NBA games into {db_path}")


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    start_date = args[0] if len(args) > 0 else "2024-10-01"
    end_date = args[1] if len(args) > 1 else "2025-01-20"

    load_nba_games_to_duckdb(start_date=start_date, end_date=end_date)
