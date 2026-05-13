#!/usr/bin/env python3
"""Import free historical MLB opening/closing odds into PostgreSQL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugins.db_manager import default_db  # noqa: E402
from plugins.mlb_modeling.free_odds_sources import (  # noqa: E402
    DEFAULT_FREE_HISTORICAL_ODDS_URL,
    save_free_historical_mlb_odds,
)


def main() -> int:
    """CLI entry point for importing free historical MLB odds."""
    parser = argparse.ArgumentParser(
        description="Import free historical MLB moneyline odds into PostgreSQL."
    )
    parser.add_argument(
        "input_path",
        help=(
            "Path to a downloaded free historical odds CSV/XLSX, e.g. a "
            "Princeton Historical Sports Odds export."
        ),
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Optional source label stored in mlb_odds_snapshots. Defaults by file format.",
    )
    args = parser.parse_args()

    inserted = save_free_historical_mlb_odds(
        db=default_db,
        path=args.input_path,
        source=args.source,
    )
    print(f"Imported {inserted} MLB odds snapshots from {args.input_path}")
    print(f"Suggested free source: {DEFAULT_FREE_HISTORICAL_ODDS_URL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
