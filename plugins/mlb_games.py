#!/usr/bin/env python3
"""
Download MLB game data from MLB Stats API.
"""

import requests
import json
import time
from pathlib import Path


from plugins.base_games import BaseGamesFetcher


class MLBGames(BaseGamesFetcher):
    """Fetch MLB game data from statsapi.mlb.com."""

    SPORT = "mlb"
    BASE_URL = "https://statsapi.mlb.com/api/v1"

    def get_schedule_for_date(self, date_str):
        """
        Get schedule for a specific date.
        Date format: YYYY-MM-DD
        """
        url = f"{self.BASE_URL}/schedule"
        params = {
            "sportId": 1,  # MLB
            "date": date_str,
            "hydrate": "team,linescore,decisions,probablePitcher",
        }

        return self._make_request(url, params)

    def get_game_data(self, game_id):
        """Get detailed game data including play-by-play."""
        # Use v1.1 for live feed
        return self._fetch_game_resource(
            game_id, "game/{game_id}/feed/live", "https://statsapi.mlb.com/api/v1.1"
        )

    def get_game_boxscore(self, game_id):
        """Get boxscore for a specific game."""
        return self._fetch_game_resource(game_id, "game/{game_id}/boxscore")

    def download_games_for_date(self, date_str):
        """Download all games for a specific date."""
        print(f"Downloading MLB games for {date_str}...")

        # Get schedule
        schedule = self.get_schedule_for_date(date_str)
        schedule_file = self.output_dir / f"schedule_{date_str}.json"
        with open(schedule_file, "w") as f:
            json.dump(schedule, f, indent=2)
        print(f"  Saved schedule to {schedule_file}")

        # Get game IDs
        game_ids = []
        if "dates" in schedule and len(schedule["dates"]) > 0:
            for game in schedule["dates"][0].get("games", []):
                game_ids.append(game["gamePk"])

        print(f"  Found {len(game_ids)} games")

        # Download data for each game
        for i, game_id in enumerate(game_ids, 1):
            try:
                print(f"  [{i}/{len(game_ids)}] Downloading game {game_id}")

                # Get game feed
                game_data = self.get_game_data(game_id)
                game_file = self.output_dir / f"game_{game_id}.json"
                with open(game_file, "w") as f:
                    json.dump(game_data, f, indent=2)

                # Get boxscore
                boxscore = self.get_game_boxscore(game_id)
                boxscore_file = self.output_dir / f"boxscore_{game_id}.json"
                with open(boxscore_file, "w") as f:
                    json.dump(boxscore, f, indent=2)

                # Rate limiting
                if i < len(game_ids):
                    time.sleep(3)
            except Exception as e:
                print(f"  Error downloading game {game_id}: {e}")

        return len(game_ids)


if __name__ == "__main__":
    # Test
    fetcher = MLBGames()
    fetcher.download_games_for_date("2021-04-01")
