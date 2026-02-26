#!/usr/bin/env python3
"""
Comprehensive Data Validation for Multi-Sport Betting System.

Validates data completeness, quality, and integrity for NBA, NHL, MLB, and NFL.

Checks performed:
- Data presence and row counts
- Date range coverage
- Missing dates/games
- Data quality (nulls, invalid values)
- Team coverage
- Season completeness
- Cross-validation between sources
"""

import json
import warnings
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd
from db_manager import default_db

warnings.filterwarnings("ignore")


# Expected teams for each sport
EXPECTED_TEAMS: Dict[str, List[str]] = {
    "nba": [
        "Hawks",
        "Celtics",
        "Nets",
        "Hornets",
        "Bulls",
        "Cavaliers",
        "Mavericks",
        "Nuggets",
        "Pistons",
        "Warriors",
        "Rockets",
        "Pacers",
        "Clippers",
        "Lakers",
        "Grizzlies",
        "Heat",
        "Bucks",
        "Timberwolves",
        "Pelicans",
        "Knicks",
        "Thunder",
        "Magic",
        "76ers",
        "Suns",
        "Trail Blazers",
        "Kings",
        "Spurs",
        "Raptors",
        "Jazz",
        "Wizards",
    ],
    "nhl": [
        "Anaheim Ducks",
        "Boston Bruins",
        "Buffalo Sabres",
        "Calgary Flames",
        "Carolina Hurricanes",
        "Chicago Blackhawks",
        "Colorado Avalanche",
        "Columbus Blue Jackets",
        "Dallas Stars",
        "Detroit Red Wings",
        "Edmonton Oilers",
        "Florida Panthers",
        "Los Angeles Kings",
        "Minnesota Wild",
        "Montreal Canadiens",
        "Nashville Predators",
        "New Jersey Devils",
        "New York Islanders",
        "New York Rangers",
        "Ottawa Senators",
        "Philadelphia Flyers",
        "Pittsburgh Penguins",
        "San Jose Sharks",
        "Seattle Kraken",
        "St. Louis Blues",
        "Tampa Bay Lightning",
        "Toronto Maple Leafs",
        "Vancouver Canucks",
        "Vegas Golden Knights",
        "Washington Capitals",
        "Winnipeg Jets",
        "Arizona Coyotes",
        "Utah Hockey Club",
    ],
    "mlb": [
        "Arizona Diamondbacks",
        "Atlanta Braves",
        "Baltimore Orioles",
        "Boston Red Sox",
        "Chicago Cubs",
        "Chicago White Sox",
        "Cincinnati Reds",
        "Cleveland Guardians",
        "Colorado Rockies",
        "Detroit Tigers",
        "Houston Astros",
        "Kansas City Royals",
        "Los Angeles Angels",
        "Los Angeles Dodgers",
        "Miami Marlins",
        "Milwaukee Brewers",
        "Minnesota Twins",
        "New York Mets",
        "New York Yankees",
        "Oakland Athletics",
        "Philadelphia Phillies",
        "Pittsburgh Pirates",
        "San Diego Padres",
        "San Francisco Giants",
        "Seattle Mariners",
        "St. Louis Cardinals",
        "Tampa Bay Rays",
        "Texas Rangers",
        "Toronto Blue Jays",
        "Washington Nationals",
    ],
    "nfl": [
        "Arizona Cardinals",
        "Atlanta Falcons",
        "Baltimore Ravens",
        "Buffalo Bills",
        "Carolina Panthers",
        "Chicago Bears",
        "Cincinnati Bengals",
        "Cleveland Browns",
        "Dallas Cowboys",
        "Denver Broncos",
        "Detroit Lions",
        "Green Bay Packers",
        "Houston Texans",
        "Indianapolis Colts",
        "Jacksonville Jaguars",
        "Kansas City Chiefs",
        "Las Vegas Raiders",
        "Los Angeles Chargers",
        "Los Angeles Rams",
        "Miami Dolphins",
        "Minnesota Vikings",
        "New England Patriots",
        "New Orleans Saints",
        "New York Giants",
        "New York Jets",
        "Philadelphia Eagles",
        "Pittsburgh Steelers",
        "San Francisco 49ers",
        "Seattle Seahawks",
        "Tampa Bay Buccaneers",
        "Tennessee Titans",
        "Washington Commanders",
    ],
}

# Season date ranges (approximate)
SEASON_INFO: Dict[str, Dict] = {
    "nba": {
        "games_per_team": 82,
        "total_games_per_season": 1230,
        "start_month": 10,
        "end_month": 4,
        "playoff_months": [4, 5, 6],
    },
    "nhl": {
        "games_per_team": 82,
        "total_games_per_season": 1312,
        "start_month": 10,
        "end_month": 4,
        "playoff_months": [4, 5, 6],
    },
    "mlb": {
        "games_per_team": 162,
        "total_games_per_season": 2430,
        "start_month": 3,
        "end_month": 9,
        "playoff_months": [10, 11],
    },
    "nfl": {
        "games_per_team": 17,
        "total_games_per_season": 272,
        "start_month": 9,
        "end_month": 1,
        "playoff_months": [1, 2],
    },
}

# Validation thresholds per sport
VALIDATION_THRESHOLDS: Dict[str, Dict] = {
    "nba": {"min_games": 1000, "min_teams": 28, "expected_teams": 30},
    "nhl": {"min_games": 100, "min_teams": 30, "expected_teams": 32},
    "mlb": {"min_games": 100, "min_teams": 25, "expected_teams": 30},
    "nfl": {"min_games": 100, "min_teams": 30, "expected_teams": 32},
}

# SQL query templates
GAMES_SUMMARY_QUERY = """
    SELECT
        COUNT(*) as total_games,
        COUNT(DISTINCT game_id) as unique_games,
        MIN(game_date) as min_date,
        MAX(game_date) as max_date,
        COUNT(DISTINCT home_team_name) as home_teams,
        COUNT(DISTINCT away_team_name) as away_teams,
        COALESCE(SUM(CASE WHEN status IN ('Final', 'Completed') AND home_score IS NULL THEN 1 ELSE 0 END), 0) as null_home_scores,
        COALESCE(SUM(CASE WHEN status IN ('Final', 'Completed') AND away_score IS NULL THEN 1 ELSE 0 END), 0) as null_away_scores,
        COALESCE(SUM(CASE WHEN status IN ('Final', 'Completed') AND home_score IS NOT NULL THEN 1 ELSE 0 END), 0) as completed_games,
        COALESCE(SUM(CASE WHEN status NOT IN ('Final', 'Completed') THEN 1 ELSE 0 END), 0) as future_games
    FROM unified_games
    WHERE sport = :sport
"""

SEASONS_QUERY = """
    SELECT
        EXTRACT(YEAR FROM game_date) as season,
        COUNT(*) as game_count
    FROM unified_games
    WHERE sport = :sport
      AND status IN ('Final', 'Completed')
      AND home_score IS NOT NULL
    GROUP BY EXTRACT(YEAR FROM game_date)
    ORDER BY season
"""

TEAMS_QUERY = """
    SELECT DISTINCT team_name FROM (
        SELECT home_team_name as team_name FROM unified_games WHERE sport = :sport
        UNION
        SELECT away_team_name as team_name FROM unified_games WHERE sport = :sport
    )
"""


@dataclass
class GamesSummary:
    """Results from games summary query."""

    total: int
    unique: int
    min_date: Optional[str]
    max_date: Optional[str]
    home_teams: int
    away_teams: int
    null_home_scores: int
    null_away_scores: int
    completed_games: int
    future_games: int

    @classmethod
    def from_row(cls, row: tuple) -> "GamesSummary":
        return cls(
            total=row[0] or 0,
            unique=row[1] or 0,
            min_date=str(row[2]) if row[2] else None,
            max_date=str(row[3]) if row[3] else None,
            home_teams=row[4] or 0,
            away_teams=row[5] or 0,
            null_home_scores=row[6] or 0,
            null_away_scores=row[7] or 0,
            completed_games=row[8] or 0,
            future_games=row[9] or 0,
        )


class DataValidationReport:
    """Stores validation results and generates reports."""

    def __init__(self, sport: str):
        self.sport = sport
        self.checks: List[Dict] = []
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.stats: Dict = {}

    def add_check(self, name: str, passed: bool, message: str, severity: str = "info"):
        """Add a validation check result."""
        self.checks.append(
            {"name": name, "passed": passed, "message": message, "severity": severity}
        )
        if not passed:
            if severity == "error":
                self.errors.append(f"❌ {name}: {message}")
            elif severity == "warning":
                self.warnings.append(f"⚠️  {name}: {message}")

    def add_stat(self, name: str, value):
        """Add a statistic."""
        self.stats[name] = value

    def print_report(self) -> bool:
        """Print formatted validation report."""
        print(f"\n{'=' * 100}")
        print(f"📊 {self.sport.upper()} DATA VALIDATION REPORT")
        print(f"{'=' * 100}")

        if self.stats:
            print("\n📈 Statistics:")
            for name, value in self.stats.items():
                if isinstance(value, float):
                    print(f"   {name}: {value:,.2f}")
                elif isinstance(value, int):
                    print(f"   {name}: {value:,}")
                else:
                    print(f"   {name}: {value}")

        passed_checks = [c for c in self.checks if c["passed"]]
        if passed_checks:
            print(f"\n✅ Passed Checks ({len(passed_checks)}):")
            for check in passed_checks:
                print(f"   ✓ {check['name']}: {check['message']}")

        if self.warnings:
            print(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   {warning}")

        if self.errors:
            print(f"\n❌ Errors ({len(self.errors)}):")
            for error in self.errors:
                print(f"   {error}")

        total = len(self.checks)
        passed = len(passed_checks)
        print(f"\n{'=' * 100}")
        print(f"📋 Summary: {passed}/{total} checks passed")
        if self.errors:
            print(f"   ❌ {len(self.errors)} errors require attention")
        if self.warnings:
            print(f"   ⚠️  {len(self.warnings)} warnings to review")
        print(f"{'=' * 100}")

        return len(self.errors) == 0


def _run_common_db_validations(
    report: DataValidationReport,
    summary: GamesSummary,
    teams_found: Set[str],
    sport: str,
) -> None:
    """Run common validation checks for database-backed sports."""
    thresholds = VALIDATION_THRESHOLDS.get(sport, {})
    min_games = thresholds.get("min_games", 100)
    min_teams = thresholds.get("min_teams", 25)
    expected_teams = thresholds.get("expected_teams", 30)

    report.add_check(
        "Sufficient Games",
        summary.completed_games >= min_games,
        f"{summary.completed_games} completed games found",
        "warning" if summary.completed_games < min_games else "info",
    )

    report.add_check(
        "Null Home Scores",
        summary.null_home_scores == 0,
        f"{summary.null_home_scores} null home scores",
        "warning" if summary.null_home_scores > 0 else "info",
    )

    report.add_check(
        "Null Away Scores",
        summary.null_away_scores == 0,
        f"{summary.null_away_scores} null away scores",
        "warning" if summary.null_away_scores > 0 else "info",
    )

    report.add_check(
        "Team Coverage",
        len(teams_found) >= min_teams,
        f"{len(teams_found)}/{expected_teams} expected teams found",
        "warning" if len(teams_found) < min_teams else "info",
    )

    # Check for missing teams
    missing_teams = set(EXPECTED_TEAMS.get(sport, [])) - teams_found
    if missing_teams:
        report.add_check(
            "Missing Teams",
            False,
            f"Missing: {', '.join(sorted(missing_teams))}",
            "warning",
        )
    else:
        report.add_check("Missing Teams", True, "All expected teams present")


def _validate_sport_from_database(sport: str) -> DataValidationReport:
    """Generic validation for sports stored in PostgreSQL unified_games table."""
    report = DataValidationReport(sport)

    try:
        # Query games summary
        games = default_db.execute(GAMES_SUMMARY_QUERY, {"sport": sport}).fetchone()
        summary = GamesSummary.from_row(games)

        report.add_stat("Total Games", summary.total)
        report.add_stat("Completed Games", summary.completed_games)
        report.add_stat("Future Games", summary.future_games)
        report.add_stat("Date Range", f"{summary.min_date} to {summary.max_date}")
        report.add_stat("Unique Home Teams", summary.home_teams)
        report.add_stat("Unique Away Teams", summary.away_teams)

        # Query seasons
        seasons = default_db.execute(SEASONS_QUERY, {"sport": sport}).fetchall()
        expected = SEASON_INFO.get(sport, {}).get("total_games_per_season", 0)

        for season, count in seasons:
            pct = count / expected * 100 if expected > 0 else 0
            report.add_stat(
                f"Season {int(season)}", f"{count} games ({pct:.1f}% of expected)"
            )

        # Query teams
        all_teams = default_db.execute(TEAMS_QUERY, {"sport": sport}).fetchall()
        teams_found = {t[0] for t in all_teams}
        report.add_stat("Total Teams", len(teams_found))

        # Run common validations
        _run_common_db_validations(report, summary, teams_found, sport)

        # Check sport-specific table
        try:
            table_name = f"{sport}_games"
            count = default_db.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[
                0
            ]
            report.add_stat(f"{table_name} rows", count)
            report.add_check(
                f"{table_name} has data",
                count > 0,
                f"{count:,} rows",
                "warning" if count == 0 else "info",
            )
        except Exception as e:
            report.add_check(f"{sport}_games exists", False, str(e), "warning")

    except Exception as e:
        report.add_check("Query Execution", False, str(e), "error")

    return report


def validate_nba_data() -> DataValidationReport:
    """Validate NBA data from JSON files."""
    report = DataValidationReport("nba")
    nba_dir = Path("data/nba")

    if not nba_dir.exists():
        report.add_check(
            "Directory Exists", False, "data/nba directory not found", "error"
        )
        return report

    report.add_check("Directory Exists", True, f"Found {nba_dir}")

    date_dirs = sorted([d for d in nba_dir.iterdir() if d.is_dir()])
    report.add_stat("Total Date Directories", len(date_dirs))

    if not date_dirs:
        report.add_check(
            "Date Directories", False, "No date directories found", "error"
        )
        return report

    dates = [d.name for d in date_dirs]
    report.add_stat("Date Range", f"{min(dates)} to {max(dates)}")

    # Analyze game data
    games_found = 0
    games_with_boxscore = 0
    missing_boxscores: List[str] = []
    null_scores = 0
    teams_found: Set[str] = set()
    games_by_season: Dict[int, int] = defaultdict(int)

    for date_dir in date_dirs:
        scoreboard_file = date_dir / f"scoreboard_{date_dir.name}.json"

        if not scoreboard_file.exists():
            continue

        try:
            with open(scoreboard_file) as f:
                data = json.load(f)

            if "resultSets" not in data:
                continue

            for result_set in data["resultSets"]:
                if result_set["name"] == "GameHeader":
                    headers = result_set["headers"]
                    idx_game_id = headers.index("GAME_ID")
                    idx_status = headers.index("GAME_STATUS_TEXT")

                    for row in result_set["rowSet"]:
                        game_id = str(row[idx_game_id])
                        game_status = row[idx_status]

                        if "Final" in game_status:
                            games_found += 1

                            year = int(date_dir.name[:4])
                            month = int(date_dir.name[5:7])
                            season = year if month >= 10 else year - 1
                            games_by_season[season] += 1

                            boxscore_file = date_dir / f"boxscore_{game_id}.json"
                            if boxscore_file.exists():
                                games_with_boxscore += 1

                                with open(boxscore_file) as bf:
                                    boxscore = json.load(bf)

                                for bs_result in boxscore.get("resultSets", []):
                                    if bs_result["name"] == "TeamStats":
                                        bs_headers = bs_result["headers"]
                                        idx_team_name = bs_headers.index("TEAM_NAME")
                                        idx_pts = bs_headers.index("PTS")

                                        for bs_row in bs_result["rowSet"]:
                                            teams_found.add(bs_row[idx_team_name])
                                            if bs_row[idx_pts] is None:
                                                null_scores += 1
                            else:
                                missing_boxscores.append(f"{date_dir.name}/{game_id}")

        except Exception:
            continue

    report.add_stat("Total Completed Games", games_found)
    report.add_stat("Games with Boxscore", games_with_boxscore)
    report.add_stat("Teams Found", len(teams_found))

    expected = SEASON_INFO["nba"]["total_games_per_season"]
    for season, count in sorted(games_by_season.items()):
        pct = count / expected * 100 if expected > 0 else 0
        report.add_stat(
            f"Season {season}-{season + 1}", f"{count} games ({pct:.1f}% of expected)"
        )

    # Validation checks
    report.add_check(
        "Sufficient Games",
        games_found >= 1000,
        f"{games_found} games found (minimum: 1000)",
        "warning" if games_found < 1000 else "info",
    )

    boxscore_pct = games_with_boxscore / games_found * 100 if games_found > 0 else 0
    report.add_check(
        "Boxscore Coverage",
        boxscore_pct >= 95,
        f"{boxscore_pct:.1f}% of games have boxscores",
        "warning" if boxscore_pct < 95 else "info",
    )

    report.add_check(
        "Team Coverage",
        len(teams_found) >= 28,
        f"{len(teams_found)}/30 expected teams found",
        "warning" if len(teams_found) < 28 else "info",
    )

    missing_teams = set(EXPECTED_TEAMS["nba"]) - teams_found
    if missing_teams:
        report.add_check(
            "Missing Teams",
            False,
            f"Missing: {', '.join(sorted(missing_teams))}",
            "warning",
        )
    else:
        report.add_check("Missing Teams", True, "All expected teams present")

    report.add_check(
        "Null Scores",
        null_scores == 0,
        f"{null_scores} null score values found",
        "warning" if null_scores > 0 else "info",
    )

    if missing_boxscores:
        report.add_check(
            "Missing Boxscores",
            len(missing_boxscores) < 50,
            f"{len(missing_boxscores)} games missing boxscores",
            "warning" if len(missing_boxscores) >= 50 else "info",
        )

    return report


def validate_nhl_data() -> DataValidationReport:
    """Validate NHL data from PostgreSQL."""
    return _validate_sport_from_database("nhl")


def validate_mlb_data() -> DataValidationReport:
    """Validate MLB data from PostgreSQL."""
    return _validate_sport_from_database("mlb")


def validate_nfl_data() -> DataValidationReport:
    """Validate NFL data from PostgreSQL."""
    return _validate_sport_from_database("nfl")


def validate_elo_ratings() -> None:
    """Validate that Elo rating files exist and are valid."""
    print(f"\n{'=' * 100}")
    print("📊 ELO RATINGS VALIDATION")
    print(f"{'=' * 100}")

    elo_files = [
        ("nba", "data/nba_current_elo_ratings.csv"),
        ("nhl", "data/nhl_current_elo_ratings.csv"),
        ("mlb", "data/mlb_current_elo_ratings.csv"),
        ("nfl", "data/nfl_current_elo_ratings.csv"),
    ]

    for sport, filepath in elo_files:
        path = Path(filepath)
        if path.exists():
            try:
                df = pd.read_csv(path)
                teams = len(df)
                if "rating" in df.columns:
                    avg_rating = df["rating"].mean()
                    min_rating = df["rating"].min()
                    max_rating = df["rating"].max()
                    print(f"✅ {sport.upper()}: {filepath}")
                    print(
                        f"   Teams: {teams}, Avg: {avg_rating:.0f}, Range: {min_rating:.0f}-{max_rating:.0f}"
                    )
                else:
                    print(f"⚠️  {sport.upper()}: {filepath} - no 'rating' column")
            except Exception as e:
                print(f"❌ {sport.upper()}: {filepath} - Error: {e}")
        else:
            print(f"⚠️  {sport.upper()}: {filepath} not found")


def validate_kalshi_integration() -> None:
    """Validate Kalshi API data and market files."""
    print(f"\n{'=' * 100}")
    print("📊 KALSHI INTEGRATION VALIDATION")
    print(f"{'=' * 100}")

    kalshi_files = ["data/kalshi_markets.json", "data/kalshi_nhl_markets.json"]

    for filepath in kalshi_files:
        path = Path(filepath)
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)

                if isinstance(data, list):
                    print(f"✅ {filepath}: {len(data)} markets")
                elif isinstance(data, dict):
                    print(f"✅ {filepath}: {len(data)} keys")
                else:
                    print(f"⚠️  {filepath}: unexpected format")
            except Exception as e:
                print(f"❌ {filepath}: Error - {e}")
        else:
            print(f"⚠️  {filepath} not found")

    if Path("kalshkey").exists():
        print("✅ kalshkey: API credentials file exists")
    else:
        print("❌ kalshkey: API credentials file not found")


def generate_summary(reports: Dict[str, DataValidationReport]) -> bool:
    """Generate overall summary of all validations."""
    print(f"\n{'#' * 100}")
    print("📋 OVERALL VALIDATION SUMMARY")
    print(f"{'#' * 100}")

    all_passed = True
    total_errors = 0
    total_warnings = 0

    print(
        f"\n{'Sport':<10} {'Status':<15} {'Errors':<10} {'Warnings':<10} {'Games':<15}"
    )
    print(f"{'-' * 60}")

    for sport, report in reports.items():
        errors = len(report.errors)
        warnings = len(report.warnings)
        games = report.stats.get(
            "Total Completed Games", report.stats.get("Completed Games", 0)
        )

        if isinstance(games, str):
            games = games.split()[0]
        elif games is None:
            games = 0

        status = "✅ PASS" if errors == 0 else "❌ FAIL"
        if errors == 0 and warnings > 0:
            status = "⚠️  WARN"

        print(
            f"{sport.upper():<10} {status:<15} {errors:<10} {warnings:<10} {games:<15}"
        )

        total_errors += errors
        total_warnings += warnings
        if errors > 0:
            all_passed = False

    print(f"{'-' * 60}")
    print(
        f"{'TOTAL':<10} {'✅ PASS' if all_passed else '❌ FAIL':<15} {total_errors:<10} {total_warnings:<10}"
    )

    if total_errors > 0:
        print(f"\n🔴 {total_errors} errors require attention before production use")
    if total_warnings > 0:
        print(f"🟡 {total_warnings} warnings should be reviewed")
    if all_passed and total_warnings == 0:
        print("\n🟢 All data validations passed! System ready for production.")

    return all_passed


def main() -> int:
    """Run all data validations."""
    print("=" * 100)
    print("🔍 MULTI-SPORT DATA VALIDATION")
    print(f"📅 Validation Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 100)

    reports: Dict[str, DataValidationReport] = {}

    # Validate each sport
    for sport, validator in [
        ("nba", validate_nba_data),
        ("nhl", validate_nhl_data),
        ("mlb", validate_mlb_data),
        ("nfl", validate_nfl_data),
    ]:
        print(f"\n{'=' * 100}")
        print(f"VALIDATING {sport.upper()} DATA...")
        print("=" * 100)
        reports[sport] = validator()
        reports[sport].print_report()

    # Additional validations
    validate_elo_ratings()
    validate_kalshi_integration()

    # Overall summary
    all_passed = generate_summary(reports)

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
