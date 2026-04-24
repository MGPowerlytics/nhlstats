"""
College basketball (CBB) box-score fetcher.

Covers both NCAAB (men's) and WNCAAB (women's).

Data sources
------------
1. **ESPN Scoreboard API** (primary box-score source)::

       GET https://site.api.espn.com/apis/site/v2/sports/basketball/
               {league}/scoreboard?dates={YYYYMMDD}

   where ``{league}`` is ``mens-college-basketball`` or
   ``womens-college-basketball``.

   Detailed box-score per game::

       GET https://site.api.espn.com/apis/site/v2/sports/basketball/
               {league}/summary?event={event_id}

Rate limit: ``RATE_LIMIT_SECONDS = 0.5`` (ESPN API is undocumented; 2 req/s).

Extension tables: ``ncaab_team_game_stats_ext`` / ``wncaab_team_game_stats_ext``
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import requests

from plugins.db_manager import DBManager
from plugins.stats.advanced_stats import (
    compute_basketball_drtg,
    compute_basketball_efg,
    compute_basketball_ortg,
    compute_basketball_pace,
    compute_basketball_ts,
    estimate_basketball_possessions,
)
from plugins.stats.base import BoxScoreFetcher

logger = logging.getLogger(__name__)

_ESPN_SCOREBOARD_URL: str = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball"
    "/{league}/scoreboard?dates={date_str}"
)
_ESPN_SUMMARY_URL: str = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball"
    "/{league}/summary?event={event_id}"
)

_LEAGUE_SLUGS: dict[str, str] = {
    "NCAAB": "mens-college-basketball",
    "WNCAAB": "womens-college-basketball",
}

# ESPN stat name → internal key
_ESPN_STAT_MAP: dict[str, str] = {
    "fieldGoalsMade": "fgm",
    "fieldGoalsAttempted": "fga",
    "threePointFieldGoalsMade": "fg3m",
    "threePointFieldGoalsAttempted": "fg3a",
    "freeThrowsMade": "ftm",
    "freeThrowsAttempted": "fta",
    "assists": "ast",
    "totalRebounds": "reb",
    "offensiveRebounds": "oreb",
    "steals": "stl",
    "blocks": "blk",
    "turnovers": "tov",
    "fouls": "pf",
    "points": "pts",
}


def _season_label_from_date(d: date) -> str:
    """Derive CBB season label from a game date.

    Args:
        d: Game date.

    Returns:
        Season label like ``"2023-24"``.
    """
    year = d.year
    if d.month >= 10:
        return f"{year}-{str(year + 1)[2:]}"
    return f"{year - 1}-{str(year)[2:]}"


class CBBBoxScoreFetcher(BoxScoreFetcher):
    """Fetch and persist college basketball team box-score data.

    Handles both NCAAB and WNCAAB by accepting a *sport* parameter at
    construction.  Uses ESPN's undocumented public scoreboard + summary API
    endpoints as the primary box-score source.

    Example:
        >>> fetcher = CBBBoxScoreFetcher(sport="NCAAB")
        >>> rows = fetcher.fetch_game_stats("espn_401503425")
        >>> fetcher.upsert_rows(rows)
    """

    SPORT: str = "NCAAB"  # default; overridden per-instance
    RATE_LIMIT_SECONDS: float = 0.5  # 2 req/s
    EXT_TABLE: str = "ncaab_team_game_stats_ext"

    def __init__(
        self,
        sport: str = "NCAAB",
        db: DBManager | None = None,
    ) -> None:
        """Initialise the CBB fetcher for the specified division.

        Args:
            sport: ``"NCAAB"`` for men's or ``"WNCAAB"`` for women's.
            db: Optional shared :class:`~plugins.db_manager.DBManager`.

        Raises:
            ValueError: If *sport* is not ``"NCAAB"`` or ``"WNCAAB"``.
        """
        if sport not in _LEAGUE_SLUGS:
            raise ValueError(
                f"sport must be one of {list(_LEAGUE_SLUGS)}, got {sport!r}"
            )
        self.SPORT = sport  # instance-level override
        self.EXT_TABLE = f"{sport.lower()}_team_game_stats_ext"
        self._espn_league: str = _LEAGUE_SLUGS[sport]
        super().__init__(db=db)

    # ------------------------------------------------------------------
    # ESPN API helpers
    # ------------------------------------------------------------------

    def _fetch_espn_summary(self, event_id: str) -> dict[str, Any] | None:
        """Call ESPN summary endpoint and return the JSON payload.

        Args:
            event_id: Numeric ESPN event ID string.

        Returns:
            Parsed JSON dict or ``None`` on failure.
        """
        self._rate_limit()
        url = _ESPN_SUMMARY_URL.format(league=self._espn_league, event_id=event_id)
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("⚠️ ESPN summary failed for event %s: %s", event_id, exc)
            return None

    def _fetch_espn_scoreboard(self, d: date) -> list[str]:
        """Return ESPN event IDs for all games on a given date.

        Args:
            d: Game date.

        Returns:
            List of ESPN event ID strings.
        """
        self._rate_limit()
        date_str = d.strftime("%Y%m%d")
        url = _ESPN_SCOREBOARD_URL.format(league=self._espn_league, date_str=date_str)
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return [e["id"] for e in data.get("events", [])]
        except Exception as exc:
            logger.warning("⚠️ ESPN scoreboard failed for %s: %s", d, exc)
            return []

    @staticmethod
    def _parse_statistics(stats_list: list[dict]) -> dict[str, Any]:
        """Parse ESPN statistics array into a flat dict.

        Args:
            stats_list: List of ``{"name": ..., "displayValue": ...}`` dicts.

        Returns:
            Mapping of internal stat key → integer or None.
        """
        raw: dict[str, str] = {s["name"]: s["displayValue"] for s in stats_list}
        out: dict[str, Any] = {}
        for espn_name, key in _ESPN_STAT_MAP.items():
            val = raw.get(espn_name)
            if val is None:
                out[key] = None
                continue
            try:
                # Handle fractions like "5-10"
                if "-" in str(val):
                    made, _ = str(val).split("-", 1)
                    out[key] = int(made)
                else:
                    out[key] = int(float(val))
            except (ValueError, TypeError):
                out[key] = None
        return out

    def _parse_summary(
        self, data: dict[str, Any], game_id: str
    ) -> list[dict[str, Any]]:
        """Parse ESPN summary JSON into two team-game dicts.

        Args:
            data: ESPN summary JSON payload.
            game_id: Internal game_id string (e.g. ``"espn_401503425"``).

        Returns:
            List of two normalised dicts (away, home).
        """
        boxscore = data.get("boxscore", {})
        teams_data = boxscore.get("teams", [])
        if not teams_data:
            logger.warning("⚠️ No boxscore.teams in ESPN data for %s", game_id)
            return []

        # Derive game date from header
        game_date: date | None = None
        try:
            header = data.get("header", {})
            competitions = header.get("competitions", [{}])
            date_str = competitions[0].get("date", "")[:10]
            game_date = date.fromisoformat(date_str)
        except Exception:
            game_date = date.today()

        season_label = _season_label_from_date(game_date) if game_date else "unknown"

        rows: list[dict[str, Any]] = []
        home_team_name: str = ""
        away_team_name: str = ""

        # Determine home/away from competitions block
        competitors = []
        try:
            competitions = data.get("header", {}).get("competitions", [{}])
            competitors = competitions[0].get("competitors", [])
        except Exception:
            pass

        home_score: int | None = None
        away_score: int | None = None
        for comp in competitors:
            if comp.get("homeAway") == "home":
                home_team_name = comp.get("team", {}).get("displayName", "")
                try:
                    home_score = int(comp.get("score", 0))
                except (ValueError, TypeError):
                    home_score = None
            else:
                away_team_name = comp.get("team", {}).get("displayName", "")
                try:
                    away_score = int(comp.get("score", 0))
                except (ValueError, TypeError):
                    away_score = None

        for team_block in teams_data:
            team_info = team_block.get("team", {})
            team_name = team_info.get("displayName", "")
            stats_list = team_block.get("statistics", [])
            stats = self._parse_statistics(stats_list)

            is_home = team_name == home_team_name
            opponent = away_team_name if is_home else home_team_name
            pts = stats.get("pts") or 0
            opp_pts = (home_score if not is_home else away_score) or 0

            # Advanced stats
            fga = stats.get("fga") or 0
            fgm = stats.get("fgm") or 0
            fg3m = stats.get("fg3m") or 0
            fg3a = stats.get("fg3a") or 0
            fta = stats.get("fta") or 0
            ftm = stats.get("ftm") or 0
            oreb = stats.get("oreb") or 0
            reb = stats.get("reb") or 0
            tov = stats.get("tov") or 0
            ast = stats.get("ast") or 0
            stl = stats.get("stl") or 0
            blk = stats.get("blk") or 0
            pf = stats.get("pf") or 0

            fg_pct = fgm / fga if fga > 0 else None
            fg3_pct = fg3m / fg3a if fg3a > 0 else None
            efg_pct = compute_basketball_efg(fgm, fg3m, fga)
            ts_pct = compute_basketball_ts(pts, fga, fta)
            poss = estimate_basketball_possessions(fga, fta, oreb, tov)
            pace = compute_basketball_pace(poss, 40.0)  # 40-min CBB game
            off_rating = compute_basketball_ortg(pts, poss)
            def_rating = compute_basketball_drtg(opp_pts, poss)

            won: bool | None = None
            if home_score is not None and away_score is not None:
                if is_home:
                    won = (home_score or 0) > (away_score or 0)
                else:
                    won = (away_score or 0) > (home_score or 0)

            team_pts = home_score if is_home else away_score
            opp_team_pts = away_score if is_home else home_score

            ext = {
                "fg_pct": round(fg_pct, 4) if fg_pct is not None else None,
                "fg3m": fg3m or None,
                "fg3a": fg3a or None,
                "fg3_pct": round(fg3_pct, 4) if fg3_pct is not None else None,
                "ast": ast or None,
                "reb": reb or None,
                "stl": stl or None,
                "blk": blk or None,
                "tov": tov or None,
                "pf": pf or None,
                "ts_pct": round(ts_pct, 4) if ts_pct else None,
                "efg_pct": round(efg_pct, 4) if efg_pct else None,
            }

            rows.append(
                {
                    "game_id": game_id,
                    "sport": self.SPORT,
                    "team": team_name,
                    "opponent": opponent,
                    "is_home": is_home,
                    "game_date": game_date,
                    "season": season_label,
                    "points_for": team_pts,
                    "points_against": opp_team_pts,
                    "won": won,
                    "off_rating": round(off_rating, 2) if off_rating else None,
                    "def_rating": round(def_rating, 2) if def_rating else None,
                    "pace": round(pace, 2) if pace else None,
                    "margin": (
                        (team_pts - opp_team_pts)
                        if team_pts is not None and opp_team_pts is not None
                        else None
                    ),
                    "ext": ext,
                }
            )
        return rows

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_game_stats(self, game_id: str) -> list[dict[str, Any]]:
        """Fetch team box-score for one CBB game.

        Queries the ESPN ``summary`` endpoint for *game_id* and parses
        the ``boxscore.teams`` block for both teams.

        Args:
            game_id: ESPN event ID — numeric or prefixed with ``"espn_"``
                (e.g. ``"espn_401503425"``).

        Returns:
            List of two dicts (home team, away team).
        """
        event_id = game_id.removeprefix("espn_")
        data = self._fetch_espn_summary(event_id)
        if data is None:
            return []
        canonical_id = f"espn_{event_id}"
        return self._parse_summary(data, canonical_id)

    def fetch_date_range(self, start: date, end: date) -> list[dict[str, Any]]:
        """Fetch CBB box-scores for all games in a date range.

        Iterates day-by-day, calling the ESPN scoreboard for event IDs, then
        fetches each game's detailed box-score.

        Args:
            start: First date (inclusive).
            end: Last date (inclusive).

        Returns:
            Flat list of normalised team-row dicts.
        """
        all_rows: list[dict[str, Any]] = []
        current = start
        while current <= end:
            event_ids = self._fetch_espn_scoreboard(current)
            for eid in event_ids:
                game_id = f"espn_{eid}"
                try:
                    rows = self.fetch_game_stats(game_id)
                    all_rows.extend(rows)
                except Exception as exc:
                    logger.warning("⚠️ Failed to fetch %s: %s", game_id, exc)
            current += timedelta(days=1)
        logger.info("✓ Fetched %d CBB rows for %s–%s", len(all_rows), start, end)
        return all_rows

    def upsert_rows(self, rows: list[dict[str, Any]]) -> int:
        """Persist CBB rows to ``team_game_stats`` and sport extension table.

        Skips rows whose ``game_id`` is not present in ``unified_games``.

        Args:
            rows: Normalised team-game dicts.

        Returns:
            Total rows upserted.
        """
        if not rows:
            return 0

        all_game_ids = list({r["game_id"] for r in rows})
        placeholders = ", ".join(f":gid_{i}" for i in range(len(all_game_ids)))
        params_check = {f"gid_{i}": gid for i, gid in enumerate(all_game_ids)}
        try:
            result = self.db.execute(
                f"SELECT game_id FROM unified_games WHERE game_id IN ({placeholders})",
                params_check,
            )
            valid_ids: set[str] = {r[0] for r in result.fetchall()}
        except Exception as exc:
            logger.error("❌ unified_games lookup failed: %s", exc)
            valid_ids = set()

        upserted = 0
        for row in rows:
            if row["game_id"] not in valid_ids:
                logger.debug("⏭ Skipping %s — not in unified_games", row["game_id"])
                continue
            ext = row.get("ext", {})
            core_params = {
                "game_id": row["game_id"],
                "sport": row["sport"],
                "team": row["team"],
                "opponent": row["opponent"],
                "is_home": row["is_home"],
                "game_date": row["game_date"],
                "season": row["season"],
                "points_for": row.get("points_for"),
                "points_against": row.get("points_against"),
                "won": row.get("won"),
                "off_rating": row.get("off_rating"),
                "def_rating": row.get("def_rating"),
                "pace": row.get("pace"),
                "margin": row.get("margin"),
            }
            try:
                self.db.execute(
                    """
                    INSERT INTO team_game_stats
                        (game_id, sport, team, opponent, is_home, game_date, season,
                         points_for, points_against, won, off_rating, def_rating, pace, margin)
                    VALUES
                        (:game_id, :sport, :team, :opponent, :is_home, :game_date, :season,
                         :points_for, :points_against, :won, :off_rating, :def_rating, :pace, :margin)
                    ON CONFLICT (game_id, team) DO UPDATE SET
                        sport=EXCLUDED.sport, opponent=EXCLUDED.opponent,
                        is_home=EXCLUDED.is_home, game_date=EXCLUDED.game_date,
                        season=EXCLUDED.season, points_for=EXCLUDED.points_for,
                        points_against=EXCLUDED.points_against, won=EXCLUDED.won,
                        off_rating=EXCLUDED.off_rating, def_rating=EXCLUDED.def_rating,
                        pace=EXCLUDED.pace, margin=EXCLUDED.margin, updated_at=NOW()
                    """,
                    core_params,
                )
            except Exception as exc:
                logger.error(
                    "❌ Core upsert failed for %s/%s: %s",
                    row["game_id"],
                    row["team"],
                    exc,
                )
                continue

            if ext:
                ext_params = {
                    "game_id": row["game_id"],
                    "team": row["team"],
                    **{
                        k: ext.get(k)
                        for k in (
                            "fg_pct",
                            "fg3m",
                            "fg3a",
                            "fg3_pct",
                            "ast",
                            "reb",
                            "stl",
                            "blk",
                            "tov",
                            "pf",
                            "ts_pct",
                            "efg_pct",
                        )
                    },
                }
                try:
                    self.db.execute(
                        f"""
                        INSERT INTO {self.EXT_TABLE}
                            (game_id, team, fg_pct, fg3m, fg3a, fg3_pct,
                             ast, reb, stl, blk, tov, pf, ts_pct, efg_pct)
                        VALUES
                            (:game_id, :team, :fg_pct, :fg3m, :fg3a, :fg3_pct,
                             :ast, :reb, :stl, :blk, :tov, :pf, :ts_pct, :efg_pct)
                        ON CONFLICT (game_id, team) DO UPDATE SET
                            fg_pct=EXCLUDED.fg_pct, fg3m=EXCLUDED.fg3m,
                            fg3a=EXCLUDED.fg3a, fg3_pct=EXCLUDED.fg3_pct,
                            ast=EXCLUDED.ast, reb=EXCLUDED.reb, stl=EXCLUDED.stl,
                            blk=EXCLUDED.blk, tov=EXCLUDED.tov, pf=EXCLUDED.pf,
                            ts_pct=EXCLUDED.ts_pct, efg_pct=EXCLUDED.efg_pct
                        """,
                        ext_params,
                    )
                except Exception as exc:
                    logger.warning(
                        "⚠️ Ext upsert failed for %s/%s: %s",
                        row["game_id"],
                        row["team"],
                        exc,
                    )

            upserted += 1

        logger.info("✓ Upserted %d/%d CBB rows", upserted, len(rows))
        return upserted
