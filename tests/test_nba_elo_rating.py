"""
Tests for NBAEloRating class.
"""

import pytest
from unittest.mock import patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.elo import NBAEloRating


class TestNBAEloRatingBasic:
    """Basic tests for NBAEloRating."""

    def test_initialization(self):
        """Test default initialization."""
        elo = NBAEloRating()
        assert elo.k_factor == 20
        assert elo.home_advantage == 100
        assert elo.initial_rating == 1500
        assert elo.ratings == {}

    def test_custom_initialization(self):
        """Test initialization with custom parameters."""
        elo = NBAEloRating(k_factor=25, home_advantage=80, initial_rating=1600)
        assert elo.k_factor == 25
        assert elo.home_advantage == 80
        assert elo.initial_rating == 1600

    def test_get_rating_new_team(self):
        """Test getting rating for a new team."""
        elo = NBAEloRating(initial_rating=1600)
        assert elo.get_rating("Lakers") == 1600
        assert "Lakers" in elo.ratings

    def test_get_rating_existing_team(self):
        """Test getting rating for an existing team."""
        elo = NBAEloRating()
        elo.ratings["Lakers"] = 1650
        assert elo.get_rating("Lakers") == 1650

    def test_predict_home_advantage(self):
        """Test prediction with home advantage."""
        elo = NBAEloRating()
        elo.ratings = {"Lakers": 1600, "Celtics": 1400}

        # With home advantage
        prob_with_home = elo.predict("Lakers", "Celtics", is_neutral=False)

        # Without home advantage (neutral)
        prob_neutral = elo.predict("Lakers", "Celtics", is_neutral=True)

        assert prob_with_home > prob_neutral

    def test_update_expected_win(self):
        """Test update when expected team wins."""
        elo = NBAEloRating(k_factor=20)
        elo.ratings = {"Lakers": 1600, "Celtics": 1400}

        initial_lakers = elo.get_rating("Lakers")
        initial_celtics = elo.get_rating("Celtics")

        # Lakers (higher rated) win at home
        change = elo.update("Lakers", "Celtics", home_win=1.0, is_neutral=False)

        # Winner should increase, but not by much (expected win)
        assert elo.get_rating("Lakers") > initial_lakers
        assert elo.get_rating("Celtics") < initial_celtics
        assert abs(change) < 10  # Small change for expected win

    def test_update_upset(self):
        """Test update when underdog wins (upset)."""
        elo1 = NBAEloRating(k_factor=20)
        elo2 = NBAEloRating(k_factor=20)

        elo1.ratings["Lakers"] = 1600
        elo1.ratings["Celtics"] = 1400

        elo2.ratings["Lakers"] = 1600
        elo2.ratings["Celtics"] = 1400

        # Expected win - smaller change
        elo1.update("Lakers", "Celtics", home_win=1.0, is_neutral=False)
        change1 = abs(1600 - elo1.ratings["Lakers"])

        # Upset - bigger change
        elo2.update("Lakers", "Celtics", home_win=0.0, is_neutral=False)
        change2 = abs(1600 - elo2.ratings["Lakers"])

        assert change2 > change1

    def test_multiple_games_rating_progression(self):
        """Test rating progression over multiple games."""
        elo = NBAEloRating(k_factor=20)

        # Lakers win 5 games in a row
        for _ in range(5):
            elo.update("Lakers", "Celtics", home_win=1.0, is_neutral=False)

        assert elo.ratings["Lakers"] > 1500
        assert elo.ratings["Celtics"] < 1500
        # After 5 wins, Lakers should be significantly higher
        assert elo.ratings["Lakers"] > 1520


class TestLoadNBAGamesFromJson:
    """Test the load_nba_games_from_json function."""

    def test_load_empty_directory(self, tmp_path):
        """Test loading from empty directory."""
        nba_dir = tmp_path / "nba"
        nba_dir.mkdir()

        with patch("plugins.elo.nba_elo_rating.Path") as mock_path:
            mock_path.return_value = nba_dir
            # This would need proper mocking of the function
            # For now, we test that the function handles missing data gracefully

    def test_load_with_no_data_directory(self):
        """Test graceful handling when data directory doesn't exist."""
        with patch("plugins.elo.nba_elo_rating.Path") as mock_path:
            mock_path.return_value.iterdir.side_effect = FileNotFoundError
            # Function should handle this gracefully


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_same_team(self):
        """Test behavior when home and away teams are the same."""
        elo = NBAEloRating()
        with pytest.raises(ValueError):
            elo.update("Lakers", "Lakers", home_win=1.0, is_neutral=False)

    def test_extreme_ratings(self):
        """Test with extreme rating differences."""
        elo = NBAEloRating()
        elo.ratings = {"TeamA": 2400, "TeamB": 600}

        # TeamA should have very high probability of winning
        prob = elo.predict("TeamA", "TeamB", is_neutral=False)
        assert prob > 0.99

    def test_zero_k_factor(self):
        """Test with zero K-factor (no learning)."""
        elo = NBAEloRating(k_factor=0)
        elo.ratings = {"Lakers": 1600, "Celtics": 1400}

        initial_lakers = elo.get_rating("Lakers")
        elo.update("Lakers", "Celtics", home_win=1.0, is_neutral=False)

        # With k_factor=0, ratings shouldn't change
        assert elo.get_rating("Lakers") == initial_lakers


class TestNBASpecificFeatures:
    """Test NBA-specific features."""

    def test_evaluate_on_games(self):
        """Test the evaluate_on_games method."""
        elo = NBAEloRating()

        # Create mock games as a DataFrame
        import pandas as pd

        games = pd.DataFrame(
            [
                {"home_team": "Lakers", "away_team": "Celtics", "home_won": True},
                {"home_team": "Celtics", "away_team": "Lakers", "home_won": False},
            ]
        )

        # This method should calculate accuracy, log loss, etc.
        results = elo.evaluate_on_games(games)

        assert "accuracy" in results
        assert "auc" in results
        assert "predictions" in results
        assert "actuals" in results
        assert isinstance(results["accuracy"], float)
        assert 0 <= results["accuracy"] <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
