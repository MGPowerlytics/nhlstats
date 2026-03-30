"""
Game verification for betting system.

Extracted from KalshiBetting to reduce class size and improve separation of concerns.
Handles checking if games have started using The Odds API with caching.
"""

import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
import requests
from plugins.betting_types import GameIdentity


class GameVerifier:
    """Verifies if games have started using The Odds API with caching."""

    # Sport mapping to The Odds API sport keys
    SPORT_TO_ODDS_API: Dict[str, str] = {
        "NBA": "basketball_nba",
        "NHL": "icehockey_nhl",
        "MLB": "baseball_mlb",
        "NFL": "americanfootball_nfl",
        "EPL": "soccer_epl",
        "LIGUE1": "soccer_france_ligue_one",
        "NCAAB": "basketball_ncaab",
        "WNCAAB": "basketball_ncaaw",
        "TENNIS": "tennis_atp",
    }

    # Cache duration in seconds (5 minutes)
    CACHE_DURATION: int = 300

    # HTTP timeout for API requests
    ODDS_API_TIMEOUT: int = 10

    # HTTP status code for successful requests
    HTTP_OK: int = 200

    def __init__(self, odds_api_key: Optional[str] = None):
        """
        Initialize game verifier.

        Args:
            odds_api_key: Optional API key for The Odds API. If None,
                         game verification will be skipped.
        """
        self.odds_api_key = odds_api_key
        self._scores_cache: Dict[str, List[Dict]] = {}
        self._scores_cache_time: Dict[str, float] = {}

    def _normalize_team_name(self, name: str) -> str:
        """
        Normalize team name for comparison (lowercase, alphanumeric).

        Args:
            name: Team name to normalize

        Returns:
            Normalized team name with only lowercase alphanumeric characters
        """
        return re.sub(r"[^a-z0-9]", "", name.lower())

    def _get_scores_cached(self, sport_key: str) -> List[Dict]:
        """
        Fetch scores from The Odds API with caching.

        Args:
            sport_key: The Odds API sport key

        Returns:
            List of game scores from The Odds API, or empty list on error
        """
        now = time.time()
        cached_time = self._scores_cache_time.get(sport_key, 0)

        if now - cached_time < self.CACHE_DURATION:
            return self._scores_cache.get(sport_key, [])

        try:
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores/"
            params = {"apiKey": self.odds_api_key, "daysFrom": 1}
            response = requests.get(url, params=params, timeout=self.ODDS_API_TIMEOUT)

            if response.status_code == self.HTTP_OK:
                scores = response.json()
                self._scores_cache[sport_key] = scores
                self._scores_cache_time[sport_key] = now
                return scores
            return []
        except Exception as e:
            print(f"   ⚠️  Error fetching scores for {sport_key}: {e}")
            return []

    def verify_game_not_started(self, game: GameIdentity) -> bool:
        """
        Verify game has not started using The Odds API.

        Args:
            game: Game identity to verify

        Returns:
            True if game has NOT started, False if it has started or completed.
            Returns True if verification cannot be performed (no API key, etc.)
        """
        if not self.odds_api_key:
            print("   ⚠️  No Odds API key - cannot verify game start time")
            return True

        sport_key = self.SPORT_TO_ODDS_API.get(game.sport.upper())
        if not sport_key:
            return True

        scores = self._get_scores_cached(sport_key)
        home_norm = self._normalize_team_name(game.home_team)
        away_norm = self._normalize_team_name(game.away_team)

        for s_game in scores:
            game_home = self._normalize_team_name(s_game.get("home_team", ""))
            game_away = self._normalize_team_name(s_game.get("away_team", ""))

            # Match teams (bidirectional contains check)
            if (home_norm in game_home or game_home in home_norm) and (
                away_norm in game_away or game_away in away_norm
            ):
                if s_game.get("scores") or s_game.get("completed"):
                    print(
                        f"   ❌ Game has STARTED/COMPLETED: {s_game.get('commence_time')}"
                    )
                    return False

        return True

    def is_game_started(self, market: Dict) -> bool:
        """
        Check if game has started based on Kalshi market status.

        Args:
            market: Kalshi market dictionary

        Returns:
            True if game has started, False otherwise
        """
        if market.get("status", "").lower() in ["closed", "settled", "finalized"]:
            return True
        close_time = market.get("close_time")
        if not close_time:
            return False
        try:
            return datetime.now(timezone.utc) >= datetime.fromisoformat(
                close_time.replace("Z", "+00:00")
            )
        except Exception:
            return False
