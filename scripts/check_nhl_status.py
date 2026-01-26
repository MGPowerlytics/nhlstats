#!/usr/bin/env python3
"""Check NHL data status and backfill if needed."""

import duckdb

conn = duckdb.connect("data/nhlstats.duckdb", read_only=True)

# Check latest NHL games
result = conn.execute("""
    SELECT MAX(game_date), COUNT(*)
    FROM games
    WHERE game_state IN ('OFF', 'FINAL')
""").fetchone()
print(f"Latest NHL game in DB: {result[0]}")
print(f"Total completed games: {result[1]}")

# Check if there are any 2025-26 season games at all
result2 = conn.execute("""
    SELECT game_state, COUNT(*)
    FROM games
    WHERE game_date >= '2025-10-01'
    GROUP BY game_state
""").fetchall()
print(f"Games since Oct 2025 by state: {result2}")

conn.close()
