#!/usr/bin/env python3
"""
Download NFL game data using nfl-data-py library.
"""

from pathlib import Path
from datetime import datetime
import pandas as pd
try:
    import nfl_data_py as nfl

    NFL_DATA_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in import-only environments
    nfl = None
    NFL_DATA_AVAILABLE = False


from plugins.base_games import BaseGamesFetcher


class NFLGames(BaseGamesFetcher):
    """Fetch NFL game data using nfl-data-py."""

    SPORT = "nfl"

    @staticmethod
    def _require_nfl_data_py():
        """Raise a clear error when the optional nfl_data_py dependency is missing."""
        if not NFL_DATA_AVAILABLE or nfl is None:
            raise ImportError(
                "nfl_data_py is required to download NFL games. "
                "Install it to enable NFL schedule ingestion."
            )
        return nfl

    def _get_season_year(self, date_obj):
        """Determine NFL season year (season starts in September)."""
        if date_obj.month >= 9:
            return date_obj.year
        return date_obj.year - 1

    def _download_and_save_schedule(self, season_year, date_obj, date_str):
        """Download and save schedule for a specific date."""
        nfl_api = self._require_nfl_data_py()
        # Get schedule for the season
        schedule = nfl_api.import_schedules([season_year])

        # Filter games for the specific date
        schedule["gameday"] = pd.to_datetime(schedule["gameday"])
        date_games = schedule[schedule["gameday"].dt.date == date_obj.date()]

        if len(date_games) == 0:
            print(f"  No NFL games found for {date_str}")
            return None

        print(f"  Found {len(date_games)} games for {date_str}")

        # Save schedule for this date
        schedule_file = self.output_dir / f"schedule_{date_str}.json"
        date_games.to_json(schedule_file, orient="records", indent=2)
        print(f"  Saved schedule to {schedule_file}")
        return date_games

    def _download_and_save_pbp(self, season_year, game_ids, date_str):
        """Download and save play-by-play data for these games."""
        print("  Downloading play-by-play data...")
        try:
            nfl_api = self._require_nfl_data_py()
            pbp = nfl_api.import_pbp_data([season_year], downcast=False)

            # Filter to just these games
            date_pbp = pbp[pbp["game_id"].isin(game_ids)]

            if len(date_pbp) > 0:
                pbp_file = self.output_dir / f"pbp_{date_str}.json"
                date_pbp.to_json(pbp_file, orient="records", indent=2)
                print(f"  Saved play-by-play to {pbp_file}")
        except Exception as pbp_error:
            # Play-by-play data may not be available yet for recent/future games
            error_msg = str(pbp_error)
            if (
                "404" in error_msg
                or "Not Found" in error_msg
                or "name 'Error' is not defined" in error_msg
            ):
                print(f"  Play-by-play data not available for {season_year} season")
            else:
                raise

    def _download_and_save_weekly_stats(self, season_year, week, date_str):
        """Download and save weekly stats for the given week."""
        try:
            nfl_api = self._require_nfl_data_py()
            weekly = nfl_api.import_weekly_data([season_year])
            date_weekly = weekly[
                (weekly["season"] == season_year) & (weekly["week"] == week)
            ]

            if len(date_weekly) > 0:
                weekly_file = self.output_dir / f"weekly_{date_str}.json"
                date_weekly.to_json(weekly_file, orient="records", indent=2)
                print(f"  Saved weekly stats to {weekly_file}")
        except Exception as weekly_error:
            print(
                f"  Weekly stats not available for {season_year} season: {weekly_error}"
            )

    def download_games_for_date(self, date_str):
        """
        Download games for a specific date.
        Date format: YYYY-MM-DD
        """
        print(f"Downloading NFL games for {date_str}...")

        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        season_year = self._get_season_year(date_obj)

        try:
            self._require_nfl_data_py()
            date_games = self._download_and_save_schedule(
                season_year, date_obj, date_str
            )
            if date_games is None or len(date_games) == 0:
                return 0

            game_ids = date_games["game_id"].tolist()
            self._download_and_save_pbp(season_year, game_ids, date_str)

            # Weekly data is player-level, not game-level, so filter by season/week
            week = date_games.iloc[0]["week"]
            self._download_and_save_weekly_stats(season_year, week, date_str)

            return len(date_games)

        except Exception as e:
            print(f"Error downloading NFL data for {date_str}: {e}")
            raise


if __name__ == "__main__":
    # Test with a date that has games
    fetcher = NFLGames()
    fetcher.download_games_for_date("2021-09-09")
