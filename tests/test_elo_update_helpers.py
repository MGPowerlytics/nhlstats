"""Tests for elo_update_helpers module."""

import pandas as pd
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, date
from plugins.elo.elo_update_helpers import (
    load_previous_ratings,
    is_valid_score,
    process_games_with_elo,
    save_elo_ratings,
    _log_rating_changes,
)


class TestIsValidScore:
    """Test is_valid_score function."""

    def test_valid_score_int(self):
        """Test integer scores are valid."""
        assert is_valid_score(3) is True
        assert is_valid_score(0) is True
        assert is_valid_score(-1) is True

    def test_valid_score_float(self):
        """Test float scores are valid."""
        assert is_valid_score(3.5) is True
        assert is_valid_score(0.0) is True

    def test_invalid_score_none(self):
        """Test None score is invalid."""
        assert is_valid_score(None) is False

    def test_invalid_score_nan(self):
        """Test NaN score is invalid."""
        import math

        assert is_valid_score(float("nan")) is False

    def test_invalid_score_inf(self):
        """Test infinite score is invalid."""
        import math

        assert is_valid_score(float("inf")) is False
        assert is_valid_score(float("-inf")) is False


class TestProcessGamesWithElo:
    """Test process_games_with_elo function."""

    def test_basic_game_processing(self):
        """Test basic game processing with home_win column."""
        # Create mock Elo instance
        elo_instance = Mock()
        elo_instance.update = Mock()
        elo_instance.legacy_update = Mock()

        # Create test data
        games_df = pd.DataFrame(
            {
                "home_team": ["Team A", "Team B"],
                "away_team": ["Team C", "Team D"],
                "home_win": [True, False],
                "game_date": ["2024-01-01", "2024-01-02"],
            }
        )

        # Create mock config
        config = Mock()
        config.team_mapper = None
        config.sport_id = "test"
        config.use_legacy_update = False
        config.season_reversion_factor = None

        # Process games
        result = process_games_with_elo(
            elo_instance, games_df, config, progress_interval=1000
        )

        # Verify
        assert result == 2
        assert elo_instance.update.call_count == 2
        elo_instance.update.assert_any_call("Team A", "Team C", True)
        elo_instance.update.assert_any_call("Team B", "Team D", False)

    def test_team_mapping(self):
        """Test team mapping functionality."""
        # Create mock Elo instance
        elo_instance = Mock()
        elo_instance.update = Mock()

        # Create test data with team names that need mapping
        games_df = pd.DataFrame(
            {
                "home_team": ["LA Lakers", "Boston Celtics"],
                "away_team": ["Golden State Warriors", "Miami Heat"],
                "home_win": [True, False],
                "game_date": ["2024-01-01", "2024-01-02"],
            }
        )

        # Create team mapper function
        def team_mapper(name):
            mapping = {
                "LA Lakers": "Lakers",
                "Boston Celtics": "Celtics",
                "Golden State Warriors": "Warriors",
                "Miami Heat": "Heat",
            }
            return mapping.get(name)

        # Create mock config
        config = Mock()
        config.team_mapper = team_mapper
        config.sport_id = "test"
        config.use_legacy_update = False
        config.season_reversion_factor = None

        # Process games
        result = process_games_with_elo(
            elo_instance, games_df, config, progress_interval=1000
        )

        # Verify
        assert result == 2
        elo_instance.update.assert_any_call("Lakers", "Warriors", True)
        elo_instance.update.assert_any_call("Celtics", "Heat", False)

    def test_team_mapping_skips_invalid(self):
        """Test that invalid team mapping results are skipped."""
        # Create mock Elo instance
        elo_instance = Mock()
        elo_instance.update = Mock()

        # Create test data with one invalid team
        games_df = pd.DataFrame(
            {
                "home_team": ["Valid Team", "Invalid Team"],
                "away_team": ["Other Team", "Another Team"],
                "home_win": [True, False],
                "game_date": ["2024-01-01", "2024-01-02"],
            }
        )

        # Create team mapper that returns None for invalid team
        def team_mapper(name):
            if name == "Invalid Team":
                return None
            return name

        # Create mock config
        config = Mock()
        config.team_mapper = team_mapper
        config.sport_id = "test"
        config.use_legacy_update = False
        config.season_reversion_factor = None

        # Process games
        result = process_games_with_elo(
            elo_instance, games_df, config, progress_interval=1000
        )

        # Verify only one game processed
        assert result == 1
        elo_instance.update.assert_called_once_with("Valid Team", "Other Team", True)

    def test_result_column_processing(self):
        """Test processing with result column (H/A/D)."""
        # Create mock Elo instance
        elo_instance = Mock()
        elo_instance.update = Mock()

        # Create test data with result column
        games_df = pd.DataFrame(
            {
                "home_team": ["Team A", "Team B", "Team C"],
                "away_team": ["Team D", "Team E", "Team F"],
                "result": ["H", "A", "D"],  # Home win, Away win, Draw
                "game_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            }
        )

        # Create mock config
        config = Mock()
        config.team_mapper = None
        config.sport_id = "test"
        config.use_legacy_update = False
        config.season_reversion_factor = None

        # Process games
        result = process_games_with_elo(
            elo_instance, games_df, config, progress_interval=1000
        )

        # Verify
        assert result == 3
        elo_instance.update.assert_any_call("Team A", "Team D", True)  # Home win
        elo_instance.update.assert_any_call("Team B", "Team E", False)  # Away win
        elo_instance.update.assert_any_call("Team C", "Team F", 0.5)  # Draw

    def test_score_based_result(self):
        """Test result determination from scores."""
        # Create mock Elo instance
        elo_instance = Mock()
        elo_instance.update = Mock()

        # Create test data with scores
        games_df = pd.DataFrame(
            {
                "home_team": ["Team A", "Team B", "Team C"],
                "away_team": ["Team D", "Team E", "Team F"],
                "home_score": [100, 90, 80],
                "away_score": [90, 100, 80],
                "game_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            }
        )

        # Create mock config
        config = Mock()
        config.team_mapper = None
        config.sport_id = "test"
        config.use_legacy_update = False
        config.season_reversion_factor = None

        # Process games
        result = process_games_with_elo(
            elo_instance, games_df, config, progress_interval=1000
        )

        # Verify
        assert result == 3
        elo_instance.update.assert_any_call(
            "Team A", "Team D", True, home_score=100, away_score=90
        )  # Home win 100-90
        elo_instance.update.assert_any_call(
            "Team B", "Team E", False, home_score=90, away_score=100
        )  # Away win 90-100
        elo_instance.update.assert_any_call(
            "Team C", "Team F", False, home_score=80, away_score=80
        )  # Tie 80-80 (home_won=False for tie)

    def test_skip_invalid_scores(self):
        """Test that games with invalid scores are skipped."""
        # Create mock Elo instance
        elo_instance = Mock()
        elo_instance.update = Mock()

        # Create test data with invalid scores
        games_df = pd.DataFrame(
            {
                "home_team": ["Team A", "Team B", "Team C"],
                "away_team": ["Team D", "Team E", "Team F"],
                "home_score": [100, None, float("nan")],
                "away_score": [90, 100, 80],
                "game_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            }
        )

        # Create mock config
        config = Mock()
        config.team_mapper = None
        config.sport_id = "test"
        config.use_legacy_update = False
        config.season_reversion_factor = None

        # Process games
        result = process_games_with_elo(
            elo_instance, games_df, config, progress_interval=1000
        )

        # Verify only first game processed
        assert result == 1
        elo_instance.update.assert_called_once_with(
            "Team A", "Team D", True, home_score=100.0, away_score=90
        )

    def test_legacy_update_mode(self):
        """Test legacy update mode."""
        # Create mock Elo instance
        elo_instance = Mock()
        elo_instance.legacy_update = Mock()
        elo_instance.update = Mock()

        # Create test data
        games_df = pd.DataFrame(
            {
                "home_team": ["Team A", "Team B"],
                "away_team": ["Team C", "Team D"],
                "home_win": [True, False],
                "game_date": ["2024-01-01", "2024-01-02"],
            }
        )

        # Create mock config
        config = Mock()
        config.team_mapper = None
        config.sport_id = "test"
        config.use_legacy_update = True  # Use legacy update
        config.season_reversion_factor = None

        # Process games
        result = process_games_with_elo(
            elo_instance, games_df, config, progress_interval=1000
        )

        # Verify legacy_update called, not update
        assert result == 2
        assert elo_instance.legacy_update.call_count == 2
        assert elo_instance.update.call_count == 0

    def test_additional_update_parameters(self):
        """Test additional update parameters (scores, neutral, tour)."""
        # Create mock Elo instance
        elo_instance = Mock()
        elo_instance.update = Mock()

        # Create test data with additional parameters
        games_df = pd.DataFrame(
            {
                "home_team": ["Team A", "Team B", "Team C"],
                "away_team": ["Team D", "Team E", "Team F"],
                "home_win": [True, False, True],
                "home_score": [100, 90, 80],
                "away_score": [90, 100, 70],
                "neutral": [False, True, False],
                "tour": [None, None, "ATP"],
                "game_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            }
        )

        # Create mock config
        config = Mock()
        config.team_mapper = None
        config.sport_id = "tennis"  # Tennis sport to test tour parameter
        config.use_legacy_update = False
        config.season_reversion_factor = None

        # Process games
        result = process_games_with_elo(
            elo_instance, games_df, config, progress_interval=1000
        )

        # Verify
        assert result == 3
        # First call: scores + neutral=False + tour=None
        elo_instance.update.assert_any_call(
            "Team A",
            "Team D",
            True,
            home_score=100,
            away_score=90,
            is_neutral=False,
            tour=None,
        )
        # Second call: scores + neutral=True + tour=None
        elo_instance.update.assert_any_call(
            "Team B",
            "Team E",
            False,
            home_score=90,
            away_score=100,
            is_neutral=True,
            tour=None,
        )
        # Third call: scores + neutral=False + tour='ATP' (tennis)
        elo_instance.update.assert_any_call(
            "Team C",
            "Team F",
            True,
            home_score=80,
            away_score=70,
            is_neutral=False,
            tour="ATP",
        )

    def test_nba_season_detection(self):
        """Test NBA season detection logic."""
        # Create mock Elo instance with season reversion method
        elo_instance = Mock()
        elo_instance.update = Mock()
        elo_instance.apply_season_reversion = Mock()

        # Create test data spanning NBA offseason
        games_df = pd.DataFrame(
            {
                "home_team": ["Team A", "Team B", "Team C", "Team D"],
                "away_team": ["Team E", "Team F", "Team G", "Team H"],
                "home_win": [True, False, True, False],
                "game_date": [
                    "2024-04-15",  # End of season
                    "2024-10-20",  # Start of new season (>120 days)
                    "2024-10-25",  # Same season
                    "2024-10-30",  # Same season
                ],
            }
        )

        # Create mock config for NBA
        config = Mock()
        config.team_mapper = None
        config.sport_id = "nba"
        config.use_legacy_update = False
        config.season_reversion_factor = 0.4

        # Process games
        result = process_games_with_elo(
            elo_instance, games_df, config, progress_interval=1000
        )

        # Verify
        assert result == 4
        # Season reversion should be called once (between game 1 and 2)
        assert elo_instance.apply_season_reversion.call_count == 1
        elo_instance.apply_season_reversion.assert_called_with(0.4)

    def test_progress_reporting(self):
        """Test progress interval reporting."""
        # Create mock Elo instance
        elo_instance = Mock()
        elo_instance.update = Mock()

        # Create test data with 5 games
        games_df = pd.DataFrame(
            {
                "home_team": [f"Team {i}" for i in range(5)],
                "away_team": [f"Opponent {i}" for i in range(5)],
                "home_win": [True] * 5,
                "game_date": ["2024-01-01"] * 5,
            }
        )

        # Create mock config
        config = Mock()
        config.team_mapper = None
        config.sport_id = "test"
        config.use_legacy_update = False
        config.season_reversion_factor = None

        # Process games with progress interval of 2
        result = process_games_with_elo(
            elo_instance, games_df, config, progress_interval=2
        )

        # Verify all games processed
        assert result == 5
        assert elo_instance.update.call_count == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
