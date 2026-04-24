#!/usr/bin/env python3
"""Verify naming resolver behavior against actual bet files."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import sys
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGINS_DIR = REPO_ROOT / "plugins"
DATA_DIR = REPO_ROOT / "data"

if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))

from naming_resolver import NamingContext, NamingResolver


SUPPORTED_SPORTS = ("epl", "nba", "mlb", "nhl")


@dataclass(frozen=True)
class AuditRow:
    """Resolved output for a single raw team name."""

    raw_name: str
    canonical_name: str
    elo_name: str
    is_valid_elo_name: bool


@dataclass(frozen=True)
class SportAudit:
    """Verification summary for one sport."""

    sport: str
    bet_file: Path
    rows: tuple[AuditRow, ...]

    @property
    def unresolved_rows(self) -> tuple[AuditRow, ...]:
        """Return rows that do not resolve to a current Elo team."""
        return tuple(row for row in self.rows if not row.is_valid_elo_name)


@lru_cache(maxsize=None)
def load_elo_teams(sport: str) -> frozenset[str]:
    """Load the current Elo team names for a sport."""
    csv_path = DATA_DIR / f"{sport}_current_elo_ratings.csv"
    with csv_path.open(encoding="utf-8", newline="") as csv_file:
        return frozenset(row["team"] for row in csv.DictReader(csv_file))


def latest_bet_file(sport: str) -> Path:
    """Return the latest dated bet file for a sport."""
    bet_files = sorted((DATA_DIR / sport).glob("bets_20??-??-??.json"))
    if not bet_files:
        raise FileNotFoundError(f"No dated bet files found for {sport}")
    return bet_files[-1]


def load_bet_names(bet_file: Path) -> tuple[str, ...]:
    """Load the unique team names present in a bet file."""
    with bet_file.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    names: set[str] = set()
    for entry in payload:
        for key in ("home_team", "away_team", "bet_on"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                names.add(value)

    return tuple(sorted(names))


def resolve_to_elo_name(sport: str, raw_name: str) -> AuditRow:
    """Resolve a raw team name through the canonical and Elo stages."""
    canonical_name = NamingResolver.resolve(
        NamingContext(sport=sport, source="kalshi", name=raw_name)
    )
    elo_name = NamingResolver.resolve(
        NamingContext(sport=sport, source="elo", name=canonical_name)
    )

    return AuditRow(
        raw_name=raw_name,
        canonical_name=canonical_name,
        elo_name=elo_name,
        is_valid_elo_name=elo_name in load_elo_teams(sport),
    )


def audit_sport(sport: str) -> SportAudit:
    """Audit the latest bet file for a sport."""
    bet_file = latest_bet_file(sport)
    rows = tuple(
        resolve_to_elo_name(sport, raw_name) for raw_name in load_bet_names(bet_file)
    )
    return SportAudit(sport=sport, bet_file=bet_file, rows=rows)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Verify naming_resolver.py against actual bet files."
    )
    parser.add_argument(
        "--sport",
        action="append",
        choices=SUPPORTED_SPORTS,
        help="Limit verification to one or more sports.",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=5,
        help="Number of sample rows to print per sport.",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    """Run the bet-file verification audit."""
    args = parse_args(argv)
    sports = tuple(args.sport) if args.sport else SUPPORTED_SPORTS

    print("✓ Verifying naming resolver against actual bet files")
    print("=" * 72)

    audits = [audit_sport(sport) for sport in sports]
    has_failures = False

    for audit in audits:
        unresolved_rows = audit.unresolved_rows
        has_failures = has_failures or bool(unresolved_rows)

        print(f"\n{audit.sport.upper()}  {audit.bet_file.relative_to(REPO_ROOT)}")
        print(
            f"  ✓ checked {len(audit.rows)} unique names, "
            f"{len(unresolved_rows)} unresolved"
        )

        sample_rows = audit.rows[: args.sample_limit]
        for row in sample_rows:
            status = "✓" if row.is_valid_elo_name else "✗"
            print(
                f"  {status} {row.raw_name} -> {row.canonical_name} -> {row.elo_name}"
            )

        if unresolved_rows:
            print("  ⚠️  unresolved names:")
            for row in unresolved_rows:
                print(
                    f"     - {row.raw_name} -> {row.canonical_name} -> {row.elo_name}"
                )

    print("\n" + "=" * 72)
    if has_failures:
        print("⚠️  Naming resolver verification found unresolved names.")
        return 1

    print("✓ Naming resolver verification passed for all checked bet files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
