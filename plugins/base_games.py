#!/usr/bin/env python3
"""
Base classes and utilities for sport-specific game data fetchers.
"""

import requests
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

# HTTP Status Codes
HTTP_NOT_FOUND = 404
HTTP_TOO_MANY_REQUESTS = 429

# Fetching Defaults
DEFAULT_MAX_RETRIES = 5
DEFAULT_TIMEOUT = 30
DEFAULT_BASE_WAIT_TIME = 2


@dataclass
class RequestConfig:
    """Configuration for HTTP requests with retry logic.

    Attributes:
        max_retries: Maximum number of retry attempts for failed requests
        timeout: Request timeout in seconds
        base_wait_time: Base wait time in seconds for exponential backoff
    """

    max_retries: int = DEFAULT_MAX_RETRIES
    timeout: int = DEFAULT_TIMEOUT
    base_wait_time: int = DEFAULT_BASE_WAIT_TIME

    def execute(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request with exponential backoff with jitter for rate limits and errors.

        Args:
            url: The URL to fetch.
            params: Optional query parameters.
            headers: Optional HTTP headers.

        Returns:
            The JSON response as a dictionary.

        Raises:
            Exception: If all retries fail.
        """
        for attempt in range(self.max_retries):
            try:
                return self._execute_single_attempt(url, params, headers, attempt)
            except requests.exceptions.RequestException as e:
                if self._should_retry(attempt, e):
                    self._handle_retry(url, e, attempt)
                    continue
                raise

        raise Exception(f"Failed to fetch {url} after {self.max_retries} attempts")

    def _execute_single_attempt(
        self,
        url: str,
        params: Optional[Dict[str, Any]],
        headers: Optional[Dict[str, Any]],
        attempt: int,
    ) -> Dict[str, Any]:
        """Execute a single HTTP request attempt with error handling."""
        response = requests.get(
            url, params=params, headers=headers, timeout=self.timeout
        )

        # Handle rate limiting (already sleeps internally)
        if self._handle_rate_limit(response, attempt):
            raise requests.exceptions.RequestException("Rate limited, retry loop will continue")

        if self._handle_not_found(response, url):
            return {}

        response.raise_for_status()
        return response.json()

    def _should_retry(self, attempt: int, error: Exception) -> bool:
        """Determine if a request should be retried."""
        return attempt < self.max_retries - 1

    def _handle_retry(self, url: str, error: Exception, attempt: int) -> None:
        """Handle retry logic with exponential backoff."""
        wait_time = self._calculate_wait_time(attempt, max_wait=60.0)
        print(
            f"Request failed for {url}: {error}. "
            f"Retrying in {wait_time:.1f}s (attempt {attempt + 1}/{self.max_retries})..."
        )
        time.sleep(wait_time)

    def _handle_rate_limit(self, response: requests.Response, attempt: int) -> bool:
        """Handle rate limiting (429) response with exponential backoff.

        Args:
            response: HTTP response object
            attempt: Current retry attempt number (0-indexed)

        Returns:
            True if rate limited and should retry, False otherwise
        """

        if response.status_code == HTTP_TOO_MANY_REQUESTS:
            wait_time = self._calculate_wait_time(attempt, max_wait=120.0)
            print(
                f"Rate limited ({HTTP_TOO_MANY_REQUESTS}). "
                f"Waiting {wait_time:.1f}s (attempt {attempt + 1}/{self.max_retries})"
            )
            time.sleep(wait_time)
            return True
        return False

    def _handle_not_found(self, response: requests.Response, url: str) -> bool:
        """Handle 404 Not Found response.

        Args:
            response: HTTP response object
            url: The URL that was requested

        Returns:
            True if resource was not found (404), False otherwise
        """
        if response.status_code == HTTP_NOT_FOUND:
            print(f"  Resource not found ({HTTP_NOT_FOUND}): {url}")
            return True
        return False

    def _calculate_wait_time(self, attempt: int, max_wait: float = 60.0) -> float:
        """Calculate exponential backoff wait time with jitter.

        Args:
            attempt: Current retry attempt number (0-indexed)
            max_wait: Maximum wait time in seconds

        Returns:
            Wait time in seconds
        """
        import random

        base_wait = (2**attempt) * self.base_wait_time
        jitter = random.uniform(0.8, 1.2)  # ±20% jitter
        wait_time = base_wait * jitter
        return min(wait_time, max_wait)


# Massey Ratings Constants
MASSEY_DEFAULT_SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
MASSEY_CURRENT_SEASON = 2026

# Massey Format 1 (Numeric) CSV Columns
MASSEY_F1_COL_DATE = 1
MASSEY_F1_COL_T1_ID = 2
MASSEY_F1_COL_LOC1 = 3
MASSEY_F1_COL_S1 = 4
MASSEY_F1_COL_T2_ID = 5
MASSEY_F1_COL_S2 = 7

# Massey Location Constants
MASSEY_LOC_HOME = 1
MASSEY_LOC_AWAY = -1


@dataclass
class UnifiedGameInfo:
    """Shared data structure for game-related information across plugins."""

    sport: str
    game_date: str
    home_team: str
    away_team: str
    canon_home: str
    canon_away: str
    game_id: Optional[str] = None
    commence_time: Optional[str] = None
    status: str = "Scheduled"


class BaseGamesFetcher:
    """Base class for fetching game data from various APIs."""

    SPORT = "base"
    OUTPUT_DIR: Optional[str] = None

    def __init__(
        self,
        sport: Optional[str] = None,
        output_dir: Optional[str] = None,
        date_folder: Optional[str] = None,
    ) -> None:
        """
        Initialize the fetcher.

        Args:
            sport: The sport name (used for default output directory).
            output_dir: Optional custom output directory.
            date_folder: Optional date folder to append to the output directory.
        """
        self.sport = sport or self.SPORT

        if output_dir:
            self.output_dir = Path(output_dir)
        elif self.OUTPUT_DIR:
            self.output_dir = Path(self.OUTPUT_DIR)
        else:
            self.output_dir = Path(f"data/{self.sport.lower()}")

        if date_folder:
            self.output_dir = self.output_dir / date_folder

        self.data_dir = self.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _fetch_game_resource(
        self, game_id: Any, path_template: str, base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generic helper to fetch a game-specific resource.

        Args:
            game_id: The ID of the game.
            path_template: The path template (e.g., 'game/{game_id}/boxscore').
            base_url: Optional base URL (defaults to self.BASE_URL).
        """
        base = base_url or getattr(self, "BASE_URL", "")
        url = f"{base}/{path_template.format(game_id=game_id)}"
        return self._make_request(url)

    def _make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make HTTP request with exponential backoff for rate limits and errors.

        Args:
            url: The URL to fetch.
            params: Optional query parameters.
            headers: Optional HTTP headers.
            request_config: RequestConfig object containing retry and timeout settings.
                If not provided, uses default values from RequestConfig or kwargs.
            **kwargs: Additional arguments to pass to RequestConfig constructor if request_config is None.

        Returns:
            The JSON response as a dictionary.

        Raises:
            Exception: If all retries fail.
        """
        # Use provided RequestConfig or default one (optionally built from kwargs)
        config = request_config or RequestConfig(**kwargs)
        return config.execute(url, params=params, headers=headers)


class MasseyGamesFetcher(BaseGamesFetcher):
    """Base class for fetching game data from Massey Ratings."""

    def __init__(
        self,
        sport: str,
        sub_id: str,
        data_dir: Optional[str] = None,
        seasons: Optional[list] = None,
    ) -> None:
        """
        Initialize the Massey fetcher.

        Args:
            sport: The sport name (e.g., 'ncaab', 'wncaab').
            sub_id: Massey sub-ID for the sport.
            data_dir: Optional custom data directory.
            seasons: Optional list of seasons to fetch.
        """
        super().__init__(sport=sport, output_dir=data_dir)
        self.sub_id = sub_id
        self.seasons = seasons or MASSEY_DEFAULT_SEASONS

    def download_games(self) -> bool:
        """Download historical and current data from Massey Ratings."""
        import requests
        import time

        success = True

        for season in self.seasons:
            # 1. Download Team Mapping (Format 2)
            teams_url = f"https://masseyratings.com/scores.php?s=cb{season}&sub={self.sub_id}&all=1&mode=3&format=2"
            teams_file = self.output_dir / f"teams_{season}.csv"

            # Re-download if current season or missing
            if not teams_file.exists() or season == MASSEY_CURRENT_SEASON:
                print(f"📥 Downloading {self.sport.upper()} teams ({season})...")
                try:
                    resp = requests.get(teams_url, timeout=DEFAULT_TIMEOUT)
                    resp.raise_for_status()
                    with open(teams_file, "wb") as f:
                        f.write(resp.content)
                    time.sleep(1)
                except Exception as e:
                    print(f"✗ Failed to download teams for {season}: {e}")
                    success = False

            # 2. Download Games (Format 1 - Numeric)
            games_url = f"https://masseyratings.com/scores.php?s=cb{season}&sub={self.sub_id}&all=1&mode=3&format=1"
            games_file = self.output_dir / f"games_{season}.csv"

            if not games_file.exists() or season == MASSEY_CURRENT_SEASON:
                print(f"📥 Downloading {self.sport.upper()} games ({season})...")
                try:
                    resp = requests.get(games_url, timeout=DEFAULT_TIMEOUT)
                    resp.raise_for_status()
                    with open(games_file, "wb") as f:
                        f.write(resp.content)
                    print(f"✓ Saved {self.sport.upper()} data for {season}")
                    time.sleep(1)
                except Exception as e:
                    print(f"✗ Failed to download games for {season}: {e}")
                    success = False

        return success

    def _load_raw_data(self, season: int) -> Tuple[Optional[Dict[int, str]], Any]:
        """Helper to load team map and games dataframe for a season."""
        import pandas as pd

        teams_file = self.output_dir / f"teams_{season}.csv"
        games_file = self.output_dir / f"games_{season}.csv"

        if not teams_file.exists() or not games_file.exists():
            return None, None

        # Load Teams
        teams_df = pd.read_csv(teams_file, header=None, names=["team_id", "team_name"])
        teams_df["team_name"] = teams_df["team_name"].str.strip()
        team_map = dict(zip(teams_df["team_id"], teams_df["team_name"]))

        # Load Games
        try:
            games_df = pd.read_csv(games_file, header=None)
        except pd.errors.EmptyDataError:
            return team_map, None

        return team_map, games_df

    def _parse_game_row(
        self, row: Any, team_map: Dict[int, str]
    ) -> Optional[Dict[str, Any]]:
        """Parse a single row from a Massey format 1 game CSV."""
        import pandas as pd

        try:
            date_int = row[MASSEY_F1_COL_DATE]
            t1_id = row[MASSEY_F1_COL_T1_ID]
            loc1 = row[MASSEY_F1_COL_LOC1]  # 1=Home, -1=Away, 0=Neutral
            s1 = row[MASSEY_F1_COL_S1]
            t2_id = row[MASSEY_F1_COL_T2_ID]
            # row[6] is usually unused/blank
            s2 = row[MASSEY_F1_COL_S2]

            t1_name = team_map.get(t1_id, f"ID_{t1_id}")
            t2_name = team_map.get(t2_id, f"ID_{t2_id}")

            # Normalize to Home vs Away
            if loc1 == MASSEY_LOC_HOME:
                home_team, away_team = t1_name, t2_name
                home_score, away_score = s1, s2
                neutral = False
            elif loc1 == MASSEY_LOC_AWAY:  # T1 is Away
                home_team, away_team = t2_name, t1_name
                home_score, away_score = s2, s1
                neutral = False
            else:
                # Neutral
                home_team, away_team = t1_name, t2_name
                home_score, away_score = s1, s2
                neutral = True

            # Parse date YYYYMMDD
            date_str = str(date_int).strip()
            game_date = pd.to_datetime(date_str, format="%Y%m%d")

            return {
                "date": game_date,
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score,
                "neutral": neutral,
            }
        except Exception:
            return None
