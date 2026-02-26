"""
TDD Tests for UnrivaledEloRating.

Tests the Unrivaled (3x3 women's basketball) Elo rating implementation.
All tests follow TDD principles - written to verify the unified Elo interface
and Unrivaled-specific behavior.
"""

import pytest
from plugins.elo import BaseEloRating, UnrivaledEloRating


class TestUnrivaledEloInheritance:
    """Test that UnrivaledEloRating properly inherits from BaseEloRating."""

    def test_inherits_from_base(self):
        """UnrivaledEloRating should inherit from BaseEloRating."""
        assert issubclass(UnrivaledEloRating, BaseEloRating)

    def test_can_be_instantiated(self):
        """UnrivaledEloRating can be instantiated without arguments."""
        elo = UnrivaledEloRating()
        assert isinstance(elo, BaseEloRating)

    def test_has_required_methods(self):
        """UnrivaledEloRating has all required abstract methods."""
        elo = UnrivaledEloRating()
        required_methods = [
            "predict",
            "update",
            "get_rating",
            "expected_score",
            "get_all_ratings",
        ]
        for method in required_methods:
            assert hasattr(elo, method), f"Missing method: {method}"
            assert callable(getattr(elo, method)), f"Method not callable: {method}"


class TestUnrivaledEloParameters:
    """Test Unrivaled-specific Elo parameters."""

    def test_default_k_factor(self):
        """Default K-factor should be 24 (higher for 3x3 variance)."""
        elo = UnrivaledEloRating()
        assert elo.k_factor == 24.0

    def test_default_home_advantage_is_zero(self):
        """Home advantage should be 0 (all games at same venue)."""
        elo = UnrivaledEloRating()
        assert elo.home_advantage == 0.0

    def test_default_initial_rating(self):
        """Initial rating should be 1500."""
        elo = UnrivaledEloRating()
        assert elo.initial_rating == 1500.0

    def test_custom_parameters(self):
        """Custom parameters should be accepted."""
        elo = UnrivaledEloRating(k_factor=32, home_advantage=0, initial_rating=1600)
        assert elo.k_factor == 32.0
        assert elo.home_advantage == 0.0
        assert elo.initial_rating == 1600.0


class TestUnrivaledEloFunctionality:
    """Test UnrivaledEloRating functionality."""

    def test_get_rating_new_team(self):
        """Get rating for a new team returns initial rating."""
        elo = UnrivaledEloRating()
        rating = elo.get_rating("Rose BC")
        assert rating == 1500.0

    def test_get_rating_returns_float(self):
        """get_rating returns a float."""
        elo = UnrivaledEloRating()
        rating = elo.get_rating("Lunar Owls BC")
        assert isinstance(rating, float)

    def test_predict_returns_probability(self):
        """predict returns a probability between 0 and 1."""
        elo = UnrivaledEloRating()
        prob = elo.predict("Rose BC", "Lunar Owls BC")
        assert isinstance(prob, float)
        assert 0.0 <= prob <= 1.0

    def test_predict_equal_teams(self):
        """Equal teams should have ~50% probability."""
        elo = UnrivaledEloRating()
        prob = elo.predict("Rose BC", "Lunar Owls BC")
        assert abs(prob - 0.5) < 0.01  # Should be very close to 50%

    def test_predict_higher_rated_favored(self):
        """Higher rated team should be favored."""
        elo = UnrivaledEloRating()
        elo.ratings["Rose BC"] = 1600
        elo.ratings["Lunar Owls BC"] = 1400
        prob = elo.predict("Rose BC", "Lunar Owls BC")
        assert prob > 0.5

    def test_predict_neutral_site(self):
        """Neutral site flag should not change prediction (home_advantage=0)."""
        elo = UnrivaledEloRating()
        elo.ratings["Rose BC"] = 1600
        elo.ratings["Lunar Owls BC"] = 1400

        prob_normal = elo.predict("Rose BC", "Lunar Owls BC", is_neutral=False)
        prob_neutral = elo.predict("Rose BC", "Lunar Owls BC", is_neutral=True)

        # With home_advantage=0, these should be equal
        assert abs(prob_normal - prob_neutral) < 0.001

    def test_expected_score_returns_probability(self):
        """expected_score returns a probability between 0 and 1."""
        elo = UnrivaledEloRating()
        expected = elo.expected_score(1600.0, 1400.0)
        assert isinstance(expected, float)
        assert 0.0 <= expected <= 1.0

    def test_expected_score_higher_rating_favored(self):
        """Higher rating should give higher expected score."""
        elo = UnrivaledEloRating()
        expected = elo.expected_score(1600.0, 1400.0)
        assert expected > 0.5

    def test_expected_score_equal_ratings(self):
        """Equal ratings should give 50% expected score."""
        elo = UnrivaledEloRating()
        expected = elo.expected_score(1500.0, 1500.0)
        assert expected == 0.5


class TestUnrivaledEloUpdate:
    """Test rating updates after games."""

    def test_update_adjusts_ratings(self):
        """Update should adjust ratings after a game."""
        elo = UnrivaledEloRating()
        initial_home = elo.get_rating("Rose BC")
        initial_away = elo.get_rating("Lunar Owls BC")

        elo.update("Rose BC", "Lunar Owls BC", home_won=True, is_neutral=True)

        # Winner should gain rating
        assert elo.get_rating("Rose BC") > initial_home
        # Loser should lose rating
        assert elo.get_rating("Lunar Owls BC") < initial_away

    def test_update_home_win_increases_home_rating(self):
        """Home win should increase home team rating."""
        elo = UnrivaledEloRating()
        initial = elo.get_rating("Rose BC")

        elo.update("Rose BC", "Lunar Owls BC", home_won=True)

        assert elo.get_rating("Rose BC") > initial

    def test_update_home_loss_decreases_home_rating(self):
        """Home loss should decrease home team rating."""
        elo = UnrivaledEloRating()
        initial = elo.get_rating("Rose BC")

        elo.update("Rose BC", "Lunar Owls BC", home_won=False)

        assert elo.get_rating("Rose BC") < initial

    def test_update_returns_change(self):
        """Update should return the rating change."""
        elo = UnrivaledEloRating()
        change = elo.update("Rose BC", "Lunar Owls BC", home_won=True)

        assert isinstance(change, float)
        assert change > 0  # Winner gain should be positive

    def test_update_with_home_win_alias(self):
        """Update should accept home_win as alias for home_won."""
        elo = UnrivaledEloRating()
        initial = elo.get_rating("Rose BC")

        elo.update("Rose BC", "Lunar Owls BC", home_win=True)

        assert elo.get_rating("Rose BC") > initial

    def test_update_requires_result(self):
        """Update should raise error if no result provided."""
        elo = UnrivaledEloRating()
        with pytest.raises(ValueError):
            elo.update("Rose BC", "Lunar Owls BC")


class TestUnrivaledEloGetAllRatings:
    """Test get_all_ratings method."""

    def test_get_all_ratings_returns_dict(self):
        """get_all_ratings returns a dictionary."""
        elo = UnrivaledEloRating()
        ratings = elo.get_all_ratings()
        assert isinstance(ratings, dict)

    def test_get_all_ratings_empty_initially(self):
        """Initially no ratings exist."""
        elo = UnrivaledEloRating()
        ratings = elo.get_all_ratings()
        assert len(ratings) == 0

    def test_get_all_ratings_after_games(self):
        """Ratings should be populated after games."""
        elo = UnrivaledEloRating()
        elo.update("Rose BC", "Lunar Owls BC", home_won=True)

        ratings = elo.get_all_ratings()
        assert "Rose BC" in ratings
        assert "Lunar Owls BC" in ratings

    def test_get_all_ratings_returns_copy(self):
        """get_all_ratings should return a copy, not the internal dict."""
        elo = UnrivaledEloRating()
        elo.update("Rose BC", "Lunar Owls BC", home_won=True)

        ratings = elo.get_all_ratings()
        ratings["Rose BC"] = 9999  # Modify returned dict

        # Internal rating should not change
        assert elo.ratings["Rose BC"] != 9999


class TestUnrivaledEloLegacySupport:
    """Test backward compatibility methods."""

    def test_has_legacy_update(self):
        """Should have legacy_update method for backward compatibility."""
        elo = UnrivaledEloRating()
        assert hasattr(elo, "legacy_update")
        assert callable(elo.legacy_update)

    def test_legacy_update_works(self):
        """legacy_update should work the same as update."""
        elo = UnrivaledEloRating()
        initial = elo.get_rating("Rose BC")

        elo.legacy_update("Rose BC", "Lunar Owls BC", home_won=True, is_neutral=True)

        assert elo.get_rating("Rose BC") > initial


class TestUnrivaledEloNeutralSite:
    """Test neutral site handling (critical for Unrivaled)."""

    def test_all_games_effectively_neutral(self):
        """With home_advantage=0, all games should be effectively neutral."""
        elo = UnrivaledEloRating()
        elo.ratings["Rose BC"] = 1550
        elo.ratings["Lunar Owls BC"] = 1450

        # Run two updates - one with neutral=True, one with neutral=False
        elo1 = UnrivaledEloRating()
        elo1.ratings["Rose BC"] = 1550
        elo1.ratings["Lunar Owls BC"] = 1450
        elo1.update("Rose BC", "Lunar Owls BC", home_won=True, is_neutral=True)

        elo2 = UnrivaledEloRating()
        elo2.ratings["Rose BC"] = 1550
        elo2.ratings["Lunar Owls BC"] = 1450
        elo2.update("Rose BC", "Lunar Owls BC", home_won=True, is_neutral=False)

        # Results should be identical when home_advantage=0
        assert elo1.ratings["Rose BC"] == elo2.ratings["Rose BC"]
        assert elo1.ratings["Lunar Owls BC"] == elo2.ratings["Lunar Owls BC"]


class TestUnrivaledEloRegistry:
    """Test that Unrivaled is properly registered in the Elo factory."""

    def test_in_elo_class_registry(self):
        """UnrivaledEloRating should be in ELO_CLASS_REGISTRY."""
        from plugins.elo import ELO_CLASS_REGISTRY

        assert "unrivaled" in ELO_CLASS_REGISTRY
        assert ELO_CLASS_REGISTRY["unrivaled"] == UnrivaledEloRating

    def test_get_elo_class_returns_unrivaled(self):
        """get_elo_class('unrivaled') should return UnrivaledEloRating."""
        from plugins.elo import get_elo_class

        elo_class = get_elo_class("unrivaled")
        assert elo_class == UnrivaledEloRating

    def test_create_elo_instance(self):
        """create_elo_instance('unrivaled') should work."""
        from plugins.elo import create_elo_instance

        elo = create_elo_instance("unrivaled", k_factor=28)
        assert isinstance(elo, UnrivaledEloRating)
        assert elo.k_factor == 28


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
