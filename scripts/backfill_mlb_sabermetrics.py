#!/usr/bin/env python
"""
Backfill MLB sabermetrics feature tables from historical game data.

Populates (in order):
  1. mlb_player_game_batting_stats   — from MLB Stats API boxscore/live-feed
  2. mlb_player_game_pitching_stats  — from MLB Stats API boxscore/live-feed
  3. mlb_pitch_level_features        — from MLB Stats API live-feed
  4. mlb_player_rolling_features     — computed from the stats tables
  5. mlb_matchup_features            — assembled from rolling + other sources

Usage:
    python scripts/backfill_mlb_sabermetrics.py [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
    python scripts/backfill_mlb_sabermetrics.py --rolling-only
    python scripts/backfill_mlb_sabermetrics.py --matchup-only
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

# Ensure plugins directory is importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from plugins.db_manager import default_db as db
from plugins.mlb_modeling.player_stats_fetcher import MLBPlayerStatsFetcher

logger = logging.getLogger("backfill_mlb")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

_COMPLETED_GAMES_SQL = """
    SELECT game_id::TEXT AS game_id, game_date, home_team, away_team,
           home_score, away_score, status
    FROM mlb_games
    WHERE status IN ('Final', 'Game Over', 'Completed Early')
      AND home_score IS NOT NULL
      AND away_score IS NOT NULL
      AND game_date BETWEEN :start_date AND :end_date
    ORDER BY game_date, game_id
"""

_PROCESSED_GAME_IDS_SQL = """
    SELECT DISTINCT game_id::TEXT
    FROM mlb_player_game_pitching_stats
"""

_GAME_DATE_COUNT_SQL = """
    SELECT COUNT(DISTINCT game_id) AS cnt
    FROM mlb_player_game_pitching_stats
"""

# ---------------------------------------------------------------------------
# Checkpoint (simple text file with last-processed game_id)
# ---------------------------------------------------------------------------

CHECKPOINT_FILE = _REPO_ROOT / "data" / ".mlb_sabermetrics_backfill_checkpoint"


def _load_checkpoint() -> Optional[str]:
    if CHECKPOINT_FILE.exists():
        return CHECKPOINT_FILE.read_text().strip() or None
    return None


def _save_checkpoint(game_id: str) -> None:
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(game_id)


# ---------------------------------------------------------------------------
# Signal handling for graceful shutdown
# ---------------------------------------------------------------------------

_shutdown_requested = False


def _handle_signal(signum: int, frame: object) -> None:
    global _shutdown_requested
    logger.info("Shutdown requested — will stop after current game completes.")
    _shutdown_requested = True


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ---------------------------------------------------------------------------
# Stage 1: Player stats
# ---------------------------------------------------------------------------


def backfill_player_stats(
    start_date: date,
    end_date: date,
    *,
    resume: bool = True,
) -> tuple[int, int]:
    """Fetch and store player stats for all completed games in the date range.

    Returns (games_processed, games_skipped).
    """
    games = db.fetch_df(
        _COMPLETED_GAMES_SQL,
        {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
    )

    if games is None or games.empty:
        logger.info("No completed games found in %s to %s.", start_date, end_date)
        return 0, 0

    # Determine which games are already processed
    processed_result = db.execute(_PROCESSED_GAME_IDS_SQL)
    processed_ids: set[str] = set()
    if processed_result:
        for row in processed_result:
            processed_ids.add(str(row[0]))

    # Load checkpoint (resume from last game)
    checkpoint_id = _load_checkpoint() if resume else None
    past_checkpoint = checkpoint_id is None

    fetcher = MLBPlayerStatsFetcher(db=db)
    processed = 0
    skipped = 0
    total = len(games)

    logger.info(
        "Stage 1: Player stats backfill — %d games, %d already processed, "
        "checkpoint=%s",
        total,
        len(processed_ids),
        checkpoint_id,
    )

    start = time.monotonic()
    for idx, (_, game) in enumerate(games.iterrows()):
        if _shutdown_requested:
            logger.info("Shutting down. Progress saved at game_id=%s.", checkpoint_id)
            break

        game_id = str(game["game_id"])
        game_date_val = game["game_date"]

        # Skip past the checkpoint
        if not past_checkpoint:
            if game_id == checkpoint_id:
                past_checkpoint = True
            else:
                continue

        # Skip already-processed games
        if game_id in processed_ids:
            skipped += 1
            continue

        try:
            result = fetcher.fetch_game_stats(
                game_id,
                game_date=(
                    game_date_val
                    if isinstance(game_date_val, date)
                    else date.fromisoformat(str(game_date_val))
                ),
            )
            fetcher.upsert_all(result)
            processed += 1
            checkpoint_id = game_id
            _save_checkpoint(game_id)

            elapsed = time.monotonic() - start
            rate = (processed + skipped) / elapsed if elapsed > 0 else 0
            pct = (idx + 1) / total * 100
            logger.info(
                "[%d/%d] %.1f%%  game_id=%s  date=%s  %s @ %s  "
                "(bat=%d pit=%d pf=%d)  rate=%.1f g/s",
                idx + 1,
                total,
                pct,
                game_id,
                game_date_val,
                f"{game['away_team']} @ {game['home_team']}",
                game.get("status", "?"),
                len(result.batting_rows),
                len(result.pitching_rows),
                len(result.pitch_features),
                rate,
            )
        except Exception as exc:
            logger.error(
                "Failed to fetch stats for game %s (%s @ %s, %s): %s",
                game_id,
                game.get("away_team", "?"),
                game.get("home_team", "?"),
                game_date_val,
                exc,
            )
            # Don't checkpoint on failure — retry next run

    # Clear checkpoint when complete
    if not _shutdown_requested:
        CHECKPOINT_FILE.unlink(missing_ok=True)

    elapsed = time.monotonic() - start
    logger.info(
        "Stage 1 complete: %d processed, %d skipped in %.1f min",
        processed,
        skipped,
        elapsed / 60,
    )
    return processed, skipped


# ---------------------------------------------------------------------------
# Stage 2: Rolling features
# ---------------------------------------------------------------------------


def backfill_rolling_features(
    start_date: date,
    end_date: date,
) -> int:
    """Compute rolling features for each game date in the range.

    Returns total rows upserted.
    """
    from plugins.mlb_modeling.rolling_features import compute_all_rolling_features

    # Get distinct dates that have games with pitching stats
    dates_df = db.fetch_df(
        """
        SELECT DISTINCT m.game_date
        FROM mlb_games m
        JOIN mlb_player_game_pitching_stats p ON m.game_id::TEXT = p.game_id
        WHERE m.game_date BETWEEN :start_date AND :end_date
        ORDER BY m.game_date
        """,
        {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
    )

    if dates_df is None or dates_df.empty:
        logger.info("No dates with stats to compute rolling features for.")
        return 0

    dates: list[date] = []
    for _, row in dates_df.iterrows():
        d = row["game_date"]
        if isinstance(d, date):
            dates.append(d)
        else:
            dates.append(date.fromisoformat(str(d)))

    logger.info(
        "Stage 2: Rolling features for %d dates (%s to %s)",
        len(dates),
        dates[0] if dates else "?",
        dates[-1] if dates else "?",
    )

    total = 0
    start = time.monotonic()
    for i, d in enumerate(dates):
        if _shutdown_requested:
            break
        try:
            rows = compute_all_rolling_features(db, as_of_date=d)
            total += rows
            if rows > 0:
                logger.info(
                    "  [%d/%d] %s — %d rows upserted",
                    i + 1,
                    len(dates),
                    d,
                    rows,
                )
        except Exception:
            logger.exception("Failed to compute rolling features for %s", d)

    elapsed = time.monotonic() - start
    logger.info(
        "Stage 2 complete: %d total rows upserted in %.1f min",
        total,
        elapsed / 60,
    )
    return total


# ---------------------------------------------------------------------------
# Stage 3: Matchup features
# ---------------------------------------------------------------------------


def backfill_matchup_features(
    start_date: date,
    end_date: date,
) -> int:
    """Assemble matchup feature vectors for historical completed games.

    Uses ``assemble_matchup_features`` to reconstruct pre-game feature
    vectors for each completed game, then persists them via the
    matchup-feature upsert SQL.

    Returns number of games assembled.
    """
    from plugins.mlb_modeling.matchup_assembler import (
        assemble_matchup_features,
        _upsert_matchup_features,
    )

    games = db.fetch_df(
        """
        SELECT m.game_id::TEXT AS game_id, m.game_date, m.home_team, m.away_team
        FROM mlb_games m
        WHERE m.status IN ('Final', 'Game Over', 'Completed Early')
          AND m.home_score IS NOT NULL
          AND m.away_score IS NOT NULL
          AND m.game_date BETWEEN :start_date AND :end_date
        ORDER BY m.game_date, m.game_id
        """,
        {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
    )

    if games is None or games.empty:
        logger.info("No games to assemble matchup features for.")
        return 0

    # Skip games already in matchup_features
    existing_result = db.execute(
        "SELECT DISTINCT game_id FROM mlb_matchup_features"
    )
    existing: set[str] = set()
    if existing_result:
        for row in existing_result:
            existing.add(str(row[0]))

    assembled = 0
    skipped = 0
    total = len(games)

    logger.info(
        "Stage 3: Matchup features for %d games (%d already processed)",
        total,
        len(existing),
    )

    start = time.monotonic()
    for idx, (_, game) in enumerate(games.iterrows()):
        if _shutdown_requested:
            break

        game_id = str(game["game_id"])
        if game_id in existing:
            skipped += 1
            continue

        game_date_val = game["game_date"]
        if not isinstance(game_date_val, date):
            game_date_val = date.fromisoformat(str(game_date_val))

        try:
            result = assemble_matchup_features(
                db,
                game_id=game_id,
                home_team=str(game["home_team"]),
                away_team=str(game["away_team"]),
                game_date=game_date_val,
            )
            _upsert_matchup_features(db, result, game_id)
            assembled += 1

            if assembled % 50 == 0:
                elapsed = time.monotonic() - start
                rate = (assembled + skipped) / elapsed if elapsed > 0 else 0
                logger.info(
                    "  [%d/%d] %.1f%%  assembled=%d  rate=%.1f g/s",
                    idx + 1,
                    total,
                    (idx + 1) / total * 100,
                    assembled,
                    rate,
                )
        except Exception:
            logger.exception(
                "Failed to assemble matchup features for game %s (%s)",
                game_id,
                game_date_val,
            )

    elapsed = time.monotonic() - start
    logger.info(
        "Stage 3 complete: %d assembled, %d skipped in %.1f min",
        assembled,
        skipped,
        elapsed / 60,
    )
    return assembled


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill MLB sabermetrics feature tables"
    )
    parser.add_argument(
        "--start-date",
        type=_parse_date,
        default="2021-03-01",
        help="Start date for backfill (default: 2021-03-01)",
    )
    parser.add_argument(
        "--end-date",
        type=_parse_date,
        help="End date for backfill (default: today)",
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Only run Stage 1 (player stats from MLB API).",
    )
    parser.add_argument(
        "--rolling-only",
        action="store_true",
        help="Only run Stage 2 (rolling features from stats tables).",
    )
    parser.add_argument(
        "--matchup-only",
        action="store_true",
        help="Only run Stage 3 (matchup features from rolling data).",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not resume from checkpoint.",
    )
    args = parser.parse_args()

    end_date = args.end_date or date.today()

    logger.info("=" * 60)
    logger.info("MLB Sabermetrics Backfill")
    logger.info("  Range: %s to %s", args.start_date, end_date)
    logger.info("=" * 60)

    # Determine which stages to run
    stats_only = args.stats_only
    rolling_only = args.rolling_only
    matchup_only = args.matchup_only
    all_stages = not (stats_only or rolling_only or matchup_only)

    if stats_only or all_stages:
        logger.info("")
        processed, skipped = backfill_player_stats(
            args.start_date,
            end_date,
            resume=not args.no_resume,
        )
        if processed == 0 and not _shutdown_requested:
            logger.info("No new games to fetch — stats tables are up to date.")

    if rolling_only or all_stages:
        logger.info("")
        total = backfill_rolling_features(args.start_date, end_date)
        if total == 0 and not _shutdown_requested:
            logger.info(
                "No rolling features computed — "
                "ensure Stage 1 has populated stats tables first."
            )

    if matchup_only or all_stages:
        logger.info("")
        assembled = backfill_matchup_features(args.start_date, end_date)
        if assembled == 0 and not _shutdown_requested:
            logger.info(
                "No matchup features assembled — "
                "ensure Stage 2 has populated rolling features first."
            )

    if not _shutdown_requested:
        logger.info("\n✓ Backfill complete.")
    else:
        logger.info("\n⚠️  Backfill interrupted — re-run to continue.")


if __name__ == "__main__":
    main()
