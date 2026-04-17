"""
NBA box-score fetcher.

Data source
-----------
``nba_api`` (PyPI: ``nba_api``) — specifically:
  - ``nba_api.stats.endpoints.BoxScoreTraditionalV2``  for counting stats
    (points, rebounds, assists, steals, blocks, turnovers, FG/3P/FT lines)
  - ``nba_api.stats.endpoints.BoxScoreAdvancedV2``     for advanced stats
    (eFG%, TS%, pace, ORtg, DRtg, etc.)
  - ``nba_api.stats.endpoints.LeagueGameFinder``       for date-range enumeration

Rate limit: ~3 requests / second (``RATE_LIMIT_SECONDS = 0.34``).

Extension table: ``nba_team_game_stats_ext``
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd
from nba_api.stats.endpoints import (
    boxscoreadvancedv2,
    boxscoretraditionalv2,
    leaguegamefinder,
)

from plugins.db_manager import DBManager
from plugins.stats.advanced_stats import compute_basketball_efg, compute_basketball_ts
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


class NBABoxScoreFetcher(BoxScoreFetcher):
    """Fetch and persist NBA team-level box-score data via ``nba_api``.

    Example:
        >>> fetcher = NBABoxScoreFetcher()
        >>> rows = fetcher.fetch_game_stats("0022300001")
        >>> fetcher.upsert_rows(rows)

    Note:
        ``nba_api`` endpoints are scraped from stats.nba.com and carry an
        implicit rate limit.  ``RATE_LIMIT_SECONDS = 0.34`` allows up to
        ~3 requests/s; increase it if 429 responses are observed.
    """

    SPORT: str = "NBA"
    RATE_LIMIT_SECONDS: float = 0.34  # ~3 req/s
    EXT_TABLE: str = "nba_team_game_stats_ext"

    def __init__(self, db: DBManager | None = None) -> None:
        """Initialise the NBA fetcher.

        Args:
            db: Optional shared :class:`~plugins.db_manager.DBManager`.
        """
        super().__init__(db=db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_game_stats(self, game_id: str) -> list[dict[str, Any]]:
        """Fetch traditional + advanced team box-score for one NBA game.

        Calls ``BoxScoreTraditionalV2`` and ``BoxScoreAdvancedV2`` for
        *game_id* and merges the results into two dicts — one per team.
        The ``"ext"`` key on each dict contains NBA-specific advanced fields
        destined for ``nba_team_game_stats_ext``.

        Args:
            game_id: NBA game ID string (e.g. ``"0022300001"``).

        Returns:
            List of two dicts (home team, away team) in the canonical
            ``team_game_stats`` format.  Returns an empty list if the
            response cannot be parsed.
        """
        # -- Traditional stats (counting stats + game summary) --------
        self._rate_limit()
        trad_endpoint = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id)
        trad_df = trad_endpoint.team_stats.get_data_frame()
        summary_df = trad_endpoint.game_summary.get_data_frame()

        # -- Advanced stats (eFG%, TS%, pace, ratings) -----------------
        self._rate_limit()
        adv_endpoint = boxscoreadvancedv2.BoxScoreAdvancedV2(game_id=game_id)
        adv_df = adv_endpoint.team_stats.get_data_frame()

        if trad_df.empty or summary_df.empty:
            logger.warning("⚠️ NBA game %s returned empty data frames", game_id)
            return []

        # -- Game-level metadata from summary -------------------------
        game_date = str(summary_df["GAME_DATE_EST"].iloc[0])[:10]
        # Season encoded in game_id: "0022300001" → chars 3-4 = "23" → 2023
        try:
            season = str(2000 + int(game_id[3:5]))
        except (IndexError, ValueError):
            season = game_date[:4]
        home_team_id = int(summary_df["HOME_TEAM_ID"].iloc[0])

        # -- Merge traditional + advanced on TEAM_ID ------------------
        adv_cols = ["TEAM_ID"] + [
            c
            for c in (
                "OFF_RATING",
                "DEF_RATING",
                "PACE",
                "EFG_PCT",
                "TS_PCT",
                "USG_PCT",
            )
            if c in adv_df.columns
        ]
        merged = trad_df.merge(
            adv_df[adv_cols], on="TEAM_ID", how="left", suffixes=("", "_adv")
        )

        if len(merged) < 2:
            logger.warning("⚠️ NBA game %s has fewer than 2 team rows", game_id)
            return []

        rows: list[dict[str, Any]] = []
        for _, row in merged.iterrows():
            team_abbrev = str(row["TEAM_ABBREVIATION"])
            is_home = int(row["TEAM_ID"]) == home_team_id

            pts = int(row["PTS"]) if not pd.isna(row.get("PTS", float("nan"))) else 0
            opp_row = merged[merged["TEAM_ID"] != row["TEAM_ID"]].iloc[0]
            opp_abbrev = str(opp_row["TEAM_ABBREVIATION"])
            opp_pts = (
                int(opp_row["PTS"])
                if not pd.isna(opp_row.get("PTS", float("nan")))
                else 0
            )

            fgm = float(row.get("FGM") or 0)
            fg3m = float(row.get("FG3M") or 0)
            fga = float(row.get("FGA") or 0)
            fta = float(row.get("FTA") or 0)

            # Use advanced values when available; fall back to local computation
            raw_efg = row.get("EFG_PCT")
            raw_ts = row.get("TS_PCT")
            efg_pct = (
                float(raw_efg)
                if raw_efg is not None and not pd.isna(raw_efg)
                else compute_basketball_efg(fgm, fg3m, fga)
            )
            ts_pct = (
                float(raw_ts)
                if raw_ts is not None and not pd.isna(raw_ts)
                else compute_basketball_ts(pts, fga, fta)
            )

            def _f(key: str) -> float | None:
                """Return float or None for an optional column."""
                val = row.get(key)
                return float(val) if val is not None and not pd.isna(val) else None

            def _i(key: str) -> int | None:
                """Return int or None for an optional column."""
                val = row.get(key)
                return int(val) if val is not None and not pd.isna(val) else None

            core: dict[str, Any] = {
                "game_id": game_id,
                "sport": self.SPORT,
                "team": team_abbrev,
                "opponent": opp_abbrev,
                "is_home": bool(is_home),
                "game_date": game_date,
                "season": season,
                "points_for": pts,
                "points_against": opp_pts,
                "won": pts > opp_pts,
                "off_rating": _f("OFF_RATING"),
                "def_rating": _f("DEF_RATING"),
                "pace": _f("PACE"),
                "margin": pts - opp_pts,
            }
            ext: dict[str, Any] = {
                "game_id": game_id,
                "team": team_abbrev,
                "fg_pct": _f("FG_PCT"),
                "fg3m": _i("FG3M"),
                "fg3a": _i("FG3A"),
                "fg3_pct": _f("FG3_PCT"),
                "ast": _i("AST"),
                "reb": _i("REB"),
                "oreb": _i("OREB"),
                "dreb": _i("DREB"),
                "stl": _i("STL"),
                "blk": _i("BLK"),
                "tov": _i("TO"),
                "pf": _i("PF"),
                "ts_pct": round(ts_pct, 4),
                "efg_pct": round(efg_pct, 4),
                "usage_pct": _f("USG_PCT"),
            }
            rows.append({**core, "ext": ext})

        return rows

    def fetch_date_range(self, start: date, end: date) -> list[dict[str, Any]]:
        """Fetch NBA box-scores for all games played in a date range.

        Uses ``LeagueGameFinder`` to enumerate completed game IDs between
        *start* and *end*, then calls :meth:`fetch_game_stats` for each,
        respecting :attr:`RATE_LIMIT_SECONDS`.

        Args:
            start: First date (inclusive).
            end: Last date (inclusive).

        Returns:
            Flat list of normalised team-row dicts.
        """
        self._rate_limit()
        finder = leaguegamefinder.LeagueGameFinder(
            date_from_nullable=start.strftime("%m/%d/%Y"),
            date_to_nullable=end.strftime("%m/%d/%Y"),
            league_id_nullable="00",  # NBA
        )
        games_df = finder.get_data_frames()[0]
        # Each game appears once per team — deduplicate
        unique_game_ids: list[str] = games_df["GAME_ID"].unique().tolist()

        rows: list[dict[str, Any]] = []
        for gid in unique_game_ids:
            try:
                game_rows = self.fetch_game_stats(str(gid))
                rows.extend(game_rows)
            except Exception as exc:
                logger.warning("⚠️ Failed to fetch NBA game %s: %s", gid, exc)
        return rows

    def upsert_rows(self, rows: list[dict[str, Any]]) -> int:
        """Persist NBA rows to ``team_game_stats`` and ``nba_team_game_stats_ext``.

        Splits each row into a core dict (for ``team_game_stats``) and an
        ``"ext"`` dict (for ``nba_team_game_stats_ext``), then issues
        ``INSERT … ON CONFLICT DO UPDATE`` for both tables.  Rows whose
        ``game_id`` is absent from ``unified_games`` are skipped with a
        warning to avoid FK violations.

        Args:
            rows: Normalised team-game dicts as returned by
                :meth:`fetch_game_stats`.

        Returns:
            Total number of rows upserted (both tables counted as one
            logical row).
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
                self._upsert_nba_ext(ext, game_id, team)
            count += 1
        return count

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _game_exists_in_unified(self, game_id: str) -> bool:
        """Return True if *game_id* is present in ``unified_games``."""
        try:
            result = self.db.fetch_df(
                "SELECT 1 FROM unified_games WHERE game_id = :game_id LIMIT 1",
                {"game_id": game_id},
            )
            if result.empty:
                logger.warning(
                    "⚠️ NBA game %s not found in unified_games — skipping", game_id
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

    def _upsert_nba_ext(self, ext: dict[str, Any], game_id: str, team: str) -> None:
        """Upsert a single row to ``nba_team_game_stats_ext``."""
        sql = """
            INSERT INTO nba_team_game_stats_ext (
                game_id, team, fg_pct, fg3m, fg3a, fg3_pct,
                ast, reb, oreb, dreb, stl, blk, tov, pf,
                ts_pct, efg_pct, usage_pct
            ) VALUES (
                :game_id, :team, :fg_pct, :fg3m, :fg3a, :fg3_pct,
                :ast, :reb, :oreb, :dreb, :stl, :blk, :tov, :pf,
                :ts_pct, :efg_pct, :usage_pct
            )
            ON CONFLICT (game_id, team) DO UPDATE SET
                fg_pct     = EXCLUDED.fg_pct,
                fg3m       = EXCLUDED.fg3m,
                fg3a       = EXCLUDED.fg3a,
                fg3_pct    = EXCLUDED.fg3_pct,
                ast        = EXCLUDED.ast,
                reb        = EXCLUDED.reb,
                oreb       = EXCLUDED.oreb,
                dreb       = EXCLUDED.dreb,
                stl        = EXCLUDED.stl,
                blk        = EXCLUDED.blk,
                tov        = EXCLUDED.tov,
                pf         = EXCLUDED.pf,
                ts_pct     = EXCLUDED.ts_pct,
                efg_pct    = EXCLUDED.efg_pct,
                usage_pct  = EXCLUDED.usage_pct
        """
        try:
            self.db.execute(sql, ext)
        except Exception as exc:
            logger.error(
                "Error upserting nba_team_game_stats_ext for %s/%s: %s",
                game_id,
                team,
                exc,
            )
