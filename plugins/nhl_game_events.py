#!/usr/bin/env python3
"""
Download NHL game event data including shots, goals, hits, and other events with coordinates.
"""

import requests
import json
import time
from pathlib import Path


class NHLGameEvents:
    """Fetch detailed play-by-play event data for NHL games."""

    BASE_URL = "https://api-web.nhle.com/v1"
    LEGACY_URL = "https://statsapi.web.nhl.com/api/v1"

    def __init__(self, output_dir="data/games", date_folder=None):
        self.output_dir = Path(output_dir)
        if date_folder:
            self.output_dir = self.output_dir / date_folder
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _make_request(self, url, max_retries=5):
        """Make HTTP request with exponential backoff for rate limits."""
        for attempt in range(max_retries):
            try:
                response = requests.get(url)

                # Handle rate limiting
                if response.status_code == 429:
                    wait_time = (2**attempt) * 2  # 2, 4, 8, 16, 32 seconds
                    print(
                        f"Rate limited. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}"
                    )
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = (2**attempt) * 2
                print(f"Request failed: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)

        raise Exception(f"Failed to fetch {url} after {max_retries} attempts")

    def get_schedule_by_date(self, date_str):
        """
        Get schedule for a specific date.
        Date format: YYYY-MM-DD
        """
        url = f"{self.BASE_URL}/schedule/{date_str}"
        return self._make_request(url)

    def get_season_schedule(self, season="20232024"):
        """
        Get schedule for a season.
        Season format: YYYYYYYY (e.g., 20232024 for 2023-24 season)
        """
        url = f"{self.BASE_URL}/schedule/{season}"
        return self._make_request(url)

    def get_game_data(self, game_id):
        """
        Get detailed play-by-play data for a specific game.
        Game ID format: SSSSTTGGGGG (e.g., 2023020001)
        - SSSS: Season (2023)
        - TT: Game type (02=regular season, 03=playoffs)
        - GGGGG: Game number (00001)
        """
        url = f"{self.BASE_URL}/gamecenter/{game_id}/play-by-play"
        return self._make_request(url)

    def get_game_boxscore(self, game_id):
        """Get boxscore data including player stats."""
        url = f"{self.BASE_URL}/gamecenter/{game_id}/boxscore"
        return self._make_request(url)

    def download_game(self, game_id, include_boxscore=True):
        """Download and save all data for a game."""
        print(f"Downloading game {game_id}...")

        # Get play-by-play data
        play_by_play = self.get_game_data(game_id)
        pbp_file = self.output_dir / f"{game_id}_playbyplay.json"
        with open(pbp_file, "w") as f:
            json.dump(play_by_play, f, indent=2)
        print(f"  Saved play-by-play to {pbp_file}")

        # Get boxscore
        if include_boxscore:
            boxscore = self.get_game_boxscore(game_id)
            box_file = self.output_dir / f"{game_id}_boxscore.json"
            with open(box_file, "w") as f:
                json.dump(boxscore, f, indent=2)
            print(f"  Saved boxscore to {box_file}")

        return play_by_play, boxscore if include_boxscore else None

    def download_season(self, season="20232024", game_type="02"):
        """
        Download all games for a season.
        game_type: 02=regular season, 03=playoffs
        """
        print(f"Fetching schedule for {season}...")
        schedule = self.get_season_schedule(season)

        game_ids = []
        for week in schedule.get("gameWeek", []):
            for game in week.get("games", []):
                gid = game.get("id")
                # Filter by game type if specified
                if game_type and str(gid)[4:6] == game_type:
                    game_ids.append(gid)

        print(f"Found {len(game_ids)} games")

        for i, game_id in enumerate(game_ids, 1):
            try:
                print(f"[{i}/{len(game_ids)}] ", end="")
                self.download_game(game_id)
            except Exception as e:
                print(f"  Error downloading game {game_id}: {e}")

        print(f"\nCompleted! Data saved to {self.output_dir}")

    def download_games_for_date(self, date_str):
        """
        Download all games for a specific date.
        Date format: YYYY-MM-DD
        """
        print(f"Fetching schedule for {date_str}...")
        schedule = self.get_schedule_by_date(date_str)

        game_ids = []
        for week in schedule.get("gameWeek", []):
            for game in week.get("games", []):
                gid = game.get("id")
                game_ids.append(gid)

        if not game_ids:
            print(f"No games found for {date_str}")
            return

        print(f"Found {len(game_ids)} games")

        for i, game_id in enumerate(game_ids, 1):
            try:
                print(f"[{i}/{len(game_ids)}] ", end="")
                self.download_game(game_id)
            except Exception as e:
                print(f"  Error downloading game {game_id}: {e}")

        print(f"\nCompleted! Data saved to {self.output_dir}")

    def extract_shot_data(self, play_by_play):
        """Extract shot attempts with coordinates from play-by-play data."""
        shots = []

        plays = play_by_play.get("plays", [])
        for play in plays:
            event_type = play.get("typeDescKey")

            # Shot events include: shot-on-goal, missed-shot, blocked-shot, goal
            if event_type in ["shot-on-goal", "missed-shot", "blocked-shot", "goal"]:
                details = play.get("details", {})
                shot_data = {
                    "event_id": play.get("eventId"),
                    "period": play.get("periodDescriptor", {}).get("number"),
                    "time_in_period": play.get("timeInPeriod"),
                    "time_remaining": play.get("timeRemaining"),
                    "event_type": event_type,
                    "x_coord": details.get("xCoord"),
                    "y_coord": details.get("yCoord"),
                    "zone_code": details.get("zoneCode"),
                    "shot_type": details.get("shotType"),
                    "shooter": details.get("shootingPlayerId"),
                    "goalie": details.get("goalieInNetId"),
                    "team": play.get("teamId"),
                }
                shots.append(shot_data)

        return shots


def main():
    """Example usage."""
    fetcher = NHLGameEvents()

    # Example 1: Download a specific game
    # Game 1 of 2023-24 regular season
    game_id = 2023020001
    fetcher.download_game(game_id)

    # Example 2: Download entire season (commented out - this takes a while!)
    # fetcher.download_season("20232024", game_type="02")

    # Example 3: Extract shot data from downloaded game
    with open(f"data/games/{game_id}_playbyplay.json", "r") as f:
        play_by_play = json.load(f)

    shots = fetcher.extract_shot_data(play_by_play)
    print(f"\nExtracted {len(shots)} shot attempts from game {game_id}")
    print("\nFirst 3 shots:")
    for shot in shots[:3]:
        print(json.dumps(shot, indent=2))


if __name__ == "__main__":
    main()
