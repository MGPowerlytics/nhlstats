#!/usr/bin/env python3
"""
Download NBA game data from ESPN API.
"""

import requests
import json
import time
from pathlib import Path
from datetime import datetime, timedelta


class NBAGames:
    """Fetch NBA game data from ESPN."""

    BASE_URL = "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    def __init__(self, output_dir="data/nba", date_folder=None):
        self.output_dir = Path(output_dir)
        if date_folder:
            self.output_dir = self.output_dir / date_folder
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _make_request(self, url, params=None, max_retries=3):
        """Make HTTP request with exponential backoff for rate limits."""
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url, headers=self.HEADERS, params=params, timeout=30
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    print(f"Error fetching {url}: {e}")
                    raise
                wait_time = (2**attempt) * 2
                time.sleep(wait_time)

        raise Exception(f"Failed to fetch {url} after {max_retries} attempts")

    def get_games_for_date(self, date_str):
        """
        Get games for a specific date from ESPN.
        Date format: YYYY-MM-DD
        """
        # ESPN expects YYYYMMDD in the dates parameter
        date_formatted = date_str.replace("-", "")
        params = {
            "dates": date_formatted
        }
        return self._make_request(self.BASE_URL, params)

    def download_games_for_date(self, date_str):
        """Download all games for a specific date."""
        print(f"Downloading NBA games for {date_str} (ESPN)...")

        # Get scoreboard
        scoreboard = self.get_games_for_date(date_str)

        # Check if we got valid data
        if not scoreboard or 'events' not in scoreboard:
            print("  No events found or invalid response")
            return 0

        scoreboard_file = self.output_dir / f"scoreboard_{date_str}.json"
        with open(scoreboard_file, "w") as f:
            json.dump(scoreboard, f, indent=2)
        print(f"  Saved scoreboard to {scoreboard_file}")

        events = scoreboard.get('events', [])
        print(f"  Found {len(events)} games")

        # Note: We are currently only downloading the scoreboard as it contains
        # all necessary info (scores, status, teams) for the workflow.
        # Boxscores and PBP are skipped for now to streamline the migration to ESPN.

        return len(events)


if __name__ == "__main__":
    # Test
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    fetcher = NBAGames()
    fetcher.download_games_for_date(date)
