"""
CBA Games Downloader - Chinese Basketball Association

Downloads game data from TheSportsDB (free API).
Includes backfill capability for historical seasons.
"""

import json
import pandas as pd
import requests
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


from plugins.base_games import BaseGamesFetcher


class CBAGames(BaseGamesFetcher):
    """Download and manage CBA game data from TheSportsDB."""

    # TheSportsDB API endpoints (free tier)
    BASE_URL = "https://www.thesportsdb.com/api/v1/json/3"

    # CBA League ID in TheSportsDB
    LEAGUE_ID = "4387"  # Chinese Basketball Association

    # Seasons to fetch (CBA season is Oct-Apr, labeled by end year)
    # e.g., 2024-25 season is "2025"
    DEFAULT_SEASONS = ["2022", "2023", "2024", "2025", "2026"]

    def __init__(self, data_dir: str = "data/cba", seasons: Optional[List[str]] = None):
        """
        Initialize CBA games downloader.

        Args:
            data_dir: Directory to store downloaded data
            seasons: Optional list of seasons to fetch
        """
        super().__init__(sport="cba", output_dir=data_dir)

        # Load team mapping for name normalization
        self.team_mapping = self._load_team_mapping()

        self.seasons = seasons or self.DEFAULT_SEASONS

    def _load_team_mapping(self) -> Dict:
        """Load team name mapping from JSON file."""
        mapping_file = Path("data/cba_team_mapping.json")
        if mapping_file.exists():
            with open(mapping_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"name_to_canonical": {}, "abbreviation_mapping": {}}

    def normalize_team_name(self, name: str) -> str:
        """
        Normalize a team name to its canonical form.

        Args:
            name: Raw team name from API

        Returns:
            Canonical team name
        """
        if not name:
            return name

        # Check direct mapping
        if name in self.team_mapping.get("name_to_canonical", {}):
            return self.team_mapping["name_to_canonical"][name]

        # Check abbreviation
        if name.upper() in self.team_mapping.get("abbreviation_mapping", {}):
            return self.team_mapping["abbreviation_mapping"][name.upper()]

        # Check teams dict for aliases
        for canonical, info in self.team_mapping.get("teams", {}).items():
            if name == canonical:
                return canonical
            if name in info.get("aliases", []):
                return canonical

        # Return original if no mapping found
        return name

    def download_games(self) -> bool:
        """
        Download historical and current CBA data.

        Returns:
            True if successful, False otherwise
        """
        success = True

        for season in self.seasons:
            print(f"📥 Downloading CBA games for {season} season...")

            try:
                # Get past events for the season
                events = self._fetch_season_events(season)

                if events:
                    # Save to file
                    season_file = self.data_dir / f"games_{season}.json"
                    with open(season_file, "w", encoding="utf-8") as f:
                        json.dump(events, f, indent=2, ensure_ascii=False)
                    print(f"✓ Saved {len(events)} CBA games for {season}")
                else:
                    print(f"⚠️ No games found for {season} season")

                # Rate limiting - TheSportsDB free tier
                time.sleep(1)

            except Exception as e:
                print(f"✗ Failed to download CBA games for {season}: {e}")
                success = False

        return success

    def _fetch_season_events(self, season: str) -> List[Dict]:
        """
        Fetch all events for a specific season.

        Args:
            season: Season year (e.g., "2025" for 2024-25 season)

        Returns:
            List of event dictionaries
        """
        url = f"{self.BASE_URL}/eventsseason.php"
        params = {"id": self.LEAGUE_ID, "s": season}

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        events = data.get("events", []) or []

        return events

    def download_games_for_date(self, date_str: str) -> bool:
        """
        Download games for a specific date.

        Args:
            date_str: Date string in YYYY-MM-DD format

        Returns:
            True if successful
        """
        print(f"📥 Downloading CBA games for {date_str}...")

        try:
            # TheSportsDB events by day endpoint
            url = f"{self.BASE_URL}/eventsday.php"
            params = {"d": date_str, "l": self.LEAGUE_ID}

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            events = data.get("events", []) or []

            if events:
                # Save to date-specific file
                date_file = self.data_dir / f"games_{date_str}.json"
                with open(date_file, "w", encoding="utf-8") as f:
                    json.dump(events, f, indent=2, ensure_ascii=False)
                print(f"✓ Downloaded {len(events)} CBA games for {date_str}")
            else:
                print(f"📭 No CBA games found for {date_str}")

            return True

        except Exception as e:
            print(f"✗ Failed to download CBA games for {date_str}: {e}")
            return False

    def load_games(self) -> pd.DataFrame:
        """
        Load and merge all CBA games into a DataFrame.

        Returns:
            DataFrame with columns: date, home_team, away_team, home_score,
            away_score, neutral, season, game_id
        """
        # Ensure we have downloaded data
        self.download_games()

        all_games = []

        # Load from season files
        for season_file in self.data_dir.glob("games_20*.json"):
            try:
                with open(season_file, "r", encoding="utf-8") as f:
                    events = json.load(f)

                for event in events:
                    game = self._parse_event(event)
                    if game:
                        all_games.append(game)

            except Exception as e:
                print(f"⚠️ Error loading {season_file}: {e}")

        if not all_games:
            print("⚠️ No CBA games loaded")
            return pd.DataFrame(
                columns=[
                    "date",
                    "home_team",
                    "away_team",
                    "home_score",
                    "away_score",
                    "neutral",
                    "season",
                    "game_id",
                ]
            )

        df = pd.DataFrame(all_games)

        # Remove duplicates by game_id
        df = df.drop_duplicates(subset=["game_id"], keep="last")

        # Sort by date
        df = df.sort_values("date").reset_index(drop=True)

        print(f"✓ Loaded {len(df)} CBA games")

        return df

    def _parse_event(self, event: Dict) -> Optional[Dict]:
        """
        Parse a TheSportsDB event into our standard format.

        Args:
            event: Raw event from API

        Returns:
            Parsed game dict or None if invalid
        """
        try:
            # Extract basic event info
            event_id, date_str = self._extract_basic_event_info(event)
            if not date_str:
                return None

            # Parse game date
            game_date = self._parse_game_date(date_str)
            if game_date is None:
                return None

            # Get and normalize team names
            home_team, away_team = self._normalize_team_names(event)
            if not home_team or not away_team:
                return None

            # Parse scores
            home_score, away_score = self._parse_scores(event)

            # Extract season
            season = self._extract_season(event)

            # Game status
            status = event.get("strStatus", "")

            return {
                "date": game_date,
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score,
                "neutral": False,  # CBA games are not at neutral sites
                "season": season,
                "game_id": f"CBA_{event_id}",
                "status": status,
            }

        except Exception as e:
            print(f"⚠️ Error parsing event: {e}")
            return None

    def _extract_basic_event_info(self, event: Dict) -> Tuple[str, str]:
        """Extract basic event information from raw API data.

        Args:
            event: Raw event from API

        Returns:
            Tuple of (event_id, date_str)
        """
        event_id = event.get("idEvent", "")
        date_str = event.get("dateEvent", "")
        return event_id, date_str

    def _parse_game_date(self, date_str: str) -> Optional[pd.Timestamp]:
        """Parse game date string to pandas Timestamp.

        Args:
            date_str: Date string from API

        Returns:
            Parsed timestamp or None if invalid
        """
        try:
            return pd.to_datetime(date_str)
        except Exception:
            return None

    def _normalize_team_names(self, event: Dict) -> Tuple[Optional[str], Optional[str]]:
        """Extract and normalize home and away team names.

        Args:
            event: Raw event from API

        Returns:
            Tuple of (home_team, away_team) or (None, None) if missing
        """
        home_team_raw = event.get("strHomeTeam", "")
        away_team_raw = event.get("strAwayTeam", "")

        if not home_team_raw or not away_team_raw:
            return None, None

        home_team = self.normalize_team_name(home_team_raw)
        away_team = self.normalize_team_name(away_team_raw)

        return home_team, away_team

    def _parse_scores(self, event: Dict) -> Tuple[Optional[int], Optional[int]]:
        """Parse home and away scores from event data.

        Args:
            event: Raw event from API

        Returns:
            Tuple of (home_score, away_score)
        """
        home_score = event.get("intHomeScore")
        away_score = event.get("intAwayScore")

        # Convert scores to int if present
        def _safe_int(score) -> Optional[int]:
            if score is None:
                return None
            try:
                return int(score)
            except (ValueError, TypeError):
                return None

        return _safe_int(home_score), _safe_int(away_score)

    def _extract_season(self, event: Dict) -> str:
        """Extract season from event data.

        Args:
            event: Raw event from API

        Returns:
            Season string (e.g., "2025")
        """
        season = event.get("strSeason", "")
        if "-" in season:
            # "2024-2025" -> "2025"
            season = season.split("-")[-1]
        return season

    def get_games_for_date(self, date_str: str) -> pd.DataFrame:
        """
        Get games for a specific date.

        Args:
            date_str: Date string in YYYY-MM-DD format

        Returns:
            DataFrame with games for that date
        """
        # Try to download fresh data for this date
        self.download_games_for_date(date_str)

        # Load all games and filter
        df = self.load_games()

        if df.empty:
            return df

        # Filter to target date
        target_date = pd.to_datetime(date_str)
        df["date"] = pd.to_datetime(df["date"])
        mask = df["date"].dt.date == target_date.date()

        return df[mask].copy()

    def get_completed_games(self) -> pd.DataFrame:
        """
        Get only completed games with final scores.

        Returns:
            DataFrame with completed games only
        """
        df = self.load_games()

        if df.empty:
            return df

        # Filter for games with scores
        mask = df["home_score"].notna() & df["away_score"].notna()
        return df[mask].copy()

    def backfill_history(self, start_season: str = "2020") -> bool:
        """
        Backfill historical CBA data.

        Args:
            start_season: Earliest season to backfill

        Returns:
            True if successful
        """
        print(f"📥 Backfilling CBA history from {start_season}...")

        # Extend seasons list for backfill
        current_year = datetime.now().year
        seasons = [str(year) for year in range(int(start_season), current_year + 1)]

        success = True
        total_games = 0

        for season in seasons:
            try:
                events = self._fetch_season_events(season)

                if events:
                    season_file = self.data_dir / f"games_{season}.json"
                    with open(season_file, "w", encoding="utf-8") as f:
                        json.dump(events, f, indent=2, ensure_ascii=False)
                    total_games += len(events)
                    print(f"✓ Backfilled {len(events)} games for {season}")

                time.sleep(1)  # Rate limiting

            except Exception as e:
                print(f"✗ Failed to backfill {season}: {e}")
                success = False

        print(f"✓ Total backfilled: {total_games} CBA games")
        return success


if __name__ == "__main__":
    cba = CBAGames()

    # Download current data
    cba.download_games()

    # Load and display
    df = cba.load_games()
    print(f"\nLoaded {len(df)} CBA games")

    if not df.empty:
        print("\nRecent games:")
        print(df.tail(10))

        print("\nCompleted games:")
        completed = cba.get_completed_games()
        print(f"{len(completed)} completed games with scores")
