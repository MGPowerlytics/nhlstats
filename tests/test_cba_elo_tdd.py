"""
TDD test for CBAEloRating - Chinese Basketball Association Elo ratings.

These tests define the expected behavior for the CBA Elo class before implementation.
Following TDD: Write tests first, then implement to make them pass.
"""

import pytest
import sys
from pathlib import Path

# Add plugins directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))


class TestCBAEloInheritance:
    """Test that CBAEloRating properly inherits from BaseEloRating."""

    def test_inherits_from_base(self):
        """Test that CBAEloRating inherits from BaseEloRating."""
        from elo import CBAEloRating, BaseEloRating

        assert issubclass(CBAEloRating, BaseEloRating), (
            f"CBAEloRating does not inherit from BaseEloRating. "
            f"Bases: {CBAEloRating.__bases__}"
        )

    def test_has_required_methods(self):
        """Test that CBAEloRating implements all required abstract methods."""
        from elo import CBAEloRating

        elo = CBAEloRating()

        required_methods = [
            "predict",
            "update",
            "get_rating",
            "expected_score",
            "get_all_ratings",
        ]
        for method_name in required_methods:
            assert hasattr(elo, method_name), f"Missing method: {method_name}"
            assert callable(getattr(elo, method_name)), (
                f"Method {method_name} is not callable"
            )


class TestCBAEloParameters:
    """Test CBA-specific Elo parameters."""

    def test_default_k_factor(self):
        """Test default k_factor is 20 (standard for basketball)."""
        from elo import CBAEloRating

        elo = CBAEloRating()
        assert elo.config.k_factor == 20.0, f"Expected k_factor=20.0, got {elo.config.k_factor}"

    def test_default_home_advantage(self):
        """Test default home_advantage is 80 (strong home advantage in CBA)."""
        from elo import CBAEloRating

        elo = CBAEloRating()
        assert elo.config.home_advantage == 80.0, (
            f"Expected home_advantage=80.0, got {elo.config.home_advantage}"
        )

    def test_default_initial_rating(self):
        """Test default initial_rating is 1500."""
        from elo import CBAEloRating

        elo = CBAEloRating()
        assert elo.config.initial_rating == 1500.0, (
            f"Expected initial_rating=1500.0, got {elo.config.initial_rating}"
        )

    def test_custom_parameters(self):
        """Test that custom parameters can be passed."""
        from elo import CBAEloRating

        elo = CBAEloRating(k_factor=25, home_advantage=100, initial_rating=1400)
        assert elo.config.k_factor == 25
        assert elo.config.home_advantage == 100
        assert elo.config.initial_rating == 1400


class TestCBAEloFunctionality:
    """Test CBA Elo rating functionality."""

    def test_get_rating_new_team(self):
        """Test that new teams get the initial rating."""
        from elo import CBAEloRating

        elo = CBAEloRating()
        rating = elo.get_rating("Guangdong Southern Tigers")
        assert rating == 1500.0

    def test_predict_returns_probability(self):
        """Test that predict returns a probability between 0 and 1."""
        from elo import CBAEloRating

        elo = CBAEloRating()
        prob = elo.predict("Guangdong Southern Tigers", "Beijing Ducks")
        assert 0.0 <= prob <= 1.0, f"Probability {prob} not in range [0, 1]"

    def test_predict_home_advantage(self):
        """Test that home team has advantage in prediction."""
        from elo import CBAEloRating

        elo = CBAEloRating()
        # With equal ratings, home team should have > 50% win probability
        prob = elo.predict("Guangdong Southern Tigers", "Beijing Ducks")
        assert prob > 0.5, f"Home team should have > 50% probability, got {prob}"

    def test_predict_neutral_site(self):
        """Test that neutral site removes home advantage."""
        from elo import CBAEloRating

        elo = CBAEloRating()
        # At neutral site, equal ratings should give ~50% probability
        prob = elo.predict(
            "Guangdong Southern Tigers", "Beijing Ducks", is_neutral=True
        )
        assert 0.49 <= prob <= 0.51, (
            f"Neutral site should give ~50% probability, got {prob}"
        )

    def test_update_adjusts_ratings(self):
        """Test that update adjusts team ratings appropriately."""
        from elo import CBAEloRating

        elo = CBAEloRating()
        initial_home = elo.get_rating("Guangdong Southern Tigers")
        initial_away = elo.get_rating("Beijing Ducks")

        # Home team wins
        elo.update("Guangdong Southern Tigers", "Beijing Ducks", home_won=True)

        new_home = elo.get_rating("Guangdong Southern Tigers")
        new_away = elo.get_rating("Beijing Ducks")

        # Winner's rating should increase, loser's should decrease
        assert new_home > initial_home, "Winner's rating should increase"
        assert new_away < initial_away, "Loser's rating should decrease"

    def test_update_same_team_raises_error(self):
        """Test that updating with same home and away team raises error."""
        from elo import CBAEloRating

        elo = CBAEloRating()
        with pytest.raises(ValueError):
            elo.update("Guangdong Southern Tigers", "Guangdong Southern Tigers", True)

    def test_get_all_ratings(self):
        """Test that get_all_ratings returns all team ratings."""
        from elo import CBAEloRating

        elo = CBAEloRating()
        elo.get_rating("Guangdong Southern Tigers")
        elo.get_rating("Beijing Ducks")
        elo.get_rating("Liaoning Flying Leopards")

        all_ratings = elo.get_all_ratings()
        assert isinstance(all_ratings, dict)
        assert len(all_ratings) == 3
        assert "Guangdong Southern Tigers" in all_ratings
        assert "Beijing Ducks" in all_ratings
        assert "Liaoning Flying Leopards" in all_ratings

    def test_expected_score(self):
        """Test expected score calculation."""
        from elo import CBAEloRating

        elo = CBAEloRating()
        # Equal ratings should give 0.5 expected score
        expected = elo.expected_score(1500, 1500)
        assert 0.49 <= expected <= 0.51

        # Higher rating should have higher expected score
        expected_higher = elo.expected_score(1600, 1400)
        assert expected_higher > 0.5


class TestCBAEloRegistration:
    """Test that CBA Elo is properly registered in the factory."""

    def test_registered_in_elo_class_registry(self):
        """Test that CBA is in the ELO_CLASS_REGISTRY."""
        from elo import ELO_CLASS_REGISTRY

        assert "cba" in ELO_CLASS_REGISTRY, (
            f"'cba' not found in ELO_CLASS_REGISTRY. "
            f"Available sports: {list(ELO_CLASS_REGISTRY.keys())}"
        )

    def test_get_elo_class_returns_cba(self):
        """Test that get_elo_class returns CBAEloRating for 'cba'."""
        from elo import get_elo_class, CBAEloRating

        cls = get_elo_class("cba")
        assert cls is CBAEloRating

    def test_create_elo_instance_works(self):
        """Test that create_elo_instance works for CBA."""
        from elo import create_elo_instance, CBAEloRating

        elo = create_elo_instance("cba")
        assert isinstance(elo, CBAEloRating)

    def test_create_elo_instance_with_params(self):
        """Test that create_elo_instance passes parameters correctly."""
        from elo import create_elo_instance

        elo = create_elo_instance("cba", k_factor=30, home_advantage=90)
        assert elo.config.k_factor == 30
        assert elo.config.home_advantage == 90


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
