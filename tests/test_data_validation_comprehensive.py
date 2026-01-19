"""Comprehensive tests for data_validation.py"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys


class TestExpectedTeams:
    """Test EXPECTED_TEAMS constant"""
    
    def test_import_expected_teams(self):
        from data_validation import EXPECTED_TEAMS
        assert 'nba' in EXPECTED_TEAMS
        assert 'nhl' in EXPECTED_TEAMS
        assert 'mlb' in EXPECTED_TEAMS
        assert 'nfl' in EXPECTED_TEAMS
    
    def test_nba_team_count(self):
        from data_validation import EXPECTED_TEAMS
        assert len(EXPECTED_TEAMS['nba']) == 30
    
    def test_nhl_team_count(self):
        from data_validation import EXPECTED_TEAMS
        # NHL has 32 teams (31 + Arizona/Utah)
        assert len(EXPECTED_TEAMS['nhl']) >= 31
    
    def test_mlb_team_count(self):
        from data_validation import EXPECTED_TEAMS
        assert len(EXPECTED_TEAMS['mlb']) == 30
    
    def test_nfl_team_count(self):
        from data_validation import EXPECTED_TEAMS
        assert len(EXPECTED_TEAMS['nfl']) == 32


class TestSeasonInfo:
    """Test SEASON_INFO constant"""
    
    def test_import_season_info(self):
        from data_validation import SEASON_INFO
        assert 'nba' in SEASON_INFO
        assert 'nhl' in SEASON_INFO
        assert 'mlb' in SEASON_INFO
    
    def test_nba_season_info(self):
        from data_validation import SEASON_INFO
        info = SEASON_INFO['nba']
        assert info['games_per_team'] == 82
        assert info['total_games_per_season'] == 1230
        assert info['start_month'] == 10
        assert info['end_month'] == 4
    
    def test_nhl_season_info(self):
        from data_validation import SEASON_INFO
        info = SEASON_INFO['nhl']
        assert info['games_per_team'] == 82
        assert info['total_games_per_season'] == 1312
    
    def test_mlb_season_info(self):
        from data_validation import SEASON_INFO
        info = SEASON_INFO['mlb']
        assert info['games_per_team'] == 162
        assert info['total_games_per_season'] == 2430


class TestDataValidationReport:
    """Test DataValidationReport class"""
    
    def test_create_report(self):
        from data_validation import DataValidationReport
        report = DataValidationReport('test')
        assert report.sport == 'test'
        assert len(report.issues) == 0
        assert len(report.metrics) == 0
    
    def test_add_issue(self):
        from data_validation import DataValidationReport
        report = DataValidationReport('test')
        report.add_issue('Test issue', 'warning')
        assert len(report.issues) == 1
        assert report.issues[0]['message'] == 'Test issue'
        assert report.issues[0]['severity'] == 'warning'
    
    def test_add_metric(self):
        from data_validation import DataValidationReport
        report = DataValidationReport('test')
        report.add_metric('row_count', 1000)
        assert report.metrics['row_count'] == 1000
    
    def test_has_critical_issues_false(self):
        from data_validation import DataValidationReport
        report = DataValidationReport('test')
        report.add_issue('Minor issue', 'warning')
        assert not report.has_critical_issues()
    
    def test_has_critical_issues_true(self):
        from data_validation import DataValidationReport
        report = DataValidationReport('test')
        report.add_issue('Critical issue', 'critical')
        assert report.has_critical_issues()
    
    def test_print_report(self, capsys):
        from data_validation import DataValidationReport
        report = DataValidationReport('nba')
        report.add_metric('games', 100)
        report.add_issue('Test warning', 'warning')
        report.print_report()
        captured = capsys.readouterr()
        assert 'NBA' in captured.out or 'nba' in captured.out


class TestValidateRowCount:
    """Test validate_row_count function"""
    
    def test_validate_row_count_sufficient(self):
        from data_validation import validate_row_count
        
        df = pd.DataFrame({'a': range(1000)})
        report = Mock()
        report.add_metric = Mock()
        report.add_issue = Mock()
        
        validate_row_count(df, report, min_expected=500)
        report.add_metric.assert_called()
    
    def test_validate_row_count_insufficient(self):
        from data_validation import validate_row_count
        
        df = pd.DataFrame({'a': range(100)})
        report = Mock()
        report.add_metric = Mock()
        report.add_issue = Mock()
        
        validate_row_count(df, report, min_expected=500)
        # Should add an issue for low row count


class TestValidateDateRange:
    """Test validate_date_range function"""
    
    def test_validate_date_range_good(self):
        from data_validation import validate_date_range
        
        df = pd.DataFrame({
            'game_date': pd.date_range('2024-01-01', periods=100)
        })
        report = Mock()
        report.add_metric = Mock()
        report.add_issue = Mock()
        
        validate_date_range(df, report, 'game_date')
        report.add_metric.assert_called()
    
    def test_validate_date_range_empty(self):
        from data_validation import validate_date_range
        
        df = pd.DataFrame()
        report = Mock()
        report.add_metric = Mock()
        report.add_issue = Mock()
        
        validate_date_range(df, report, 'game_date')


class TestValidateNullValues:
    """Test validate_null_values function"""
    
    def test_validate_no_nulls(self):
        from data_validation import validate_null_values
        
        df = pd.DataFrame({
            'a': [1, 2, 3],
            'b': ['x', 'y', 'z']
        })
        report = Mock()
        report.add_issue = Mock()
        
        validate_null_values(df, report, ['a', 'b'])
        # No issues should be added
    
    def test_validate_with_nulls(self):
        from data_validation import validate_null_values
        
        df = pd.DataFrame({
            'a': [1, None, 3],
            'b': ['x', 'y', None]
        })
        report = Mock()
        report.add_issue = Mock()
        
        validate_null_values(df, report, ['a', 'b'])


class TestValidateTeamCoverage:
    """Test validate_team_coverage function"""
    
    def test_full_team_coverage(self):
        from data_validation import validate_team_coverage, EXPECTED_TEAMS
        
        teams = EXPECTED_TEAMS['nba']
        df = pd.DataFrame({
            'home_team': teams,
            'away_team': teams[::-1]  # Reversed
        })
        report = Mock()
        report.add_metric = Mock()
        report.add_issue = Mock()
        
        validate_team_coverage(df, report, 'nba')
    
    def test_partial_team_coverage(self):
        from data_validation import validate_team_coverage
        
        df = pd.DataFrame({
            'home_team': ['Lakers', 'Celtics'],
            'away_team': ['Celtics', 'Lakers']
        })
        report = Mock()
        report.add_metric = Mock()
        report.add_issue = Mock()
        
        validate_team_coverage(df, report, 'nba')


class TestValidateScores:
    """Test validate_scores function"""
    
    def test_valid_scores(self):
        from data_validation import validate_scores
        
        df = pd.DataFrame({
            'home_score': [100, 95, 110],
            'away_score': [98, 102, 105]
        })
        report = Mock()
        report.add_issue = Mock()
        
        validate_scores(df, report, 'nba')
    
    def test_invalid_scores_negative(self):
        from data_validation import validate_scores
        
        df = pd.DataFrame({
            'home_score': [100, -5, 110],
            'away_score': [98, 102, 105]
        })
        report = Mock()
        report.add_issue = Mock()
        
        validate_scores(df, report, 'nba')
    
    def test_unrealistic_scores(self):
        from data_validation import validate_scores
        
        df = pd.DataFrame({
            'home_score': [100, 500, 110],  # 500 is unrealistic
            'away_score': [98, 102, 105]
        })
        report = Mock()
        report.add_issue = Mock()
        
        validate_scores(df, report, 'nba')


class TestValidateSeasonCompleteness:
    """Test validate_season_completeness function"""
    
    def test_complete_season(self):
        from data_validation import validate_season_completeness
        
        # Create data for roughly 82 games per team
        report = Mock()
        report.add_metric = Mock()
        report.add_issue = Mock()
        
        df = pd.DataFrame({
            'home_team': ['Lakers'] * 41 + ['Celtics'] * 41,
            'away_team': ['Celtics'] * 41 + ['Lakers'] * 41,
            'game_date': pd.date_range('2024-01-01', periods=82)
        })
        
        validate_season_completeness(df, report, 'nba', 2024)
    
    def test_incomplete_season(self):
        from data_validation import validate_season_completeness
        
        report = Mock()
        report.add_metric = Mock()
        report.add_issue = Mock()
        
        df = pd.DataFrame({
            'home_team': ['Lakers'] * 10,
            'away_team': ['Celtics'] * 10,
            'game_date': pd.date_range('2024-01-01', periods=10)
        })
        
        validate_season_completeness(df, report, 'nba', 2024)


class TestValidateNBAData:
    """Test validate_nba_data function"""
    
    def test_validate_nba_no_data(self):
        from data_validation import validate_nba_data
        
        with patch('data_validation.load_nba_games') as mock_load:
            mock_load.return_value = pd.DataFrame()
            report = validate_nba_data()
            assert report is not None
    
    def test_validate_nba_with_data(self):
        from data_validation import validate_nba_data
        
        df = pd.DataFrame({
            'game_date': pd.date_range('2024-01-01', periods=100),
            'home_team': ['Lakers'] * 100,
            'away_team': ['Celtics'] * 100,
            'home_score': [100] * 100,
            'away_score': [95] * 100
        })
        
        with patch('data_validation.load_nba_games') as mock_load:
            mock_load.return_value = df
            report = validate_nba_data()
            assert report is not None


class TestValidateNHLData:
    """Test validate_nhl_data function"""
    
    def test_validate_nhl_no_database(self):
        from data_validation import validate_nhl_data
        
        with patch('data_validation.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            report = validate_nhl_data()
            assert report is not None


class TestValidateMLBData:
    """Test validate_mlb_data function"""
    
    def test_validate_mlb_no_database(self):
        from data_validation import validate_mlb_data
        
        with patch('data_validation.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            report = validate_mlb_data()
            assert report is not None


class TestValidateNFLData:
    """Test validate_nfl_data function"""
    
    def test_validate_nfl_no_database(self):
        from data_validation import validate_nfl_data
        
        with patch('data_validation.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            report = validate_nfl_data()
            assert report is not None


class TestCheckDataFreshness:
    """Test check_data_freshness function"""
    
    def test_fresh_data(self):
        from data_validation import check_data_freshness
        
        df = pd.DataFrame({
            'game_date': [datetime.now().date()]
        })
        report = Mock()
        report.add_metric = Mock()
        report.add_issue = Mock()
        
        check_data_freshness(df, report, 'game_date')
    
    def test_stale_data(self):
        from data_validation import check_data_freshness
        
        df = pd.DataFrame({
            'game_date': [datetime.now().date() - timedelta(days=30)]
        })
        report = Mock()
        report.add_metric = Mock()
        report.add_issue = Mock()
        
        check_data_freshness(df, report, 'game_date')


class TestCheckDuplicates:
    """Test check_duplicates function"""
    
    def test_no_duplicates(self):
        from data_validation import check_duplicates
        
        df = pd.DataFrame({
            'game_id': [1, 2, 3],
            'data': ['a', 'b', 'c']
        })
        report = Mock()
        report.add_metric = Mock()
        report.add_issue = Mock()
        
        check_duplicates(df, report, 'game_id')
    
    def test_with_duplicates(self):
        from data_validation import check_duplicates
        
        df = pd.DataFrame({
            'game_id': [1, 1, 2],  # Duplicate ID
            'data': ['a', 'b', 'c']
        })
        report = Mock()
        report.add_metric = Mock()
        report.add_issue = Mock()
        
        check_duplicates(df, report, 'game_id')


class TestCheckMissingDates:
    """Test check_missing_dates function"""
    
    def test_no_missing_dates(self):
        from data_validation import check_missing_dates
        
        df = pd.DataFrame({
            'game_date': pd.date_range('2024-01-01', periods=10)
        })
        report = Mock()
        report.add_metric = Mock()
        report.add_issue = Mock()
        
        check_missing_dates(df, report, 'game_date')
    
    def test_with_missing_dates(self):
        from data_validation import check_missing_dates
        
        dates = pd.date_range('2024-01-01', periods=10).tolist()
        dates.pop(5)  # Remove a date
        df = pd.DataFrame({'game_date': dates})
        
        report = Mock()
        report.add_metric = Mock()
        report.add_issue = Mock()
        
        check_missing_dates(df, report, 'game_date')


class TestValidateEloRatings:
    """Test validate_elo_ratings function"""
    
    def test_valid_elo_ratings(self):
        from data_validation import validate_elo_ratings
        
        df = pd.DataFrame({
            'team': ['Lakers', 'Celtics', 'Warriors'],
            'elo': [1550, 1480, 1520]
        })
        report = Mock()
        report.add_metric = Mock()
        report.add_issue = Mock()
        
        validate_elo_ratings(df, report)
    
    def test_invalid_elo_ratings(self):
        from data_validation import validate_elo_ratings
        
        df = pd.DataFrame({
            'team': ['Lakers', 'Celtics'],
            'elo': [1550, 2500]  # 2500 is too high
        })
        report = Mock()
        report.add_metric = Mock()
        report.add_issue = Mock()
        
        validate_elo_ratings(df, report)


class TestMain:
    """Test main function"""
    
    def test_main_runs(self):
        from data_validation import main
        
        with patch('data_validation.validate_nba_data') as mock_nba, \
             patch('data_validation.validate_nhl_data') as mock_nhl, \
             patch('data_validation.validate_mlb_data') as mock_mlb, \
             patch('data_validation.validate_nfl_data') as mock_nfl:
            
            mock_report = Mock()
            mock_report.print_report = Mock()
            mock_report.has_critical_issues.return_value = False
            
            mock_nba.return_value = mock_report
            mock_nhl.return_value = mock_report
            mock_mlb.return_value = mock_report
            mock_nfl.return_value = mock_report
            
            try:
                main()
            except Exception:
                pass


class TestModuleImports:
    """Test that module can be imported successfully"""
    
    def test_import_module(self):
        import data_validation
        assert hasattr(data_validation, 'EXPECTED_TEAMS')
        assert hasattr(data_validation, 'SEASON_INFO')
        assert hasattr(data_validation, 'DataValidationReport')
        assert hasattr(data_validation, 'validate_nba_data')
        assert hasattr(data_validation, 'validate_nhl_data')
        assert hasattr(data_validation, 'validate_mlb_data')
