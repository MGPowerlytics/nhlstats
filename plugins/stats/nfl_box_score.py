"""
NFL box-score fetcher.

Data source
-----------
``nfl_data_py`` (PyPI) — specifically:

* ``nfl_data_py.import_schedules(years)`` — per-game schedule DataFrame
  including ``game_id``, ``home_team``, ``away_team``, ``home_score``,
  ``away_score``, ``gameday``, ``season``, and ``week``.
* ``nfl_data_py.import_pbp_data(years)`` — play-by-play DataFrame used to
  aggregate per-team EPA, success-rate, passing/rushing yards, turnovers,
  third-down conversion rate, and more.

Caching: schedule and PBP DataFrames are cached in module-level dicts keyed
by season year so that ``fetch_date_range`` only downloads each season once.

Rate limit: ``RATE_LIMIT_SECONDS = 1.0`` between season bulk downloads.

Extension table: ``nfl_team_game_stats_ext``
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from plugins.db_manager import DBManager
from plugins.stats.advanced_stats import compute_nfl_epa_aggregate
from plugins.stats.base import BoxScoreFetcher

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional nfl_data_py import — graceful degradation if unavailable
# ---------------------------------------------------------------------------
try:
    import nfl_data_py as nfl  # type: ignore[import]

    _NFL_DATA_AVAILABLE = True
except ImportError:  # pragma: no cover - covered in import-only environments
    nfl = None
    _NFL_DATA_AVAILABLE = False
import pandas as pd

# Module-level season caches (reset only by tests via ``_clear_caches()``)
_schedule_cache: dict[int, Any] = {}
_pbp_cache: dict[int, Any] = {}


def _clear_caches() -> None:
    """Clear module-level season caches.  Used by tests to isolate state."""
    _schedule_cache.clear()
    _pbp_cache.clear()


def _season_from_game_id(game_id: str) -> int:
    """Parse the season year from a nfl_data_py game_id string.

    Args:
        game_id: nfl_data_py game identifier, e.g. ``"2023_01_DET_KC"``.

    Returns:
        Season year as an integer (e.g. ``2023``).

    Raises:
        ValueError: If *game_id* does not start with a 4-digit year.
    """
    return int(game_id.split("_")[0])


def _safe_int(val: Any, default: int = 0) -> int:
    """Coerce *val* to int, returning *default* on failure."""
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Coerce *val* to float, returning *default* on failure."""
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


class NFLBoxScoreFetcher(BoxScoreFetcher):
    """Fetch and persist NFL team-level box-score data via ``nfl_data_py``.

    Uses ``import_schedules`` for game-level metadata and
    ``import_pbp_data`` aggregated via
    :func:`~plugins.stats.advanced_stats.compute_nfl_epa_aggregate` to derive
    per-game EPA and success-rate metrics.

    Example:
        >>> fetcher = NFLBoxScoreFetcher()
        >>> rows = fetcher.fetch_game_stats("2023_01_DET_KC")
        >>> fetcher.upsert_rows(rows)
    """

    SPORT: str = "NFL"
    RATE_LIMIT_SECONDS: float = 1.0
    EXT_TABLE: str = "nfl_team_game_stats_ext"

    def __init__(self, db: DBManager | None = None) -> None:
        """Initialise the NFL fetcher.

        Args:
            db: Optional shared :class:`~plugins.db_manager.DBManager`.
        """
        super().__init__(db=db)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _game_in_unified(self, game_id: str) -> bool:
        """Return True if *game_id* exists in ``unified_games``."""
        result = self.db.execute(
            "SELECT 1 FROM unified_games WHERE game_id = :gid",
            {"gid": game_id},
        )
        return result.fetchone() is not None

    def _load_schedule(self, season: int) -> Any:
        """Load (and cache) the nfl_data_py schedule DataFrame for *season*.

        Args:
            season: NFL season year (e.g. ``2023``).

        Returns:
            :class:`pandas.DataFrame` of the season schedule.
        """
        if season not in _schedule_cache:
            self._rate_limit()
            _schedule_cache[season] = nfl.import_schedules([season])
        return _schedule_cache[season]

    def _load_pbp(self, season: int) -> Any:
        """Load (and cache) the nfl_data_py PBP DataFrame for *season*.

        Args:
            season: NFL season year.

        Returns:
            :class:`pandas.DataFrame` of play-by-play for the season, or an
            empty DataFrame if the data is unavailable.
        """
        if season not in _pbp_cache:
            self._rate_limit()
            try:
                _pbp_cache[season] = nfl.import_pbp_data([season], downcast=False)
            except Exception as exc:  # noqa: BLE001
                logger.warning("⚠️  PBP data unavailable for season %s: %s", season, exc)
                import pandas as _pd  # local import to keep module importable

                _pbp_cache[season] = _pd.DataFrame()
        return _pbp_cache[season]

    def _aggregate_team_pbp(
        self,
        game_pbp: Any,
        team: str,
    ) -> dict[str, Any]:
        """Aggregate play-by-play stats for *team* in *game_pbp*.

        Args:
            game_pbp: PBP DataFrame filtered to a single game.
            team: Team abbreviation (posteam perspective).

        Returns:
            Dict of aggregated stats keyed by ext-table column name.
        """
        # Plays where this team had possession (offense)
        off = (
            game_pbp[game_pbp.get("posteam", pd.Series(dtype=str)) == team]
            if ("posteam" in game_pbp.columns)
            else game_pbp.iloc[0:0]
        )

        passing = (
            off[off.get("pass", pd.Series(dtype=float)).fillna(0) == 1]
            if ("pass" in off.columns)
            else off.iloc[0:0]
        )

        rushing = (
            off[off.get("rush", pd.Series(dtype=float)).fillna(0) == 1]
            if ("rush" in off.columns)
            else off.iloc[0:0]
        )

        passing_yards = _safe_int(
            passing["passing_yards"].sum() if "passing_yards" in passing.columns else 0
        )
        passing_tds = _safe_int(
            passing["touchdown"].sum() if "touchdown" in passing.columns else 0
        )
        passing_ints = _safe_int(
            passing["interception"].sum() if "interception" in passing.columns else 0
        )
        rushing_yards = _safe_int(
            rushing["rushing_yards"].sum() if "rushing_yards" in rushing.columns else 0
        )
        rushing_tds = _safe_int(
            rushing["touchdown"].sum() if "touchdown" in rushing.columns else 0
        )
        rushing_attempts = len(rushing)
        total_yards = passing_yards + rushing_yards

        turnovers = _safe_int(
            off["interception"].sum() if "interception" in off.columns else 0
        ) + _safe_int(off["fumble_lost"].sum() if "fumble_lost" in off.columns else 0)

        third_conv = _safe_int(
            off["third_down_converted"].sum()
            if "third_down_converted" in off.columns
            else 0
        )
        third_fail = _safe_int(
            off["third_down_failed"].sum() if "third_down_failed" in off.columns else 0
        )
        third_att = third_conv + third_fail
        third_pct = round(third_conv / third_att, 4) if third_att > 0 else 0.0

        first_downs = _safe_int(
            (
                off.get("first_down_rush", pd.Series(dtype=float)).fillna(0)
                + off.get("first_down_pass", pd.Series(dtype=float)).fillna(0)
                + off.get("first_down_penalty", pd.Series(dtype=float)).fillna(0)
            ).sum()
            if "first_down_rush" in off.columns
            else 0
        )

        # Penalties where this team was the offending team
        pen_plays = (
            game_pbp[
                (game_pbp.get("penalty", pd.Series(dtype=float)).fillna(0) == 1)
                & (
                    game_pbp.get("penalty_team", pd.Series(dtype=str)).fillna("")
                    == team
                )
            ]
            if "penalty_team" in game_pbp.columns
            else game_pbp.iloc[0:0]
        )
        penalties = len(pen_plays)
        penalty_yards = _safe_int(
            pen_plays["penalty_yards"].sum()
            if "penalty_yards" in pen_plays.columns
            else 0
        )

        # Sacks allowed = times this team's offence was sacked
        sacks_allowed = _safe_int(off["sack"].sum() if "sack" in off.columns else 0)

        # EPA (offensive plays)
        epa_dict = compute_nfl_epa_aggregate(off)

        return {
            "passing_yards": passing_yards,
            "passing_tds": passing_tds,
            "passing_ints": passing_ints,
            "rushing_yards": rushing_yards,
            "rushing_tds": rushing_tds,
            "rushing_attempts": rushing_attempts,
            "total_yards": total_yards,
            "turnovers": turnovers,
            "third_down_conversions": third_conv,
            "third_down_attempts": third_att,
            "third_down_pct": third_pct,
            "time_of_possession": None,  # not derivable from standard PBP
            "penalties": penalties,
            "penalty_yards": penalty_yards,
            "sacks_allowed": sacks_allowed,
            "first_downs": first_downs,
            "epa_offense_mean": round(_safe_float(epa_dict.get("epa_offense_mean")), 4),
            "epa_defense_mean": round(_safe_float(epa_dict.get("epa_defense_mean")), 4),
            "success_rate": round(_safe_float(epa_dict.get("success_rate")), 4),
        }

    def _build_rows_for_game(
        self,
        game_id: str,
        game_row: Any,
        game_pbp: Any,
    ) -> list[dict[str, Any]]:
        """Build home + away row dicts for a single game.

        Args:
            game_id: nfl_data_py game identifier.
            game_row: Single-row schedule Series for the game.
            game_pbp: PBP DataFrame filtered to this game_id.

        Returns:
            List of two row dicts (home, away).
        """
        gameday_val = game_row.get("gameday", "")
        try:
            game_date = date.fromisoformat(str(gameday_val)[:10])
        except (TypeError, ValueError):
            game_date = date.today()
        season = str(int(game_row.get("season", _season_from_game_id(game_id))))

        home_team: str = str(game_row.get("home_team", "HOME"))
        away_team: str = str(game_row.get("away_team", "AWAY"))
        home_score = _safe_int(game_row.get("home_score"))
        away_score = _safe_int(game_row.get("away_score"))

        rows: list[dict[str, Any]] = []
        for team, opp, is_home, pts_for, pts_against in [
            (home_team, away_team, True, home_score, away_score),
            (away_team, home_team, False, away_score, home_score),
        ]:
            pbp_agg = self._aggregate_team_pbp(game_pbp, team)

            rows.append(
                {
                    "game_id": game_id,
                    "sport": self.SPORT,
                    "team": team,
                    "opponent": opp,
                    "is_home": is_home,
                    "game_date": game_date,
                    "season": season,
                    "points_for": pts_for,
                    "points_against": pts_against,
                    "won": pts_for > pts_against,
                    "margin": pts_for - pts_against,
                    "ext": {
                        "passing_yards": pbp_agg["passing_yards"],
                        "passing_tds": pbp_agg["passing_tds"],
                        "passing_ints": pbp_agg["passing_ints"],
                        "rushing_yards": pbp_agg["rushing_yards"],
                        "rushing_tds": pbp_agg["rushing_tds"],
                        "rushing_attempts": pbp_agg["rushing_attempts"],
                        "total_yards": pbp_agg["total_yards"],
                        "turnovers": pbp_agg["turnovers"],
                        "third_down_conversions": pbp_agg["third_down_conversions"],
                        "third_down_attempts": pbp_agg["third_down_attempts"],
                        "third_down_pct": pbp_agg["third_down_pct"],
                        "time_of_possession": pbp_agg["time_of_possession"],
                        "penalties": pbp_agg["penalties"],
                        "penalty_yards": pbp_agg["penalty_yards"],
                        "sacks_allowed": pbp_agg["sacks_allowed"],
                        "first_downs": pbp_agg["first_downs"],
                        "epa_offense_mean": pbp_agg["epa_offense_mean"],
                        "epa_defense_mean": pbp_agg["epa_defense_mean"],
                        "success_rate": pbp_agg["success_rate"],
                    },
                }
            )

        return rows

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_game_stats(self, game_id: str) -> list[dict[str, Any]]:
        """Fetch team box-score for one NFL game.

        Filters ``import_schedules`` and ``import_pbp_data`` output to the
        single *game_id* row, then produces two normalised team dicts.
        Returns an empty list (with a logged warning) if *game_id* is not in
        ``unified_games``.

        Args:
            game_id: nfl_data_py game identifier string, e.g.
                ``"2023_01_DET_KC"``.

        Returns:
            List of two dicts (home team, away team), or empty list if the
            game is not found in ``unified_games``.

        Raises:
            RuntimeError: If ``nfl_data_py`` is not installed.
        """
        if not _NFL_DATA_AVAILABLE:
            raise RuntimeError(
                "nfl_data_py is not installed; cannot fetch NFL box scores"
            )

        if not self._game_in_unified(game_id):
            logger.warning("⚠️  NFL game %s not in unified_games — skipping", game_id)
            return []

        season = _season_from_game_id(game_id)
        schedule_df = self._load_schedule(season)
        game_rows = schedule_df[schedule_df["game_id"] == game_id]
        if game_rows.empty:
            logger.warning(
                "⚠️  NFL game %s not found in %d schedule — skipping", game_id, season
            )
            return []

        game_row = game_rows.iloc[0]
        pbp_df = self._load_pbp(season)
        game_pbp = (
            pbp_df[pbp_df["game_id"] == game_id]
            if "game_id" in pbp_df.columns
            else pbp_df.iloc[0:0]
        )

        return self._build_rows_for_game(game_id, game_row, game_pbp)

    def fetch_date_range(self, start: date, end: date) -> list[dict[str, Any]]:
        """Fetch NFL box-scores for all games in an inclusive date range.

        Determines the NFL seasons that overlap [*start*, *end*], bulk-loads
        schedule and PBP data once per season (cached), then filters to the
        requested date range and processes each game.

        Args:
            start: First date (inclusive).
            end: Last date (inclusive).

        Returns:
            Flat list of normalised team-row dicts.

        Raises:
            RuntimeError: If ``nfl_data_py`` is not installed.
        """
        if not _NFL_DATA_AVAILABLE:
            raise RuntimeError(
                "nfl_data_py is not installed; cannot fetch NFL box scores"
            )

        # Determine seasons covered by [start, end]
        def _year_to_season(y: int, m: int) -> int:
            return y if m >= 9 else y - 1

        seasons = set()
        for yr in range(start.year - 1, end.year + 1):
            for mo in (1, 9):
                seasons.add(_year_to_season(yr, mo))

        all_rows: list[dict[str, Any]] = []

        for season in sorted(seasons):
            schedule_df = self._load_schedule(season)
            if "gameday" not in schedule_df.columns:
                continue

            mask = (
                pd.to_datetime(schedule_df["gameday"], errors="coerce").dt.date >= start
            ) & (pd.to_datetime(schedule_df["gameday"], errors="coerce").dt.date <= end)
            filtered = schedule_df[mask]

            pbp_df = self._load_pbp(season)

            for _, game_row in filtered.iterrows():
                gid = str(game_row["game_id"])
                if not self._game_in_unified(gid):
                    logger.warning(
                        "⚠️  NFL game %s not in unified_games — skipping", gid
                    )
                    continue
                game_pbp = (
                    pbp_df[pbp_df["game_id"] == gid]
                    if "game_id" in pbp_df.columns
                    else pbp_df.iloc[0:0]
                )
                try:
                    all_rows.extend(self._build_rows_for_game(gid, game_row, game_pbp))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("⚠️  NFL game %s failed: %s", gid, exc)

        return all_rows

    def upsert_rows(self, rows: list[dict[str, Any]]) -> int:
        """Persist NFL rows to ``team_game_stats`` and ``nfl_team_game_stats_ext``.

        Splits each row into core + ext dicts and issues upserts with
        ``ON CONFLICT DO UPDATE`` semantics.

        Args:
            rows: Normalised team-game dicts as returned by
                :meth:`fetch_game_stats` or :meth:`fetch_date_range`.

        Returns:
            Total number of rows upserted across both tables.
        """
        if not rows:
            return 0

        core_sql = """
            INSERT INTO team_game_stats
                (game_id, sport, team, opponent, is_home, game_date, season,
                 points_for, points_against, won, margin, updated_at)
            VALUES
                (:game_id, :sport, :team, :opponent, :is_home, :game_date, :season,
                 :points_for, :points_against, :won, :margin, NOW())
            ON CONFLICT (game_id, team) DO UPDATE SET
                points_for     = EXCLUDED.points_for,
                points_against = EXCLUDED.points_against,
                won            = EXCLUDED.won,
                margin         = EXCLUDED.margin,
                updated_at     = NOW()
        """

        ext_sql = """
            INSERT INTO nfl_team_game_stats_ext
                (game_id, team, passing_yards, passing_tds, passing_ints,
                 rushing_yards, rushing_tds, rushing_attempts, total_yards,
                 turnovers, third_down_conversions, third_down_attempts,
                 third_down_pct, time_of_possession, penalties, penalty_yards,
                 sacks_allowed, first_downs)
            VALUES
                (:game_id, :team, :passing_yards, :passing_tds, :passing_ints,
                 :rushing_yards, :rushing_tds, :rushing_attempts, :total_yards,
                 :turnovers, :third_down_conversions, :third_down_attempts,
                 :third_down_pct, :time_of_possession, :penalties, :penalty_yards,
                 :sacks_allowed, :first_downs)
            ON CONFLICT (game_id, team) DO UPDATE SET
                passing_yards          = EXCLUDED.passing_yards,
                passing_tds            = EXCLUDED.passing_tds,
                passing_ints           = EXCLUDED.passing_ints,
                rushing_yards          = EXCLUDED.rushing_yards,
                rushing_tds            = EXCLUDED.rushing_tds,
                rushing_attempts       = EXCLUDED.rushing_attempts,
                total_yards            = EXCLUDED.total_yards,
                turnovers              = EXCLUDED.turnovers,
                third_down_conversions = EXCLUDED.third_down_conversions,
                third_down_attempts    = EXCLUDED.third_down_attempts,
                third_down_pct         = EXCLUDED.third_down_pct,
                time_of_possession     = EXCLUDED.time_of_possession,
                penalties              = EXCLUDED.penalties,
                penalty_yards          = EXCLUDED.penalty_yards,
                sacks_allowed          = EXCLUDED.sacks_allowed,
                first_downs            = EXCLUDED.first_downs
        """

        count = 0
        for row in rows:
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
                "margin": row.get("margin"),
            }
            self.db.execute(core_sql, core_params)

            if ext:
                ext_params = {
                    "game_id": row["game_id"],
                    "team": row["team"],
                    "passing_yards": ext.get("passing_yards"),
                    "passing_tds": ext.get("passing_tds"),
                    "passing_ints": ext.get("passing_ints"),
                    "rushing_yards": ext.get("rushing_yards"),
                    "rushing_tds": ext.get("rushing_tds"),
                    "rushing_attempts": ext.get("rushing_attempts"),
                    "total_yards": ext.get("total_yards"),
                    "turnovers": ext.get("turnovers"),
                    "third_down_conversions": ext.get("third_down_conversions"),
                    "third_down_attempts": ext.get("third_down_attempts"),
                    "third_down_pct": ext.get("third_down_pct"),
                    "time_of_possession": ext.get("time_of_possession"),
                    "penalties": ext.get("penalties"),
                    "penalty_yards": ext.get("penalty_yards"),
                    "sacks_allowed": ext.get("sacks_allowed"),
                    "first_downs": ext.get("first_downs"),
                }
                self.db.execute(ext_sql, ext_params)

            count += 1

        return count
