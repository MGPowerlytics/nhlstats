"""
Fix NHL Data Issues
Resolves duplicates, filters exhibition games, and standardizes team names.
"""

import duckdb


def fix_data_issues(db_path="data/nhlstats.duckdb", dry_run=False):
    """Fix identified data issues"""

    conn = duckdb.connect(db_path, read_only=dry_run)

    print("=" * 70)
    print("NHL DATA CLEANUP")
    print("=" * 70)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print()

    # 1. Find and remove duplicate matchups
    print("1. REMOVING DUPLICATE MATCHUPS")
    print("-" * 70)

    result = conn.execute("""
        SELECT game_date, home_team_abbrev, away_team_abbrev,
               GROUP_CONCAT(game_id, ', ') as game_ids,
               COUNT(*) as count
        FROM games
        GROUP BY game_date, home_team_abbrev, away_team_abbrev
        HAVING COUNT(*) > 1
    """).fetchall()

    if result:
        print(f"Found {len(result)} duplicate matchups:")
        for date, home, away, gids, count in result:
            print(f"  {date}: {home} vs {away} - Game IDs: {gids}")

            if not dry_run:
                # Keep the first game_id, delete others
                game_ids = gids.split(", ")
                to_delete = game_ids[1:]  # Keep first, delete rest

                for gid in to_delete:
                    conn.execute("DELETE FROM games WHERE game_id = ?", (gid,))
                    print(f"    ✓ Deleted game_id: {gid}")
    else:
        print("  ✓ No duplicates found")

    # 2. Standardize Utah Hockey Club name
    print("\n2. STANDARDIZING TEAM NAMES")
    print("-" * 70)

    result = conn.execute("""
        SELECT COUNT(*) FROM games
        WHERE (home_team_abbrev = 'UTA' AND home_team_name != 'Utah Hockey Club')
           OR (away_team_abbrev = 'UTA' AND away_team_name != 'Utah Hockey Club')
    """).fetchone()

    utah_issues = result[0]
    if utah_issues > 0:
        print(f"  Found {utah_issues} Utah name inconsistencies")
        if not dry_run:
            conn.execute("""
                UPDATE games SET home_team_name = 'Utah Hockey Club'
                WHERE home_team_abbrev = 'UTA'
            """)
            conn.execute("""
                UPDATE games SET away_team_name = 'Utah Hockey Club'
                WHERE away_team_abbrev = 'UTA'
            """)
            print("  ✓ Updated Utah Hockey Club names")
    else:
        print("  ✓ Team names consistent")

    # 3. Report on exhibition games (don't delete, just identify)
    print("\n3. EXHIBITION/NON-NHL GAMES")
    print("-" * 70)

    exhibition_teams = [
        "CAN",
        "USA",
        "ATL",
        "MET",
        "CEN",
        "PAC",
        "SWE",
        "FIN",
        "EIS",
        "MUN",
        "SCB",
        "KLS",
        "KNG",
        "MKN",
        "HGS",
        "MAT",
        "MCD",
    ]

    placeholders = ",".join(["?" for _ in exhibition_teams])
    result = conn.execute(
        f"""
        SELECT COUNT(*) FROM games
        WHERE home_team_abbrev IN ({placeholders})
           OR away_team_abbrev IN ({placeholders})
    """,
        exhibition_teams + exhibition_teams,
    ).fetchone()

    exhibition_count = result[0]
    print(f"  Found {exhibition_count} exhibition/All-Star games")
    print("  ℹ️  These will be filtered in Elo calculations (not deleted)")

    # 4. Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if dry_run:
        print("\n⚠️  DRY RUN - No changes made")
        print("\nWould fix:")
        print(f"  • {len(result) if result else 0} duplicate matchups")
        print(f"  • {utah_issues} Utah name issues")
        print(f"  • {exhibition_count} exhibition games identified for filtering")
    else:
        print("\n✅ CLEANUP COMPLETE")
        print(f"  • Removed {len(result) if result else 0} duplicate games")
        print(f"  • Fixed {utah_issues} team name issues")
        print(f"  • Identified {exhibition_count} exhibition games")

        # Verify
        result = conn.execute("""
            SELECT COUNT(*) FROM games
        """).fetchone()
        print(f"\n  Total games remaining: {result[0]:,}")

    conn.close()


if __name__ == "__main__":
    import sys

    dry_run = "--dry-run" in sys.argv
    fix_data_issues(dry_run=dry_run)
