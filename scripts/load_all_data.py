#!/usr/bin/env python3
"""Quick load of all available data into DuckDB"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.append("/mnt/data2/nhlstats/plugins")
from db_loader import NHLDatabaseLoader

start_date = datetime(2021, 1, 1)
end_date = datetime(2026, 1, 18)

current_date = start_date
dates_processed = 0

print(f"Loading all available data from {start_date.date()} to {end_date.date()}\n")

try:
    with NHLDatabaseLoader(db_path="data/nhlstats.duckdb") as loader:
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")

            try:
                loader.load_date(date_str, data_dir=Path("data"))
            except Exception:
                # Silently skip errors
                pass

            dates_processed += 1

            if dates_processed % 300 == 0:
                print(f"[Progress] Processed {dates_processed} dates...")

            current_date += timedelta(days=1)

        print(f"\nCompleted loading {dates_processed} dates")

        # Final verification
        nhl_count = loader.conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        mlb_count = loader.conn.execute("SELECT COUNT(*) FROM mlb_games").fetchone()[0]
        nfl_count = loader.conn.execute("SELECT COUNT(*) FROM nfl_games").fetchone()[0]

        print("\n" + "=" * 60)
        print("FINAL DATA COUNTS:")
        print(f"  NHL games: {nhl_count:,}")
        print(f"  MLB games: {mlb_count:,}")
        print(f"  NFL games: {nfl_count:,}")
        print(f"  TOTAL: {nhl_count + mlb_count + nfl_count:,}")
        print("=" * 60)

        # Show date ranges
        if nhl_count > 0:
            nhl_min = loader.conn.execute(
                "SELECT MIN(game_date) FROM games"
            ).fetchone()[0]
            nhl_max = loader.conn.execute(
                "SELECT MAX(game_date) FROM games"
            ).fetchone()[0]
            print(f"\nNHL: {nhl_min} to {nhl_max}")

        if mlb_count > 0:
            mlb_min = loader.conn.execute(
                "SELECT MIN(game_date) FROM mlb_games"
            ).fetchone()[0]
            mlb_max = loader.conn.execute(
                "SELECT MAX(game_date) FROM mlb_games"
            ).fetchone()[0]
            print(f"MLB: {mlb_min} to {mlb_max}")

        if nfl_count > 0:
            nfl_min = loader.conn.execute(
                "SELECT MIN(game_date) FROM nfl_games"
            ).fetchone()[0]
            nfl_max = loader.conn.execute(
                "SELECT MAX(game_date) FROM nfl_games"
            ).fetchone()[0]
            print(f"NFL: {nfl_min} to {nfl_max}")

except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
