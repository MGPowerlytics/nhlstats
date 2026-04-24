"""
Test suite for EPLEloRating using TDD approach.
Tests the refactored EPLEloRating that inherits from BaseEloRating.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.elo import BaseEloRating, EPLEloRating


class TestEPLEloRatingTDD:
    """Test EPLEloRating refactoring using TDD."""

    def test_epl_elo_inherits_from_base(self):
        """Test that EPLEloRating inherits from BaseEloRating."""
        assert issubclass(EPLEloRating, BaseEloRating), (
            "EPLEloRating must inherit from BaseEloRating"
        )

    def test_epl_elo_has_required_methods(self):
        """Test that EPLEloRating implements all abstract methods."""
        elo = EPLEloRating()

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

    def test_epl_elo_backward_compatibility(self):
        """Test backward compatibility with existing functionality."""
        elo = EPLEloRating(k_factor=20, home_advantage=60, initial_rating=1500)

        # Test basic rating functionality
        assert elo.get_rating("Man City") == 1500
        assert elo.get_rating("Liverpool") == 1500

        # Test prediction (should return home win probability)
        prob = elo.predict("Man City", "Liverpool")
        assert 0 <= prob <= 1

        # Test 3-way prediction (soccer-specific method should still work)
        if hasattr(elo, "predict_3way"):
            probs = elo.predict_3way("Man City", "Liverpool")
            assert "home" in probs
            assert "draw" in probs
            assert "away" in probs
            assert abs(sum(probs.values()) - 1.0) < 0.001

    def test_epl_elo_update_functionality(self):
        """Test update functionality with new interface."""
        elo = EPLEloRating(k_factor=20, home_advantage=60, initial_rating=1500)

        # Initial ratings
        initial_home = elo.get_rating("Man City")
        initial_away = elo.get_rating("Liverpool")

        # Update with home win (True)
        elo.update("Man City", "Liverpool", home_won=True)

        # Check ratings changed
        new_home = elo.get_rating("Man City")
        new_away = elo.get_rating("Liverpool")

        assert new_home > initial_home  # Winner should gain points
        assert new_away < initial_away  # Loser should lose points

        # Test with score margin
        elo2 = EPLEloRating(k_factor=20, home_advantage=60, initial_rating=1500)
        elo2.update("Man City", "Liverpool", home_won=2.0)  # 2-goal margin

    def test_epl_elo_get_all_ratings(self):
        """Test get_all_ratings method."""
        elo = EPLEloRating(k_factor=20, home_advantage=60, initial_rating=1500)

        # Add some ratings
        elo.update("Man City", "Liverpool", home_won=True)
        elo.update("Chelsea", "Arsenal", home_won=False)

        all_ratings = elo.get_all_ratings()

        assert isinstance(all_ratings, dict)
        assert "Man City" in all_ratings
        assert "Liverpool" in all_ratings
        assert "Chelsea" in all_ratings
        assert "Arsenal" in all_ratings
        assert len(all_ratings) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
