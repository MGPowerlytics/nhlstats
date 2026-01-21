#!/usr/bin/env python3
"""
Load historical data (NHL, MLB, NFL) into DuckDB from 2021-01-01 to 2026-01-18.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add plugins to path
sys.path.append('/mnt/data2/nhlstats/plugins')
from db_loader import NHLDatabaseLoader


def load_historical_data():
    """Load all sports data from 2021-01-01 to 2026-01-18 into DuckDB"""
    start_date = datetime(2021, 1, 1)
    end_date = datetime(2026, 1, 18)

    current_date = start_date
    dates_processed = 0

    print(f"Starting data load from {start_date.date()} to {end_date.date()}\n")

    with NHLDatabaseLoader(db_path="data/nhlstats.duckdb") as loader:
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')

            try:
                loader.load_date(date_str, data_dir=Path("data"))
                dates_processed += 1

            except Exception as e:
                print(f"Error loading data for {date_str}: {e}\n")

            current_date += timedelta(days=1)

            # Progress indicator every 100 dates
            if dates_processed % 100 == 0:
                print(f"[Progress] Loaded data for {dates_processed} dates\n")

    print(f"\n" + "="*60)
    print(f"Data Load Complete!")
    print(f"  Total dates processed: {dates_processed}")
    print("="*60)


def verify_data_counts():
    """Verify the counts of games in DuckDB"""
    print("\nVerifying data counts in DuckDB...\n")

    with NHLDatabaseLoader(db_path="data/nhlstats.duckdb") as loader:
        # Get counts
        nhl_count = loader.conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        mlb_count = loader.conn.execute("SELECT COUNT(*) FROM mlb_games").fetchone()[0]
        nfl_count = loader.conn.execute("SELECT COUNT(*) FROM nfl_games").fetchone()[0]

        print("Data Counts:")
        print(f"  NHL games: {nhl_count:,}")
        print(f"  MLB games: {mlb_count:,}")
        print(f"  NFL games: {nfl_count:,}")
        print(f"  Total games: {nhl_count + mlb_count + nfl_count:,}")

        # Show date ranges
        print("\nDate Ranges:")

        if nhl_count > 0:
            nhl_min_date = loader.conn.execute("SELECT MIN(game_date) FROM games").fetchone()[0]
            nhl_max_date = loader.conn.execute("SELECT MAX(game_date) FROM games").fetchone()[0]
            print(f"  NHL: {nhl_min_date} to {nhl_max_date}")

        if mlb_count > 0:
            mlb_min_date = loader.conn.execute("SELECT MIN(game_date) FROM mlb_games").fetchone()[0]
            mlb_max_date = loader.conn.execute("SELECT MAX(game_date) FROM mlb_games").fetchone()[0]
            print(f"  MLB: {mlb_min_date} to {mlb_max_date}")

        if nfl_count > 0:
            nfl_min_date = loader.conn.execute("SELECT MIN(game_date) FROM nfl_games").fetchone()[0]
            nfl_max_date = loader.conn.execute("SELECT MAX(game_date) FROM nfl_games").fetchone()[0]
            print(f"  NFL: {nfl_min_date} to {nfl_max_date}")


if __name__ == "__main__":
    load_historical_data()
    verify_data_counts()
