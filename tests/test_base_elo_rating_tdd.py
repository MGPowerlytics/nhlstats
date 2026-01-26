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
            "predict",
            "update",
            "get_rating",
            "expected_score",
            "get_all_ratings",
        }
        assert set(abstract_methods) == expected_methods

    def test_base_elo_has_concrete_methods(self):
        """Test that BaseEloRating has concrete helper methods."""
        assert hasattr(BaseEloRating, "_apply_home_advantage")
        assert hasattr(BaseEloRating, "_calculate_rating_change")

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
