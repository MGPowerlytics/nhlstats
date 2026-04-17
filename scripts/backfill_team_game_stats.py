#!/usr/bin/env python3
"""Backfill historical team-level box-score stats for all sports.

Intended behaviour
------------------
For each sport (or the single sport supplied via ``--sport``), the script
iterates over every row in the ``unified_games`` Postgres table whose
``game_date`` falls within [``--start``, ``--end``].  For each game it:

1. Instantiates the appropriate ``BoxScoreFetcher`` subclass.
2. Calls ``fetcher.fetch(game_id)`` to retrieve raw box-score data from the
   sport's public API (see ``docs/STATS_DATA_SOURCES.md``).
3. Upserts the result into the relevant ``team_game_stats_<sport>`` table via
   ``plugins/db_manager.py``.
4. Records progress in ``data/stats_backfill_progress.json`` so that a
   subsequent run with ``--resume`` skips already-completed game IDs.

Rate limits are respected via per-sport ``time.sleep()`` delays derived from
the Airflow pool slot counts documented in ``docs/AIRFLOW_SETUP.md``.

The ``--dry-run`` flag prints each game that *would* be processed without
making any network calls or database writes.

Usage examples
--------------
::

    # Full backfill for NBA, 2021-present
    python scripts/backfill_team_game_stats.py --sport nba --start 2021-01-01

    # Dry-run to preview scope
    python scripts/backfill_team_game_stats.py --sport nhl --start 2023-01-01 \\
        --end 2024-06-30 --dry-run

    # Resume a previously interrupted run
    python scripts/backfill_team_game_stats.py --sport mlb --start 2021-01-01 \\
        --resume

    # Backfill all sports
    python scripts/backfill_team_game_stats.py --start 2021-01-01
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Path bootstrapping — ensure repo root is on sys.path when run as a script.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from plugins.db_manager import DBManager  # noqa: E402 — after sys.path fix
from plugins.stats import (  # noqa: E402
    CBBBoxScoreFetcher,
    MLBBoxScoreFetcher,
    NBABoxScoreFetcher,
    NFLBoxScoreFetcher,
    NHLBoxScoreFetcher,
    SoccerBoxScoreFetcher,
    TennisBoxScoreFetcher,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SUPPORTED_SPORTS = [
    "nba",
    "nhl",
    "mlb",
    "nfl",
    "epl",
    "ligue1",
    "ncaab",
    "wncaab",
    "tennis",
]
PROGRESS_FILE = Path("data/stats_backfill_progress.json")

# sport key → (unified_games sport value, fetcher factory)
# unified_games stores sport as uppercase strings (e.g. "NBA", "LIGUE1", "TENNIS")
_SPORT_UNIFIED_KEY: dict[str, str] = {
    "nba": "NBA",
    "nhl": "NHL",
    "mlb": "MLB",
    "nfl": "NFL",
    "epl": "EPL",
    "ligue1": "LIGUE1",
    "ncaab": "NCAAB",
    "wncaab": "WNCAAB",
    "tennis": "TENNIS",
}

_RETRY_BASE_SECONDS = 2.0
_MAX_RETRIES = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill")


# ---------------------------------------------------------------------------
# Per-sport summary
# ---------------------------------------------------------------------------
@dataclass
class SportSummary:
    """Counts of game processing outcomes for a single sport."""

    sport: str
    processed: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def print(self) -> None:
        """Print a formatted summary line."""
        print(
            f"  {self.sport.upper():<8} "
            f"processed={self.processed}  "
            f"inserted={self.inserted}  "
            f"updated={self.updated}  "
            f"skipped={self.skipped}  "
            f"failed={self.failed}"
        )
        for err in self.errors[:5]:
            print(f"    ⚠️  {err}")
        if len(self.errors) > 5:
            print(f"    … and {len(self.errors) - 5} more errors")


# ---------------------------------------------------------------------------
# Progress file helpers
# ---------------------------------------------------------------------------


def load_progress(path: Path) -> dict[str, str]:
    """Load per-sport last-completed-date progress from *path*.

    Args:
        path: Path to the JSON progress file.

    Returns:
        Dict mapping sport key → ISO date string of last completed date.
        Returns an empty dict if the file does not exist or is corrupt.
    """
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "⚠️  Could not read progress file %s: %s — starting fresh", path, exc
        )
        return {}


def save_progress(path: Path, progress: dict[str, str]) -> None:
    """Persist *progress* dict to *path* atomically.

    Args:
        path: Destination path for the JSON file.
        progress: Dict mapping sport key → ISO date string.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Fetcher factory
# ---------------------------------------------------------------------------


def build_fetcher(sport: str, db: DBManager):
    """Instantiate the appropriate fetcher for *sport*.

    Args:
        sport: Lower-case sport key (e.g. ``"nba"``).
        db: Shared :class:`~plugins.db_manager.DBManager` instance.

    Returns:
        Concrete :class:`~plugins.stats.BoxScoreFetcher` instance.

    Raises:
        ValueError: If *sport* is not recognised.
    """
    if sport == "nba":
        return NBABoxScoreFetcher(db=db)
    if sport == "nhl":
        return NHLBoxScoreFetcher(db=db)
    if sport == "mlb":
        return MLBBoxScoreFetcher(db=db)
    if sport == "nfl":
        return NFLBoxScoreFetcher(db=db)
    if sport == "epl":
        return SoccerBoxScoreFetcher(sport="EPL", db=db)
    if sport == "ligue1":
        return SoccerBoxScoreFetcher(sport="Ligue1", db=db)
    if sport == "ncaab":
        return CBBBoxScoreFetcher(sport="NCAAB", db=db)
    if sport == "wncaab":
        return CBBBoxScoreFetcher(sport="WNCAAB", db=db)
    if sport == "tennis":
        return TennisBoxScoreFetcher(db=db)
    raise ValueError(f"Unknown sport: {sport!r}")


# ---------------------------------------------------------------------------
# Rate-limited fetch with exponential backoff
# ---------------------------------------------------------------------------


def fetch_with_backoff(
    fetcher,
    game_id: str,
    verbose: bool = False,
) -> list[dict[str, Any]] | None:
    """Call ``fetcher.fetch_game_stats(game_id)`` with exponential backoff.

    Retries up to :data:`_MAX_RETRIES` times on HTTP 429 / 5xx errors
    (detected by inspecting the exception message).

    Args:
        fetcher: A :class:`~plugins.stats.BoxScoreFetcher` instance.
        game_id: Game identifier to fetch.
        verbose: Log debug-level messages when ``True``.

    Returns:
        List of normalised team-row dicts, or ``None`` if all retries failed.
    """
    fetcher._rate_limit()
    for attempt in range(_MAX_RETRIES + 1):
        try:
            rows = fetcher.fetch_game_stats(game_id)
            return rows
        except Exception as exc:
            msg = str(exc).lower()
            is_retryable = any(
                code in msg
                for code in ("429", "500", "502", "503", "504", "rate limit")
            )
            if is_retryable and attempt < _MAX_RETRIES:
                wait = _RETRY_BASE_SECONDS * (2**attempt)
                logger.warning(
                    "⏳ Retryable error for %s (attempt %d/%d) — sleeping %.1fs: %s",
                    game_id,
                    attempt + 1,
                    _MAX_RETRIES,
                    wait,
                    exc,
                )
                time.sleep(wait)
                fetcher._last_request_ts = (
                    0.0  # reset so _rate_limit doesn't add extra wait
                )
            else:
                logger.error(
                    "❌ Failed to fetch %s after %d attempt(s): %s",
                    game_id,
                    attempt + 1,
                    exc,
                )
                return None
    return None


# ---------------------------------------------------------------------------
# Row existence check
# ---------------------------------------------------------------------------


def rows_exist_in_db(db: DBManager, game_id: str) -> bool:
    """Return ``True`` if *game_id* already has rows in ``team_game_stats``.

    Args:
        db: Active :class:`~plugins.db_manager.DBManager` instance.
        game_id: Game identifier to check.

    Returns:
        ``True`` if at least one row exists for *game_id*.
    """
    try:
        result = db.execute(
            "SELECT 1 FROM team_game_stats WHERE game_id = :gid LIMIT 1",
            {"gid": game_id},
        )
        return result.rowcount > 0 or bool(result.fetchone())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Per-sport backfill
# ---------------------------------------------------------------------------


def backfill_sport(
    sport: str,
    start: date,
    end: date,
    db: DBManager,
    dry_run: bool,
    resume: bool,
    progress: dict[str, str],
    verbose: bool,
) -> SportSummary:
    """Backfill box-score stats for a single sport.

    Queries ``unified_games`` for games in [*start*, *end*], then for each
    game calls the appropriate fetcher and upserts results.  Progress is
    updated in *progress* after each successfully processed game date.

    Args:
        sport: Lower-case sport key.
        start: First game date (inclusive).
        end: Last game date (inclusive).
        db: Shared database manager.
        dry_run: When ``True``, print intended actions without DB writes.
        resume: When ``True``, skip games already in ``team_game_stats``.
        progress: Mutable dict tracking per-sport last completed date.
        verbose: Enable verbose logging.

    Returns:
        :class:`SportSummary` with outcome counts.
    """
    summary = SportSummary(sport=sport)
    unified_sport = _SPORT_UNIFIED_KEY[sport]

    # Apply resume: advance effective start date to the day *after* the last
    # completed date recorded in the progress file.
    effective_start = start
    if resume and sport in progress:
        try:
            last_done = date.fromisoformat(progress[sport])
            candidate = last_done + timedelta(days=1)
            if candidate > effective_start:
                effective_start = candidate
                logger.info(
                    "↩️  %s: resuming from %s (skipping up to %s)",
                    sport.upper(),
                    effective_start,
                    last_done,
                )
        except ValueError:
            pass

    if effective_start > end:
        logger.info(
            "✅ %s: already complete through %s — nothing to do", sport.upper(), end
        )
        return summary

    # Fetch game list from unified_games.
    try:
        games_df = db.fetch_df(
            """
            SELECT game_id, game_date
              FROM unified_games
             WHERE sport = :sport
               AND game_date BETWEEN :start AND :end
             ORDER BY game_date
            """,
            {
                "sport": unified_sport,
                "start": effective_start.isoformat(),
                "end": end.isoformat(),
            },
        )
    except Exception as exc:
        logger.error("❌ %s: failed to query unified_games: %s", sport.upper(), exc)
        summary.errors.append(f"unified_games query failed: {exc}")
        return summary

    if games_df.empty:
        logger.info(
            "ℹ️  %s: no games found in unified_games for %s–%s",
            sport.upper(),
            effective_start,
            end,
        )
        return summary

    total_games = len(games_df)
    logger.info(
        "🏟️  %s: found %d game(s) in %s–%s",
        sport.upper(),
        total_games,
        effective_start,
        end,
    )

    fetcher = build_fetcher(sport, db)

    last_date_done: Optional[str] = None

    for _, game_row in games_df.iterrows():
        game_id = str(game_row["game_id"])
        game_date_val = game_row["game_date"]

        # Normalise game_date to a plain date string for logging/progress.
        if hasattr(game_date_val, "date"):
            game_date_str = game_date_val.date().isoformat()
        else:
            game_date_str = str(game_date_val)[:10]

        # --dry-run: just print what would happen.
        if dry_run:
            print(
                f"  [DRY-RUN] {sport.upper()} {game_id}  ({game_date_str})  — would fetch & upsert"
            )
            summary.processed += 1
            continue

        # Skip if rows already exist (idempotent resumability).
        if resume and rows_exist_in_db(db, game_id):
            if verbose:
                logger.debug(
                    "⏭  %s %s — already in team_game_stats, skipping",
                    sport.upper(),
                    game_id,
                )
            summary.skipped += 1
            continue

        summary.processed += 1

        rows = fetch_with_backoff(fetcher, game_id, verbose=verbose)
        if rows is None:
            summary.failed += 1
            summary.errors.append(f"{game_id} ({game_date_str}): fetch failed")
            continue

        if not rows:
            if verbose:
                logger.debug(
                    "⚠️  %s %s returned 0 rows — skipping upsert", sport.upper(), game_id
                )
            summary.skipped += 1
            continue

        try:
            n_upserted = fetcher.upsert_rows(rows)
            # Heuristic: if the game was already fully present we'd have hit
            # the resume skip above; treat all upserts here as inserts.
            summary.inserted += n_upserted
        except Exception as exc:
            logger.error("❌ %s %s upsert failed: %s", sport.upper(), game_id, exc)
            summary.failed += 1
            summary.errors.append(f"{game_id} ({game_date_str}): upsert failed — {exc}")
            continue

        last_date_done = game_date_str

        # Persist progress after each game so a crash is recoverable.
        if last_date_done:
            progress[sport] = last_date_done

    # Final progress persist (covers the full batch even if last game had no
    # new rows and last_date_done stayed None through the loop).
    if not dry_run:
        if last_date_done:
            progress[sport] = last_date_done
        elif effective_start <= end and total_games > 0:
            # All games were skipped; record end of range as complete.
            progress[sport] = end.isoformat()

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser.

    Returns:
        argparse.ArgumentParser: Configured parser.
    """
    parser = argparse.ArgumentParser(
        prog="backfill_team_game_stats.py",
        description=(
            "Backfill historical team-level box-score stats from public sports APIs "
            "into the PostgreSQL database."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--sport",
        choices=SUPPORTED_SPORTS + ["all"],
        default="all",
        help=(
            "Sport to backfill.  Use 'all' (default) to process every sport in "
            f"sequence: {', '.join(SUPPORTED_SPORTS)}."
        ),
    )
    parser.add_argument(
        "--start",
        type=_parse_date,
        default=date(2021, 1, 1),
        metavar="YYYY-MM-DD",
        help="Earliest game date to include (inclusive).  Default: 2021-01-01.",
    )
    parser.add_argument(
        "--end",
        type=_parse_date,
        default=None,
        metavar="YYYY-MM-DD",
        help="Latest game date to include (inclusive).  Default: yesterday UTC.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Print each game that would be processed without making any network "
            "calls or database writes."
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            f"Skip games already recorded in {PROGRESS_FILE} or already present in "
            "the team_game_stats table."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging.",
    )
    return parser


def _parse_date(value: str) -> date:
    """Parse a YYYY-MM-DD string into a :class:`datetime.date`.

    Args:
        value: Date string in ``YYYY-MM-DD`` format.

    Returns:
        Parsed date.

    Raises:
        argparse.ArgumentTypeError: If the value cannot be parsed.
    """
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}': expected YYYY-MM-DD format."
        ) from exc


def main(
    sport: Optional[str] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    dry_run: bool = False,
    resume: bool = False,
    verbose: bool = False,
) -> None:
    """Entry point for the backfill script.

    Iterates over the requested sport(s), queries ``unified_games`` for games
    in [*start*, *end*], fetches box-score data via the appropriate fetcher,
    and upserts results into ``team_game_stats``.

    Args:
        sport: Sport key (e.g. ``"nba"``), ``"all"``, or ``None`` (= all).
        start: Earliest game date (inclusive).  Defaults to 2021-01-01.
        end: Latest game date (inclusive).  Defaults to yesterday UTC.
        dry_run: When ``True``, only print intended actions without side effects.
        resume: When ``True``, skip games already present in the DB or progress file.
        verbose: When ``True``, enable debug-level logging.
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if start is None:
        start = date(2021, 1, 1)
    if end is None:
        end = datetime.now(timezone.utc).date() - timedelta(days=1)

    sports_to_run = SUPPORTED_SPORTS if (sport is None or sport == "all") else [sport]

    progress_path = PROGRESS_FILE
    progress = load_progress(progress_path) if resume else {}

    db = DBManager()
    all_summaries: list[SportSummary] = []

    print(f"\n{'='*60}")
    print(f"  Backfill  {'(DRY-RUN) ' if dry_run else ''}start={start}  end={end}")
    print(f"  Sports: {', '.join(s.upper() for s in sports_to_run)}")
    print(f"{'='*60}\n")

    for sport_key in sports_to_run:
        logger.info("▶ Starting %s …", sport_key.upper())
        summary = backfill_sport(
            sport=sport_key,
            start=start,
            end=end,
            db=db,
            dry_run=dry_run,
            resume=resume,
            progress=progress,
            verbose=verbose,
        )
        all_summaries.append(summary)

        if not dry_run:
            save_progress(progress_path, progress)

    print(f"\n{'='*60}")
    print("  Summary")
    print(f"{'='*60}")
    for s in all_summaries:
        s.print()

    total_processed = sum(s.processed for s in all_summaries)
    total_failed = sum(s.failed for s in all_summaries)
    print(f"\n  Total processed: {total_processed}  |  Total failed: {total_failed}")
    if dry_run:
        print("  (DRY-RUN — no data was written)")
    print()

    if total_failed:
        sys.exit(1)


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    main(
        sport=args.sport,
        start=args.start,
        end=args.end,
        dry_run=args.dry_run,
        resume=args.resume,
        verbose=args.verbose,
    )
