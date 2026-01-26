#!/usr/bin/env python3
"""
Migrate placed_bets table schema to add missing columns.

This migration adds columns that were added after the initial table creation:
- placed_time_utc: When the bet was placed (timestamp with timezone info)
- market_title: Human-readable market title
- market_close_time_utc: When the market closes
- opening_line_prob: Probability when market opened
- bet_line_prob: Probability when bet was placed
- closing_line_prob: Probability when market closed
- clv: Closing Line Value (bet_line_prob - closing_line_prob)
- updated_at: When the record was last updated

Usage:
    python scripts/migrate_placed_bets_schema.py
"""

import sys
from pathlib import Path

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from db_manager import default_db


def migrate_schema():
    """Add missing columns to placed_bets table."""

    print("🔄 Migrating placed_bets table schema...")

    # Define missing columns
    missing_columns = [
        ("placed_time_utc", "TIMESTAMP"),
        ("market_title", "VARCHAR"),
        ("market_close_time_utc", "TIMESTAMP"),
        ("opening_line_prob", "DOUBLE PRECISION"),
        ("bet_line_prob", "DOUBLE PRECISION"),
        ("closing_line_prob", "DOUBLE PRECISION"),
        ("clv", "DOUBLE PRECISION"),
        ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ]

    # Add each column
    added = 0
    for col_name, col_type in missing_columns:
        try:
            # Use IF NOT EXISTS to safely add columns
            default_db.execute(f"""
                ALTER TABLE placed_bets
                ADD COLUMN IF NOT EXISTS {col_name} {col_type}
            """)
            print(f"  ✓ Added column: {col_name}")
            added += 1
        except Exception as e:
            print(f"  ⚠️  Column {col_name} may already exist: {e}")

    print(f"\n✅ Migration complete! Added {added} columns.")

    # Verify final schema
    result = default_db.fetch_df("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'placed_bets'
        ORDER BY ordinal_position
    """)

    print(f"\n📊 Table now has {len(result)} columns:")
    for i, col in enumerate(result["column_name"], 1):
        print(f"  {i:2d}. {col}")


if __name__ == "__main__":
    migrate_schema()
