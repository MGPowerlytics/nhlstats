"""
NHL box-score fetcher.

Data source
-----------
NHL public web API — ``api-web.nhle.com``::

    GET https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore

The response includes team-aggregate stats (shots on goal, hits, blocked
shots, power-play, PIM, faceoff percentage) in the ``teamGameStats`` array.
The schedule endpoint is used for date enumeration::

    GET https://api-web.nhle.com/v1/schedule/{YYYY-MM-DD}

Rate limit: 1 request per 3 seconds (``RATE_LIMIT_SECONDS = 3.0``).

Extension table: ``nhl_team_game_stats_ext``
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import requests

from plugins.db_manager import DBManager
from plugins.stats.base import BoxScoreFetcher

logger = logging.getLogger(__name__)

# Columns that live in the core team_game_stats table.
_CORE_KEYS = frozenset(
    {
        "game_id",
        "sport",
        "team",
        "opponent",
        "is_home",
        "game_date",
        "season",
        "points_for",
        "points_against",
        "won",
        "off_rating",
        "def_rating",
        "pace",
        "margin",
    }
)

# NHL game states that indicate a completed game.
_FINAL_STATES = frozenset({"OFF", "FINAL", "7"})


class NHLBoxScoreFetcher(BoxScoreFetcher):
    """Fetch and persist NHL team-level box-score data from api-web.nhle.com.

    Calls ``/v1/gamecenter/{game_id}/boxscore`` for each game and extracts
    team-aggregate counting stats (shots on goal, hits, blocks, power-play
    goals/opportunities, penalty minutes, faceoff percentage).

    A partial Corsi proxy is stored in the ``shots`` column of the extension
    table: ``shots = sog_for + opp_blocks``.  Full Corsi computation via
    :func:`~plugins.stats.advanced_stats.compute_hockey_corsi` requires
    missed-shot data that the v1 boxscore endpoint does not expose.

    Example:
        >>> fetcher = NHLBoxScoreFetcher()
        >>> rows = fetcher.fetch_game_stats("2023020001")
        >>> fetcher.upsert_rows(rows)
    """

    SPORT: str = "NHL"
    RATE_LIMIT_SECONDS: float = 3.0  # 1 req / 3 s
    EXT_TABLE: str = "nhl_team_game_stats_ext"

    _BASE_URL: str = "https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore"
    _SCHEDULE_URL: str = "https://api-web.nhle.com/v1/schedule/{date}"

    def __init__(self, db: DBManager | None = None) -> None:
        """Initialise the NHL fetcher.

        Args:
            db: Optional shared :class:`~plugins.db_manager.DBManager`.
        """
        super().__init__(db=db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_game_stats(self, game_id: str) -> list[dict[str, Any]]:
        """Fetch team box-score for one NHL game.

        Hits ``https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore``
        and parses the ``teamGameStats`` array and the ``homeTeam`` /
        ``awayTeam`` objects.

        The ``"ext"`` sub-dict on each returned row is destined for
        ``nhl_team_game_stats_ext`` and includes the partial Corsi proxy
        (``shots`` = SOG + opponent blocks).

        Args:
            game_id: NHL game ID (e.g. ``"2023020001"``).

        Returns:
            List of two dicts — home team then away team.  Returns an empty
            list if the API call fails.
        """
        self._rate_limit()
        url = self._BASE_URL.format(game_id=game_id)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return self._parse_boxscore(str(game_id), data)

    def fetch_date_range(self, start: date, end: date) -> list[dict[str, Any]]:
        """Fetch NHL box-scores for all completed games in a date range.

        Iterates daily schedule requests to ``/v1/schedule/YYYY-MM-DD``,
        skips preseason games (gameType=1) and games that have not yet
        finished, then calls :meth:`fetch_game_stats` for each valid game.

        Args:
            start: First date (inclusive).
            end: Last date (inclusive).

        Returns:
            Flat list of normalised team-row dicts.
        """
        rows: list[dict[str, Any]] = []
        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            self._rate_limit()
            url = self._SCHEDULE_URL.format(date=date_str)
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                schedule = resp.json()
            except Exception as exc:
                logger.warning(
                    "⚠️ Failed to fetch NHL schedule for %s: %s", date_str, exc
                )
                current += timedelta(days=1)
                continue

            for week_entry in schedule.get("gameWeek", []):
                for game in week_entry.get("games", []):
                    game_date = game.get("gameDate", "")
                    if game_date != date_str:
                        continue
                    # Skip preseason and non-final games
                    if game.get("gameType", 1) == 1:
                        continue
                    if game.get("gameState", "") not in _FINAL_STATES:
                        continue
                    gid = str(game["id"])
                    try:
                        game_rows = self.fetch_game_stats(gid)
                        rows.extend(game_rows)
                    except Exception as exc:
                        logger.warning("⚠️ Failed to fetch NHL game %s: %s", gid, exc)

            current += timedelta(days=1)
        return rows

    def upsert_rows(self, rows: list[dict[str, Any]]) -> int:
        """Persist NHL rows to ``team_game_stats`` and ``nhl_team_game_stats_ext``.

        Rows whose ``game_id`` is absent from ``unified_games`` are skipped
        with a warning to avoid FK violations.

        Args:
            rows: Normalised team-game dicts as returned by
                :meth:`fetch_game_stats`.

        Returns:
            Total number of rows upserted.
        """
        count = 0
        for row in rows:
            game_id = row["game_id"]
            team = row["team"]
            ext = row.get("ext", {})

            if not self._game_exists_in_unified(game_id):
                continue

            if not self._upsert_core(row):
                continue
            if ext:
                self._upsert_nhl_ext(ext, game_id, team)
            count += 1
        return count

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_boxscore(game_id: str, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse the JSON payload from ``/v1/gamecenter/{id}/boxscore``.

        Args:
            game_id: Native NHL game ID string.
            data: Parsed JSON response body.

        Returns:
            List of two normalised team-row dicts.
        """
        game_date: str = data.get("gameDate", "")
        season_raw = data.get("season", 0)
        # 20232024 → "2023"
        season = str(season_raw)[:4] if season_raw else game_date[:4]

        home_obj = data.get("homeTeam", {})
        away_obj = data.get("awayTeam", {})
        home_abbrev = home_obj.get("abbrev", "")
        away_abbrev = away_obj.get("abbrev", "")
        home_score = int(home_obj.get("score", 0) or 0)
        away_score = int(away_obj.get("score", 0) or 0)

        # Parse teamGameStats array into a flat dict keyed by category.
        cat: dict[str, dict[str, str]] = {}
        for entry in data.get("teamGameStats", []):
            name = entry.get("category", "")
            cat[name] = {
                "home": str(entry.get("homeValue", "0")),
                "away": str(entry.get("awayValue", "0")),
            }

        def _int(mapping: dict[str, str], side: str, default: int = 0) -> int:
            try:
                return int(mapping.get(side, default))
            except (TypeError, ValueError):
                return default

        def _float(mapping: dict[str, str], side: str, default: float = 0.0) -> float:
            try:
                return float(mapping.get(side, default))
            except (TypeError, ValueError):
                return default

        def _pp(raw: str) -> tuple[int, int]:
            """Parse 'G/A' power-play string → (goals, attempts)."""
            try:
                g, a = str(raw).split("/")
                return int(g), int(a)
            except (ValueError, AttributeError):
                return 0, 0

        home_sog = _int(cat.get("sog", {}), "home")
        away_sog = _int(cat.get("sog", {}), "away")
        home_hits = _int(cat.get("hits", {}), "home")
        away_hits = _int(cat.get("hits", {}), "away")
        # blockedShots = shots blocked BY this team (defensive blocks)
        home_blocks = _int(cat.get("blockedShots", {}), "home")
        away_blocks = _int(cat.get("blockedShots", {}), "away")
        home_pim = _int(cat.get("pim", {}), "home")
        away_pim = _int(cat.get("pim", {}), "away")

        raw_fopct_home = _float(cat.get("faceoffWinningPctg", {}), "home")
        raw_fopct_away = _float(cat.get("faceoffWinningPctg", {}), "away")
        # Normalize: API may return 56.67 (%) or 0.5667
        home_fo_pct = raw_fopct_home / 100.0 if raw_fopct_home > 1 else raw_fopct_home
        away_fo_pct = raw_fopct_away / 100.0 if raw_fopct_away > 1 else raw_fopct_away

        # Power play — prefer homeTeam.powerPlayConversion if present
        home_pp_str = home_obj.get(
            "powerPlayConversion", cat.get("powerPlay", {}).get("home", "0/0")
        )
        away_pp_str = away_obj.get(
            "powerPlayConversion", cat.get("powerPlay", {}).get("away", "0/0")
        )
        home_pp_goals, home_pp_opp = _pp(home_pp_str)
        away_pp_goals, away_pp_opp = _pp(away_pp_str)

        # PK is the mirror of the opponent's PP
        home_pk_against, home_pk_opp = away_pp_goals, away_pp_opp
        away_pk_against, away_pk_opp = home_pp_goals, home_pp_opp

        def _pct(num: int, den: int) -> float:
            return round(num / den, 4) if den > 0 else 0.0

        def _pk_pct(against: int, opp: int) -> float:
            return round(1.0 - against / opp, 4) if opp > 0 else 1.0

        # Partial Corsi proxy: our SOG + opponent's blocks of our shots.
        # opponent's "blockedShots" = shots they blocked = our shot attempts blocked
        home_corsi_for = home_sog + away_blocks
        away_corsi_for = away_sog + home_blocks

        home_row: dict[str, Any] = {
            "game_id": game_id,
            "sport": "NHL",
            "team": home_abbrev,
            "opponent": away_abbrev,
            "is_home": True,
            "game_date": game_date,
            "season": season,
            "points_for": home_score,
            "points_against": away_score,
            "won": home_score > away_score,
            "off_rating": None,
            "def_rating": None,
            "pace": None,
            "margin": home_score - away_score,
            "ext": {
                "game_id": game_id,
                "team": home_abbrev,
                "shots": home_corsi_for,
                "sog": home_sog,
                "hits": home_hits,
                "blocks": home_blocks,
                "pim": home_pim,
                "faceoff_pct": round(home_fo_pct, 4),
                "pp_goals": home_pp_goals,
                "pp_opportunities": home_pp_opp,
                "pp_pct": _pct(home_pp_goals, home_pp_opp),
                "pk_goals_against": home_pk_against,
                "pk_opportunities": home_pk_opp,
                "pk_pct": _pk_pct(home_pk_against, home_pk_opp),
                "shooting_pct": _pct(home_score, home_sog),
            },
        }
        away_row: dict[str, Any] = {
            "game_id": game_id,
            "sport": "NHL",
            "team": away_abbrev,
            "opponent": home_abbrev,
            "is_home": False,
            "game_date": game_date,
            "season": season,
            "points_for": away_score,
            "points_against": home_score,
            "won": away_score > home_score,
            "off_rating": None,
            "def_rating": None,
            "pace": None,
            "margin": away_score - home_score,
            "ext": {
                "game_id": game_id,
                "team": away_abbrev,
                "shots": away_corsi_for,
                "sog": away_sog,
                "hits": away_hits,
                "blocks": away_blocks,
                "pim": away_pim,
                "faceoff_pct": round(away_fo_pct, 4),
                "pp_goals": away_pp_goals,
                "pp_opportunities": away_pp_opp,
                "pp_pct": _pct(away_pp_goals, away_pp_opp),
                "pk_goals_against": away_pk_against,
                "pk_opportunities": away_pk_opp,
                "pk_pct": _pk_pct(away_pk_against, away_pk_opp),
                "shooting_pct": _pct(away_score, away_sog),
            },
        }
        return [home_row, away_row]

    def _game_exists_in_unified(self, game_id: str) -> bool:
        """Return True if *game_id* is present in ``unified_games``."""
        try:
            result = self.db.fetch_df(
                "SELECT 1 FROM unified_games WHERE game_id = :game_id LIMIT 1",
                {"game_id": game_id},
            )
            if result.empty:
                logger.warning(
                    "⚠️ NHL game %s not found in unified_games — skipping", game_id
                )
                return False
            return True
        except Exception as exc:
            logger.error("Error checking unified_games for %s: %s", game_id, exc)
            return False

    def _upsert_core(self, row: dict[str, Any]) -> bool:
        """Upsert a single row to ``team_game_stats``.

        Returns True on success, False on error.
        """
        sql = """
            INSERT INTO team_game_stats (
                game_id, sport, team, opponent, is_home, game_date, season,
                points_for, points_against, won, off_rating, def_rating, pace, margin
            ) VALUES (
                :game_id, :sport, :team, :opponent, :is_home, :game_date, :season,
                :points_for, :points_against, :won, :off_rating, :def_rating, :pace, :margin
            )
            ON CONFLICT (game_id, team) DO UPDATE SET
                points_for     = EXCLUDED.points_for,
                points_against = EXCLUDED.points_against,
                won            = EXCLUDED.won,
                off_rating     = EXCLUDED.off_rating,
                def_rating     = EXCLUDED.def_rating,
                pace           = EXCLUDED.pace,
                margin         = EXCLUDED.margin,
                updated_at     = NOW()
        """
        params = {k: row[k] for k in _CORE_KEYS}
        try:
            self.db.execute(sql, params)
            return True
        except Exception as exc:
            logger.error(
                "Error upserting team_game_stats for %s/%s: %s",
                row["game_id"],
                row["team"],
                exc,
            )
            return False

    def _upsert_nhl_ext(self, ext: dict[str, Any], game_id: str, team: str) -> None:
        """Upsert a single row to ``nhl_team_game_stats_ext``."""
        sql = """
            INSERT INTO nhl_team_game_stats_ext (
                game_id, team, shots, sog, hits, blocks, pim, faceoff_pct,
                pp_goals, pp_opportunities, pp_pct,
                pk_goals_against, pk_opportunities, pk_pct, shooting_pct
            ) VALUES (
                :game_id, :team, :shots, :sog, :hits, :blocks, :pim, :faceoff_pct,
                :pp_goals, :pp_opportunities, :pp_pct,
                :pk_goals_against, :pk_opportunities, :pk_pct, :shooting_pct
            )
            ON CONFLICT (game_id, team) DO UPDATE SET
                shots             = EXCLUDED.shots,
                sog               = EXCLUDED.sog,
                hits              = EXCLUDED.hits,
                blocks            = EXCLUDED.blocks,
                pim               = EXCLUDED.pim,
                faceoff_pct       = EXCLUDED.faceoff_pct,
                pp_goals          = EXCLUDED.pp_goals,
                pp_opportunities  = EXCLUDED.pp_opportunities,
                pp_pct            = EXCLUDED.pp_pct,
                pk_goals_against  = EXCLUDED.pk_goals_against,
                pk_opportunities  = EXCLUDED.pk_opportunities,
                pk_pct            = EXCLUDED.pk_pct,
                shooting_pct      = EXCLUDED.shooting_pct
        """
        try:
            self.db.execute(sql, ext)
        except Exception as exc:
            logger.error(
                "Error upserting nhl_team_game_stats_ext for %s/%s: %s",
                game_id,
                team,
                exc,
            )
