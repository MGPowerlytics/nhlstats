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
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import pandas as pd
from plugins.db_manager import default_db
from plugins.utils import DictStoreMixin

warnings.filterwarnings("ignore")


@dataclass
class CheckResult:
    """Result of a single validation check."""

    name: str
    passed: bool
    message: str
    severity: str = "info"


@dataclass
class BaseValidationReport:
    """Base class for validation reports with common fields and methods."""

    sport: str
    checks: List[CheckResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize empty lists if not provided."""
        if self.checks is None:
            self.checks = []
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.stats is None:
            self.stats = {}

    def add_check(
        self,
        name_or_result: Union[str, CheckResult],
        passed: Optional[bool] = None,
        message: Optional[str] = None,
        severity: str = "info",
    ) -> None:
        """Add a validation check result.

        This method accepts either:
        1. A CheckResult object directly
        2. Primitive parameters (name, passed, message, severity) for backward compatibility

        Args:
            name_or_result: Either a CheckResult object or the name of the check
            passed: Whether the check passed (required if name_or_result is a string)
            message: Description of the check result (required if name_or_result is a string)
            severity: Severity level ("info", "warning", "error")
        """
        if isinstance(name_or_result, CheckResult):
            # Direct CheckResult object provided
            check_result = name_or_result
        else:
            # Primitive parameters provided (backward compatibility)
            if passed is None or message is None:
                raise ValueError(
                    "When providing primitive parameters, 'passed' and 'message' are required"
                )
            check_result = CheckResult(
                name=name_or_result, passed=passed, message=message, severity=severity
            )

        self._add_check_result(check_result)

    def _add_check_result(self, check_result: CheckResult) -> None:
        """Add a CheckResult object to the report.

        This internal method handles the common logic for adding check results
        and maintains backward compatibility with error/warning lists.

        Args:
            check_result: The check result to add
        """
        self.checks.append(check_result)

        # For backward compatibility with tests - add to errors/warnings lists
        # Child classes can override to customize formatting (e.g., add emojis)
        if not check_result.passed:
            if check_result.severity == "error":
                self.errors.append(self._format_error_message(check_result))
            elif check_result.severity == "warning":
                self.warnings.append(self._format_warning_message(check_result))

    def _format_check_message(self, check_result: CheckResult, prefix: str = "") -> str:
        """Format check message for backward compatibility.

        Can be overridden by child classes to add custom formatting (e.g., emojis).

        Args:
            check_result: The check result to format
            prefix: Optional prefix to add before the message

        Returns:
            Formatted check message
        """
        return f"{prefix}{check_result.name}: {check_result.message}"

    def _format_error_message(self, check_result: CheckResult) -> str:
        """Format error message for backward compatibility.

        Can be overridden by child classes to add custom formatting (e.g., emojis).

        Args:
            check_result: The check result to format

        Returns:
            Formatted error message
        """
        return self._format_check_message(check_result)

    def _format_warning_message(self, check_result: CheckResult) -> str:
        """Format warning message for backward compatibility.

        Can be overridden by child classes to add custom formatting (e.g., emojis).

        Args:
            check_result: The check result to format

        Returns:
            Formatted warning message
        """
        return self._format_check_message(check_result)


@dataclass
class DataValidationReport(BaseValidationReport, DictStoreMixin):
    """Simple data validation report class for backward compatibility with tests."""

    def add_stat(self, name: str, value: Any) -> None:
        """Add a statistic to the report.

        Uses the generic store_in_dict() method from DictStoreMixin
        to eliminate code duplication while maintaining domain-specific
        naming and documentation.

        Args:
            name: Name of the statistic
            value: Value of the statistic

        Raises:
            ValueError: If statistic name is empty
        """
        if not name:
            raise ValueError("Statistic name cannot be empty")
        self.store_in_dict("stats", name, value)

    def print_report(self) -> bool:
        """Print the validation report.

        This is a minimal implementation for backward compatibility with tests.

        Returns:
            True if no errors, False otherwise
        """
        print(f"\n{'=' * REPORT_SEPARATOR_WIDTH}")
        print(f"Validation Report for {self.sport.upper()}")
        print(f"{'=' * REPORT_SEPARATOR_WIDTH}")
        print(f"\n{'=' * REPORT_SEPARATOR_WIDTH}")
        print(f"Validation Report for {self.sport.upper()}")
        print(f"{'=' * REPORT_SEPARATOR_WIDTH}")

        if self.stats:
            print("\nStatistics:")
            for name, value in self.stats.items():
                print(f"  {name}: {value}")

        if self.errors:
            print(f"\nErrors ({len(self.errors)}):")
            for error in self.errors:
                print(f"  ❌ {error}")

        if self.warnings:
            print(f"\nWarnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  ⚠️  {warning}")

        if not self.errors and not self.warnings:
            print("\n✅ All checks passed!")

        return len(self.errors) == 0


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

# Magic number constants for better maintainability
REPORT_SEPARATOR_WIDTH = 100
DEFAULT_MIN_GAMES_THRESHOLD = 100
DEFAULT_MIN_TEAMS_THRESHOLD = 25
DEFAULT_EXPECTED_TEAMS_THRESHOLD = 30

# Additional constants for magic numbers
PERCENTAGE_MULTIPLIER = 100  # For converting fractions to percentages
YEAR_START_INDEX = 0  # Start index for year in date string (YYYY-MM-DD)
YEAR_END_INDEX = 4  # End index for year in date string
MONTH_START_INDEX = 5  # Start index for month in date string
MONTH_END_INDEX = 7  # End index for month in date string
NBA_BOXSCORE_COVERAGE_THRESHOLD = 95  # Minimum boxscore coverage percentage for NBA
NBA_MISSING_BOXSCORES_THRESHOLD = 50  # Maximum allowed missing boxscores for NBA
NBA_OCTOBER_MONTH = 10  # Month when NBA season starts (for season calculation)


@dataclass
class GamesSummary(BaseValidationReport):
    """Results from games summary query."""

    total: int = 0
    unique: int = 0
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    home_teams: int = 0
    away_teams: int = 0
    null_home_scores: int = 0
    null_away_scores: int = 0
    completed_games: int = 0
    future_games: int = 0

    # Array index constants for from_row method
    TOTAL_GAMES_INDEX = 0
    UNIQUE_GAMES_INDEX = 1
    MIN_DATE_INDEX = 2
    MAX_DATE_INDEX = 3
    HOME_TEAMS_INDEX = 4
    AWAY_TEAMS_INDEX = 5
    NULL_HOME_SCORES_INDEX = 6
    NULL_AWAY_SCORES_INDEX = 7
    COMPLETED_GAMES_INDEX = 8
    FUTURE_GAMES_INDEX = 9

    # Field specifications for from_row method
    _FIELD_SPECS = [
        ("total", TOTAL_GAMES_INDEX, "_safe_int"),
        ("unique", UNIQUE_GAMES_INDEX, "_safe_int"),
        ("min_date", MIN_DATE_INDEX, "_safe_date_str"),
        ("max_date", MAX_DATE_INDEX, "_safe_date_str"),
        ("home_teams", HOME_TEAMS_INDEX, "_safe_int"),
        ("away_teams", AWAY_TEAMS_INDEX, "_safe_int"),
        ("null_home_scores", NULL_HOME_SCORES_INDEX, "_safe_int"),
        ("null_away_scores", NULL_AWAY_SCORES_INDEX, "_safe_int"),
        ("completed_games", COMPLETED_GAMES_INDEX, "_safe_int"),
        ("future_games", FUTURE_GAMES_INDEX, "_safe_int"),
    ]

    @staticmethod
    def _safe_int(value: Optional[int]) -> int:
        """Convert optional int to int, defaulting to 0 if None."""
        return value or 0

    @staticmethod
    def _safe_date_str(value: Any) -> Optional[str]:
        """Convert value to string if not None, otherwise return None."""
        return str(value) if value else None

    @classmethod
    def from_row(cls, row: tuple, sport: str) -> "GamesSummary":
        """Create GamesSummary from database query row tuple.

        Args:
            row: Tuple containing query results in predefined order.
            sport: The sport name (e.g., "NBA", "NHL")

        Returns:
            GamesSummary instance with safe defaults for None values.
        """
        kwargs = {"sport": sport}
        for field_name, index, converter_name in cls._FIELD_SPECS:
            converter = getattr(cls, converter_name)
            value = row[index] if index < len(row) else None
            kwargs[field_name] = converter(value)
        return cls(**kwargs)

    def _format_error_message(self, check_result: CheckResult) -> str:
        """Format error message with emoji for GamesSummary reports.

        Args:
            check_result: The check result to format

        Returns:
            Formatted error message with error emoji
        """
        return self._format_check_message(check_result, "❌ ")

    def _format_warning_message(self, check_result: CheckResult) -> str:
        """Format warning message with emoji for GamesSummary reports.

        Args:
            check_result: The check result to format

        Returns:
            Formatted warning message with warning emoji
        """
        return self._format_check_message(check_result, "⚠️  ")

    def _print_header(self) -> None:
        """Print report header."""
        print(f"\n{'=' * REPORT_SEPARATOR_WIDTH}")
        print(f"📊 {self.sport.upper()} DATA VALIDATION REPORT")
        print(f"{'=' * REPORT_SEPARATOR_WIDTH}")
        """Print statistics section."""
        if not self.stats:
            return

        print("\n📈 Statistics:")
        for name, value in self.stats.items():
            if isinstance(value, float):
                print(f"   {name}: {value:,.2f}")
            elif isinstance(value, int):
                print(f"   {name}: {value:,}")
            else:
                print(f"   {name}: {value}")

    def _print_passed_checks(self) -> None:
        """Print passed checks section."""
        passed_checks = [c for c in self.checks if c.passed]
        if not passed_checks:
            return

        print(f"\n✅ Passed Checks ({len(passed_checks)}):")
        for check in passed_checks:
            print(f"   ✓ {check.name}: {check.message}")

    def _print_check_list(self, check_list: List[str], emoji: str, label: str) -> None:
        """Print a list of checks (warnings or errors).

        Args:
            check_list: List of check messages to print
            emoji: Emoji to display in header
            label: Label for the section (e.g., "Warnings", "Errors")
        """
        if not check_list:
            return

        print(f"\n{emoji} {label} ({len(check_list)}):")
        for check in check_list:
            print(f"   {check}")

    def _print_warnings(self) -> None:
        """Print warnings section."""
        self._print_check_list(self.warnings, "⚠️", "Warnings")

    def _print_errors(self) -> None:
        """Print errors section."""
        self._print_check_list(self.errors, "❌", "Errors")

    def _print_summary(self) -> None:
        """Print summary section."""
        passed_checks = [c for c in self.checks if c.passed]
        total = len(self.checks)
        passed = len(passed_checks)

        print(f"\n{'=' * REPORT_SEPARATOR_WIDTH}")
        print(f"📋 Summary: {passed}/{total} checks passed")
        if self.errors:
            print(f"   ❌ {len(self.errors)} errors require attention")
        if self.warnings:
            print(f"   ⚠️  {len(self.warnings)} warnings to review")
        print(f"{'=' * REPORT_SEPARATOR_WIDTH}")

    def print_report(self) -> bool:
        """Print formatted validation report."""
        self._print_header()
        self._print_statistics()
        self._print_passed_checks()
        self._print_warnings()
        self._print_errors()
        self._print_summary()

        return len(self.errors) == 0


def _run_common_db_validations(
    report: "DataValidationReport",
    summary: GamesSummary,
    teams_found: Set[str],
    sport: str,
) -> None:
    """Run common validation checks for database-backed sports."""
    thresholds = VALIDATION_THRESHOLDS.get(sport, {})
    min_games = thresholds.get("min_games", DEFAULT_MIN_GAMES_THRESHOLD)
    min_teams = thresholds.get("min_teams", DEFAULT_MIN_TEAMS_THRESHOLD)
    expected_teams = thresholds.get("expected_teams", DEFAULT_EXPECTED_TEAMS_THRESHOLD)

    # Extract validation logic into intention-revealing methods
    _validate_sufficient_games(report, summary, min_games)
    _validate_null_scores(report, summary)
    _validate_team_coverage(report, teams_found, sport, min_teams, expected_teams)


def _validate_sufficient_games(
    report: "DataValidationReport", summary: GamesSummary, min_games: int
) -> None:
    """Validate that we have sufficient completed games for accurate predictions.

    Args:
        report: Validation report to add checks to
        summary: Games summary statistics
        min_games: Minimum number of completed games required
    """
    # Sufficient games check - CRITICAL for prediction accuracy
    report.add_check(
        CheckResult(
            name="Sufficient Games",
            passed=summary.completed_games >= min_games,
            message=f"{summary.completed_games} completed games found (minimum: {min_games})",
            severity="error" if summary.completed_games < min_games else "info",
        )
    )


def _validate_null_scores(
    report: "DataValidationReport", summary: GamesSummary
) -> None:
    """Validate that there are no null scores which would break Elo updates.

    Args:
        report: Validation report to add checks to
        summary: Games summary statistics
    """
    # Null scores checks - CRITICAL for accurate Elo updates
    report.add_check(
        CheckResult(
            name="Null Home Scores",
            passed=summary.null_home_scores == 0,
            message=f"{summary.null_home_scores} null home scores",
            severity="error" if summary.null_home_scores > 0 else "info",
        )
    )

    report.add_check(
        CheckResult(
            name="Null Away Scores",
            passed=summary.null_away_scores == 0,
            message=f"{summary.null_away_scores} null away scores",
            severity="error" if summary.null_away_scores > 0 else "info",
        )
    )


def _validate_team_coverage(
    report: "DataValidationReport",
    teams_found: Set[str],
    sport: str,
    min_teams: int,
    expected_teams: int,
) -> None:
    """Validate team coverage to ensure complete league representation.

    Args:
        report: Validation report to add checks to
        teams_found: Set of team names found in the data
        sport: Sport being validated
        min_teams: Minimum number of teams required
        expected_teams: Expected number of teams in the league
    """
    # Team coverage check - CRITICAL for complete league coverage
    report.add_check(
        "Team Coverage",
        len(teams_found) >= min_teams,
        f"{len(teams_found)}/{expected_teams} expected teams found",
        "error" if len(teams_found) < min_teams else "info",
    )

    # Check for missing teams - CRITICAL for complete league coverage
    missing_teams = set(EXPECTED_TEAMS.get(sport, [])) - teams_found
    if missing_teams:
        report.add_check(
            "Missing Teams",
            False,
            f"Missing: {', '.join(sorted(missing_teams))}",
            "error",
        )
    else:
        report.add_check("Missing Teams", True, "All expected teams present")


def _validate_sport_from_database(sport: str) -> "DataValidationReport":
    """Generic validation for sports stored in PostgreSQL unified_games table."""
    report = DataValidationReport(sport)

    try:
        # Query games summary
        games = default_db.execute(GAMES_SUMMARY_QUERY, {"sport": sport}).fetchone()
        summary = GamesSummary.from_row(games, sport)

        # Add game statistics to report
        _add_game_statistics_to_report(report, summary)

        # Add season statistics to report
        _add_season_statistics_to_report(report, sport)

        # Add team statistics to report
        teams_found = _add_team_statistics_to_report(report, sport)

        # Run common validations
        _run_common_db_validations(report, summary, teams_found, sport)

        # Check sport-specific table
        _check_sport_specific_table(report, sport)

    except Exception as e:
        report.add_check("Query Execution", False, str(e), "error")

    return report


def _add_game_statistics_to_report(
    report: "DataValidationReport", summary: "GamesSummary"
) -> None:
    """Add game summary statistics to validation report."""
    report.add_stat("Total Games", summary.total)
    report.add_stat("Completed Games", summary.completed_games)
    report.add_stat("Future Games", summary.future_games)
    report.add_stat("Date Range", f"{summary.min_date} to {summary.max_date}")
    report.add_stat("Unique Home Teams", summary.home_teams)
    report.add_stat("Unique Away Teams", summary.away_teams)


def _add_season_statistics_to_report(
    report: "DataValidationReport", sport: str
) -> None:
    """Add season statistics to validation report."""
    seasons = default_db.execute(SEASONS_QUERY, {"sport": sport}).fetchall()
    expected = SEASON_INFO.get(sport, {}).get("total_games_per_season", 0)

    for season, count in seasons:
        pct = count / expected * PERCENTAGE_MULTIPLIER if expected > 0 else 0
        report.add_stat(
            f"Season {int(season)}", f"{count} games ({pct:.1f}% of expected)"
        )


def _add_team_statistics_to_report(
    report: "DataValidationReport", sport: str
) -> Set[str]:
    """Add team statistics to validation report and return set of found teams."""
    all_teams = default_db.execute(TEAMS_QUERY, {"sport": sport}).fetchall()
    teams_found = {t[0] for t in all_teams}
    report.add_stat("Total Teams", len(teams_found))
    return teams_found


def _check_sport_specific_table(report: "DataValidationReport", sport: str) -> None:
    """Check if sport-specific table exists and has data."""
    try:
        table_name = f"{sport}_games"
        count = default_db.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        report.add_stat(f"{table_name} rows", count)
        report.add_check(
            f"{table_name} has data",
            count > 0,
            f"{count:,} rows",
            "warning" if count == 0 else "info",
        )
    except Exception as e:
        report.add_check(f"{sport}_games exists", False, str(e), "warning")


def validate_nba_data() -> "DataValidationReport":
    """Validate NBA data from JSON files."""
    report = DataValidationReport("nba")
    nba_dir = Path("data/nba")

    # Validate directory structure
    if not _validate_nba_directory_structure(report, nba_dir):
        return report

    # Get date directories
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
    analysis_result = _analyze_nba_game_data(date_dirs)

    # Add statistics to report
    _add_nba_statistics_to_report(report, analysis_result)

    # Add validation checks
    _add_nba_validation_checks(report, analysis_result)

    return report


def _validate_nba_directory_structure(
    report: "DataValidationReport", nba_dir: Path
) -> bool:
    """Validate NBA directory structure and add initial checks."""
    if not nba_dir.exists():
        report.add_check(
            "Directory Exists", False, "data/nba directory not found", "error"
        )
        return False

    report.add_check("Directory Exists", True, f"Found {nba_dir}")
    return True


def _analyze_nba_game_data(date_dirs: List[Path]) -> Dict[str, any]:
    """Analyze NBA game data from date directories.

    Returns:
        Dictionary containing analysis results:
        - games_found: Total completed games
        - games_with_boxscore: Games with boxscore files
        - missing_boxscores: List of missing boxscore files
        - null_scores: Count of null score values
        - teams_found: Set of team names found
        - games_by_season: Dictionary mapping season to game count
    """
    games_found = 0
    games_with_boxscore = 0
    missing_boxscores: List[str] = []
    null_scores = 0
    teams_found: Set[str] = set()
    games_by_season: Dict[int, int] = defaultdict(int)

    for date_dir in date_dirs:
        date_result = _process_nba_date_directory(date_dir)
        if date_result:
            games_found += date_result["games_found"]
            games_with_boxscore += date_result["games_with_boxscore"]
            missing_boxscores.extend(date_result["missing_boxscores"])
            null_scores += date_result["null_scores"]
            teams_found.update(date_result["teams_found"])
            for season, count in date_result["games_by_season"].items():
                games_by_season[season] += count

    return {
        "games_found": games_found,
        "games_with_boxscore": games_with_boxscore,
        "missing_boxscores": missing_boxscores,
        "null_scores": null_scores,
        "teams_found": teams_found,
        "games_by_season": games_by_season,
    }


def _process_nba_date_directory(date_dir: Path) -> Optional[Dict[str, any]]:
    """Process a single NBA date directory.

    Returns:
        Dictionary with analysis results for this date directory, or None if no data.
    """
    # Load scoreboard data
    data = _load_nba_scoreboard_data(date_dir)
    if data is None:
        return None

    # Process game headers from the data
    return _process_nba_game_headers(data, date_dir)


def _load_nba_scoreboard_data(date_dir: Path) -> Optional[Dict[str, any]]:
    """Load NBA scoreboard data from JSON file.

    Returns:
        Parsed JSON data or None if file doesn't exist or has errors.
    """
    scoreboard_file = date_dir / f"scoreboard_{date_dir.name}.json"

    if not scoreboard_file.exists():
        return None

    try:
        with open(scoreboard_file) as f:
            data = json.load(f)

        if "resultSets" not in data:
            return None

        return data
    except Exception:
        # Skip directories with errors
        return None


def _process_nba_game_headers(data: Dict[str, any], date_dir: Path) -> Dict[str, any]:
    """Process GameHeader result sets from NBA scoreboard data.

    Returns:
        Dictionary with analysis results for game headers.
    """
    games_found = 0
    games_with_boxscore = 0
    missing_boxscores: List[str] = []
    null_scores = 0
    teams_found: Set[str] = set()
    games_by_season: Dict[int, int] = defaultdict(int)

    for result_set in data["resultSets"]:
        if result_set["name"] != "GameHeader":
            continue

        header_result = _process_game_header(result_set, date_dir)
        if header_result is None:
            continue

        # Aggregate results from this header
        games_found += header_result["games_found"]
        games_with_boxscore += header_result["games_with_boxscore"]
        missing_boxscores.extend(header_result["missing_boxscores"])
        null_scores += header_result["null_scores"]
        teams_found.update(header_result["teams_found"])

        for season, count in header_result["games_by_season"].items():
            games_by_season[season] += count

    return {
        "games_found": games_found,
        "games_with_boxscore": games_with_boxscore,
        "missing_boxscores": missing_boxscores,
        "null_scores": null_scores,
        "teams_found": teams_found,
        "games_by_season": games_by_season,
    }


def _process_game_header(result_set: Dict, date_dir: Path) -> Optional[Dict[str, any]]:
    """Process GameHeader result set from NBA scoreboard.

    Returns:
        Dictionary with analysis results for this GameHeader, or None if no data.
    """
    headers = result_set["headers"]
    idx_game_id = headers.index("GAME_ID")
    idx_status = headers.index("GAME_STATUS_TEXT")

    games_found = 0
    games_with_boxscore = 0
    missing_boxscores: List[str] = []
    null_scores = 0
    teams_found: Set[str] = set()
    games_by_season: Dict[int, int] = defaultdict(int)

    for row in result_set["rowSet"]:
        game_id = str(row[idx_game_id])
        game_status = row[idx_status]

        if "Final" in game_status:
            games_found += 1

            # Calculate season
            year = int(date_dir.name[YEAR_START_INDEX:YEAR_END_INDEX])
            month = int(date_dir.name[MONTH_START_INDEX:MONTH_END_INDEX])
            season = year if month >= NBA_OCTOBER_MONTH else year - 1
            games_by_season[season] += 1

            # Check boxscore
            boxscore_file = date_dir / f"boxscore_{game_id}.json"
            if boxscore_file.exists():
                games_with_boxscore += 1
                boxscore_result = _process_boxscore_file(boxscore_file)
                if boxscore_result:
                    teams_found.update(boxscore_result["teams_found"])
                    null_scores += boxscore_result["null_scores"]
            else:
                missing_boxscores.append(f"{date_dir.name}/{game_id}")

    return {
        "games_found": games_found,
        "games_with_boxscore": games_with_boxscore,
        "missing_boxscores": missing_boxscores,
        "null_scores": null_scores,
        "teams_found": teams_found,
        "games_by_season": games_by_season,
    }


def _process_boxscore_file(boxscore_file: Path) -> Optional[Dict[str, any]]:
    """Process NBA boxscore file to extract team data and scores.

    Returns:
        Dictionary with teams_found and null_scores, or None if error.
    """
    try:
        with open(boxscore_file) as bf:
            boxscore = json.load(bf)

        teams_found: Set[str] = set()
        null_scores = 0

        for bs_result in boxscore.get("resultSets", []):
            if bs_result["name"] == "TeamStats":
                team_result = _process_team_stats(bs_result)
                if team_result:
                    teams_found.update(team_result["teams_found"])
                    null_scores += team_result["null_scores"]

        return {"teams_found": teams_found, "null_scores": null_scores}
    except Exception:
        # Skip boxscore files with errors
        return None


def _process_team_stats(team_stats: Dict) -> Dict[str, any]:
    """Process TeamStats from NBA boxscore.

    Returns:
        Dictionary with teams_found and null_scores.
    """
    bs_headers = team_stats["headers"]
    idx_team_name = bs_headers.index("TEAM_NAME")
    idx_pts = bs_headers.index("PTS")

    teams_found: Set[str] = set()
    null_scores = 0

    for bs_row in team_stats["rowSet"]:
        teams_found.add(bs_row[idx_team_name])
        if bs_row[idx_pts] is None:
            null_scores += 1

    return {"teams_found": teams_found, "null_scores": null_scores}


def _add_nba_statistics_to_report(
    report: "DataValidationReport", analysis_result: Dict[str, any]
) -> None:
    """Add NBA statistics to validation report."""
    games_found = analysis_result["games_found"]
    games_with_boxscore = analysis_result["games_with_boxscore"]
    teams_found = analysis_result["teams_found"]
    games_by_season = analysis_result["games_by_season"]

    report.add_stat("Total Completed Games", games_found)
    report.add_stat("Games with Boxscore", games_with_boxscore)
    report.add_stat("Teams Found", len(teams_found))

    expected = SEASON_INFO["nba"]["total_games_per_season"]
    for season, count in sorted(games_by_season.items()):
        pct = count / expected * PERCENTAGE_MULTIPLIER if expected > 0 else 0
        report.add_stat(
            f"Season {season}-{season + 1}", f"{count} games ({pct:.1f}% of expected)"
        )


def _add_nba_validation_checks(
    report: "DataValidationReport", analysis_result: Dict[str, any]
) -> None:
    """Add NBA validation checks to report."""
    # Extract data from analysis result
    games_found = analysis_result["games_found"]
    games_with_boxscore = analysis_result["games_with_boxscore"]
    teams_found = analysis_result["teams_found"]
    null_scores = analysis_result["null_scores"]
    missing_boxscores = analysis_result["missing_boxscores"]

    # Get NBA validation thresholds
    nba_thresholds = VALIDATION_THRESHOLDS.get("nba", {})
    min_games = nba_thresholds.get("min_games", 1000)
    min_teams = nba_thresholds.get("min_teams", 28)
    expected_teams = nba_thresholds.get("expected_teams", 30)

    # Add all validation checks
    _add_sufficient_games_check(report, games_found, min_games)
    _add_boxscore_coverage_check(report, games_found, games_with_boxscore)
    _add_team_coverage_check(report, teams_found, min_teams, expected_teams)
    _add_missing_teams_check(report, teams_found)
    _add_null_scores_check(report, null_scores)
    _add_missing_boxscores_check(report, missing_boxscores)


def _add_sufficient_games_check(
    report: "DataValidationReport", games_found: int, min_games: int
) -> None:
    """Add sufficient games check - CRITICAL for prediction accuracy."""
    report.add_check(
        CheckResult(
            name="Sufficient Games",
            passed=games_found >= min_games,
            message=f"{games_found} games found (minimum: {min_games})",
            severity="error" if games_found < min_games else "info",
        )
    )


def _add_boxscore_coverage_check(
    report: "DataValidationReport", games_found: int, games_with_boxscore: int
) -> None:
    """Add boxscore coverage check - CRITICAL for data quality."""
    boxscore_pct = (
        games_with_boxscore / games_found * PERCENTAGE_MULTIPLIER
        if games_found > 0
        else 0
    )
    report.add_check(
        CheckResult(
            name="Boxscore Coverage",
            passed=boxscore_pct >= NBA_BOXSCORE_COVERAGE_THRESHOLD,
            message=f"{boxscore_pct:.1f}% of games have boxscores (minimum: {NBA_BOXSCORE_COVERAGE_THRESHOLD}%)",
            severity="error"
            if boxscore_pct < NBA_BOXSCORE_COVERAGE_THRESHOLD
            else "info",
        )
    )


def _add_team_coverage_check(
    report: "DataValidationReport",
    teams_found: Set[str],
    min_teams: int,
    expected_teams: int,
) -> None:
    """Add team coverage check - CRITICAL for complete league coverage."""
    report.add_check(
        "Team Coverage",
        len(teams_found) >= min_teams,
        f"{len(teams_found)}/{expected_teams} expected teams found",
        "error" if len(teams_found) < min_teams else "info",
    )


def _add_missing_teams_check(
    report: "DataValidationReport", teams_found: Set[str]
) -> None:
    """Add missing teams check - CRITICAL for complete league coverage."""
    missing_teams = set(EXPECTED_TEAMS["nba"]) - teams_found
    if missing_teams:
        report.add_check(
            "Missing Teams",
            False,
            f"Missing: {', '.join(sorted(missing_teams))}",
            "error",
        )
    else:
        report.add_check("Missing Teams", True, "All expected teams present")


def _add_null_scores_check(report: "DataValidationReport", null_scores: int) -> None:
    """Add null scores check - CRITICAL for accurate Elo updates."""
    report.add_check(
        "Null Scores",
        null_scores == 0,
        f"{null_scores} null score values found",
        "error" if null_scores > 0 else "info",
    )


def _add_missing_boxscores_check(
    report: "DataValidationReport", missing_boxscores: List[str]
) -> None:
    """Add missing boxscores check."""
    if missing_boxscores:
        report.add_check(
            "Missing Boxscores",
            len(missing_boxscores) < NBA_MISSING_BOXSCORES_THRESHOLD,
            f"{len(missing_boxscores)} games missing boxscores (maximum allowed: {NBA_MISSING_BOXSCORES_THRESHOLD})",
            "warning"
            if len(missing_boxscores) >= NBA_MISSING_BOXSCORES_THRESHOLD
            else "info",
        )


def validate_nhl_data() -> "DataValidationReport":
    """Validate NHL data from PostgreSQL."""
    return _validate_sport_from_database("nhl")


def validate_mlb_data() -> "DataValidationReport":
    """Validate MLB data from PostgreSQL."""
    return _validate_sport_from_database("mlb")


def validate_nfl_data() -> "DataValidationReport":
    """Validate NFL data from PostgreSQL."""
    return _validate_sport_from_database("nfl")


def validate_elo_ratings() -> None:
    """Validate that Elo rating files exist and are valid."""
    print(f"\n{'=' * REPORT_SEPARATOR_WIDTH}")
    print("📊 ELO RATINGS VALIDATION")
    print(f"{'=' * REPORT_SEPARATOR_WIDTH}")

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
    print(f"\n{'=' * REPORT_SEPARATOR_WIDTH}")
    print("📊 KALSHI INTEGRATION VALIDATION")
    print(f"{'=' * REPORT_SEPARATOR_WIDTH}")

    kalshi_files = ["data/kalshi_markets.json", "data/kalshi_nhl_markets.json"]

    for filepath in kalshi_files:
        _validate_kalshi_file(filepath)

    _validate_kalshi_credentials()


def _validate_kalshi_file(filepath: str) -> None:
    """Validate a single Kalshi market file."""
    path = Path(filepath)

    if not path.exists():
        print(f"⚠️  {filepath} not found")
        return

    try:
        with open(path) as f:
            data = json.load(f)
        _print_kalshi_file_status(filepath, data)
    except Exception as e:
        print(f"❌ {filepath}: Error - {e}")


def _print_kalshi_file_status(filepath: str, data: Any) -> None:
    """Print validation status for a Kalshi file based on its data."""
    if isinstance(data, list):
        print(f"✅ {filepath}: {len(data)} markets")
    elif isinstance(data, dict):
        print(f"✅ {filepath}: {len(data)} keys")
    else:
        print(f"⚠️  {filepath}: unexpected format")


def _validate_kalshi_credentials() -> None:
    """Validate Kalshi API credentials file."""
    if Path("kalshkey").exists():
        print("✅ kalshkey: API credentials file exists")
    else:
        print("❌ kalshkey: API credentials file not found")


def generate_summary(reports: Dict[str, "DataValidationReport"]) -> bool:
    """Generate overall summary of all validations."""
    _print_summary_header()

    sport_rows = _calculate_sport_summaries(reports)
    all_passed, total_errors, total_warnings = _print_sport_summary_table(sport_rows)

    _print_final_summary(all_passed, total_errors, total_warnings)

    return all_passed


def _print_summary_header() -> None:
    """Print the summary header section."""
    print(f"\n{'#' * REPORT_SEPARATOR_WIDTH}")
    print("📋 OVERALL VALIDATION SUMMARY")
    print(f"{'#' * REPORT_SEPARATOR_WIDTH}")


def _calculate_sport_summaries(
    reports: Dict[str, "DataValidationReport"],
) -> List[Dict[str, Any]]:
    """Calculate summary statistics for each sport.

    Returns:
        List of dictionaries with sport summary data
    """
    sport_rows = []

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

        sport_rows.append(
            {
                "sport": sport.upper(),
                "status": status,
                "errors": errors,
                "warnings": warnings,
                "games": games,
            }
        )

    return sport_rows


def _print_sport_summary_table(
    sport_rows: List[Dict[str, Any]],
) -> Tuple[bool, int, int]:
    """Print the sport summary table and calculate totals.

    Returns:
        Tuple of (all_passed, total_errors, total_warnings)
    """
    print(
        f"\n{'Sport':<10} {'Status':<15} {'Errors':<10} {'Warnings':<10} {'Games':<15}"
    )
    print(f"{'-' * 60}")

    all_passed = True
    total_errors = 0
    total_warnings = 0

    for row in sport_rows:
        print(
            f"{row['sport']:<10} {row['status']:<15} {row['errors']:<10} {row['warnings']:<10} {row['games']:<15}"
        )

        total_errors += row["errors"]
        total_warnings += row["warnings"]
        if row["errors"] > 0:
            all_passed = False

    print(f"{'-' * 60}")
    print(
        f"{'TOTAL':<10} {'✅ PASS' if all_passed else '❌ FAIL':<15} {total_errors:<10} {total_warnings:<10}"
    )

    return all_passed, total_errors, total_warnings


def _print_final_summary(
    all_passed: bool, total_errors: int, total_warnings: int
) -> None:
    """Print final summary recommendations."""
    if total_errors > 0:
        print(f"\n🔴 {total_errors} errors require attention before production use")
    if total_warnings > 0:
        print(f"🟡 {total_warnings} warnings should be reviewed")
    if all_passed and total_warnings == 0:
        print("\n🟢 All data validations passed! System ready for production.")


def main() -> int:
    """Run all data validations."""
    print("=" * REPORT_SEPARATOR_WIDTH)
    print("🔍 MULTI-SPORT DATA VALIDATION")
    print(f"📅 Validation Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * REPORT_SEPARATOR_WIDTH)

    reports: Dict[str, DataValidationReport] = {}

    # Validate each sport
    for sport, validator in [
        ("nba", validate_nba_data),
        ("nhl", validate_nhl_data),
        ("mlb", validate_mlb_data),
        ("nfl", validate_nfl_data),
    ]:
        print(f"\n{'=' * REPORT_SEPARATOR_WIDTH}")
        print(f"VALIDATING {sport.upper()} DATA...")
        print("=" * REPORT_SEPARATOR_WIDTH)
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
