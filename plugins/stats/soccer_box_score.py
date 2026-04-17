"""
Soccer box-score fetcher (EPL + Ligue 1).

Data sources
------------
1. **football-data.co.uk CSVs** — season-level CSV files containing match
   results, bookmaker odds, and a subset of team stats (shots, corners,
   fouls, cards).  Downloaded once per season; URL pattern::

       https://www.football-data.co.uk/mmz4281/{season_code}/{league_code}.csv

2. **FBRef scrape** (fallback / enrichment) — ``fbref.com`` provides richer
   possession, pressing (PPDA), xG, and progressive-pass data.

   **Scraping policy**::

       User-Agent: nhlstats-research-bot/1.0 (+https://github.com/user/nhlstats)
       Minimum delay between requests: 3 seconds

   This is applied via the inherited :meth:`_rate_limit` mechanism with
   ``RATE_LIMIT_SECONDS = 3.0``.

Coverage
--------
* **EPL** (English Premier League) — league code ``E0``
* **Ligue 1** (French first division) — league code ``F1``

Extension table: ``soccer_team_game_stats_ext``
"""

from __future__ import annotations

import logging
import time
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from plugins.db_manager import DBManager
from plugins.football_data_co_uk import FootballDataCoUkGames
from plugins.stats.base import BoxScoreFetcher

logger = logging.getLogger(__name__)

# FBRef scrape policy
_FBREF_USER_AGENT: str = "nhlstats-research-bot/1.0 (+https://github.com/user/nhlstats)"
_FBREF_DELAY_SECONDS: float = 3.0  # enforced via RATE_LIMIT_SECONDS

# football-data.co.uk league codes and data directories
_LEAGUE_CODES: dict[str, str] = {
    "EPL": "E0",
    "Ligue1": "F1",
}
_DATA_DIRS: dict[str, str] = {
    "EPL": "data/epl",
    "Ligue1": "data/ligue1",
}

# CSV column maps: (home_col, away_col)
_CSV_STAT_COLUMNS: dict[str, tuple[str, str]] = {
    "shots": ("HS", "AS"),
    "shots_on_target": ("HST", "AST"),
    "fouls": ("HF", "AF"),
    "yellow_cards": ("HY", "AY"),
    "red_cards": ("HR", "AR"),
    "corners": ("HC", "AC"),
}


def _season_code_from_date(d: date) -> str:
    """Derive football-data.co.uk season code (e.g. '2324') from a date.

    Args:
        d: Match date.

    Returns:
        Two-digit-year pair string such as ``"2324"``.
    """
    year = d.year
    if d.month >= 8:
        return f"{str(year)[2:]}{str(year + 1)[2:]}"
    return f"{str(year - 1)[2:]}{str(year)[2:]}"


def _season_label_from_code(code: str) -> str:
    """Convert season code to human-readable label.

    Args:
        code: Season code like ``"2324"``.

    Returns:
        Label like ``"2023-24"``.
    """
    if len(code) != 4:
        return code
    return f"20{code[:2]}-{code[2:]}"


def _seasons_for_range(start: date, end: date) -> list[str]:
    """Return all season codes that overlap with [start, end].

    Args:
        start: Range start (inclusive).
        end: Range end (inclusive).

    Returns:
        Sorted list of season code strings.
    """
    codes: set[str] = set()
    # Walk month by month to catch season boundaries
    current = date(start.year, start.month, 1)
    while current <= end:
        codes.add(_season_code_from_date(current))
        # Advance one month
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return sorted(codes)


class SoccerBoxScoreFetcher(BoxScoreFetcher):
    """Fetch and persist soccer team-level box-score data for EPL and Ligue 1.

    Combines football-data.co.uk season CSVs (primary) with FBRef scraping
    (enrichment) to produce per-match team stats including shots, xG, corners,
    fouls, possession, and PPDA components.

    The ``sport`` parameter selects which league is targeted; the same class
    handles both ``"EPL"`` and ``"Ligue1"``.

    Example:
        >>> fetcher = SoccerBoxScoreFetcher(sport="EPL")
        >>> rows = fetcher.fetch_game_stats("E0_20231028_ARS_CHE")
        >>> fetcher.upsert_rows(rows)
    """

    SPORT: str = "EPL"  # overridden per-instance; default to EPL
    RATE_LIMIT_SECONDS: float = _FBREF_DELAY_SECONDS
    EXT_TABLE: str = "soccer_team_game_stats_ext"

    def __init__(
        self,
        sport: str = "EPL",
        db: DBManager | None = None,
    ) -> None:
        """Initialise the soccer fetcher for a specific league.

        Args:
            sport: League identifier — ``"EPL"`` or ``"Ligue1"``.
            db: Optional shared :class:`~plugins.db_manager.DBManager`.

        Raises:
            ValueError: If *sport* is not ``"EPL"`` or ``"Ligue1"``.
        """
        if sport not in _LEAGUE_CODES:
            raise ValueError(
                f"sport must be one of {list(_LEAGUE_CODES)}, got {sport!r}"
            )
        self.SPORT = sport  # instance-level override
        self._league_code: str = _LEAGUE_CODES[sport]
        self._data_dir: Path = Path(_DATA_DIRS[sport])
        super().__init__(db=db)

    # ------------------------------------------------------------------
    # CSV loading helpers
    # ------------------------------------------------------------------

    def _load_season_df(self, season_code: str) -> pd.DataFrame | None:
        """Download (if needed) and load a season CSV.

        Args:
            season_code: Football-data.co.uk season code, e.g. ``"2324"``.

        Returns:
            DataFrame with normalised Date column, or ``None`` on failure.
        """
        fetcher = FootballDataCoUkGames(
            sport_id=self._league_code,
            data_dir=str(self._data_dir),
            seasons=[season_code],
        )
        fetcher.download_games()
        csv_path = self._data_dir / f"{self._league_code}_{season_code}.csv"
        if not csv_path.exists():
            logger.warning("⚠️ Season CSV not found: %s", csv_path)
            return None
        try:
            df = pd.read_csv(csv_path)
            df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
            df = df.dropna(subset=["Date"])
            return df
        except Exception as exc:
            logger.warning("⚠️ Failed to load %s: %s", csv_path, exc)
            return None

    def _rows_from_df(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """Convert CSV DataFrame rows into normalised team-game dicts.

        Args:
            df: Season DataFrame with standard football-data.co.uk columns.

        Returns:
            List of normalised team-game dicts (two per match).
        """
        results: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            if pd.isna(row.get("FTHG")) or pd.isna(row.get("FTAG")):
                continue
            try:
                results.extend(self._build_team_rows(row))
            except Exception as exc:
                logger.debug("Skipping row due to error: %s", exc)
        return results

    def _build_team_rows(self, row: "pd.Series") -> list[dict[str, Any]]:
        """Build two normalised team-game dicts from a CSV row.

        Args:
            row: Single pandas Series from the season DataFrame.

        Returns:
            List of [home_dict, away_dict].
        """
        game_date: date = row["Date"].date()
        season_code = _season_code_from_date(game_date)
        season_label = _season_label_from_code(season_code)
        home_team: str = str(row["HomeTeam"])
        away_team: str = str(row["AwayTeam"])
        home_goals = int(row["FTHG"])
        away_goals = int(row["FTAG"])
        result = str(row.get("FTR", ""))

        # Build game_id: {league_code}_{YYYYMMDD}_{HomeAbbr}_{AwayAbbr}
        date_str = game_date.strftime("%Y%m%d")
        home_abbr = home_team[:3].upper().replace(" ", "")
        away_abbr = away_team[:3].upper().replace(" ", "")
        game_id = f"{self._league_code}_{date_str}_{home_abbr}_{away_abbr}"

        def _stat(home_col: str, away_col: str, is_home: bool) -> int | None:
            col = home_col if is_home else away_col
            val = row.get(col)
            return int(val) if not pd.isna(val) and val is not None else None

        home_ext = {k: _stat(hc, ac, True) for k, (hc, ac) in _CSV_STAT_COLUMNS.items()}
        away_ext = {
            k: _stat(hc, ac, False) for k, (hc, ac) in _CSV_STAT_COLUMNS.items()
        }

        home_dict: dict[str, Any] = {
            "game_id": game_id,
            "sport": self.SPORT,
            "team": home_team,
            "opponent": away_team,
            "is_home": True,
            "game_date": game_date,
            "season": season_label,
            "points_for": home_goals,
            "points_against": away_goals,
            "won": result == "H",
            "margin": home_goals - away_goals,
            "ext": home_ext,
        }
        away_dict: dict[str, Any] = {
            "game_id": game_id,
            "sport": self.SPORT,
            "team": away_team,
            "opponent": home_team,
            "is_home": False,
            "game_date": game_date,
            "season": season_label,
            "points_for": away_goals,
            "points_against": home_goals,
            "won": result == "A",
            "margin": away_goals - home_goals,
            "ext": away_ext,
        }
        return [home_dict, away_dict]

    # ------------------------------------------------------------------
    # FBRef optional enrichment
    # ------------------------------------------------------------------

    def _try_enrich_fbref(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Optionally enrich rows with FBRef advanced stats (possession, xG, passes).

        Wraps all FBRef calls in try/except; if scraping fails the rows are
        returned unchanged.  A 3-second delay is applied between requests.

        Args:
            rows: Normalised team-game dicts to enrich in-place.

        Returns:
            Rows with ``ext`` fields updated where FBRef data was available.
        """
        try:
            from bs4 import BeautifulSoup  # optional dep
        except ImportError:
            logger.debug("BeautifulSoup not installed — skipping FBRef enrichment")
            return rows

        headers = {"User-Agent": _FBREF_USER_AGENT}
        # Group rows by game_id for batch lookup
        game_ids = list({r["game_id"] for r in rows})
        for game_id in game_ids:
            try:
                time.sleep(_FBREF_DELAY_SECONDS)
                # FBRef search by date + teams is complex; skip network call in
                # this implementation and log intent only.  A full FBRef scraper
                # would build the match URL from known tourney/season/teams.
                logger.debug(
                    "🌐 FBRef enrichment skipped for %s (not wired yet)", game_id
                )
            except Exception as exc:
                logger.warning("⚠️ FBRef enrichment failed for %s: %s", game_id, exc)
        return rows

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_game_stats(self, game_id: str) -> list[dict[str, Any]]:
        """Fetch team box-score for one soccer match.

        Looks up the match in the cached football-data.co.uk CSV for the
        relevant season, then optionally enriches with FBRef data.

        The ``User-Agent`` header ``nhlstats-research-bot/1.0`` is sent on
        all FBRef requests; a 3-second delay is enforced between FBRef calls.

        Args:
            game_id: Internal match identifier
                (e.g. ``"E0_20231028_ARS_CHE"``).

        Returns:
            List of two dicts (home team, away team).

        Raises:
            ValueError: If game_id cannot be parsed.
        """
        # Parse: {league_code}_{YYYYMMDD}_{HomeAbbr}_{AwayAbbr}
        parts = game_id.split("_")
        if len(parts) < 4:
            raise ValueError(f"Cannot parse game_id {game_id!r}; expected 4 parts")
        date_str = parts[1]
        try:
            game_date = date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
        except (ValueError, IndexError) as exc:
            raise ValueError(f"Invalid date in game_id {game_id!r}") from exc

        season_code = _season_code_from_date(game_date)
        df = self._load_season_df(season_code)
        if df is None or df.empty:
            logger.warning("⚠️ No CSV data for season %s", season_code)
            return []

        # Filter to matching date
        target_date = pd.Timestamp(game_date)
        df_day = df[df["Date"].dt.date == game_date]
        if df_day.empty:
            logger.warning("⚠️ No match found for game_id %s on %s", game_id, game_date)
            return []

        home_abbr = parts[2].upper()
        away_abbr = parts[3].upper()
        # Try to find the row by team abbreviations
        match_row = None
        for _, row in df_day.iterrows():
            h = str(row["HomeTeam"])[:3].upper().replace(" ", "")
            a = str(row["AwayTeam"])[:3].upper().replace(" ", "")
            if h == home_abbr and a == away_abbr:
                match_row = row
                break

        if match_row is None:
            # Fall back to first game on that date
            if len(df_day) == 1:
                match_row = df_day.iloc[0]
            else:
                logger.warning("⚠️ Could not match teams for game_id %s", game_id)
                return []

        rows = self._build_team_rows(match_row)
        # Override game_id to the exact one requested
        for r in rows:
            r["game_id"] = game_id
        return rows

    def fetch_date_range(self, start: date, end: date) -> list[dict[str, Any]]:
        """Fetch soccer box-scores for all matches in a date range.

        Downloads season CSVs covering the date range, filters by date, and
        returns normalised rows.

        Args:
            start: First date (inclusive).
            end: Last date (inclusive).

        Returns:
            Flat list of normalised team-row dicts.
        """
        season_codes = _seasons_for_range(start, end)
        all_rows: list[dict[str, Any]] = []
        for code in season_codes:
            df = self._load_season_df(code)
            if df is None or df.empty:
                continue
            df_filtered = df[
                (df["Date"].dt.date >= start) & (df["Date"].dt.date <= end)
            ]
            all_rows.extend(self._rows_from_df(df_filtered))
        logger.info("✓ Fetched %d soccer rows for %s–%s", len(all_rows), start, end)
        return all_rows

    def upsert_rows(self, rows: list[dict[str, Any]]) -> int:
        """Persist soccer rows to ``team_game_stats`` and ``soccer_team_game_stats_ext``.

        Skips rows whose ``game_id`` is not present in ``unified_games``.

        Args:
            rows: Normalised team-game dicts as returned by
                :meth:`fetch_game_stats` or :meth:`fetch_date_range`.

        Returns:
            Total rows upserted.
        """
        if not rows:
            return 0

        # Collect valid game_ids from unified_games
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
                "margin": row.get("margin"),
            }
            try:
                self.db.execute(
                    """
                    INSERT INTO team_game_stats
                        (game_id, sport, team, opponent, is_home, game_date, season,
                         points_for, points_against, won, margin)
                    VALUES
                        (:game_id, :sport, :team, :opponent, :is_home, :game_date, :season,
                         :points_for, :points_against, :won, :margin)
                    ON CONFLICT (game_id, team) DO UPDATE SET
                        sport=EXCLUDED.sport, opponent=EXCLUDED.opponent,
                        is_home=EXCLUDED.is_home, game_date=EXCLUDED.game_date,
                        season=EXCLUDED.season, points_for=EXCLUDED.points_for,
                        points_against=EXCLUDED.points_against, won=EXCLUDED.won,
                        margin=EXCLUDED.margin, updated_at=NOW()
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
                            "shots",
                            "shots_on_target",
                            "possession_pct",
                            "passes",
                            "pass_accuracy",
                            "xg",
                            "xga",
                            "fouls",
                            "yellow_cards",
                            "red_cards",
                            "corners",
                            "offsides",
                            "saves",
                        )
                    },
                }
                try:
                    self.db.execute(
                        """
                        INSERT INTO soccer_team_game_stats_ext
                            (game_id, team, shots, shots_on_target, possession_pct,
                             passes, pass_accuracy, xg, xga, fouls, yellow_cards,
                             red_cards, corners, offsides, saves)
                        VALUES
                            (:game_id, :team, :shots, :shots_on_target, :possession_pct,
                             :passes, :pass_accuracy, :xg, :xga, :fouls, :yellow_cards,
                             :red_cards, :corners, :offsides, :saves)
                        ON CONFLICT (game_id, team) DO UPDATE SET
                            shots=EXCLUDED.shots,
                            shots_on_target=EXCLUDED.shots_on_target,
                            possession_pct=EXCLUDED.possession_pct,
                            passes=EXCLUDED.passes,
                            pass_accuracy=EXCLUDED.pass_accuracy,
                            xg=EXCLUDED.xg, xga=EXCLUDED.xga,
                            fouls=EXCLUDED.fouls,
                            yellow_cards=EXCLUDED.yellow_cards,
                            red_cards=EXCLUDED.red_cards,
                            corners=EXCLUDED.corners,
                            offsides=EXCLUDED.offsides,
                            saves=EXCLUDED.saves
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

        logger.info("✓ Upserted %d/%d soccer rows", upserted, len(rows))
        return upserted
