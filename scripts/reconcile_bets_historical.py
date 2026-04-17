#!/usr/bin/env python3
"""
Reconcile Placed Bets – Historical Backfill
============================================

CLI script that reconciles all local ``placed_bets`` rows against Kalshi's
source-of-truth fills, optionally starting from a configurable date.

Usage
-----
    python scripts/reconcile_bets_historical.py
    python scripts/reconcile_bets_historical.py --since 2024-01-01
    python scripts/reconcile_bets_historical.py --since 2024-06-01 --dry-run

The script is **idempotent**: re-running it will not produce duplicate audit
rows because the reconciliation only writes rows when discrepancies are found,
and ``insert_missing_bet`` returns ``False`` (no-op) on duplicates.

Exit codes
----------
0 – success (even if discrepancies were found)
1 – unhandled exception / configuration error
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure plugins/ is on the import path when running as a standalone script
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "plugins"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _earliest_bet_date(db) -> date | None:
    """Query the earliest placed bet date from placed_bets.

    Args:
        db: A ``DBManager`` instance.

    Returns:
        The earliest ``placed_date`` (or ``placed_time_utc``) as a ``date``,
        or ``None`` when the table is empty or both columns are absent.
    """
    # Try placed_time_utc first (timestamp), then placed_date (text/date)
    for col in ("placed_time_utc", "placed_date"):
        try:
            df = db.fetch_df(
                f"SELECT MIN({col}) AS min_date FROM placed_bets WHERE {col} IS NOT NULL"
            )
            if not df.empty and df["min_date"].iloc[0] is not None:
                raw = df["min_date"].iloc[0]
                if isinstance(raw, date):
                    return raw
                # Coerce string/Timestamp → date
                from pandas import Timestamp

                if isinstance(raw, Timestamp):
                    return raw.date()
                return date.fromisoformat(str(raw)[:10])
        except Exception:
            continue
    return None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile placed_bets against Kalshi fills. "
            "Defaults to processing all bets since the earliest bet date."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        default=None,
        help=(
            "Only reconcile bets placed on or after this date. "
            "Default: earliest placed bet date from the database."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=(
            "Print what would be reconciled without making any changes. "
            "NOTE: Kalshi API calls are still made to fetch state."
        ),
    )
    parser.add_argument(
        "--output-json",
        metavar="FILE",
        default=None,
        help="Write the summary dict as JSON to this file path.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Enable DEBUG logging.",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    args = _parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # ---- Set up DB connection -----------------------------------------------
    try:
        from db_manager import DBManager

        db = DBManager()
    except Exception as exc:
        logger.error("❌ Could not connect to database: %s", exc)
        return 1

    # ---- Determine since_date -----------------------------------------------
    since_date: date | None = None
    if args.since:
        try:
            since_date = date.fromisoformat(args.since)
        except ValueError:
            logger.error(
                "❌ Invalid --since date '%s'. Expected YYYY-MM-DD.", args.since
            )
            return 1
    else:
        since_date = _earliest_bet_date(db)
        if since_date is not None:
            logger.info("📅 Using earliest bet date from DB: %s", since_date)
        else:
            logger.info("📅 No existing bets found; reconciling all fills from Kalshi.")

    # ---- Dry-run mode --------------------------------------------------------
    if args.dry_run:
        logger.info("🔍 DRY-RUN mode – no database changes will be written.")
        logger.info("    Would reconcile bets since: %s", since_date or "all time")
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "since_date": str(since_date) if since_date else None,
                    "message": "No changes made (dry-run).",
                },
                indent=2,
            )
        )
        return 0

    # ---- Run reconciliation --------------------------------------------------
    try:
        from bet_reconciliation import reconcile_all

        logger.info("🔄 Starting reconciliation (since=%s) …", since_date or "all time")
        summary = reconcile_all(db=db, since_date=since_date)
    except Exception as exc:
        logger.error("❌ Reconciliation failed: %s", exc, exc_info=True)
        return 1

    # ---- Print summary -------------------------------------------------------
    print("\n" + "=" * 60)
    print("  Bet Reconciliation Summary")
    print("=" * 60)
    print(f"  Since date          : {since_date or 'all time'}")
    print(f"  Run ID              : {summary.get('run_id', 'N/A')}")
    print(f"  Bets checked        : {summary.get('checked', 0)}")
    print(f"  Discrepancies found : {summary.get('discrepancies', 0)}")
    print(f"  Corrected           : {summary.get('corrected', 0)}")
    print(f"  Missing → inserted  : {summary.get('missing_locally_inserted', 0)}")
    print(f"  Missing on Kalshi   : {summary.get('missing_on_kalshi', 0)}")
    print(f"  Audit rows written  : {summary.get('audit_rows_written', 0)}")
    print("=" * 60 + "\n")

    # ---- Optional JSON output -----------------------------------------------
    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {**summary, "since_date": str(since_date) if since_date else None},
                indent=2,
                default=str,
            )
        )
        logger.info("📄 Summary written to %s", out_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
