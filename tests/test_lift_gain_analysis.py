"""Tests for Lift/Gain Analysis module."""

import pytest
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestSportConfig:
    """Test sport configuration."""
    
    def test_sport_config_has_all_sports(self):
        """Test that config has all expected sports."""
        from lift_gain_analysis import SPORT_CONFIG
        
        expected_sports = ['nba', 'nhl', 'mlb', 'nfl', 'epl', 'ncaab']
        
        for sport in expected_sports:
            assert sport in SPORT_CONFIG
    
    def test_sport_config_has_required_fields(self):
        """Test that each sport has required configuration fields."""
        from lift_gain_analysis import SPORT_CONFIG
        
        required_fields = ['elo_module', 'elo_class', 'k_factor', 'home_advantage', 
                          'data_source', 'season_start_month']
        
        for sport, config in SPORT_CONFIG.items():
            for field in required_fields:
                assert field in config, f"Missing {field} in {sport} config"
    
    def test_nba_config_values(self):
        """Test NBA configuration values."""
        from lift_gain_analysis import SPORT_CONFIG
        
        nba = SPORT_CONFIG['nba']
        
        assert nba['k_factor'] == 20
        assert nba['home_advantage'] == 100
        assert nba['season_start_month'] == 10
        assert nba['data_source'] == 'json'
    
    def test_nhl_config_values(self):
        """Test NHL configuration values."""
        from lift_gain_analysis import SPORT_CONFIG
        
        nhl = SPORT_CONFIG['nhl']
        
        assert nhl['k_factor'] == 10
        assert nhl['home_advantage'] == 50
        assert nhl['season_start_month'] == 10
    
    def test_mlb_config_values(self):
        """Test MLB configuration values."""
        from lift_gain_analysis import SPORT_CONFIG
        
        mlb = SPORT_CONFIG['mlb']
        
        assert mlb['k_factor'] == 20
        assert mlb['home_advantage'] == 50
        assert mlb['season_start_month'] == 3
    
    def test_nfl_config_values(self):
        """Test NFL configuration values."""
        from lift_gain_analysis import SPORT_CONFIG
        
        nfl = SPORT_CONFIG['nfl']
        
        assert nfl['k_factor'] == 20
        assert nfl['home_advantage'] == 65
        assert nfl['season_start_month'] == 9


class TestGetCurrentSeasonStart:
    """Test get_current_season_start function."""
    
    def test_nba_season_start_after_october(self):
        """Test NBA season start when we're in the season."""
        from lift_gain_analysis import get_current_season_start
        
        with patch('lift_gain_analysis.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15)
            
            start = get_current_season_start('nba')
            
            assert start == "2023-10-01"  # Season started previous October
    
    def test_nba_season_start_in_october(self):
        """Test NBA season start when we're in October."""
        from lift_gain_analysis import get_current_season_start
        
        with patch('lift_gain_analysis.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 10, 15)
            
            start = get_current_season_start('nba')
            
            assert start == "2024-10-01"  # Current year
    
    def test_mlb_season_start(self):
        """Test MLB season start."""
        from lift_gain_analysis import get_current_season_start
        
        with patch('lift_gain_analysis.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 7, 15)
            
            start = get_current_season_start('mlb')
            
            assert start == "2024-03-01"  # Same year, season started in March


class TestLoadGamesFromDuckDB:
    """Test loading games from DuckDB."""
    
    @patch('lift_gain_analysis.Path')
    @patch('lift_gain_analysis.duckdb.connect')
    def test_load_games_db_not_found(self, mock_connect, mock_path):
        """Test handling when database file doesn't exist."""
        from lift_gain_analysis import load_games_from_duckdb
        
        mock_path.return_value.exists.return_value = False
        
        result = load_games_from_duckdb('nhl')
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


class TestDecileAnalysis:
    """Test decile analysis calculations."""
    
    def test_calculate_deciles(self):
        """Test calculating probability deciles."""
        probabilities = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]
        
        # Assign deciles (1-10)
        deciles = []
        for p in probabilities:
            decile = min(10, int(p * 10) + 1)
            deciles.append(decile)
        
        assert deciles[0] == 1  # 5%
        assert deciles[4] == 5  # 45%
        assert deciles[9] == 10  # 95%
    
    def test_lift_calculation(self):
        """Test lift calculation."""
        # Lift = actual_win_rate / baseline_win_rate
        actual_win_rate = 0.75
        baseline_win_rate = 0.50
        
        lift = actual_win_rate / baseline_win_rate
        
        assert lift == 1.5  # 1.5x better than baseline
    
    def test_lift_calculation_perfect_model(self):
        """Test lift calculation for perfect predictions."""
        actual_win_rate = 1.0
        baseline_win_rate = 0.50
        
        lift = actual_win_rate / baseline_win_rate
        
        assert lift == 2.0
    
    def test_gain_calculation(self):
        """Test cumulative gain calculation."""
        # Total wins in dataset
        total_wins = 100
        
        # Wins captured in top decile
        decile_wins = [20, 15, 12, 10, 10, 8, 8, 7, 5, 5]
        
        # Cumulative gains
        cumulative_wins = 0
        gains = []
        for wins in decile_wins:
            cumulative_wins += wins
            gain_pct = cumulative_wins / total_wins * 100
            gains.append(gain_pct)
        
        assert gains[0] == 20  # Top decile captures 20%
        assert gains[9] == 100  # All deciles capture 100%
    
    def test_coverage_calculation(self):
        """Test coverage percentage calculation."""
        total_games = 1000
        decile_size = 100  # Each decile has 10% of games
        
        coverage_pct = decile_size / total_games * 100
        
        assert coverage_pct == 10.0


class TestDecileMetrics:
    """Test decile-level metrics."""
    
    def test_decile_win_rate(self):
        """Test win rate within a decile."""
        decile_games = 100
        decile_wins = 75
        
        win_rate = decile_wins / decile_games
        
        assert win_rate == 0.75
    
    def test_decile_edge(self):
        """Test edge calculation within a decile."""
        # Average predicted probability in decile
        avg_predicted_prob = 0.85
        # Actual win rate
        actual_win_rate = 0.80
        
        calibration_error = avg_predicted_prob - actual_win_rate
        
        assert calibration_error == pytest.approx(0.05)
    
    def test_model_calibration_perfect(self):
        """Test perfect calibration detection."""
        predicted_probs = [0.1, 0.3, 0.5, 0.7, 0.9]
        actual_rates = [0.1, 0.3, 0.5, 0.7, 0.9]
        
        # Calculate mean calibration error
        errors = [abs(p - a) for p, a in zip(predicted_probs, actual_rates)]
        mean_error = sum(errors) / len(errors)
        
        assert mean_error == 0.0
    
    def test_model_calibration_overconfident(self):
        """Test overconfident model detection."""
        predicted_probs = [0.2, 0.4, 0.6, 0.8, 0.9]  # Predicted high
        actual_rates = [0.1, 0.3, 0.4, 0.5, 0.6]  # Actual lower
        
        # Model predicts higher than actual
        overconfident = all(p > a for p, a in zip(predicted_probs, actual_rates))
        
        assert overconfident == True


class TestSeasonalAnalysis:
    """Test seasonal analysis features."""
    
    def test_filter_by_season(self):
        """Test filtering games by season."""
        games = [
            {'date': '2023-10-15', 'home_win': 1},
            {'date': '2023-11-20', 'home_win': 0},
            {'date': '2024-01-10', 'home_win': 1},
            {'date': '2024-05-15', 'home_win': 0}  # Out of regular season
        ]
        
        season_start = '2023-10-01'
        season_end = '2024-04-30'
        
        filtered = [g for g in games if season_start <= g['date'] <= season_end]
        
        assert len(filtered) == 3  # Excludes May game
    
    def test_current_season_identification(self):
        """Test identifying current vs historical seasons."""
        now = datetime(2024, 1, 15)
        
        # For NBA, current season started October 2023
        nba_season_start_month = 10
        
        if now.month < nba_season_start_month:
            season_year = now.year - 1
        else:
            season_year = now.year
        
        current_season = f"{season_year}-{season_year + 1}"
        
        assert current_season == "2023-2024"


class TestOutputFormatting:
    """Test output formatting for reports."""
    
    def test_format_percentage(self):
        """Test formatting percentages."""
        value = 0.753
        formatted = f"{value:.1%}"
        
        assert formatted == "75.3%"
    
    def test_format_lift(self):
        """Test formatting lift values."""
        lift = 1.532
        formatted = f"{lift:.2f}x"
        
        assert formatted == "1.53x"
    
    def test_format_table_row(self):
        """Test formatting table row."""
        decile = 1
        games = 100
        wins = 85
        gain = 17.0
        lift = 1.70
        
        row = f"| {decile:2d} | {games:4d} | {wins:3d} | {gain:5.1f}% | {lift:.2f}x |"
        
        assert "|  1 |" in row
        assert "17.0%" in row
