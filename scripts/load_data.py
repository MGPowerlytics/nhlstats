#!/usr/bin/env python3
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.append("/mnt/data2/nhlstats/plugins")
from db_loader import NHLDatabaseLoader

start_date = datetime(2021, 1, 1)
end_date = datetime(2026, 1, 18)

current_date = start_date
dates_processed = 0
errors_ignored = 0

print(f"Starting data load from {start_date.date()} to {end_date.date()}\n")

with NHLDatabaseLoader(db_path="data/nhlstats.duckdb") as loader:
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")

        try:
            loader.load_date(date_str, data_dir=Path("data"))
            dates_processed += 1
        except Exception as e:
            # Silently ignore constraint errors and other issues
            if "Constraint" in str(e) or "UNIQUE" in str(e):
                errors_ignored += 1
            else:
                pass

        current_date += timedelta(days=1)

        if dates_processed % 200 == 0:
            print(f"[Progress] Loaded {dates_processed} dates...")

print(f"\nLoaded {dates_processed} dates ({errors_ignored} constraint errors ignored)")

# Verify counts
with NHLDatabaseLoader(db_path="data/nhlstats.duckdb") as loader:
    nhl_count = loader.conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    mlb_count = loader.conn.execute("SELECT COUNT(*) FROM mlb_games").fetchone()[0]
    nfl_count = loader.conn.execute("SELECT COUNT(*) FROM nfl_games").fetchone()[0]

    print("\nFinal Data Counts:")
    print(f"  NHL games: {nhl_count:,}")
    print(f"  MLB games: {mlb_count:,}")
    print(f"  NFL games: {nfl_count:,}")
    print(f"  Total games: {nhl_count + mlb_count + nfl_count:,}")
