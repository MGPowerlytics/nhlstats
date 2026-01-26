"""
Test suite for Ligue1EloRating using TDD approach.
Tests the refactored Ligue1EloRating that inherits from BaseEloRating.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.elo import BaseEloRating, Ligue1EloRating


class TestLigue1EloRatingTDD:
    """Test Ligue1EloRating refactoring using TDD."""

    def test_ligue1_elo_inherits_from_base(self):
        """Test that Ligue1EloRating inherits from BaseEloRating."""
        assert issubclass(Ligue1EloRating, BaseEloRating), (
            "Ligue1EloRating must inherit from BaseEloRating"
        )

    def test_ligue1_elo_has_required_methods(self):
        """Test that Ligue1EloRating implements all abstract methods."""
        elo = Ligue1EloRating()

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

    def test_ligue1_elo_backward_compatibility(self):
        """Test backward compatibility with existing functionality."""
        elo = Ligue1EloRating(k_factor=20, home_advantage=60, initial_rating=1500)

        # Test basic rating functionality
        assert elo.get_rating("PSG") == 1500
        assert elo.get_rating("Marseille") == 1500

        # Test prediction (should return home win probability)
        prob = elo.predict("PSG", "Marseille")
        assert 0 <= prob <= 1

        # Test 3-way prediction (soccer-specific method should still work)
        if hasattr(elo, "predict_3way"):
            probs = elo.predict_3way("PSG", "Marseille")
            assert "home" in probs
            assert "draw" in probs
            assert "away" in probs
            assert abs(sum(probs.values()) - 1.0) < 0.001

    def test_ligue1_elo_update_functionality(self):
        """Test update functionality with new interface."""
        elo = Ligue1EloRating(k_factor=20, home_advantage=60, initial_rating=1500)

        # Initial ratings
        initial_home = elo.get_rating("PSG")
        initial_away = elo.get_rating("Marseille")

        # Update with home win (True)
        elo.update("PSG", "Marseille", home_won=True)

        # Check ratings changed
        new_home = elo.get_rating("PSG")
        new_away = elo.get_rating("Marseille")

        assert new_home > initial_home  # Winner should gain points
        assert new_away < initial_away  # Loser should lose points

        # Test with score margin
        elo2 = Ligue1EloRating(k_factor=20, home_advantage=60, initial_rating=1500)
        elo2.update("PSG", "Marseille", home_won=2.0)  # 2-goal margin

    def test_ligue1_elo_get_all_ratings(self):
        """Test get_all_ratings method."""
        elo = Ligue1EloRating(k_factor=20, home_advantage=60, initial_rating=1500)

        # Add some ratings
        elo.update("PSG", "Marseille", home_won=True)
        elo.update("Lyon", "Monaco", home_won=False)

        all_ratings = elo.get_all_ratings()

        assert isinstance(all_ratings, dict)
        assert "PSG" in all_ratings
        assert "Marseille" in all_ratings
        assert "Lyon" in all_ratings
        assert "Monaco" in all_ratings
        assert len(all_ratings) == 4

    def test_ligue1_elo_expected_score(self):
        """Test expected_score method (already exists in Ligue1EloRating)."""
        elo = Ligue1EloRating()

        # Test expected score calculation
        # Equal ratings should give 0.5
        assert abs(elo.expected_score(1500, 1500) - 0.5) < 0.001

        # Home advantage included in predict, not expected_score
        # 200 point difference should give ~0.76
        expected = 1 / (1 + 10 ** ((1500 - 1700) / 400))
        assert abs(elo.expected_score(1700, 1500) - expected) < 0.001


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
