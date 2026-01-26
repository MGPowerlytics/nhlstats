"""
NHL Data Validation Script
Comprehensive validation of NHL game data for Elo rating accuracy.
"""

import duckdb
from datetime import datetime
from collections import defaultdict
import sys


class NHLDataValidator:
    def __init__(self, db_path="data/nhlstats.duckdb"):
        self.db_path = db_path
        self.conn = None
        self.issues = []
        self.warnings = []

    def connect(self):
        """Connect to database"""
        self.conn = duckdb.connect(self.db_path, read_only=True)

    def close(self):
        """Close connection"""
        if self.conn:
            self.conn.close()

    def add_issue(self, category, message):
        """Add a critical issue"""
        self.issues.append(f"[{category}] {message}")

    def add_warning(self, category, message):
        """Add a warning"""
        self.warnings.append(f"[{category}] {message}")

    def validate_basic_stats(self):
        """Validate basic database statistics"""
        print("=" * 70)
        print("1. BASIC DATABASE STATISTICS")
        print("=" * 70)

        # Total games
        result = self.conn.execute("SELECT COUNT(*) FROM games").fetchone()
        total_games = result[0]
        print(f"✓ Total games in database: {total_games:,}")

        if total_games == 0:
            self.add_issue("BASIC", "No games found in database!")
            return

        # Date range
        result = self.conn.execute("""
            SELECT MIN(game_date) as min_date, MAX(game_date) as max_date
            FROM games
        """).fetchone()
        min_date, max_date = result
        print(f"✓ Date range: {min_date} to {max_date}")

        # Games by state
        results = self.conn.execute("""
            SELECT game_state, COUNT(*) as count
            FROM games
            GROUP BY game_state
            ORDER BY count DESC
        """).fetchall()

        print("\n  Games by state:")
        for state, count in results:
            print(f"    {state:15} {count:6,} games")

        # Completed games
        result = self.conn.execute("""
            SELECT COUNT(*) FROM games
            WHERE game_state IN ('OFF', 'FINAL')
        """).fetchone()
        completed = result[0]
        print(f"\n✓ Completed games (OFF/FINAL): {completed:,}")

        if completed < total_games * 0.5:
            self.add_warning(
                "BASIC",
                f"Only {completed / total_games * 100:.1f}% of games are completed",
            )

    def validate_seasons(self):
        """Validate season data"""
        print("\n" + "=" * 70)
        print("2. SEASON VALIDATION")
        print("=" * 70)

        results = self.conn.execute("""
            SELECT season,
                   COUNT(*) as total_games,
                   SUM(CASE WHEN game_state IN ('OFF', 'FINAL') THEN 1 ELSE 0 END) as completed_games,
                   MIN(game_date) as start_date,
                   MAX(game_date) as end_date,
                   COUNT(DISTINCT home_team_abbrev) as num_teams
            FROM games
            GROUP BY season
            ORDER BY season DESC
        """).fetchall()

        print(
            f"\n{'Season':<8} {'Total':>7} {'Complete':>9} {'Teams':>6} {'Date Range':>25}"
        )
        print("-" * 70)

        for season, total, completed, start, end, teams in results:
            print(
                f"{season:<8} {total:>7,} {completed:>9,} {teams:>6} {start} to {end}"
            )

            # Expected games per season (82 games * 32 teams / 2)
            expected_min = 1200  # Rough minimum for full season
            if completed > 0 and completed < expected_min and season < 2026:
                self.add_warning(
                    "SEASON",
                    f"Season {season} has only {completed} completed games (expected ~1312)",
                )

            # Expected 32 teams (or 31 before Seattle joined)
            if teams < 30:
                self.add_issue(
                    "SEASON", f"Season {season} has only {teams} teams (expected 30-32)"
                )

    def validate_teams(self):
        """Validate team data"""
        print("\n" + "=" * 70)
        print("3. TEAM VALIDATION")
        print("=" * 70)

        # All teams
        results = self.conn.execute("""
            SELECT home_team_abbrev as team, COUNT(*) as games
            FROM games
            WHERE game_state IN ('OFF', 'FINAL')
            GROUP BY home_team_abbrev
            UNION ALL
            SELECT away_team_abbrev as team, COUNT(*) as games
            FROM games
            WHERE game_state IN ('OFF', 'FINAL')
            GROUP BY away_team_abbrev
        """).fetchall()

        team_games = defaultdict(int)
        for team, games in results:
            team_games[team] += games

        print(f"\n✓ Found {len(team_games)} unique teams")
        print("\nGames per team:")

        sorted_teams = sorted(team_games.items(), key=lambda x: x[1], reverse=True)
        for team, games in sorted_teams:
            print(f"  {team:4} {games:5,} games")

        # Check for teams with very few games
        min_games = min(team_games.values())
        max_games = max(team_games.values())

        if min_games < 50:
            low_teams = [t for t, g in team_games.items() if g < 50]
            self.add_warning("TEAMS", f"Teams with <50 games: {', '.join(low_teams)}")

        # Check for large variance (might indicate missing data)
        if max_games > min_games * 2:
            self.add_warning(
                "TEAMS", f"Large variance in games per team: {min_games} to {max_games}"
            )

        # Current season validation
        current_season = 2024
        results = self.conn.execute(f"""
            SELECT home_team_abbrev as team, COUNT(*) as games
            FROM games
            WHERE season = {current_season} AND game_state IN ('OFF', 'FINAL')
            GROUP BY home_team_abbrev
            UNION ALL
            SELECT away_team_abbrev as team, COUNT(*) as games
            FROM games
            WHERE season = {current_season} AND game_state IN ('OFF', 'FINAL')
            GROUP BY away_team_abbrev
        """).fetchall()

        current_team_games = defaultdict(int)
        for team, games in results:
            current_team_games[team] += games

        if len(current_team_games) < 30:
            self.add_warning(
                "TEAMS",
                f"Current season {current_season} has only {len(current_team_games)} teams",
            )

    def validate_date_gaps(self):
        """Check for unexpected date gaps"""
        print("\n" + "=" * 70)
        print("4. DATE GAP ANALYSIS")
        print("=" * 70)

        # Get all dates with games
        results = self.conn.execute("""
            SELECT game_date, COUNT(*) as games
            FROM games
            WHERE game_state IN ('OFF', 'FINAL')
            GROUP BY game_date
            ORDER BY game_date
        """).fetchall()

        if not results:
            self.add_issue("DATES", "No completed games found")
            return

        dates_with_games = [
            (datetime.strptime(str(d), "%Y-%m-%d").date(), cnt) for d, cnt in results
        ]

        # Find gaps > 7 days (potential missing data)
        large_gaps = []
        for i in range(1, len(dates_with_games)):
            prev_date, _ = dates_with_games[i - 1]
            curr_date, _ = dates_with_games[i]
            gap_days = (curr_date - prev_date).days

            if gap_days > 7:
                large_gaps.append((prev_date, curr_date, gap_days))

        if large_gaps:
            print(f"\n⚠️  Found {len(large_gaps)} gaps > 7 days:")
            for start, end, days in large_gaps[:10]:  # Show first 10
                print(f"    {start} to {end}: {days} days")

                # Off-season gaps are expected (June-September)
                if start.month >= 6 and end.month <= 9:
                    continue  # Expected off-season
                else:
                    self.add_warning(
                        "DATES", f"Unexpected {days}-day gap: {start} to {end}"
                    )
        else:
            print("\n✓ No unexpected date gaps found")

        # Check recent data
        if dates_with_games:
            most_recent = dates_with_games[-1][0]
            days_ago = (datetime.now().date() - most_recent).days
            print(f"\n✓ Most recent game: {most_recent} ({days_ago} days ago)")

            if days_ago > 3:
                self.add_warning(
                    "DATES",
                    f"Most recent game is {days_ago} days old - data may be stale",
                )

    def validate_scores(self):
        """Validate score data"""
        print("\n" + "=" * 70)
        print("5. SCORE DATA VALIDATION")
        print("=" * 70)

        # Games with missing scores
        result = self.conn.execute("""
            SELECT COUNT(*) FROM games
            WHERE game_state IN ('OFF', 'FINAL')
            AND (home_score IS NULL OR away_score IS NULL)
        """).fetchone()

        missing_scores = result[0]
        if missing_scores > 0:
            print(f"\n❌ {missing_scores} completed games missing scores")
            self.add_issue(
                "SCORES", f"{missing_scores} completed games have NULL scores"
            )
        else:
            print("\n✓ All completed games have scores")

        # Score distribution
        results = self.conn.execute("""
            SELECT
                home_score + away_score as total_goals,
                COUNT(*) as games
            FROM games
            WHERE game_state IN ('OFF', 'FINAL')
            AND home_score IS NOT NULL AND away_score IS NOT NULL
            GROUP BY total_goals
            ORDER BY total_goals
        """).fetchall()

        print("\n  Total goals distribution:")
        for goals, games in results[:15]:  # Show 0-14 goals
            bar = "█" * (games // 100)
            print(f"    {goals:2} goals: {games:5,} games {bar}")

        # Suspiciously high scores
        result = self.conn.execute("""
            SELECT game_id, game_date, home_team_abbrev, away_team_abbrev,
                   home_score, away_score
            FROM games
            WHERE game_state IN ('OFF', 'FINAL')
            AND (home_score > 10 OR away_score > 10)
            ORDER BY (home_score + away_score) DESC
            LIMIT 5
        """).fetchall()

        if result:
            print("\n  High-scoring games (verify these are correct):")
            for gid, date, home, away, hs, aws in result:
                print(f"    {date}: {home} {hs} - {aws} {away}")

    def validate_duplicates(self):
        """Check for duplicate games"""
        print("\n" + "=" * 70)
        print("6. DUPLICATE DETECTION")
        print("=" * 70)

        # Same game_id multiple times
        result = self.conn.execute("""
            SELECT game_id, COUNT(*) as count
            FROM games
            GROUP BY game_id
            HAVING COUNT(*) > 1
        """).fetchall()

        if result:
            print(f"\n❌ Found {len(result)} duplicate game IDs:")
            for gid, count in result[:10]:
                print(f"    {gid}: {count} entries")
            self.add_issue("DUPLICATES", f"{len(result)} duplicate game IDs found")
        else:
            print("\n✓ No duplicate game IDs")

        # Same matchup on same date
        result = self.conn.execute("""
            SELECT game_date, home_team_abbrev, away_team_abbrev, COUNT(*) as count
            FROM games
            GROUP BY game_date, home_team_abbrev, away_team_abbrev
            HAVING COUNT(*) > 1
        """).fetchall()

        if result:
            print(f"\n❌ Found {len(result)} duplicate matchups:")
            for date, home, away, count in result[:10]:
                print(f"    {date}: {home} vs {away} ({count} entries)")
            self.add_issue(
                "DUPLICATES", f"{len(result)} duplicate matchups on same date"
            )
        else:
            print("\n✓ No duplicate matchups on same date")

    def validate_team_consistency(self):
        """Check for team name/abbreviation consistency"""
        print("\n" + "=" * 70)
        print("7. TEAM NAME CONSISTENCY")
        print("=" * 70)

        # Check if same abbrev has different full names
        results = self.conn.execute("""
            SELECT home_team_abbrev, COUNT(DISTINCT home_team_name) as name_count,
                   GROUP_CONCAT(DISTINCT home_team_name, ' | ') as names
            FROM games
            GROUP BY home_team_abbrev
            HAVING COUNT(DISTINCT home_team_name) > 1
        """).fetchall()

        if results:
            print("\n⚠️  Teams with inconsistent names:")
            for abbrev, count, names in results:
                print(f"    {abbrev}: {names}")
            self.add_warning(
                "CONSISTENCY", f"{len(results)} teams have inconsistent names"
            )
        else:
            print("\n✓ Team names are consistent")

    def print_summary(self):
        """Print validation summary"""
        print("\n" + "=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)

        if not self.issues and not self.warnings:
            print("\n✅ ALL CHECKS PASSED - Data quality looks good!")
        else:
            if self.issues:
                print(f"\n❌ CRITICAL ISSUES ({len(self.issues)}):")
                for issue in self.issues:
                    print(f"  • {issue}")

            if self.warnings:
                print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
                for warning in self.warnings:
                    print(f"  • {warning}")

        return len(self.issues) == 0

    def run_all_validations(self):
        """Run all validation checks"""
        try:
            self.connect()

            self.validate_basic_stats()
            self.validate_seasons()
            self.validate_teams()
            self.validate_date_gaps()
            self.validate_scores()
            self.validate_duplicates()
            self.validate_team_consistency()

            passed = self.print_summary()

            self.close()

            return 0 if passed else 1

        except Exception as e:
            print(f"\n❌ Validation failed with error: {e}")
            import traceback

            traceback.print_exc()
            return 1


if __name__ == "__main__":
    validator = NHLDataValidator()
    sys.exit(validator.run_all_validations())
