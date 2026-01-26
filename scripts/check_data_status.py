#!/usr/bin/env python3
"""Check current data status for all leagues."""

import duckdb
from pathlib import Path
from datetime import datetime

print("=== CURRENT DATA STATUS FOR ALL LEAGUES ===\n")
DB_PATH = "data/nhlstats.duckdb"


def check_table(conn, table_name, date_col, condition=None, season_start=None):
    print(f"\n📊 {table_name.upper().replace('_', ' ')} (DuckDB)")
    try:
        where_clause = f"WHERE {condition}" if condition else ""

        # Check if table exists
        exists = conn.execute(
            f"SELECT count(*) FROM information_schema.tables WHERE table_name = '{table_name}'"
        ).fetchone()[0]
        if not exists:
            print(f"   ⚠️ Table '{table_name}' does not exist.")
            return

        query = f"""
            SELECT
                COUNT(*) as total_games,
                MIN({date_col}) as oldest_game,
                MAX({date_col}) as newest_game
            FROM {table_name}
            {where_clause}
        """
        result = conn.execute(query).fetchone()

        print(f"   Total games: {result[0]:,}")
        print(f"   Date range: {result[1]} to {result[2]}")

        if season_start and result[2]:
            season_games = conn.execute(f"""
                SELECT COUNT(*) FROM {table_name}
                {where_clause}
                {"AND" if where_clause else "WHERE"} {date_col} >= '{season_start}'
            """).fetchone()[0]
            print(f"   Current season games (>= {season_start}): {season_games:,}")

    except Exception as e:
        print(f"   Error checking {table_name}: {e}")


try:
    conn = duckdb.connect(DB_PATH, read_only=True)

    # NHL
    check_table(
        conn, "games", "game_date", "game_state IN ('OFF', 'FINAL')", "2024-10-01"
    )

    # MLB
    check_table(conn, "mlb_games", "game_date", "status = 'Final'", "2025-03-27")

    # NFL
    check_table(
        conn, "nfl_games", "game_date", "status IN ('Final', 'Completed')", "2024-09-05"
    )

    # EPL
    check_table(conn, "epl_games", "game_date", None, "2024-08-16")

    # Tennis
    check_table(conn, "tennis_games", "game_date", None, "2025-01-01")

    # NCAAB
    check_table(conn, "ncaab_games", "game_date", None, "2024-11-04")

    conn.close()

except Exception as e:
    print(f"CRITICAL ERROR accessing database: {e}")

# NBA - from JSON files
print("\n📊 NBA (JSON files)")
nba_path = Path("data/nba")
if nba_path.exists():
    date_folders = sorted([d for d in nba_path.iterdir() if d.is_dir()])
    if date_folders:
        # Approximate count
        print(f"   Total game dates with data: {len(date_folders)}")
        try:
            print(f"   Date range: {date_folders[0].name} to {date_folders[-1].name}")
            current_season = [d for d in date_folders if d.name >= "2024-10-22"]
            print(f"   2024-25 season dates: {len(current_season)}")
        except IndexError:
            pass
else:
    print("   No NBA data directory found")

print(f"\n📅 Today's date: {datetime.now().strftime('%Y-%m-%d')}")
