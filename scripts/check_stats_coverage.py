#!/usr/bin/env python3
"""CLI tool to check unified_games coverage statistics for operators.

Queries unified_games and compares actual game counts to expected season
totals.  Useful for diagnosing incomplete data ingestion.

Usage::

    python scripts/check_stats_coverage.py
    python scripts/check_stats_coverage.py --sports NBA NHL
    python scripts/check_stats_coverage.py --seasons 2023 2024
    python scripts/check_stats_coverage.py --sports NBA --seasons 2024 --format json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Allow running from the repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from plugins.data_validation import validate_unified_games_coverage_for_stats

_STATUS_SYMBOLS: dict[str, str] = {
    "ok": "✅",
    "warn": "⚠️ ",
    "fail": "❌",
}


def _print_table(report: dict[str, Any]) -> None:
    """Print coverage report as a formatted table.

    Args:
        report: Nested dict from :func:`validate_unified_games_coverage_for_stats`.
    """
    if not report or "error" in report:
        error = report.get("error", "No data returned")
        print(f"❌ Error: {error}")
        return

    header = f"{'Sport':<14} {'Season':<8} {'Actual':>10} {'Expected':>10} {'Coverage':>10}  Status"
    separator = "-" * len(header)
    print(separator)
    print(header)
    print(separator)

    for sport in sorted(report):
        for season in sorted(report[sport]):
            data = report[sport][season]
            actual = data["actual"]
            expected = data["expected"]
            coverage = data["coverage_pct"]
            status = data["status"]
            symbol = _STATUS_SYMBOLS.get(status, "❓")
            coverage_str = f"{coverage * 100:.1f}%"
            print(
                f"{sport:<14} {str(season):<8} {actual:>10,} {expected:>10,} "
                f"{coverage_str:>10}  {symbol} {status}"
            )

    print(separator)


def _worst_status(report: dict[str, Any]) -> str:
    """Return the worst status across all entries.

    Args:
        report: Coverage report dict.

    Returns:
        One of ``"ok"``, ``"warn"``, or ``"fail"``.
    """
    statuses = [
        data["status"]
        for sport_data in report.values()
        if isinstance(sport_data, dict)
        for data in sport_data.values()
        if isinstance(data, dict) and "status" in data
    ]
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "ok"


def main() -> int:
    """Entry point for the coverage check CLI.

    Returns:
        Exit code: 0 = all ok, 1 = warnings, 2 = failures.
    """
    parser = argparse.ArgumentParser(
        description="Check unified_games coverage vs expected game counts."
    )
    parser.add_argument(
        "--sports",
        nargs="*",
        metavar="SPORT",
        help="Sports to check (e.g. NBA NHL EPL). Default: all.",
    )
    parser.add_argument(
        "--seasons",
        nargs="*",
        type=int,
        metavar="YEAR",
        help="Seasons to check (e.g. 2023 2024). Default: all.",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table).",
    )
    args = parser.parse_args()

    report = validate_unified_games_coverage_for_stats(
        sports=args.sports,
        seasons=args.seasons,
    )

    if args.format == "json":
        print(json.dumps(report, indent=2, default=str))
    else:
        _print_table(report)

    if "error" in report:
        return 2

    worst = _worst_status(report)
    if worst == "fail":
        print("\n❌ Coverage failures detected — check data ingestion pipelines.")
        return 2
    if worst == "warn":
        print("\n⚠️  Coverage warnings detected — some seasons may be incomplete.")
        return 1

    print("\n✅ All sports/seasons within expected coverage thresholds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
