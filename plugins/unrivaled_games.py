"""
Download and manage Unrivaled Basketball game data.

Unrivaled is a 3x3 women's professional basketball league that launched in 2025.
All games are played at the same venue (neutral site).

This module provides functionality to download game data from available sources
and manage local storage.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

# Unrivaled teams for the 2025-2026 inaugural season
# Team names follow the "Name BC" (Basketball Club) convention
UNRIVALED_TEAMS = {
    "Rose BC",
    "Lunar Owls BC",
    "Phantom BC",
    "Mist BC",
    "Vinyl BC",
    "Laces BC",
}

# Team abbreviations for matching with external data sources
TEAM_ABBREVIATIONS = {
    "ROSE": "Rose BC",
    "LUNAR": "Lunar Owls BC",
    "OWLS": "Lunar Owls BC",
    "PHANTOM": "Phantom BC",
    "MIST": "Mist BC",
    "VINYL": "Vinyl BC",
    "LACES": "Laces BC",
}


class UnrivaledGames:
    """Download and manage Unrivaled Basketball game data."""

    def __init__(self, data_dir: str = "data/unrivaled"):
        """
        Initialize UnrivaledGames manager.

        Args:
            data_dir: Directory for storing game data files
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Inaugural season is 2025-2026
        self.seasons = [2025, 2026]
        self.games_file = self.data_dir / "games.csv"
        self.schedule_file = self.data_dir / "schedule.csv"

    def download_games(self) -> bool:
        """
        Download Unrivaled game data from available sources.

        For a new league like Unrivaled, data may come from:
        - Official Unrivaled API/website
        - ESPN API
        - Manual entry from official sources

        Returns:
            bool: True if download was successful, False otherwise
        """
        print("📥 Checking for Unrivaled game data...")

        # Since Unrivaled is a new league, we may need to:
        # 1. Check if games file exists with manual data
        # 2. Try to fetch from ESPN or other sports APIs
        # 3. Parse from official Unrivaled website

        if self.games_file.exists():
            print(f"✓ Found existing Unrivaled games file at {self.games_file}")
            return True

        # Try ESPN API for Unrivaled (if available)
        try:
            games = self._fetch_from_espn()
            if games:
                self._save_games(games)
                return True
        except Exception as e:
            print(f"⚠️ Could not fetch from ESPN: {e}")

        # Create empty games file if no data source available
        print("⚠️ No Unrivaled game data source available yet")
        print("   Games can be manually added to: {self.games_file}")
        self._create_empty_games_file()
        return False

    def _fetch_from_espn(self) -> Optional[List[Dict]]:
        """
        Attempt to fetch Unrivaled games from ESPN API.

        Returns:
            List of game dictionaries or None if not available
        """
        # ESPN may not have Unrivaled data yet since it's a new league
        # This is a placeholder for future ESPN integration
        return None

    def _create_empty_games_file(self) -> None:
        """Create an empty games file with the correct schema."""
        df = pd.DataFrame(columns=[
            "date", "home_team", "away_team", "home_score", "away_score",
            "neutral", "season", "game_id"
        ])
        df.to_csv(self.games_file, index=False)
        print(f"✓ Created empty games file at {self.games_file}")

    def _save_games(self, games: List[Dict]) -> None:
        """
        Save games to CSV file.

        Args:
            games: List of game dictionaries
        """
        df = pd.DataFrame(games)
        df.to_csv(self.games_file, index=False)
        print(f"✓ Saved {len(games)} Unrivaled games to {self.games_file}")

    def add_game(
        self,
        date: str,
        team1: str,
        team2: str,
        score1: int,
        score2: int,
        game_id: Optional[str] = None,
    ) -> None:
        """
        Manually add a game result.

        Since Unrivaled games are all at neutral site, team1/team2 are
        arbitrarily designated as home/away for consistency.

        Args:
            date: Game date in YYYY-MM-DD format
            team1: First team name
            team2: Second team name
            score1: Team 1's score
            score2: Team 2's score
            game_id: Optional unique game identifier
        """
        # Normalize team names
        team1 = self._normalize_team_name(team1)
        team2 = self._normalize_team_name(team2)

        if game_id is None:
            game_id = f"UNR_{date.replace('-', '')}_{team1[:3]}_{team2[:3]}"

        # Determine season (season is year of start, e.g., 2025 for 2025-2026)
        game_date = pd.to_datetime(date)
        season = game_date.year if game_date.month >= 9 else game_date.year - 1

        new_game = {
            "date": date,
            "home_team": team1,
            "away_team": team2,
            "home_score": score1,
            "away_score": score2,
            "neutral": True,  # All Unrivaled games are neutral site
            "season": season,
            "game_id": game_id,
        }

        # Load existing games
        if self.games_file.exists():
            df = pd.read_csv(self.games_file)
            # Check for duplicate
            if game_id in df["game_id"].values:
                print(f"⚠️ Game {game_id} already exists, skipping")
                return
        else:
            df = pd.DataFrame()

        # Append new game
        df = pd.concat([df, pd.DataFrame([new_game])], ignore_index=True)
        df.to_csv(self.games_file, index=False)
        print(f"✓ Added game: {team1} {score1} - {score2} {team2} ({date})")

    def _normalize_team_name(self, name: str) -> str:
        """
        Normalize team name to standard format.

        Args:
            name: Raw team name or abbreviation

        Returns:
            Normalized team name
        """
        # Check abbreviations first
        name_upper = name.upper().strip()
        if name_upper in TEAM_ABBREVIATIONS:
            return TEAM_ABBREVIATIONS[name_upper]

        # Check if already a valid team name
        for team in UNRIVALED_TEAMS:
            if name.lower() == team.lower():
                return team

        # Return as-is if no match found
        return name.strip()

    def load_games(self) -> pd.DataFrame:
        """
        Load all Unrivaled games from local storage.

        Returns:
            DataFrame with columns: date, home_team, away_team, home_score,
            away_score, neutral, season
        """
        self.download_games()

        if not self.games_file.exists():
            print("⚠️ No Unrivaled games file found")
            return pd.DataFrame(columns=[
                "date", "home_team", "away_team", "home_score", "away_score",
                "neutral", "season"
            ])

        try:
            df = pd.read_csv(self.games_file)
            if len(df) == 0:
                print("⚠️ Unrivaled games file is empty")
                return df

            # Ensure date column is datetime
            df["date"] = pd.to_datetime(df["date"])

            # Ensure neutral column exists and is True
            if "neutral" not in df.columns:
                df["neutral"] = True

            print(f"✓ Loaded {len(df)} Unrivaled games")
            return df

        except Exception as e:
            print(f"✗ Error loading Unrivaled games: {e}")
            return pd.DataFrame(columns=[
                "date", "home_team", "away_team", "home_score", "away_score",
                "neutral", "season"
            ])

    def get_games_for_date(self, date_str: str) -> pd.DataFrame:
        """
        Get games scheduled for a specific date.

        Args:
            date_str: Date in YYYY-MM-DD format

        Returns:
            DataFrame of games for that date
        """
        df = self.load_games()
        if df.empty:
            return df

        target_date = pd.to_datetime(date_str).date()
        return df[df["date"].dt.date == target_date]

    def get_upcoming_games(self, date_str: Optional[str] = None) -> pd.DataFrame:
        """
        Get upcoming games (games without scores).

        Args:
            date_str: Optional date to filter from (defaults to today)

        Returns:
            DataFrame of upcoming games
        """
        df = self.load_games()
        if df.empty:
            return df

        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        target_date = pd.to_datetime(date_str)

        # Games without scores (upcoming)
        upcoming = df[
            (df["date"] >= target_date) &
            (df["home_score"].isna() | (df["home_score"] == 0))
        ]
        return upcoming.sort_values("date")

    def get_team_record(self, team: str) -> Dict[str, int]:
        """
        Get win-loss record for a team.

        Args:
            team: Team name

        Returns:
            Dictionary with 'wins' and 'losses' keys
        """
        df = self.load_games()
        team = self._normalize_team_name(team)

        wins = 0
        losses = 0

        for _, game in df.iterrows():
            if pd.isna(game["home_score"]) or pd.isna(game["away_score"]):
                continue

            if game["home_team"] == team:
                if game["home_score"] > game["away_score"]:
                    wins += 1
                else:
                    losses += 1
            elif game["away_team"] == team:
                if game["away_score"] > game["home_score"]:
                    wins += 1
                else:
                    losses += 1

        return {"wins": wins, "losses": losses}


def download_games_for_date(date_str: str) -> bool:
    """
    DAG-compatible function to download games for a date.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        bool: True if successful
    """
    games = UnrivaledGames()
    return games.download_games()


if __name__ == "__main__":
    unrivaled = UnrivaledGames()
    df = unrivaled.load_games()
    print(f"Loaded {len(df)} Unrivaled games")
    if not df.empty:
        print(df.tail())

    # Print team records
    print("\nTeam Records:")
    for team in UNRIVALED_TEAMS:
        record = unrivaled.get_team_record(team)
        print(f"  {team}: {record['wins']}-{record['losses']}")
