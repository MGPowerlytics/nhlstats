#!/usr/bin/env python3
"""One-shot Understat xG/xGA enrichment pass on existing EPL historical data.

Approach
--------
For each EPL season starting from 2021-22 through the current season, the
script:

1. Fetches all completed Understat matches for the season via
   ``UnderstatLeagueClient.fetch_league_matches()``.
2. Identifies EPL game_ids in ``soccer_team_game_stats_ext`` whose ``xg``
   column is ``NULL``.
3. For each such game_id, extracts the game date and home/away team names
   from ``unified_games``, then looks up the corresponding Understat match
   using the same date + team names.
4. Issues a targeted ``UPDATE`` on ``soccer_team_game_stats_ext`` to set
   ``xg`` and ``xga`` for the matched home and away rows.

Rate limits (3s between Understat API calls) are observed.  Progress is
recorded to ``data/understat_enrichment_progress.json`` keyed by season
so the script can be safely interrupted and resumed with ``--resume``.

Usage examples
--------------
::

    # Preview scope for 2021-08-01 onwards
    python scripts/enrich_epl_understat.py --dry-run --start 2021-08-01

    # Full backfill
    python scripts/enrich_epl_understat.py

    # Resume a previously interrupted run
    python scripts/enrich_epl_understat.py --resume

    # Targeted date range with verbose logging
    python scripts/enrich_epl_understat.py --start 2023-08-01 --end 2024-06-30 \\
        --verbose
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path bootstrapping
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from plugins.db_manager import DBManager  # noqa: E402
from plugins.naming_resolver import NamingContext, NamingResolver  # noqa: E402
from plugins.stats.understat_client import UnderstatLeagueClient  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROGRESS_FILE = Path("data/understat_enrichment_progress.json")
RATE_LIMIT_SECONDS = 3.0

# EPL seasons to process (Understat season = start year, e.g. 2021 = 2021-22)
EPL_SEASONS_START_YEAR = 2021

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("enrich_epl_understat")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _understat_seasons(start: date, end: date) -> list[int]:
    """Return list of Understat season start years for the date range.

    Understat seasons span August–May, so a match in say January 2022 belongs
    to the 2021 (2021-22) season.

    Args:
        start: Inclusive start of date range.
        end: Inclusive end of date range.

    Returns:
        Sorted list of season start years (e.g. ``[2021, 2022, 2023]``).
    """
    start_season = start.year if start.month >= 8 else start.year - 1
    end_season = end.year if end.month >= 8 else end.year - 1
    return list(range(max(start_season, EPL_SEASONS_START_YEAR), end_season + 1))


def _resolve_epl_team(raw_name: str) -> str:
    """Resolve an EPL team name to the canonical storage name.

    Uses the same resolution path as the SoccerBoxScoreFetcher
    (kalshi source) to ensure consistent team naming.

    Args:
        raw_name: Team name from any source.

    Returns:
        Canonical EPL team name as stored in the database.
    """
    return NamingResolver.resolve(
        NamingContext(sport="epl", source="kalshi", name=raw_name)
    )


# ---------------------------------------------------------------------------
# Progress helpers
# ---------------------------------------------------------------------------


def load_progress(path: Path) -> dict[str, Any]:
    """Load progress from *path*.

    Args:
        path: Path to the JSON progress file.

    Returns:
        Dict mapping season key → last completed date or "complete".
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


def save_progress(path: Path, progress: dict[str, Any]) -> None:
    """Persist *progress* dict to *path* atomically.

    Args:
        path: Destination path for the JSON file.
        progress: Dict mapping season key → status.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


@dataclass
class EnrichmentSummary:
    """Counts of enrichment outcomes."""

    seasons_processed: int = 0
    understat_matches_fetched: int = 0
    games_needing_enrichment: int = 0
    enriched: int = 0
    skipped_no_understat_match: int = 0
    skipped_already_done: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core enrichment logic
# ---------------------------------------------------------------------------


def enrich_season(
    season_start_year: int,
    db: DBManager,
    understat_client: UnderstatLeagueClient,
    dry_run: bool,
    verbose: bool,
) -> EnrichmentSummary:
    """Enrich one EPL season with Understat xG/xGA.

    Args:
        season_start_year: Understat season start year (e.g. 2021 for 2021-22).
        db: Database manager.
        understat_client: Pre-configured Understat client.
        dry_run: When True, only log intended actions.
        verbose: When True, enable debug logging.

    Returns:
        Summary of enrichment outcomes.
    """
    summary = EnrichmentSummary()
    season_label = f"{season_start_year}-{str(season_start_year + 1)[2:]}"

    if not dry_run:
        logger.info("🌐 Fetching Understat data for %s season…", season_label)
        try:
            understat_matches = understat_client.fetch_league_matches(
                sport="EPL", season=season_start_year
            )
        except Exception as exc:
            summary.errors.append(
                f"Failed to fetch Understat season {season_start_year}: {exc}"
            )
            return summary

        # Respect rate limit after the Understat API call
        time.sleep(RATE_LIMIT_SECONDS)

        summary.understat_matches_fetched = len(understat_matches)
        logger.info(
            "✓ Fetched %d Understat matches for %s",
            len(understat_matches),
            season_label,
        )

        # Build lookup: (game_date, home_team, away_team) -> match
        understat_lookup: dict[tuple[date, str, str], dict[str, Any]] = {}
        for um in understat_matches:
            gd = date.fromisoformat(um["game_date"])
            understat_lookup[(gd, um["home_team"], um["away_team"])] = um
    else:
        understat_lookup = {}

    # ---------------------------------------------------------------
    # Query DB for games needing enrichment in this season's date range
    # ---------------------------------------------------------------
    season_start = date(season_start_year, 8, 1)
    season_end = date(season_start_year + 1, 7, 31)

    try:
        target_games = db.fetch_df(
            """
            SELECT u.game_id, u.game_date,
                   u.home_team_name, u.away_team_name,
                   h.team AS home_stored_team,
                   a.team AS away_stored_team
              FROM unified_games u
              JOIN team_game_stats h
                ON u.game_id = h.game_id AND h.is_home = TRUE
              JOIN team_game_stats a
                ON u.game_id = a.game_id AND a.is_home = FALSE
             WHERE u.sport = 'EPL'
               AND u.game_date BETWEEN :start_date AND :end_date
               AND EXISTS (
                   SELECT 1 FROM soccer_team_game_stats_ext e
                    WHERE e.game_id = u.game_id
                      AND e.xg IS NULL
               )
             ORDER BY u.game_date, u.game_id
            """,
            {
                "start_date": season_start.isoformat(),
                "end_date": season_end.isoformat(),
            },
        )
    except Exception as exc:
        summary.errors.append(f"DB query failed for season {season_label}: {exc}")
        return summary

    if target_games.empty:
        logger.info("ℹ️  %s: no games need enrichment", season_label)
        return summary

    summary.games_needing_enrichment = len(target_games)
    logger.info(
        "🏟️  %s: %d game(s) with NULL xg found",
        season_label,
        len(target_games),
    )

    # ---------------------------------------------------------------
    # Build a DB-side index of existing (game_id, team) -> current xg
    # to detect already-done rows efficiently.
    # ---------------------------------------------------------------
    if not dry_run:
        try:
            existing_ext = db.fetch_df(
                """
                SELECT game_id, team, xg
                  FROM soccer_team_game_stats_ext
                 WHERE game_id LIKE 'EPL_%%'
                   AND xg IS NOT NULL
                """
            )
            already_done: set[tuple[str, str]] = set()
            if not existing_ext.empty:
                for _, row in existing_ext.iterrows():
                    already_done.add((str(row["game_id"]), str(row["team"])))
        except Exception as exc:
            logger.warning("⚠️  Could not pre-fetch existing xg rows: %s", exc)
            already_done = set()
    else:
        already_done = set()

    # ---------------------------------------------------------------
    # Process each game
    # ---------------------------------------------------------------
    for _, game_row in target_games.iterrows():
        game_id = str(game_row["game_id"])
        game_date_val = game_row["game_date"]
        raw_home = str(game_row["home_team_name"])
        raw_away = str(game_row["away_team_name"])

        if hasattr(game_date_val, "date"):
            gd = game_date_val.date()
        else:
            gd = date.fromisoformat(str(game_date_val)[:10])

        # Resolve team names to canonical (long) form for Understat lookup key.
        # The Understat client uses long-form names, so the lookup dict key
        # must match those long names.
        home_team_resolved = _resolve_epl_team(raw_home)
        away_team_resolved = _resolve_epl_team(raw_away)

        # The stored DB team names (short form like "Newcastle") are what
        # team_game_stats.team actually contains — use these for UPDATE WHERE.
        home_stored_team = str(game_row["home_stored_team"])
        away_stored_team = str(game_row["away_stored_team"])

        if dry_run:
            print(
                f"  [DRY-RUN] {game_id}  ({gd.isoformat()})  "
                f"{home_team_resolved} vs {away_team_resolved}  "
                f"[stored: {home_stored_team} vs {away_stored_team}]"
                " — would enrich xg/xga"
            )
            continue

        # Check if both rows already have xg (using stored team names)
        home_key = (game_id, home_stored_team)
        away_key = (game_id, away_stored_team)
        if home_key in already_done and away_key in already_done:
            summary.skipped_already_done += 1
            if verbose:
                logger.debug("⏭  %s — both teams already have xg, skipping", game_id)
            continue

        # Look up Understat match using resolved (long) names
        match: dict[str, Any] | None = understat_lookup.get(
            (gd, home_team_resolved, away_team_resolved)
        )
        if match is None:
            # Try reversed (in case Understat has home/away swapped vs DB)
            match = understat_lookup.get(
                (gd, away_team_resolved, home_team_resolved)
            )
        if match is None:
            summary.skipped_no_understat_match += 1
            logger.warning(
                "⚠️  No Understat match found for %s (%s vs %s on %s)",
                game_id,
                home_team_resolved,
                away_team_resolved,
                gd,
            )
            # Also check if maybe the team names in understat are slightly different
            # Build broader search
            for key, m in understat_lookup.items():
                key_date, key_home, key_away = key
                if key_date == gd:
                    candidates = []
                    if (
                        key_home.upper().replace(" ", "")
                        == home_team_resolved.upper().replace(" ", "")
                    ):
                        candidates.append(key)
                    if (
                        key_away.upper().replace(" ", "")
                        == away_team_resolved.upper().replace(" ", "")
                    ):
                        candidates.append(key)
                    if candidates:
                        logger.warning(
                            "  → Found near-match: (%s vs %s) — possible name mismatch. "
                            "DB: '%s'/'%s', Understat: '%s'/'%s'",
                            key_home,
                            key_away,
                            home_team_resolved,
                            away_team_resolved,
                            key_home,
                            key_away,
                        )
                        break
            continue

        home_xg = float(match["home_xg"])
        away_xg = float(match["away_xg"])

        try:
            # UPDATE home row using stored (raw DB) team name
            if home_key not in already_done:
                db.execute(
                    """
                    UPDATE soccer_team_game_stats_ext
                       SET xg = :xg, xga = :xga
                     WHERE game_id = :game_id AND team = :team
                    """,
                    {
                        "game_id": game_id,
                        "team": home_stored_team,
                        "xg": home_xg,
                        "xga": away_xg,
                    },
                )
                summary.enriched += 1
                if verbose:
                    logger.debug(
                        "  ✓ Home %s: xg=%.3f xga=%.3f (team=%s)",
                        game_id, home_xg, away_xg, home_stored_team,
                    )

            # UPDATE away row using stored (raw DB) team name
            if away_key not in already_done:
                db.execute(
                    """
                    UPDATE soccer_team_game_stats_ext
                       SET xg = :xg, xga = :xga
                     WHERE game_id = :game_id AND team = :team
                    """,
                    {
                        "game_id": game_id,
                        "team": away_stored_team,
                        "xg": away_xg,
                        "xga": home_xg,
                    },
                )
                summary.enriched += 1
                if verbose:
                    logger.debug(
                        "  ✓ Away %s: xg=%.3f xga=%.3f (team=%s)",
                        game_id, away_xg, home_xg, away_stored_team,
                    )

            # Check for warning: if home team name doesn't match what Understat has
            if match["home_team"] != home_team_resolved:
                logger.debug(
                    "ℹ️  Name resolution: DB '%s' → Understat home '%s'",
                    home_team_resolved,
                    match["home_team"],
                )
        except Exception as exc:
            summary.errors.append(f"UPDATE failed for {game_id}: {exc}")
            logger.error("❌ UPDATE failed for %s: %s", game_id, exc)

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
        prog="enrich_epl_understat.py",
        description=(
            "One-shot Understat xG/xGA enrichment pass on existing EPL "
            "historical data back to 2021."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--start",
        type=_parse_date,
        default=date(2021, 8, 1),
        metavar="YYYY-MM-DD",
        help="Earliest game date to include (inclusive).  Default: 2021-08-01.",
    )
    parser.add_argument(
        "--end",
        type=_parse_date,
        default=None,
        metavar="YYYY-MM-DD",
        help="Latest game date to include (inclusive).  Default: tomorrow UTC.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Print each game that would be enriched without making any "
            "Understat API calls or database writes."
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(f"Skip seasons already marked complete in {PROGRESS_FILE}."),
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(
    start: date | None = None,
    end: date | None = None,
    dry_run: bool = False,
    resume: bool = False,
    verbose: bool = False,
) -> None:
    """Entry point for the enrichment script.

    Iterates over EPL Understat seasons in [*start*, *end*], fetches Understat
    match data, and updates ``soccer_team_game_stats_ext`` rows.

    Args:
        start: Earliest game date (inclusive).  Defaults to 2021-08-01.
        end: Latest game date (inclusive).  Defaults to tomorrow UTC.
        dry_run: When ``True``, only print intended actions.
        resume: When ``True``, skip seasons already complete in progress file.
        verbose: When ``True``, enable debug-level logging.
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if start is None:
        start = date(2021, 8, 1)
    if end is None:
        end = datetime.now(timezone.utc).date() + timedelta(days=1)

    seasons = _understat_seasons(start, end)
    progress = load_progress(PROGRESS_FILE) if resume else {}
    db = DBManager()
    understat_client = UnderstatLeagueClient()

    all_seasons_summary: dict[str, EnrichmentSummary] = {}

    print(f"\n{'=' * 60}")
    print(f"  EPL Understat Enrichment  {'(DRY-RUN) ' if dry_run else ''}")
    print(f"  Date range: {start} → {end}")
    print(f"  Seasons: {', '.join(str(s) for s in seasons)}")
    if resume:
        completed = [k for k, v in progress.items() if v == "complete"]
        if completed:
            print(f"  Resuming — already complete: {', '.join(completed)}")
    print(f"{'=' * 60}\n")

    for season_start_year in seasons:
        season_key = str(season_start_year)

        if resume and progress.get(season_key) == "complete":
            logger.info(
                "⏭  Season %s-%s already complete — skipping",
                season_start_year,
                str(season_start_year + 1)[2:],
            )
            continue

        logger.info(
            "▶ Season %s-%s …",
            season_start_year,
            str(season_start_year + 1)[2:],
        )

        summary = enrich_season(
            season_start_year=season_start_year,
            db=db,
            understat_client=understat_client,
            dry_run=dry_run,
            verbose=verbose,
        )
        all_seasons_summary[season_key] = summary

        if not dry_run:
            progress[season_key] = "complete"
            save_progress(PROGRESS_FILE, progress)

    # ---------- Final summary ----------
    print(f"\n{'=' * 60}")
    print("  Summary")
    print(f"{'=' * 60}")

    total_enriched = 0
    total_fetched = 0
    total_needed = 0
    total_no_match = 0
    total_skipped_done = 0
    total_errors = 0
    total_warnings = 0

    for season_key, summary in all_seasons_summary.items():
        season_label = f"{season_key}-{str(int(season_key) + 1)[2:]}"
        print(
            f"  {season_label:<10}  "
            f"Understat matches fetched: {summary.understat_matches_fetched:<4}  "
            f"Games needing enrichment: {summary.games_needing_enrichment:<4}  "
            f"Enriched: {summary.enriched:<4}  "
            f"No Understat match: {summary.skipped_no_understat_match:<3}  "
            f"Already done: {summary.skipped_already_done:<3}  "
            f"Errors: {len(summary.errors)}"
        )
        total_enriched += summary.enriched
        total_fetched += summary.understat_matches_fetched
        total_needed += summary.games_needing_enrichment
        total_no_match += summary.skipped_no_understat_match
        total_skipped_done += summary.skipped_already_done
        total_errors += len(summary.errors)
        total_warnings += len(summary.warnings)

        for err in summary.errors[:3]:
            print(f"    ❌ {err}")

    if not all_seasons_summary and resume:
        print("  (All seasons already complete — nothing to do)")

    print(f"\n  Total Understat matches fetched: {total_fetched}")
    print(f"  Total games needing enrichment: {total_needed}")
    print(f"  Total enriched: {total_enriched}")
    print(f"  No Understat match: {total_no_match}")
    print(f"  Already had xg: {total_skipped_done}")
    print(f"  Errors: {total_errors}")

    if dry_run:
        print("  (DRY-RUN — no data was written)")
    print()

    if total_errors:
        sys.exit(1)


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    main(
        start=args.start,
        end=args.end,
        dry_run=args.dry_run,
        resume=args.resume,
        verbose=args.verbose,
    )
