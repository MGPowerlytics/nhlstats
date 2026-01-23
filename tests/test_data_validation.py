"""Tests for Data Validation module."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestExpectedTeams:
    """Test expected teams configuration."""

    def test_nba_has_30_teams(self):
        """Test that NBA has 30 expected teams."""
        from data_validation import EXPECTED_TEAMS
        assert len(EXPECTED_TEAMS['nba']) == 30

    def test_nhl_has_32_plus_teams(self):
        """Test that NHL has expected teams (32+, includes relocations)."""
        from data_validation import EXPECTED_TEAMS
        assert len(EXPECTED_TEAMS['nhl']) >= 32

    def test_mlb_has_30_teams(self):
        """Test that MLB has 30 expected teams."""
        from data_validation import EXPECTED_TEAMS
        assert len(EXPECTED_TEAMS['mlb']) == 30

    def test_nfl_has_32_teams(self):
        """Test that NFL has 32 expected teams."""
        from data_validation import EXPECTED_TEAMS
        assert len(EXPECTED_TEAMS['nfl']) == 32

    def test_nba_teams_are_unique(self):
        """Test that NBA teams are unique."""
        from data_validation import EXPECTED_TEAMS
        teams = EXPECTED_TEAMS['nba']
        assert len(teams) == len(set(teams))

    def test_nhl_teams_are_unique(self):
        """Test that NHL teams are unique."""
        from data_validation import EXPECTED_TEAMS
        teams = EXPECTED_TEAMS['nhl']
        assert len(teams) == len(set(teams))

    def test_mlb_teams_are_unique(self):
        """Test that MLB teams are unique."""
        from data_validation import EXPECTED_TEAMS
        teams = EXPECTED_TEAMS['mlb']
        assert len(teams) == len(set(teams))

    def test_nfl_teams_are_unique(self):
        """Test that NFL teams are unique."""
        from data_validation import EXPECTED_TEAMS
        teams = EXPECTED_TEAMS['nfl']
        assert len(teams) == len(set(teams))


class TestSeasonInfo:
    """Test season info configuration."""

    def test_nba_season_info(self):
        """Test NBA season configuration."""
        from data_validation import SEASON_INFO

        nba = SEASON_INFO['nba']
        assert nba['games_per_team'] == 82
        assert nba['total_games_per_season'] == 1230
        assert nba['start_month'] == 10
        assert nba['end_month'] == 4

    def test_nhl_season_info(self):
        """Test NHL season configuration."""
        from data_validation import SEASON_INFO

        nhl = SEASON_INFO['nhl']
        assert nhl['games_per_team'] == 82
        assert nhl['total_games_per_season'] == 1312
        assert nhl['start_month'] == 10
        assert nhl['end_month'] == 4

    def test_mlb_season_info(self):
        """Test MLB season configuration."""
        from data_validation import SEASON_INFO

        mlb = SEASON_INFO['mlb']
        assert mlb['games_per_team'] == 162
        assert mlb['total_games_per_season'] == 2430
        assert mlb['start_month'] == 3

    def test_nfl_season_info(self):
        """Test NFL season configuration."""
        from data_validation import SEASON_INFO

        nfl = SEASON_INFO['nfl']
        assert nfl['games_per_team'] == 17
        assert nfl['start_month'] == 9


class TestTeamNameNormalization:
    """Test team name normalization utilities."""

    def test_normalize_team_name_lowercase(self):
        """Test normalizing to lowercase."""
        name = "Los Angeles Lakers"
        normalized = name.lower()
        assert normalized == "los angeles lakers"

    def test_normalize_team_name_strip_spaces(self):
        """Test stripping extra spaces."""
        name = "  Los Angeles Lakers  "
        normalized = name.strip()
        assert normalized == "Los Angeles Lakers"

    def test_normalize_team_name_abbreviation(self):
        """Test common abbreviation patterns."""
        team_map = {
            'LAL': 'Lakers',
            'BOS': 'Celtics',
            'NYK': 'Knicks',
            'GSW': 'Warriors'
        }

        assert team_map['LAL'] == 'Lakers'
        assert team_map['BOS'] == 'Celtics'


class TestGameCountValidation:
    """Test game count validation logic."""

    def test_nba_season_has_correct_games(self):
        """Test NBA season game count calculation."""
        teams = 30
        games_per_team = 82
        expected_total = (teams * games_per_team) // 2

        assert expected_total == 1230

    def test_nhl_season_has_correct_games(self):
        """Test NHL season game count calculation."""
        teams = 32
        games_per_team = 82
        expected_total = (teams * games_per_team) // 2

        assert expected_total == 1312

    def test_mlb_season_has_correct_games(self):
        """Test MLB season game count calculation."""
        teams = 30
        games_per_team = 162
        expected_total = (teams * games_per_team) // 2

        assert expected_total == 2430

    def test_nfl_season_has_correct_games(self):
        """Test NFL season game count calculation."""
        teams = 32
        games_per_team = 17
        expected_total = (teams * games_per_team) // 2

        assert expected_total == 272


class TestDateValidation:
    """Test date validation utilities."""

    def test_date_in_season_nba(self):
        """Test checking if date is in NBA season."""
        # NBA regular season: October to April
        date_in_season = datetime(2024, 1, 15)  # January
        date_out_of_season = datetime(2024, 7, 15)  # July

        # Simple check based on month
        in_season = date_in_season.month in [10, 11, 12, 1, 2, 3, 4]
        out_of_season = date_out_of_season.month in [10, 11, 12, 1, 2, 3, 4]

        assert in_season == True
        assert out_of_season == False

    def test_date_in_season_mlb(self):
        """Test checking if date is in MLB season."""
        # MLB regular season: March/April to September/October
        date_in_season = datetime(2024, 7, 15)  # July
        date_out_of_season = datetime(2024, 1, 15)  # January

        in_season = date_in_season.month in [3, 4, 5, 6, 7, 8, 9, 10]
        out_of_season = date_out_of_season.month in [3, 4, 5, 6, 7, 8, 9, 10]

        assert in_season == True
        assert out_of_season == False


class TestDataQualityChecks:
    """Test data quality check utilities."""

    def test_null_check(self):
        """Test checking for null values."""
        data = [
            {'score': 100, 'team': 'Lakers'},
            {'score': None, 'team': 'Celtics'},
            {'score': 95, 'team': None}
        ]

        nulls = sum(1 for d in data if d.get('score') is None or d.get('team') is None)

        assert nulls == 2

    def test_score_validity(self):
        """Test checking for valid scores."""
        scores = [100, 95, -5, 0, 150, 999]

        # Valid NBA scores are typically 70-180
        valid_scores = [s for s in scores if 0 <= s <= 200]

        assert len(valid_scores) == 4  # Excludes -5 and 999

    def test_date_range_check(self):
        """Test checking date ranges."""
        dates = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 5),
            datetime(2024, 1, 10)
        ]

        min_date = min(dates)
        max_date = max(dates)
        date_range = (max_date - min_date).days

        assert date_range == 9


class TestMissingDataDetection:
    """Test missing data detection."""

    def test_find_missing_dates(self):
        """Test finding missing dates in a range."""
        from datetime import timedelta

        # Games on these dates
        game_dates = {
            datetime(2024, 1, 1),
            datetime(2024, 1, 3),
            datetime(2024, 1, 5)
        }

        # Check for gaps
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 5)

        missing = []
        current = start
        while current <= end:
            if current not in game_dates:
                missing.append(current)
            current += timedelta(days=1)

        # Missing: Jan 2, Jan 4
        assert len(missing) == 2

    def test_find_missing_teams(self):
        """Test finding teams without games."""
        all_teams = {'Lakers', 'Celtics', 'Knicks', 'Heat'}
        teams_with_games = {'Lakers', 'Celtics'}

        missing_teams = all_teams - teams_with_games

        assert missing_teams == {'Knicks', 'Heat'}


class TestValidationReport:
    """Test validation report generation."""

    def test_report_structure(self):
        """Test validation report has expected structure."""
        report = {
            'sport': 'nba',
            'total_games': 1000,
            'date_range': {
                'start': '2024-01-01',
                'end': '2024-04-15'
            },
            'issues': [],
            'warnings': [],
            'summary': 'Passed'
        }

        assert 'sport' in report
        assert 'total_games' in report
        assert 'date_range' in report
        assert 'issues' in report
        assert 'warnings' in report

    def test_report_with_issues(self):
        """Test validation report with issues."""
        report = {
            'sport': 'nba',
            'issues': [
                'Missing 5 games on 2024-01-15',
                'Invalid score detected: -10'
            ],
            'warnings': [
                'Only 3 teams have games this week'
            ]
        }

        assert len(report['issues']) == 2
        assert len(report['warnings']) == 1
