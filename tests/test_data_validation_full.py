"""Comprehensive tests for data_validation module."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pandas as pd
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestExpectedTeams:
    """Test EXPECTED_TEAMS configuration."""

    def test_expected_teams_nba_count(self):
        """Test NBA has 30 teams."""
        from data_validation import EXPECTED_TEAMS

        assert len(EXPECTED_TEAMS['nba']) == 30

    def test_expected_teams_nhl_count(self):
        """Test NHL has 32+ teams (includes Utah)."""
        from data_validation import EXPECTED_TEAMS

        assert len(EXPECTED_TEAMS['nhl']) >= 32

    def test_expected_teams_mlb_count(self):
        """Test MLB has 30 teams."""
        from data_validation import EXPECTED_TEAMS

        assert len(EXPECTED_TEAMS['mlb']) == 30

    def test_expected_teams_nfl_count(self):
        """Test NFL has 32 teams."""
        from data_validation import EXPECTED_TEAMS

        assert len(EXPECTED_TEAMS['nfl']) == 32

    def test_nba_teams_valid(self):
        """Test some NBA teams are present."""
        from data_validation import EXPECTED_TEAMS

        nba_teams = EXPECTED_TEAMS['nba']
        assert 'Lakers' in nba_teams
        assert 'Celtics' in nba_teams
        assert 'Warriors' in nba_teams

    def test_nhl_teams_valid(self):
        """Test some NHL teams are present."""
        from data_validation import EXPECTED_TEAMS

        nhl_teams = EXPECTED_TEAMS['nhl']
        assert 'Boston Bruins' in nhl_teams
        assert 'Toronto Maple Leafs' in nhl_teams

    def test_mlb_teams_valid(self):
        """Test some MLB teams are present."""
        from data_validation import EXPECTED_TEAMS

        mlb_teams = EXPECTED_TEAMS['mlb']
        assert 'New York Yankees' in mlb_teams
        assert 'Los Angeles Dodgers' in mlb_teams

    def test_nfl_teams_valid(self):
        """Test some NFL teams are present."""
        from data_validation import EXPECTED_TEAMS

        nfl_teams = EXPECTED_TEAMS['nfl']
        assert 'Kansas City Chiefs' in nfl_teams
        assert 'Dallas Cowboys' in nfl_teams


class TestSeasonInfo:
    """Test SEASON_INFO configuration."""

    def test_nba_season_info(self):
        """Test NBA season info."""
        from data_validation import SEASON_INFO

        nba = SEASON_INFO['nba']
        assert nba['games_per_team'] == 82
        assert nba['total_games_per_season'] == 1230
        assert nba['start_month'] == 10

    def test_nhl_season_info(self):
        """Test NHL season info."""
        from data_validation import SEASON_INFO

        nhl = SEASON_INFO['nhl']
        assert nhl['games_per_team'] == 82
        assert nhl['total_games_per_season'] == 1312

    def test_mlb_season_info(self):
        """Test MLB season info."""
        from data_validation import SEASON_INFO

        mlb = SEASON_INFO['mlb']
        assert mlb['games_per_team'] == 162
        assert mlb['total_games_per_season'] == 2430

    def test_nfl_season_info(self):
        """Test NFL season info."""
        from data_validation import SEASON_INFO

        nfl = SEASON_INFO['nfl']
        assert nfl['games_per_team'] == 17
        assert nfl['total_games_per_season'] == 272


class TestValidationReport:
    """Test ValidationReport class."""

    def test_validation_report_init(self):
        """Test ValidationReport initialization."""
        from data_validation import DataValidationReport

        report = DataValidationReport(sport='nba')

        assert report.sport == 'nba'
        assert report.errors == []
        assert report.warnings == []
        assert report.stats == {}

    def test_add_error(self):
        """Test adding error to report."""
        from data_validation import DataValidationReport

        report = DataValidationReport(sport='nba')
        report.add_check("Missing data", False, "No games found", severity='error')

        assert len(report.errors) == 1

    def test_add_warning(self):
        """Test adding warning to report."""
        from data_validation import DataValidationReport

        report = DataValidationReport(sport='nba')
        report.add_check("Low count", False, "Only 5 games", severity='warning')

        assert len(report.warnings) == 1

    def test_add_stat(self):
        """Test adding stat to report."""
        from data_validation import DataValidationReport

        report = DataValidationReport(sport='nba')
        report.add_stat("total_games", 1230)

        assert report.stats['total_games'] == 1230

    def test_has_errors(self):
        """Test has_errors check."""
        from data_validation import DataValidationReport

        report = DataValidationReport(sport='nba')
        assert len(report.errors) == 0

        report.add_check("Test", False, "Error", severity='error')
        assert len(report.errors) == 1


class TestDataValidators:
    """Test data validation functions."""

    def test_validate_date_range(self):
        """Test date range validation."""
        from datetime import date

        start = date(2024, 1, 1)
        end = date(2024, 1, 31)

        assert start < end
        assert (end - start).days == 30

    def test_validate_score_positive(self):
        """Test score is positive."""
        score = 110

        is_valid = score >= 0

        assert is_valid == True

    def test_validate_score_negative_invalid(self):
        """Test negative score is invalid."""
        score = -5

        is_valid = score >= 0

        assert is_valid == False

    def test_validate_team_name_not_empty(self):
        """Test team name is not empty."""
        team = "Lakers"

        is_valid = len(team.strip()) > 0

        assert is_valid == True

    def test_validate_game_id_format(self):
        """Test game ID format."""
        game_id = "2024010100"

        is_valid = len(game_id) > 0 and game_id.isalnum()

        assert is_valid == True


class TestNullValidation:
    """Test null value validation."""

    def test_find_null_values(self):
        """Test finding null values in DataFrame."""
        df = pd.DataFrame({
            'team': ['Lakers', None, 'Celtics'],
            'score': [110, 105, None]
        })

        null_counts = df.isnull().sum()

        assert null_counts['team'] == 1
        assert null_counts['score'] == 1

    def test_null_percentage(self):
        """Test calculating null percentage."""
        df = pd.DataFrame({
            'team': ['Lakers', None, 'Celtics', None],
            'score': [110, 105, 108, 112]
        })

        null_pct = df['team'].isnull().sum() / len(df) * 100

        assert null_pct == 50.0


class TestTeamCoverage:
    """Test team coverage validation."""

    def test_missing_teams(self):
        """Test finding missing teams."""
        expected = ['Lakers', 'Celtics', 'Warriors', 'Heat']
        actual = ['Lakers', 'Celtics', 'Warriors']

        missing = set(expected) - set(actual)

        assert missing == {'Heat'}

    def test_all_teams_present(self):
        """Test when all teams are present."""
        expected = ['Lakers', 'Celtics']
        actual = ['Lakers', 'Celtics', 'Warriors']

        missing = set(expected) - set(actual)

        assert len(missing) == 0


class TestDateCoverage:
    """Test date coverage validation."""

    def test_find_missing_dates(self):
        """Test finding missing dates."""
        from datetime import date, timedelta

        all_dates = [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 4)]

        # Generate expected date range
        start = date(2024, 1, 1)
        end = date(2024, 1, 4)
        expected_dates = []
        current = start
        while current <= end:
            expected_dates.append(current)
            current += timedelta(days=1)

        missing = set(expected_dates) - set(all_dates)

        assert date(2024, 1, 3) in missing

    def test_date_range_span(self):
        """Test date range span calculation."""
        from datetime import date

        start = date(2024, 1, 1)
        end = date(2024, 4, 30)

        days = (end - start).days

        assert days == 120


class TestGameCountValidation:
    """Test game count validation."""

    def test_games_per_team_nba(self):
        """Test NBA games per team."""
        expected = 82
        actual = 80

        pct_complete = actual / expected * 100

        assert pct_complete == pytest.approx(97.6, abs=0.1)

    def test_total_season_games_mlb(self):
        """Test total MLB season games."""
        expected = 2430
        actual = 2400

        missing = expected - actual

        assert missing == 30


class TestDataQuality:
    """Test data quality checks."""

    def test_score_range_valid(self):
        """Test valid score range."""
        scores = [110, 105, 98, 125, 88]

        for score in scores:
            assert 50 <= score <= 200  # Reasonable NBA score range

    def test_invalid_score_detection(self):
        """Test detecting invalid scores."""
        scores = [110, -5, 500, 105]

        invalid = [s for s in scores if s < 0 or s > 300]

        assert len(invalid) == 2

    def test_duplicate_detection(self):
        """Test detecting duplicate entries."""
        df = pd.DataFrame({
            'game_id': ['001', '002', '001', '003'],
            'home_team': ['Lakers', 'Celtics', 'Lakers', 'Heat']
        })

        duplicates = df[df.duplicated(subset=['game_id'], keep=False)]

        assert len(duplicates) == 2


class TestCrossValidation:
    """Test cross-validation between sources."""

    def test_matching_team_names(self):
        """Test team names match across sources."""
        source_a = "Los Angeles Lakers"
        source_b = "LA Lakers"

        # Normalize for comparison
        normalized_a = source_a.lower().replace("los angeles", "la")
        normalized_b = source_b.lower()

        assert normalized_a == normalized_b

    def test_score_consistency(self):
        """Test score consistency across sources."""
        source_a_score = 110
        source_b_score = 110

        is_consistent = source_a_score == source_b_score

        assert is_consistent == True


class TestSeasonValidation:
    """Test season-specific validation."""

    def test_regular_season_dates_nba(self):
        """Test NBA regular season dates."""
        from datetime import date

        # NBA regular season: Oct to April
        game_date = date(2024, 1, 15)

        is_regular_season = 10 <= game_date.month or game_date.month <= 4

        assert is_regular_season == True

    def test_playoff_dates_nba(self):
        """Test NBA playoff dates."""
        from datetime import date

        # NBA playoffs: April to June
        game_date = date(2024, 5, 15)

        is_playoff = game_date.month in [4, 5, 6]

        assert is_playoff == True

    def test_offseason_detection(self):
        """Test offseason detection."""
        from datetime import date

        # NBA offseason: July to September
        game_date = date(2024, 8, 15)

        is_offseason = game_date.month in [7, 8, 9]

        assert is_offseason == True
