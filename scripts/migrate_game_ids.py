#!/usr/bin/env python3
"""Migration script: consolidate abbreviated game_ids with full-name game_ids.

Kalshi stores games with abbreviated team names (e.g., NHL_20260324_NYI_CHI)
while TheOddsAPI uses full names (e.g., NHL_20260324_NEWYORKISLANDERS_CHICAGOBLACKHAWKS).
This creates duplicate records. This script migrates Kalshi odds from abbreviated
game_ids to their matching full-name game_ids, then deletes the abbreviated records.

Usage:
    python scripts/migrate_game_ids.py
"""
import sys
import os
import re

sys.path.insert(0, "/opt/airflow/plugins")

import psycopg2
from psycopg2.extras import execute_values

# Map abbreviated game_id → full-name game_id using NamingResolver
from naming_resolver import NamingResolver, NamingContext

DB_CONN = os.environ.get(
    "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN",
    "postgresql+psycopg2://airflow:airflow@postgres/airflow",
).replace("postgresql+psycopg2://", "postgresql://")


ABBREVIATED_PATTERN = re.compile(
    r"^(NHL|NBA|EPL)_(\d{8})_([A-Z0-9]{2,5})_([A-Z0-9]{2,5})$"
)


def abbrev_to_full_game_id(game_id: str) -> str | None:
    """Convert abbreviated game_id to expected full-name game_id via NamingResolver.

    Args:
        game_id: Abbreviated game_id (e.g. NHL_20260324_NYI_CHI).

    Returns:
        Expected full-name game_id or None if no mapping found.
    """
    m = ABBREVIATED_PATTERN.match(game_id)
    if not m:
        return None
    sport, date, home_abbrev, away_abbrev = m.groups()
    sport_lower = sport.lower()
    home_full = NamingResolver.resolve(
        NamingContext(sport_lower, "kalshi", home_abbrev.lower())
    )
    away_full = NamingResolver.resolve(
        NamingContext(sport_lower, "kalshi", away_abbrev.lower())
    )
    # If resolver returned unchanged lowercase, no mapping found → skip
    if home_full.lower() == home_abbrev.lower() or away_full.lower() == away_abbrev.lower():
        return None
    # Use same slugification as kalshi_markets.py and the_odds_api.py
    home_slug = "".join(filter(str.isalnum, home_full)).upper()
    away_slug = "".join(filter(str.isalnum, away_full)).upper()
    return f"{sport}_{date}_{home_slug}_{away_slug}"


def run_migration(conn):
    """Execute the migration.

    Args:
        conn: psycopg2 connection.
    """
    cur = conn.cursor()

    # Fetch all abbreviated game_ids for NHL, NBA, EPL
    cur.execute(
        """
        SELECT game_id FROM unified_games
        WHERE sport IN ('NHL','NBA','EPL')
        ORDER BY game_id
        """
    )
    all_game_ids = [r[0] for r in cur.fetchall()]

    abbreviated = [g for g in all_game_ids if ABBREVIATED_PATTERN.match(g)]
    full_names = set(all_game_ids) - set(abbreviated)

    print(f"Found {len(abbreviated)} abbreviated game_ids, {len(full_names)} full-name game_ids")

    migrated = 0
    skipped_no_match = 0
    skipped_no_full_record = 0

    for abbrev_id in abbreviated:
        expected_full_id = abbrev_to_full_game_id(abbrev_id)
        if not expected_full_id:
            print(f"  ⚠️  No NamingResolver mapping for: {abbrev_id}")
            skipped_no_match += 1
            continue

        if expected_full_id not in full_names:
            print(f"  ⚠️  No full-name record found for: {abbrev_id} → expected {expected_full_id}")
            skipped_no_full_record += 1
            continue

        # Move game_odds from abbrev_id to full_name_id (avoid duplicates)
        cur.execute(
            """
            UPDATE game_odds
            SET game_id = %(full_id)s
            WHERE game_id = %(abbrev_id)s
              AND NOT EXISTS (
                SELECT 1 FROM game_odds g2
                WHERE g2.game_id = %(full_id)s
                  AND g2.bookmaker = game_odds.bookmaker
                  AND g2.outcome_name = game_odds.outcome_name
              )
            """,
            {"full_id": expected_full_id, "abbrev_id": abbrev_id},
        )
        moved = cur.rowcount

        # Delete any remaining odds under abbrev_id (duplicates)
        cur.execute("DELETE FROM game_odds WHERE game_id = %(id)s", {"id": abbrev_id})
        deleted_odds = cur.rowcount

        # Merge status: if abbrev record has active/upcoming, ensure full record has it too
        cur.execute(
            """
            UPDATE unified_games SET status = ug2.status
            FROM unified_games ug2
            WHERE unified_games.game_id = %(full_id)s
              AND ug2.game_id = %(abbrev_id)s
              AND ug2.status NOT IN ('completed','cancelled')
              AND unified_games.status IN ('completed','cancelled')
            """,
            {"full_id": expected_full_id, "abbrev_id": abbrev_id},
        )

        # Delete the abbreviated unified_games record
        cur.execute(
            "DELETE FROM unified_games WHERE game_id = %(id)s",
            {"id": abbrev_id},
        )

        print(f"  ✅ {abbrev_id} → {expected_full_id} (moved {moved} odds, deleted {deleted_odds} dupes)")
        migrated += 1

    conn.commit()
    print(f"\nMigration complete: {migrated} migrated, {skipped_no_match} no-mapping, {skipped_no_full_record} no-full-record")


def main():
    """Entry point."""
    print("Connecting to database...")
    conn = psycopg2.connect(DB_CONN)
    try:
        run_migration(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
