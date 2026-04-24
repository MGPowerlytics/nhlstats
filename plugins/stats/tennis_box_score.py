"""
Tennis player-match stats fetcher.

Data source
-----------
**Jeff Sackmann's GitHub tennis repositories** (Apache-licensed CSVs):

* ATP match results: ``https://github.com/JeffSackmann/tennis_atp``
* WTA match results: ``https://github.com/JeffSackmann/tennis_wta``

The repos are cloned once into ``data/tennis/atp`` and
``data/tennis/wta`` respectively and pulled incrementally each run.
CSV columns include serve statistics (aces, double faults, 1st-serve %, etc.)
and rally/return stats where available.

Unlike the other sport fetchers, tennis is player-level rather than team-level,
so the canonical table is ``tennis_player_match_stats`` (PK:
``(game_id, player_name)``).  The ``upsert_rows`` method writes to this table
instead of ``team_game_stats``.

Rate limit: Local CSV read; no HTTP rate-limiting needed during normal
operation.  ``RATE_LIMIT_SECONDS = 0.0`` (git pull is rate-limited by the
git transport layer).

Extension table: ``tennis_player_match_stats``

Note:
    ``EXT_TABLE`` is repurposed here: there is no separate extension table;
    all columns land in ``tennis_player_match_stats`` (which also serves as
    the primary table for tennis data).
"""

from __future__ import annotations

import logging
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from plugins.db_manager import DBManager
from plugins.stats.base import BoxScoreFetcher

logger = logging.getLogger(__name__)

_DEFAULT_DATA_DIR: Path = Path("data/tennis")
_ATP_REPO: str = "https://github.com/JeffSackmann/tennis_atp.git"
_WTA_REPO: str = "https://github.com/JeffSackmann/tennis_wta.git"

_REPO_URLS: dict[str, str] = {
    "atp": _ATP_REPO,
    "wta": _WTA_REPO,
}


def _safe_int(value: Any) -> int | None:
    """Convert a value to int, returning None on failure.

    Args:
        value: Raw value (may be NaN, str, or numeric).

    Returns:
        Integer or ``None``.
    """
    try:
        if pd.isna(value):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _safe_ratio(numerator: Any, denominator: Any) -> float | None:
    """Compute a ratio, returning None if denominator is zero or inputs invalid.

    Args:
        numerator: Dividend.
        denominator: Divisor.

    Returns:
        Float ratio or ``None``.
    """
    try:
        n = float(numerator)
        d = float(denominator)
        if d <= 0 or pd.isna(n) or pd.isna(d):
            return None
        return round(n / d, 4)
    except (TypeError, ValueError):
        return None


def _parse_score(score_str: str, winner: bool) -> tuple[int, int]:
    """Parse a tennis score string into (sets_won, games_won).

    Handles standard scores like ``"6-4 7-5 6-3"``, tiebreak notation
    ``"7-6(3)"``, and retirement/walkover suffixes.

    Args:
        score_str: Raw score string from Sackmann CSV.
        winner: If ``True``, count the first number of each set as the
            winner's games.

    Returns:
        Tuple of ``(sets_won, games_won)`` as integers.
    """
    if not score_str or not isinstance(score_str, str):
        return (0, 0)

    # Strip retirement/walkover tags
    clean = re.sub(
        r"\s*(RET|W/O|DEF|ABD|Def\.?)\s*$", "", score_str.strip(), flags=re.IGNORECASE
    )
    # Strip tiebreak scores like (7)
    clean = re.sub(r"\(\d+\)", "", clean)

    sets_won = 0
    games_won = 0

    for part in clean.split():
        part = part.strip()
        if not part:
            continue
        if "-" not in part:
            continue
        try:
            left_str, right_str = part.split("-", 1)
            left = int(left_str)
            right = int(right_str)
        except ValueError:
            continue

        # winner's games are `left`, loser's are `right`
        if winner:
            games_won += left
            if left > right:
                sets_won += 1
        else:
            games_won += right
            if right > left:
                sets_won += 1

    return (sets_won, games_won)


class TennisBoxScoreFetcher(BoxScoreFetcher):
    """Fetch and persist tennis player-match stats from Jeff Sackmann CSVs.

    Reads cloned ATP / WTA CSV files from ``data/tennis/`` and produces one
    dict per *player* per match (i.e. two dicts per match: winner and loser).
    Data is persisted to ``tennis_player_match_stats``.

    The ``fetch_game_stats`` / ``fetch_date_range`` names are preserved from
    the base class interface for consistency, but logically they operate on
    player-match rows rather than team-game rows.

    Example:
        >>> fetcher = TennisBoxScoreFetcher(tour="atp")
        >>> rows = fetcher.fetch_game_stats("atp_2023-560_R128_0001")
        >>> fetcher.upsert_rows(rows)
    """

    SPORT: str = "Tennis"
    RATE_LIMIT_SECONDS: float = 0.0  # local CSV; no HTTP calls during fetch
    EXT_TABLE: str = "tennis_player_match_stats"  # primary table for tennis

    def __init__(
        self,
        tour: str = "atp",
        data_dir: Path | str | None = None,
        db: DBManager | None = None,
    ) -> None:
        """Initialise the tennis fetcher for the specified tour.

        Args:
            tour: ``"atp"`` for men's or ``"wta"`` for women's.
            data_dir: Path to local clone root.  Defaults to
                ``data/tennis`` relative to the working directory.
            db: Optional shared :class:`~plugins.db_manager.DBManager`.

        Raises:
            ValueError: If *tour* is not ``"atp"`` or ``"wta"``.
        """
        if tour not in {"atp", "wta"}:
            raise ValueError(f"tour must be 'atp' or 'wta', got {tour!r}")
        self.tour: str = tour
        self.data_dir: Path = Path(data_dir) if data_dir else _DEFAULT_DATA_DIR
        super().__init__(db=db)

    # ------------------------------------------------------------------
    # Repository management
    # ------------------------------------------------------------------

    def ensure_repos_cloned(self) -> None:
        """Clone ATP/WTA repository into ``data_dir`` if not already present.

        Uses ``git clone`` for initial setup and ``git pull`` for subsequent
        updates (best-effort).  Only the repository for :attr:`tour` is cloned.
        """
        repo_dir = self.data_dir / self.tour
        repo_url = _REPO_URLS[self.tour]
        if not repo_dir.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)
            logger.info("📥 Cloning %s into %s…", repo_url, repo_dir)
            try:
                subprocess.run(
                    ["git", "clone", repo_url, str(repo_dir)],
                    check=True,
                    capture_output=True,
                )
                logger.info("✓ Cloned %s", repo_dir)
            except subprocess.CalledProcessError as exc:
                logger.error("❌ git clone failed: %s", exc.stderr.decode())
                raise
        else:
            try:
                subprocess.run(
                    ["git", "-C", str(repo_dir), "pull"],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
                logger.info("✓ Pulled latest changes for %s", repo_dir)
            except Exception as exc:
                logger.warning("⚠️ git pull failed (best-effort): %s", exc)

    # ------------------------------------------------------------------
    # CSV loading helpers
    # ------------------------------------------------------------------

    def _csv_path(self, year: int) -> Path:
        """Return the path to the matches CSV for a given year.

        Args:
            year: Four-digit year.

        Returns:
            Path to ``{tour}_matches_{year}.csv``.
        """
        return self.data_dir / self.tour / f"{self.tour}_matches_{year}.csv"

    def _load_year_df(self, year: int) -> pd.DataFrame | None:
        """Load the matches CSV for a single year.

        Args:
            year: Four-digit year.

        Returns:
            DataFrame or ``None`` if the file does not exist / cannot be read.
        """
        csv_path = self._csv_path(year)
        if not csv_path.exists():
            logger.debug("No CSV for year %d at %s", year, csv_path)
            return None
        try:
            return pd.read_csv(csv_path, encoding="utf-8", low_memory=False)
        except UnicodeDecodeError:
            try:
                return pd.read_csv(csv_path, encoding="latin1", low_memory=False)
            except Exception as exc:
                logger.warning("⚠️ Could not read %s: %s", csv_path, exc)
                return None
        except Exception as exc:
            logger.warning("⚠️ Could not read %s: %s", csv_path, exc)
            return None

    @staticmethod
    def _build_game_id(tour: str, tourney_id: str, match_num: str) -> str:
        """Construct the canonical game_id for a tennis match.

        Args:
            tour: ``"atp"`` or ``"wta"``.
            tourney_id: Sackmann ``tourney_id`` field.
            match_num: Sackmann ``match_num`` field.

        Returns:
            Game ID string like ``"atp_2023-560_R128_0001"``.
        """
        return f"{tour}_{tourney_id}_{match_num}"

    def _parse_match_row(self, row: "pd.Series", game_id: str) -> list[dict[str, Any]]:
        """Parse one Sackmann CSV row into two player-match dicts.

        Args:
            row: Single pandas Series from a matches CSV.
            game_id: Pre-computed game_id string.

        Returns:
            List of [winner_dict, loser_dict].
        """
        score_str = str(row.get("score", ""))

        winner_sets, winner_games = _parse_score(score_str, winner=True)
        loser_sets, loser_games = _parse_score(score_str, winner=False)

        # Serve stats for winner
        w_svpt = _safe_int(row.get("w_svpt"))
        w_1stin = _safe_int(row.get("w_1stIn"))
        w_1stwon = _safe_int(row.get("w_1stWon"))
        w_2ndwon = _safe_int(row.get("w_2ndWon"))

        w_first_serve_pct = _safe_ratio(w_1stin, w_svpt)
        w_first_won_pct = _safe_ratio(w_1stwon, w_1stin)
        w_second_denom = (w_svpt or 0) - (w_1stin or 0)
        w_second_won_pct = _safe_ratio(w_2ndwon, w_second_denom)

        # Serve stats for loser
        l_svpt = _safe_int(row.get("l_svpt"))
        l_1stin = _safe_int(row.get("l_1stIn"))
        l_1stwon = _safe_int(row.get("l_1stWon"))
        l_2ndwon = _safe_int(row.get("l_2ndWon"))

        l_first_serve_pct = _safe_ratio(l_1stin, l_svpt)
        l_first_won_pct = _safe_ratio(l_1stwon, l_1stin)
        l_second_denom = (l_svpt or 0) - (l_1stin or 0)
        l_second_won_pct = _safe_ratio(l_2ndwon, l_second_denom)

        winner_dict: dict[str, Any] = {
            "game_id": game_id,
            "player_name": str(row.get("winner_name", "")),
            "aces": _safe_int(row.get("w_ace")),
            "double_faults": _safe_int(row.get("w_df")),
            "first_serve_pct": w_first_serve_pct,
            "first_serve_won_pct": w_first_won_pct,
            "second_serve_won_pct": w_second_won_pct,
            "break_points_saved": _safe_int(row.get("w_bpSaved")),
            "break_points_faced": _safe_int(row.get("w_bpFaced")),
            "winners": None,  # Not in Sackmann ATP/WTA base CSVs
            "unforced_errors": None,
            "sets_won": winner_sets,
            "games_won": winner_games,
            "won": True,
        }
        loser_dict: dict[str, Any] = {
            "game_id": game_id,
            "player_name": str(row.get("loser_name", "")),
            "aces": _safe_int(row.get("l_ace")),
            "double_faults": _safe_int(row.get("l_df")),
            "first_serve_pct": l_first_serve_pct,
            "first_serve_won_pct": l_first_won_pct,
            "second_serve_won_pct": l_second_won_pct,
            "break_points_saved": _safe_int(row.get("l_bpSaved")),
            "break_points_faced": _safe_int(row.get("l_bpFaced")),
            "winners": None,
            "unforced_errors": None,
            "sets_won": loser_sets,
            "games_won": loser_games,
            "won": False,
        }
        return [winner_dict, loser_dict]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_game_stats(self, game_id: str) -> list[dict[str, Any]]:
        """Fetch player-match stats for one tennis match.

        Scans the relevant year CSV(s) in the cloned Sackmann repository for
        a row matching *game_id* and returns two player dicts (winner, loser)
        in a normalised format.

        Args:
            game_id: Match identifier in format ``"{tour}_{tourney_id}_{match_num}"``,
                e.g. ``"atp_2023-560_R128_0001"``.

        Returns:
            List of two dicts — winner and loser — each in the
            ``tennis_player_match_stats`` column format.

        Raises:
            ValueError: If game_id format is invalid.
        """
        # Parse: {tour}_{tourney_id}_{round}_{match_num}
        # e.g. atp_2023-560_R128_0001 → tour=atp, tourney_id=2023-560, match_num=0001
        parts = game_id.split("_", 1)
        if len(parts) < 2:
            raise ValueError(f"Invalid game_id format: {game_id!r}")

        tour_from_id = parts[0]
        rest = parts[1]  # e.g. "2023-560_R128_0001"

        # Extract year from tourney_id (first 4 chars after tour prefix)
        year_match = re.match(r"^(\d{4})", rest)
        if not year_match:
            raise ValueError(f"Cannot extract year from game_id: {game_id!r}")
        year = int(year_match.group(1))

        df = self._load_year_df(year)
        if df is None or df.empty:
            logger.warning("⚠️ No CSV data for year %d", year)
            return []

        # Reconstruct tourney_id and match_num from game_id
        # Format: {tour}_{tourney_id}_{match_num}
        # Split the rest part carefully: tourney_id has format YYYY-NNN
        # match_num is everything after the round code
        tourney_match = re.match(r"^(\d{4}-\d+)_(.+)$", rest)
        if not tourney_match:
            logger.warning("⚠️ Cannot parse tourney_id/match_num from %s", game_id)
            return []

        tourney_id = tourney_match.group(1)
        match_num = tourney_match.group(2)

        if "tourney_id" not in df.columns or "match_num" not in df.columns:
            logger.warning("⚠️ CSV missing tourney_id or match_num columns")
            return []

        mask = (df["tourney_id"].astype(str) == tourney_id) & (
            df["match_num"].astype(str) == match_num
        )
        matched = df[mask]
        if matched.empty:
            logger.warning(
                "⚠️ No match found for tourney_id=%s match_num=%s", tourney_id, match_num
            )
            return []

        return self._parse_match_row(matched.iloc[0], game_id)

    def fetch_date_range(self, start: date, end: date) -> list[dict[str, Any]]:
        """Fetch player-match stats for all matches in a date range.

        Loads all relevant year CSVs, filters by ``tourney_date`` in the
        Sackmann format (``YYYYMMDD``), and returns normalised player dicts.

        Args:
            start: First date (inclusive).
            end: Last date (inclusive).

        Returns:
            Flat list of normalised player-match dicts.
        """
        years = list(range(start.year, end.year + 1))
        start_int = int(start.strftime("%Y%m%d"))
        end_int = int(end.strftime("%Y%m%d"))

        all_rows: list[dict[str, Any]] = []
        for year in years:
            df = self._load_year_df(year)
            if df is None or df.empty:
                continue
            if "tourney_date" not in df.columns:
                logger.warning("⚠️ No tourney_date column in %d CSV", year)
                continue

            df = df.copy()
            df["tourney_date"] = pd.to_numeric(df["tourney_date"], errors="coerce")
            df_filtered = df[
                (df["tourney_date"] >= start_int) & (df["tourney_date"] <= end_int)
            ]

            for _, row in df_filtered.iterrows():
                try:
                    tourney_id = str(row.get("tourney_id", ""))
                    match_num = str(row.get("match_num", ""))
                    game_id = self._build_game_id(self.tour, tourney_id, match_num)
                    all_rows.extend(self._parse_match_row(row, game_id))
                except Exception as exc:
                    logger.debug("Skipping row due to error: %s", exc)

        logger.info("✓ Fetched %d tennis rows for %s–%s", len(all_rows), start, end)
        return all_rows

    def upsert_rows(self, rows: list[dict[str, Any]]) -> int:
        """Persist tennis rows to ``tennis_player_match_stats``.

        Skips rows whose ``game_id`` is not present in ``unified_games``.
        Uses ON CONFLICT DO UPDATE semantics on ``(game_id, player_name)``.

        Args:
            rows: Normalised player-match dicts.

        Returns:
            Total rows upserted to ``tennis_player_match_stats``.
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
            params = {
                "game_id": row["game_id"],
                "player_name": row.get("player_name", ""),
                "aces": row.get("aces"),
                "double_faults": row.get("double_faults"),
                "first_serve_pct": row.get("first_serve_pct"),
                "first_serve_won_pct": row.get("first_serve_won_pct"),
                "second_serve_won_pct": row.get("second_serve_won_pct"),
                "break_points_saved": row.get("break_points_saved"),
                "break_points_faced": row.get("break_points_faced"),
                "winners": row.get("winners"),
                "unforced_errors": row.get("unforced_errors"),
                "sets_won": row.get("sets_won"),
                "games_won": row.get("games_won"),
                "won": row.get("won"),
            }
            try:
                self.db.execute(
                    """
                    INSERT INTO tennis_player_match_stats
                        (game_id, player_name, aces, double_faults,
                         first_serve_pct, first_serve_won_pct, second_serve_won_pct,
                         break_points_saved, break_points_faced, winners,
                         unforced_errors, sets_won, games_won, won)
                    VALUES
                        (:game_id, :player_name, :aces, :double_faults,
                         :first_serve_pct, :first_serve_won_pct, :second_serve_won_pct,
                         :break_points_saved, :break_points_faced, :winners,
                         :unforced_errors, :sets_won, :games_won, :won)
                    ON CONFLICT (game_id, player_name) DO UPDATE SET
                        aces=EXCLUDED.aces,
                        double_faults=EXCLUDED.double_faults,
                        first_serve_pct=EXCLUDED.first_serve_pct,
                        first_serve_won_pct=EXCLUDED.first_serve_won_pct,
                        second_serve_won_pct=EXCLUDED.second_serve_won_pct,
                        break_points_saved=EXCLUDED.break_points_saved,
                        break_points_faced=EXCLUDED.break_points_faced,
                        winners=EXCLUDED.winners,
                        unforced_errors=EXCLUDED.unforced_errors,
                        sets_won=EXCLUDED.sets_won,
                        games_won=EXCLUDED.games_won,
                        won=EXCLUDED.won
                    """,
                    params,
                )
                upserted += 1
            except Exception as exc:
                logger.error(
                    "❌ Upsert failed for %s/%s: %s",
                    row["game_id"],
                    row.get("player_name"),
                    exc,
                )

        logger.info("✓ Upserted %d/%d tennis rows", upserted, len(rows))
        return upserted
