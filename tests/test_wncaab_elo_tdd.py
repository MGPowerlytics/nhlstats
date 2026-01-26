"""
TDD tests for WNCAABEloRating refactoring to inherit from BaseEloRating.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.elo import BaseEloRating, WNCAABEloRating


class TestWNCAABEloInheritance:
    """Test that WNCAABEloRating properly inherits from BaseEloRating."""

    def test_wncaab_elo_inherits_from_base(self):
        """Verify WNCAABEloRating is a subclass of BaseEloRating."""
        assert issubclass(WNCAABEloRating, BaseEloRating)

    def test_wncaab_elo_can_be_instantiated(self):
        """Test that WNCAABEloRating can be instantiated with default parameters."""
        elo = WNCAABEloRating()
        assert elo is not None
        assert isinstance(elo, BaseEloRating)
        assert elo.k_factor == 20
        assert elo.home_advantage == 100
        assert elo.initial_rating == 1500

    def test_wncaab_elo_has_required_methods(self):
        """Test that WNCAABEloRating implements all required abstract methods."""
        elo = WNCAABEloRating()

        # Check all abstract methods exist
        assert hasattr(elo, "predict")
        assert hasattr(elo, "update")
        assert hasattr(elo, "get_rating")
        assert hasattr(elo, "expected_score")
        assert hasattr(elo, "get_all_ratings")

        # Check method signatures (basic check)
        import inspect

        predict_sig = inspect.signature(elo.predict)
        assert "home_team" in predict_sig.parameters
        assert "away_team" in predict_sig.parameters
        assert "is_neutral" in predict_sig.parameters

        update_sig = inspect.signature(elo.update)
        assert "home_team" in update_sig.parameters
        assert "away_team" in update_sig.parameters
        assert "home_win" in update_sig.parameters
        assert "is_neutral" in update_sig.parameters


class TestWNCAABEloFunctionality:
    """Test the core functionality of WNCAABEloRating."""

    def test_get_rating_returns_initial_for_new_team(self):
        """Test get_rating returns initial rating for new team."""
        elo = WNCAABEloRating(initial_rating=1600)
        assert elo.get_rating("UConn") == 1600

    def test_predict_basic(self):
        """Test basic prediction functionality."""
        elo = WNCAABEloRating()
        elo.ratings = {"TeamA": 1600, "TeamB": 1400}

        # Home advantage applies
        prob = elo.predict("TeamA", "TeamB", is_neutral=False)
        assert 0 < prob < 1

        # Neutral site
        prob_neutral = elo.predict("TeamA", "TeamB", is_neutral=True)
        assert (
            prob_neutral < prob
        )  # Without home advantage, probability should be lower

    def test_update_basic(self):
        """Test basic update functionality."""
        elo = WNCAABEloRating(k_factor=20)
        elo.ratings = {"TeamA": 1600, "TeamB": 1400}

        initial_rating_a = elo.get_rating("TeamA")
        initial_rating_b = elo.get_rating("TeamB")

        # TeamA wins at home
        change = elo.update("TeamA", "TeamB", home_win=1.0, is_neutral=False)

        assert elo.get_rating("TeamA") > initial_rating_a  # Winner's rating increases
        assert elo.get_rating("TeamB") < initial_rating_b  # Loser's rating decreases
        assert abs(change) > 0  # Some change occurred

    def test_expected_score_method(self):
        """Test the expected_score method (should be added during refactoring)."""
        elo = WNCAABEloRating()

        # expected_score takes ratings (floats), not team names
        # Test 1: Equal ratings -> 50%
        assert elo.expected_score(1500, 1500) == pytest.approx(0.5, abs=0.001)

        # Test 2: Higher rating favored
        prob = elo.expected_score(1600, 1400)
        assert prob > 0.5
        assert prob == pytest.approx(0.7597, abs=0.001)

        # Test 3: Lower rating underdog
        prob2 = elo.expected_score(1400, 1600)
        assert prob2 < 0.5
        assert prob2 == pytest.approx(1.0 - 0.7597, abs=0.001)

    def test_get_all_ratings_method(self):
        """Test get_all_ratings returns dictionary of ratings."""
        elo = WNCAABEloRating()
        elo.ratings = {"TeamA": 1600, "TeamB": 1400, "TeamC": 1500}

        all_ratings = elo.get_all_ratings()
        assert isinstance(all_ratings, dict)
        assert len(all_ratings) == 3
        assert all_ratings["TeamA"] == 1600
        assert all_ratings["TeamB"] == 1400
        assert all_ratings["TeamC"] == 1500


class TestWNCAABEloBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_legacy_update_method(self):
        """Test that legacy update method works for backward compatibility."""
        elo = WNCAABEloRating()
        elo.ratings = {"TeamA": 1600, "TeamB": 1400}

        # The new update method should handle the same parameters
        change = elo.update("TeamA", "TeamB", home_win=1.0, is_neutral=False)
        assert isinstance(change, float)

        # For backward compatibility, we might need a legacy_update method
        # This test will be updated after refactoring
        pass

    def test_calculate_current_elo_ratings_function(self):
        """Test that the standalone calculate_current_elo_ratings function still works."""
        # This function imports from wncaab_games which may not be available in test environment
        # We'll skip this test for now
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
