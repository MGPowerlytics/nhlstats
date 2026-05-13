"""Normalized Understat league client for soccer advanced match stats."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import requests

from plugins.naming_resolver import NamingContext, NamingResolver

_UNDERSTAT_BASE_URL = "https://understat.com/"
_UNDERSTAT_HEADERS = {
    "User-Agent": "nhlstats-research-bot/1.0 (+https://github.com/MGPowerlytics/nhlstats)",
    "X-Requested-With": "XMLHttpRequest",
}
_UNDERSTAT_LEAGUES = {
    "EPL": "EPL",
}


class UnderstatLeagueClient:
    """Fetch normalized Understat match payloads for supported soccer leagues."""

    def __init__(self, session: requests.Session | None = None) -> None:
        """Initialize the client with an optional shared requests session."""
        self.session = session or requests.Session()
        self._cache: dict[
            tuple[str, int], dict[tuple[date, str, str], dict[str, Any]]
        ] = {}

    def normalize_match(
        self,
        sport: str,
        season: int,
        raw_match: dict[str, Any],
    ) -> dict[str, Any]:
        """Normalize one raw Understat league-match payload to the governed contract."""
        sport_upper = sport.upper()
        game_datetime = datetime.fromisoformat(str(raw_match["datetime"]))
        home_team = self._resolve_storage_team_name(
            sport_upper, str(raw_match["h"]["title"])
        )
        away_team = self._resolve_storage_team_name(
            sport_upper, str(raw_match["a"]["title"])
        )
        forecast = raw_match.get("forecast") or {}

        return {
            "source": "UNDERSTAT",
            "sport": sport_upper,
            "season": int(season),
            "match_id": str(raw_match["id"]),
            "game_date": game_datetime.date().isoformat(),
            "home_team": home_team,
            "away_team": away_team,
            "home_xg": float(raw_match["xG"]["h"]),
            "away_xg": float(raw_match["xG"]["a"]),
            "forecast_home_win": self._optional_float(forecast.get("w")),
            "forecast_draw": self._optional_float(forecast.get("d")),
            "forecast_away_win": self._optional_float(forecast.get("l")),
        }

    def fetch_league_matches(self, sport: str, season: int) -> list[dict[str, Any]]:
        """Fetch and normalize all completed matches for a league season."""
        sport_upper = sport.upper()
        if sport_upper not in _UNDERSTAT_LEAGUES:
            raise ValueError(f"Unsupported Understat league: {sport_upper}")
        league_code = _UNDERSTAT_LEAGUES[sport_upper]
        response = self.session.get(
            f"{_UNDERSTAT_BASE_URL}getLeagueData/{league_code}/{season}",
            headers=_UNDERSTAT_HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        raw_matches = payload.get("dates", [])

        normalized_matches = [
            self.normalize_match(sport=sport_upper, season=season, raw_match=match)
            for match in raw_matches
            if match.get("isResult") and match.get("xG")
        ]
        return normalized_matches

    def get_match_stats(
        self,
        sport: str,
        season: int,
        game_date: date,
        home_team: str,
        away_team: str,
    ) -> dict[str, Any] | None:
        """Return the normalized Understat payload for one completed match."""
        index = self._season_index(sport=sport, season=season)
        return index.get((game_date, home_team, away_team))

    def _season_index(
        self,
        sport: str,
        season: int,
    ) -> dict[tuple[date, str, str], dict[str, Any]]:
        """Build or reuse the cached match index for one sport season."""
        sport_upper = sport.upper()
        cache_key = (sport_upper, int(season))
        if cache_key not in self._cache:
            matches = self.fetch_league_matches(sport=sport_upper, season=season)
            self._cache[cache_key] = {
                (
                    date.fromisoformat(match["game_date"]),
                    str(match["home_team"]),
                    str(match["away_team"]),
                ): match
                for match in matches
            }
        return self._cache[cache_key]

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        """Return a float or ``None`` for optional numeric fields."""
        if value in (None, ""):
            return None
        return float(value)

    @staticmethod
    def _resolve_storage_team_name(sport: str, raw_name: str) -> str:
        """Resolve an Understat team name to the storage-facing soccer team name."""
        canonical_name = NamingResolver.resolve(
            NamingContext(sport=sport.lower(), source="understat", name=raw_name)
        )
        return NamingResolver.resolve(
            NamingContext(
                sport=sport.lower(),
                source="kalshi",
                name=canonical_name,
            )
        )
