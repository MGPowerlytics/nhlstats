#!/usr/bin/env python3
"""
Backfill MLB data from 2021-01-01 to 2026-01-18.
Organizes data by date in subdirectories.
Skips off-season months (Nov, Dec, Jan, Feb) for 2021-2025 to save API calls.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add plugins to path
sys.path.append('/mnt/data2/nhlstats/plugins')
from mlb_games import MLBGames


def should_skip_date(date_obj):
    """Skip off-season months (Nov, Dec, Jan, Feb) for years before 2026"""
    month = date_obj.month
    year = date_obj.year

    # For 2026, only include up to Jan 18
    if year == 2026:
        return date_obj > datetime(2026, 1, 18).date()

    # For earlier years, skip off-season
    if year < 2026:
        # Season is roughly Apr-Oct, skip Nov, Dec, Jan, Feb
        if month in [11, 12, 1, 2]:
            return True

    return False


def date_already_downloaded(date_str, data_dir="data/mlb"):
    """Check if a date already has a schedule file downloaded"""
    date_dir = Path(data_dir) / date_str
    schedule_file = date_dir / f"schedule_{date_str}.json"
    # Consider a date as downloaded if the schedule file exists and is not empty
    return schedule_file.exists() and schedule_file.stat().st_size > 100


def backfill_mlb_data():
    """Download MLB games from 2021-01-01 to 2026-01-18"""
    start_date = datetime(2021, 1, 1)
    end_date = datetime(2026, 1, 18)

    current_date = start_date
    total_games = 0
    dates_processed = 0
    dates_skipped = 0
    dates_already_downloaded = 0

    print(f"Starting MLB backfill from {start_date.date()} to {end_date.date()}")
    print("Skipping off-season months (Nov-Feb) for 2021-2025 to optimize API usage")
    print("Skipping dates that already have schedule files\n")

    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')

        if should_skip_date(current_date.date()):
            dates_skipped += 1
            current_date += timedelta(days=1)
            continue

        # Check if already downloaded
        if date_already_downloaded(date_str):
            dates_already_downloaded += 1
            current_date += timedelta(days=1)
            continue

        try:
            # Create MLBGames instance with date_folder to organize by date
            fetcher = MLBGames(date_folder=date_str)
            games_count = fetcher.download_games_for_date(date_str)
            total_games += games_count
            dates_processed += 1

            print(f"  Downloaded {games_count} games")

        except Exception as e:
            print(f"Error downloading games for {date_str}: {e}")

        current_date += timedelta(days=1)

        # Progress indicator every 50 dates
        if dates_processed % 50 == 0:
            print(f"[Progress] Processed {dates_processed} new dates, downloaded {total_games} games total\n")

    print("\n" + "="*60)
    print(f"Backfill Complete!")
    print(f"  Dates processed (new): {dates_processed}")
    print(f"  Dates already downloaded: {dates_already_downloaded}")
    print(f"  Dates skipped (off-season): {dates_skipped}")
    print(f"  Total games downloaded (new): {total_games}")
    print("="*60)


if __name__ == "__main__":
    backfill_mlb_data()
