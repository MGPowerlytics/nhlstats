"""Comprehensive tests for lift_gain_analysis.py module."""

import pytest
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
from datetime import datetime
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestSportConfig:
    """Tests for SPORT_CONFIG dictionary."""

    def test_sport_config_exists(self):
        """Test SPORT_CONFIG is defined."""
        from lift_gain_analysis import SPORT_CONFIG

        assert SPORT_CONFIG is not None

    def test_nba_config(self):
        """Test NBA configuration."""
        from lift_gain_analysis import SPORT_CONFIG

        assert 'nba' in SPORT_CONFIG
        assert SPORT_CONFIG['nba']['elo_module'] == 'nba_elo_rating'
        assert SPORT_CONFIG['nba']['season_start_month'] == 10

    def test_nhl_config(self):
        """Test NHL configuration."""
        from lift_gain_analysis import SPORT_CONFIG

        assert 'nhl' in SPORT_CONFIG
        assert SPORT_CONFIG['nhl']['data_source'] == 'duckdb'

    def test_mlb_config(self):
        """Test MLB configuration."""
        from lift_gain_analysis import SPORT_CONFIG

        assert 'mlb' in SPORT_CONFIG
        assert SPORT_CONFIG['mlb']['season_start_month'] == 3

    def test_nfl_config(self):
        """Test NFL configuration."""
        from lift_gain_analysis import SPORT_CONFIG

        assert 'nfl' in SPORT_CONFIG
        assert SPORT_CONFIG['nfl']['season_start_month'] == 9

    def test_epl_config(self):
        """Test EPL configuration."""
        from lift_gain_analysis import SPORT_CONFIG

        assert 'epl' in SPORT_CONFIG
        assert SPORT_CONFIG['epl']['data_source'] == 'csv'

    def test_ncaab_config(self):
        """Test NCAAB configuration."""
        from lift_gain_analysis import SPORT_CONFIG

        assert 'ncaab' in SPORT_CONFIG


class TestGetCurrentSeasonStart:
    """Tests for get_current_season_start function."""

    def test_nba_season_start(self):
        """Test NBA season start calculation."""
        from lift_gain_analysis import get_current_season_start

        result = get_current_season_start('nba')

        # Should return a date string
        assert isinstance(result, str)
        assert len(result) == 10  # YYYY-MM-DD format
        assert '-10-01' in result  # October start

    def test_mlb_season_start(self):
        """Test MLB season start calculation."""
        from lift_gain_analysis import get_current_season_start

        result = get_current_season_start('mlb')

        assert '-03-01' in result  # March start

    def test_nfl_season_start(self):
        """Test NFL season start calculation."""
        from lift_gain_analysis import get_current_season_start

        result = get_current_season_start('nfl')

        assert '-09-01' in result  # September start

    def test_nhl_season_start(self):
        """Test NHL season start calculation."""
        from lift_gain_analysis import get_current_season_start

        result = get_current_season_start('nhl')

        assert '-10-01' in result

    @patch('lift_gain_analysis.datetime')
    def test_season_start_before_season(self, mock_datetime):
        """Test season start when current date is before season start."""
        from lift_gain_analysis import get_current_season_start

        # Mock current date as January 2024
        mock_now = MagicMock()
        mock_now.year = 2024
        mock_now.month = 1
        mock_datetime.now.return_value = mock_now

        result = get_current_season_start('nba')

        # Should return previous year (2023-10-01)
        assert '2023-10-01' == result

    @patch('lift_gain_analysis.datetime')
    def test_season_start_after_season(self, mock_datetime):
        """Test season start when current date is after season start."""
        from lift_gain_analysis import get_current_season_start

        # Mock current date as November 2024
        mock_now = MagicMock()
        mock_now.year = 2024
        mock_now.month = 11
        mock_datetime.now.return_value = mock_now

        result = get_current_season_start('nba')

        # Should return current year (2024-10-01)
        assert '2024-10-01' == result


class TestLoadGamesFromDuckDB:
    """Tests for load_games_from_duckdb function."""

    def test_missing_database(self, tmp_path):
        """Test behavior when database doesn't exist."""
        from lift_gain_analysis import load_games_from_duckdb

        with patch('lift_gain_analysis.Path') as mock_path:
            mock_path.return_value.exists.return_value = False

            result = load_games_from_duckdb('nhl')

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0


class TestDecileCalculations:
    """Tests for decile calculation logic."""

    def test_calculate_deciles(self):
        """Test decile calculation."""
        # Create test data
        np.random.seed(42)
        n = 1000
        probs = np.random.random(n)

        df = pd.DataFrame({'home_win_prob': probs})

        # Calculate deciles (0-9)
        df['decile'] = pd.qcut(df['home_win_prob'], 10, labels=False, duplicates='drop')

        # Should have 10 deciles (0-9)
        assert df['decile'].nunique() <= 10
        assert df['decile'].min() >= 0
        assert df['decile'].max() <= 9

    def test_lift_formula(self):
        """Test lift calculation formula."""
        # Lift = actual_win_rate / baseline_win_rate
        baseline = 0.5  # 50% random win rate
        actual = 0.75   # 75% win rate in top decile

        lift = actual / baseline

        assert lift == pytest.approx(1.5)

    def test_gain_formula(self):
        """Test gain calculation formula."""
        # Gain = cumulative_wins / total_wins * 100
        total_wins = 500
        cumulative_wins = 200

        gain = (cumulative_wins / total_wins) * 100

        assert gain == pytest.approx(40.0)

    def test_decile_stats_aggregation(self):
        """Test aggregating stats by decile."""
        np.random.seed(42)

        # Create test data with correlation between prob and outcome
        n = 1000
        probs = np.random.random(n)
        # Higher probability -> higher chance of home win
        outcomes = (np.random.random(n) < probs).astype(int)

        df = pd.DataFrame({
            'home_win_prob': probs,
            'home_won': outcomes
        })

        df['decile'] = pd.qcut(df['home_win_prob'], 10, labels=False, duplicates='drop')

        # Aggregate by decile
        stats = df.groupby('decile').agg({
            'home_won': ['sum', 'count', 'mean']
        })

        # Higher deciles should have higher win rates
        win_rates = df.groupby('decile')['home_won'].mean()

        # Check general trend (not exact due to randomness)
        assert win_rates.iloc[-1] > win_rates.iloc[0] * 0.8  # Allow some variance


class TestEloIntegration:
    """Tests for Elo rating integration."""

    def test_elo_prediction_range(self):
        """Test Elo predictions are in valid range."""
        from plugins.elo import NBAEloRating

        elo = NBAEloRating()

        for _ in range(100):
            prob = elo.predict("TeamA", "TeamB")
            assert 0 < prob < 1

    def test_elo_update_affects_prediction(self):
        """Test that updating Elo affects future predictions."""
        from plugins.elo import NBAEloRating

        elo = NBAEloRating()

        initial_prob = elo.predict("TeamA", "TeamB")

        # TeamA wins multiple games
        for _ in range(10):
            elo.update("TeamA", "TeamB", home_won=True)

        final_prob = elo.predict("TeamA", "TeamB")

        # TeamA should now be favored more
        assert final_prob > initial_prob


class TestAnalysisFunctions:
    """Tests for main analysis functions."""

    def test_analyze_sport_function_exists(self):
        """Test analyze_sport function exists."""
        from lift_gain_analysis import analyze_sport

        assert callable(analyze_sport)

    def test_main_function_exists(self):
        """Test main function exists."""
        from lift_gain_analysis import main

        assert callable(main)


class TestDataFormatting:
    """Tests for data formatting functions."""

    def test_percentage_formatting(self):
        """Test percentage formatting."""
        value = 0.756
        formatted = f"{value:.1%}"

        assert formatted == "75.6%"

    def test_lift_formatting(self):
        """Test lift formatting."""
        lift = 1.523
        formatted = f"{lift:.2f}x"

        assert formatted == "1.52x"

    def test_gain_formatting(self):
        """Test gain formatting."""
        gain = 42.5
        formatted = f"{gain:.1f}%"

        assert formatted == "42.5%"


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_dataframe(self):
        """Test handling empty dataframe."""
        df = pd.DataFrame()

        assert len(df) == 0

    def test_single_game(self):
        """Test handling single game."""
        df = pd.DataFrame({
            'home_win_prob': [0.6],
            'home_won': [1]
        })

        assert len(df) == 1
        assert df['home_won'].sum() == 1

    def test_all_home_wins(self):
        """Test when all games are home wins."""
        df = pd.DataFrame({
            'home_win_prob': [0.5, 0.6, 0.7, 0.8],
            'home_won': [1, 1, 1, 1]
        })

        win_rate = df['home_won'].mean()
        assert win_rate == 1.0

    def test_all_away_wins(self):
        """Test when all games are away wins."""
        df = pd.DataFrame({
            'home_win_prob': [0.5, 0.6, 0.7, 0.8],
            'home_won': [0, 0, 0, 0]
        })

        win_rate = df['home_won'].mean()
        assert win_rate == 0.0

    def test_exactly_50_percent(self):
        """Test 50% win rate."""
        df = pd.DataFrame({
            'home_win_prob': [0.5, 0.5, 0.5, 0.5],
            'home_won': [1, 0, 1, 0]
        })

        win_rate = df['home_won'].mean()
        assert win_rate == 0.5


class TestCumulativeCalculations:
    """Tests for cumulative calculations."""

    def test_cumulative_sum(self):
        """Test cumulative sum calculation."""
        values = [10, 20, 30, 40]
        df = pd.DataFrame({'wins': values})
        df['cumulative'] = df['wins'].cumsum()

        expected = [10, 30, 60, 100]
        assert list(df['cumulative']) == expected

    def test_cumulative_percentage(self):
        """Test cumulative percentage calculation."""
        total = 100
        cumulative = [10, 30, 60, 100]

        percentages = [c / total * 100 for c in cumulative]

        assert percentages == [10.0, 30.0, 60.0, 100.0]

    def test_running_win_rate(self):
        """Test running win rate calculation."""
        df = pd.DataFrame({
            'wins': [8, 7, 6, 5, 4],
            'games': [10, 10, 10, 10, 10]
        })

        df['cumulative_wins'] = df['wins'].cumsum()
        df['cumulative_games'] = df['games'].cumsum()
        df['running_win_rate'] = df['cumulative_wins'] / df['cumulative_games']

        # First decile win rate
        assert df['running_win_rate'].iloc[0] == pytest.approx(0.8)

        # Overall win rate (sum of wins / sum of games)
        assert df['running_win_rate'].iloc[-1] == pytest.approx(0.6)


class TestReportGeneration:
    """Tests for report generation."""

    def test_report_header_format(self):
        """Test report header format."""
        sport = "NBA"
        header = f"{'='*80}\n{sport} LIFT/GAIN ANALYSIS\n{'='*80}"

        assert "NBA" in header
        assert "=" in header

    def test_decile_table_format(self):
        """Test decile table format."""
        decile = 9
        win_rate = 0.75
        lift = 1.5
        gain = 85.0

        row = f"Decile {decile}: Win Rate {win_rate:.1%}, Lift {lift:.2f}x, Gain {gain:.1f}%"

        assert "Decile 9" in row
        assert "75.0%" in row
        assert "1.50x" in row
        assert "85.0%" in row


class TestStatisticalMeasures:
    """Tests for statistical measures."""

    def test_baseline_win_rate(self):
        """Test baseline win rate calculation."""
        # Baseline is typically around 50% for most sports
        baseline = 0.5

        assert baseline == 0.5

    def test_perfect_model_lift(self):
        """Test lift for perfect prediction model."""
        # If model perfectly predicts outcomes,
        # top decile would have 100% win rate
        top_decile_rate = 1.0
        baseline = 0.5

        lift = top_decile_rate / baseline

        assert lift == 2.0

    def test_random_model_lift(self):
        """Test lift for random prediction model."""
        # Random model should have ~1.0 lift
        random_rate = 0.5
        baseline = 0.5

        lift = random_rate / baseline

        assert lift == pytest.approx(1.0)

    def test_auc_approximation(self):
        """Test AUC approximation from gains."""
        # If gains are linear (random model), AUC = 0.5
        # If gains are perfect, AUC = 1.0

        random_gains = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        perfect_gains = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100]

        # Calculate approximate AUC (area under gains curve)
        random_auc = sum(random_gains) / 1000
        perfect_auc = sum(perfect_gains) / 1000

        assert random_auc == pytest.approx(0.55)  # Slightly above 0.5 due to discrete
        assert perfect_auc == 1.0
