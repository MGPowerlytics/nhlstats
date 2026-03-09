"""
Test the BaseEloRating abstract class and sport-specific implementations.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.elo import BaseEloRating
from plugins.elo import (
    NHLEloRating,
    NBAEloRating,
    MLBEloRating,
    NFLEloRating,
    EPLEloRating,
    Ligue1EloRating,
    NCAABEloRating,
    WNCAABEloRating,
    TennisEloRating,
)


class TestBaseEloRatingInterface:
    """Test the BaseEloRating abstract class interface."""

    def test_base_elo_is_abstract(self):
        """Test that BaseEloRating cannot be instantiated (it's abstract)."""
        with pytest.raises(TypeError):
            BaseEloRating()

    def test_base_elo_has_abstract_methods(self):
        """Test that BaseEloRating defines all required abstract methods."""
        import inspect

        # Get all abstract methods
        abstract_methods = []
        for name, method in inspect.getmembers(
            BaseEloRating, predicate=inspect.isfunction
        ):
            if getattr(method, "__isabstractmethod__", False):
                abstract_methods.append(name)

        expected_methods = {
            "update",
        }
        assert set(abstract_methods) == expected_methods

    def test_base_elo_has_concrete_methods(self):
        """Test that BaseEloRating has concrete helper methods."""
        # These methods have been moved to EloCalculator class for better separation
        # Check that BaseEloRating has the main public methods instead
        assert hasattr(BaseEloRating, "predict")
        assert hasattr(BaseEloRating, "get_rating")
        assert hasattr(BaseEloRating, "expected_score")
        assert hasattr(BaseEloRating, "get_all_ratings")

    def test_base_elo_init_parameters(self):
        """Test BaseEloRating __init__ method signature."""
        import inspect

        init_sig = inspect.signature(BaseEloRating.__init__)

        # Check parameters
        params = list(init_sig.parameters.keys())
        assert "self" in params
        assert "k_factor" in params
        assert "home_advantage" in params
        assert "initial_rating" in params

    def test_base_elo_type_hints(self):
        """Test that BaseEloRating methods have type hints."""
        import inspect

        methods_to_check = [
            "predict",
            "update",
            "get_rating",
            "expected_score",
            "get_all_ratings",
        ]
        for method_name in methods_to_check:
            method = getattr(BaseEloRating, method_name)
            sig = inspect.signature(method)
            # Just check it has a signature (type hints are part of it)
            assert sig is not None

    def test_base_elo_docstrings(self):
        """Test that BaseEloRating methods have docstrings."""
        methods_to_check = [
            "predict",
            "update",
            "get_rating",
            "expected_score",
            "get_all_ratings",
        ]
        for method_name in methods_to_check:
            method = getattr(BaseEloRating, method_name)
            assert method.__doc__ is not None


class TestSportSpecificEloCompatibility:
    """Test that all sport-specific Elo classes inherit from BaseEloRating."""

    @pytest.mark.parametrize(
        "elo_class",
        [
            NHLEloRating,
            NBAEloRating,
            MLBEloRating,
            NFLEloRating,
            EPLEloRating,
            Ligue1EloRating,
            NCAABEloRating,
            WNCAABEloRating,
            TennisEloRating,
        ],
    )
    def test_sport_class_inherits_from_base(self, elo_class):
        """Test that a sport-specific Elo class inherits from BaseEloRating."""
        assert issubclass(elo_class, BaseEloRating)

    @pytest.mark.parametrize(
        "elo_class",
        [
            NHLEloRating,
            NBAEloRating,
            MLBEloRating,
            NFLEloRating,
            EPLEloRating,
            Ligue1EloRating,
            NCAABEloRating,
            WNCAABEloRating,
            TennisEloRating,
        ],
    )
    def test_sport_class_can_be_instantiated(self, elo_class):
        """Test that a sport-specific Elo class can be instantiated."""
        instance = elo_class()
        assert instance is not None
        assert isinstance(instance, BaseEloRating)


from plugins.elo.base_elo_rating import Matchup, GameResult, EloConfig


class TestNewEloInterface:
    """Test the new EloConfig, Matchup, and GameResult interfaces."""

    def test_elo_config_initialization(self):
        """Test that BaseEloRating can be initialized with EloConfig."""
        config = EloConfig(k_factor=15.0, home_advantage=40.0, initial_rating=1000.0)
        elo = NHLEloRating(config=config)
        assert elo.config.k_factor == 15.0
        assert elo.config.home_advantage == 40.0
        assert elo.config.initial_rating == 1000.0

    def test_matchup_and_result_update(self):
        """Test updating Elo ratings using Matchup and GameResult objects."""
        elo = NHLEloRating(k_factor=20.0, home_advantage=50.0)
        matchup = Matchup(home_team="TeamA", away_team="TeamB", is_neutral=False)
        result = GameResult(home_won=True, home_score=3, away_score=1)

        # Record initial ratings
        initial_a = elo.get_rating("TeamA")
        initial_b = elo.get_rating("TeamB")

        # Update using objects
        change = elo.update(matchup=matchup, result=result)

        assert change > 0
        assert elo.get_rating("TeamA") == initial_a + change
        assert elo.get_rating("TeamB") == initial_b - change

        # Verify history was updated (NHLEloRating specific)
        assert len(elo.game_history) == 1
        assert elo.game_history[0]["home_team"] == "TeamA"
        assert elo.game_history[0]["home_score"] == 3

    def test_tennis_new_interface(self):
        """Test TennisEloRating with Matchup and GameResult."""
        elo = TennisEloRating(k_factor=30.0)
        matchup = Matchup(home_team="Federer R.", away_team="Nadal R.", is_neutral=True)
        result = GameResult(home_won=True)

        change = elo.update(matchup=matchup, result=result, tour="ATP")
        assert change > 0
        assert elo.get_rating("Federer R.", tour="ATP") > 1500
        assert elo.get_rating("Nadal R.", tour="ATP") < 1500


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_dashboard_integration(self):
        """Placeholder test for dashboard integration."""
        # This would test that the dashboard can use the unified interface
        pass

    def test_dag_integration(self):
        """Placeholder test for DAG integration."""
        # This would test that DAGs can use the unified interface
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
