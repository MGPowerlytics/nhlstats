"""
MLB box-score fetcher.

Data sources
------------
1. MLB Stats API — live feed endpoint::

    GET https://statsapi.mlb.com/api/v1.1/game/{gamePk}/feed/live

   Used for game metadata: official date, team abbreviations, final scores,
   and game status.

2. MLB Stats API — boxscore endpoint::

    GET https://statsapi.mlb.com/api/v1/game/{gamePk}/boxscore

   Used for per-team batting and pitching aggregates.

Rate limit: ``RATE_LIMIT_SECONDS = 0.5`` (2 req/s).

Extension table: ``mlb_team_game_stats_ext``
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import requests

from plugins.db_manager import DBManager
from plugins.stats.advanced_stats import compute_baseball_woba
from plugins.stats.base import BoxScoreFetcher
from plugins.utils import parse_innings_pitched, to_int, to_float

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# wOBA linear weights (FanGraphs 2023 season values)
# ---------------------------------------------------------------------------
_WOBA_WEIGHTS: dict[str, float] = {
    "bb": 0.690,
    "hbp": 0.722,
    "1b": 0.880,
    "2b": 1.249,
    "3b": 1.576,
    "hr": 2.031,
}

_FINAL_STATES: frozenset[str] = frozenset(
    {"Final", "Game Over", "Completed Early", "Postponed"}
)

_LIVE_FEED_URL: str = "https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
_BOXSCORE_URL: str = "https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
_SCHEDULE_URL: str = (
    "https://statsapi.mlb.com/api/v1/schedule"
    "?sportId=1&startDate={start}&endDate={end}&hydrate=team"
)




class MLBBoxScoreFetcher(BoxScoreFetcher):
    """Fetch and persist MLB team-level box-score data from statsapi.mlb.com.

    Queries ``/api/v1.1/game/{gamePk}/feed/live`` for game metadata and
    ``/api/v1/game/{gamePk}/boxscore`` for team batting / pitching aggregates.
    wOBA is derived via :func:`~plugins.stats.advanced_stats.compute_baseball_woba`.

    Example:
        >>> fetcher = MLBBoxScoreFetcher()
        >>> rows = fetcher.fetch_game_stats("745431")
        >>> fetcher.upsert_rows(rows)
    """

    SPORT: str = "MLB"
    RATE_LIMIT_SECONDS: float = 0.5  # 2 req/s
    EXT_TABLE: str = "mlb_team_game_stats_ext"

    def __init__(self, db: DBManager | None = None) -> None:
        """Initialise the MLB fetcher.

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

    def _fetch_live_feed(self, game_id: str) -> dict[str, Any]:
        """Fetch and return the parsed live-feed JSON for *game_id*."""
        self._rate_limit()
        url = _LIVE_FEED_URL.format(game_pk=game_id)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    def _fetch_boxscore(self, game_id: str) -> dict[str, Any]:
        """Fetch and return the parsed boxscore JSON for *game_id*."""
        self._rate_limit()
        url = _BOXSCORE_URL.format(game_pk=game_id)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    def _build_row(
        self,
        game_id: str,
        game_date: date,
        season: str,
        side: str,
        team_abbr: str,
        opp_abbr: str,
        runs_for: int,
        runs_against: int,
        batting: dict[str, Any],
        pitching: dict[str, Any],
        fielding: dict[str, Any],
    ) -> dict[str, Any]:
        """Assemble a normalised team-row dict from raw MLB API dicts.

        Args:
            game_id: MLB gamePk string.
            game_date: Official game date.
            season: Season year string (e.g. ``"2024"``).
            side: ``"home"`` or ``"away"``.
            team_abbr: Abbreviation for this team.
            opp_abbr: Abbreviation for the opponent.
            runs_for: Runs scored by this team.
            runs_against: Runs allowed by this team.
            batting: ``teamStats.batting`` dict from the boxscore.
            pitching: ``teamStats.pitching`` dict from the boxscore.
            fielding: ``teamStats.fielding`` dict from the boxscore.

        Returns:
            Normalised row dict with an ``"ext"`` sub-dict.
        """
        hits = to_int(batting.get("hits"))
        doubles = to_int(batting.get("doubles"))
        triples = to_int(batting.get("triples"))
        home_runs = to_int(batting.get("homeRuns"))
        walks = to_int(batting.get("baseOnBalls"))
        hbp = to_int(batting.get("hitByPitch"))
        sac_flies = to_int(batting.get("sacFlies"))
        at_bats = to_int(batting.get("atBats"))
        strikeouts = to_int(batting.get("strikeOuts"))
        lob = to_int(batting.get("leftOnBase"))
        rbi = to_int(batting.get("rbi"))
        stolen_bases = to_int(batting.get("stolenBases"))
        obp = to_float(batting.get("obp"))
        slg = to_float(batting.get("slg"))
        errors = to_int(fielding.get("errors"))

        singles = max(0, hits - doubles - triples - home_runs)
        woba = compute_baseball_woba(
            _WOBA_WEIGHTS,
            {
                "ab": at_bats,
                "bb": walks,
                "sf": sac_flies,
                "hbp": hbp,
                "1b": singles,
                "2b": doubles,
                "3b": triples,
                "hr": home_runs,
            },
        )

        ip = parse_innings_pitched(pitching.get("inningsPitched", "0.0"))
        earned_runs = to_int(pitching.get("earnedRuns"))
        era = round(earned_runs / ip * 9, 2) if ip > 0 else 0.0

        return {
            "game_id": game_id,
            "sport": self.SPORT,
            "team": team_abbr,
            "opponent": opp_abbr,
            "is_home": side == "home",
            "game_date": game_date,
            "season": season,
            "points_for": runs_for,
            "points_against": runs_against,
            "won": runs_for > runs_against,
            "margin": runs_for - runs_against,
            "ext": {
                "hits": hits,
                "errors": errors,
                "lob": lob,
                "doubles": doubles,
                "triples": triples,
                "home_runs": home_runs,
                "rbi": rbi,
                "stolen_bases": stolen_bases,
                "strikeouts": strikeouts,
                "walks": walks,
                "at_bats": at_bats,
                "obp": obp,
                "slg": slg,
                "ops": round(obp + slg, 4),
                "woba": round(woba, 4),
                "era": era,
            },
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_game_stats(self, game_id: str) -> list[dict[str, Any]]:
        """Fetch team box-score for one MLB game.

        Hits the live-feed endpoint for game metadata and the boxscore
        endpoint for batting/pitching aggregates.  Returns an empty list
        (with a logged warning) if *game_id* is not in ``unified_games`` or
        the game is not yet in a final state.

        Args:
            game_id: MLB game primary key (``gamePk``), e.g. ``"745431"``.

        Returns:
            List of two dicts (home team, away team), or empty list if the
            game is not in ``unified_games`` or is not yet final.
        """
        if not self._game_in_unified(game_id):
            logger.warning("⚠️  MLB game %s not in unified_games — skipping", game_id)
            return []

        live = self._fetch_live_feed(game_id)
        game_data = live.get("gameData", {})

        status = game_data.get("status", {}).get("detailedState", "")
        if status not in _FINAL_STATES:
            logger.warning(
                "⚠️  MLB game %s status='%s' — not final, skipping", game_id, status
            )
            return []

        official_date = game_data.get("datetime", {}).get("officialDate", "")
        game_date = date.fromisoformat(official_date) if official_date else date.today()
        season = str(game_date.year)

        linescore_teams = live.get("liveData", {}).get("linescore", {}).get("teams", {})
        home_runs = to_int(linescore_teams.get("home", {}).get("runs"))
        away_runs = to_int(linescore_teams.get("away", {}).get("runs"))

        gd_teams = game_data.get("teams", {})
        home_abbr: str = gd_teams.get("home", {}).get("abbreviation", "HOME")
        away_abbr: str = gd_teams.get("away", {}).get("abbreviation", "AWAY")

        boxscore = self._fetch_boxscore(game_id)
        bs_teams = boxscore.get("teams", {})

        rows: list[dict[str, Any]] = []
        for side, abbr, opp, runs_for, runs_against in [
            ("home", home_abbr, away_abbr, home_runs, away_runs),
            ("away", away_abbr, home_abbr, away_runs, home_runs),
        ]:
            team_bs = bs_teams.get(side, {})
            team_stats = team_bs.get("teamStats", {})
            batting = team_stats.get("batting", {})
            pitching = team_stats.get("pitching", {})
            fielding = team_stats.get("fielding", {})

            rows.append(
                self._build_row(
                    game_id=game_id,
                    game_date=game_date,
                    season=season,
                    side=side,
                    team_abbr=abbr,
                    opp_abbr=opp,
                    runs_for=runs_for,
                    runs_against=runs_against,
                    batting=batting,
                    pitching=pitching,
                    fielding=fielding,
                )
            )

        return rows

    def fetch_date_range(self, start: date, end: date) -> list[dict[str, Any]]:
        """Fetch MLB box-scores for all games in an inclusive date range.

        Queries ``statsapi.mlb.com/api/v1/schedule`` for ``gamePk`` values,
        then calls :meth:`fetch_game_stats` for each, respecting the 2 req/s
        rate limit.

        Args:
            start: First date (inclusive).
            end: Last date (inclusive).

        Returns:
            Flat list of normalised team-row dicts.
        """
        self._rate_limit()
        sched_url = _SCHEDULE_URL.format(start=start.isoformat(), end=end.isoformat())
        resp = requests.get(sched_url, timeout=30)
        resp.raise_for_status()
        sched_data = resp.json()

        game_pks: list[str] = []
        for day in sched_data.get("dates", []):
            for game in day.get("games", []):
                pk = game.get("gamePk")
                if pk is not None:
                    game_pks.append(str(pk))

        all_rows: list[dict[str, Any]] = []
        for gid in game_pks:
            try:
                all_rows.extend(self.fetch_game_stats(gid))
            except Exception as exc:  # noqa: BLE001
                logger.warning("⚠️  MLB game %s failed: %s", gid, exc)

        return all_rows

    def upsert_rows(self, rows: list[dict[str, Any]]) -> int:
        """Persist MLB rows to ``team_game_stats`` and ``mlb_team_game_stats_ext``.

        Each row is split into a core dict (written to ``team_game_stats``)
        and an ``"ext"`` sub-dict (written to ``mlb_team_game_stats_ext``).
        Both writes use ``ON CONFLICT DO UPDATE`` semantics.

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
            INSERT INTO mlb_team_game_stats_ext
                (game_id, team, hits, errors, lob, doubles, triples, home_runs,
                 rbi, stolen_bases, strikeouts, walks, at_bats, obp, slg, ops,
                 woba, era)
            VALUES
                (:game_id, :team, :hits, :errors, :lob, :doubles, :triples,
                 :home_runs, :rbi, :stolen_bases, :strikeouts, :walks, :at_bats,
                 :obp, :slg, :ops, :woba, :era)
            ON CONFLICT (game_id, team) DO UPDATE SET
                hits         = EXCLUDED.hits,
                errors       = EXCLUDED.errors,
                lob          = EXCLUDED.lob,
                doubles      = EXCLUDED.doubles,
                triples      = EXCLUDED.triples,
                home_runs    = EXCLUDED.home_runs,
                rbi          = EXCLUDED.rbi,
                stolen_bases = EXCLUDED.stolen_bases,
                strikeouts   = EXCLUDED.strikeouts,
                walks        = EXCLUDED.walks,
                at_bats      = EXCLUDED.at_bats,
                obp          = EXCLUDED.obp,
                slg          = EXCLUDED.slg,
                ops          = EXCLUDED.ops,
                woba         = EXCLUDED.woba,
                era          = EXCLUDED.era
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
                    **ext,
                }
                self.db.execute(ext_sql, ext_params)

            count += 1

        return count
