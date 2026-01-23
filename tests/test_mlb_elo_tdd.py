"""
TDD test for MLBEloRating refactoring to inherit from BaseEloRating.
"""

import pytest
import sys
from pathlib import Path

# Add plugins directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))

from elo import MLBEloRating, BaseEloRating


def test_mlb_elo_inheritance():
    """Test that MLBEloRating inherits from BaseEloRating (should pass after refactoring)."""
    assert BaseEloRating in MLBEloRating.__bases__, \
        f"MLBEloRating does not inherit from BaseEloRating. Bases: {MLBEloRating.__bases__}"


def test_mlb_elo_abstract_methods():
    """Test that MLBEloRating implements all required abstract methods."""
    # Create instance to check methods
    elo = MLBEloRating()

    # Check required methods exist
    required_methods = ['predict', 'update', 'get_rating', 'expected_score', 'get_all_ratings']
    for method_name in required_methods:
        assert hasattr(elo, method_name), f"Missing method: {method_name}"

    # Check method signatures
    import inspect

    # predict should accept is_neutral parameter
    sig = inspect.signature(elo.predict)
    params = list(sig.parameters.keys())
    assert 'home_team' in params
    assert 'away_team' in params
    assert 'is_neutral' in params or 'is_neutral' in str(sig), \
        f"predict method missing is_neutral parameter. Signature: {sig}"

    # update should accept is_neutral parameter
    sig = inspect.signature(elo.update)
    params = list(sig.parameters.keys())
    # BaseEloRating update signature: update(home_team, away_team, home_won, is_neutral=False)
    assert 'home_team' in params
    assert 'away_team' in params
    assert 'home_won' in params
    assert 'is_neutral' in params or 'is_neutral' in str(sig), \
        f"update method missing is_neutral parameter. Signature: {sig}"


def test_mlb_elo_backward_compatibility():
    """Test that MLBEloRating maintains backward compatibility."""
    elo = MLBEloRating(k_factor=20, home_advantage=50, initial_rating=1500)

    # Test default values
    assert elo.k_factor == 20
    assert elo.home_advantage == 50
    assert elo.initial_rating == 1500

    # Test basic functionality still works
    assert elo.get_rating("Yankees") == 1500
    prob = elo.predict("Yankees", "Red Sox")
    assert 0 <= prob <= 1

    # Test update with new interface (home_won boolean)
    elo.update("Yankees", "Red Sox", home_won=True)
    assert "Yankees" in elo.ratings
    assert "Red Sox" in elo.ratings

    # Test backward compatibility method update_with_scores
    elo2 = MLBEloRating()
    elo2.update_with_scores("Dodgers", "Giants", home_score=5, away_score=3)
    assert "Dodgers" in elo2.ratings
    assert "Giants" in elo2.ratings
    # Dodgers should have higher rating after win
    assert elo2.get_rating("Dodgers") > 1500
    assert elo2.get_rating("Giants") < 1500

    # Test legacy update_legacy method
    elo3 = MLBEloRating()
    elo3.update_legacy("Cubs", "Cardinals", home_score=2, away_score=4)
    assert "Cubs" in elo3.ratings
    assert "Cardinals" in elo3.ratings
    # Cubs lost, so should have lower rating
    assert elo3.get_rating("Cubs") < 1500
    assert elo3.get_rating("Cardinals") > 1500


def test_mlb_elo_expected_score():
    """Test expected_score method implementation."""
    elo = MLBEloRating()

    # Test equal ratings
    assert elo.expected_score(1500, 1500) == pytest.approx(0.5, abs=0.001)

    # Test rating difference
    prob = elo.expected_score(1600, 1400)
    assert prob > 0.5
    assert prob < 1.0

    # Test reverse
    prob2 = elo.expected_score(1400, 1600)
    assert prob2 < 0.5
    assert prob2 > 0.0


def test_mlb_elo_get_all_ratings():
    """Test get_all_ratings method."""
    elo = MLBEloRating()

    # Initially empty
    ratings = elo.get_all_ratings()
    assert isinstance(ratings, dict)
    assert len(ratings) == 0

    # After getting a rating
    elo.get_rating("Dodgers")
    ratings = elo.get_all_ratings()
    assert "Dodgers" in ratings
    assert ratings["Dodgers"] == 1500

    # After update
    elo.update("Dodgers", "Giants", home_won=True)
    ratings = elo.get_all_ratings()
    assert "Dodgers" in ratings
    assert "Giants" in ratings
    assert len(ratings) == 2


def test_mlb_elo_home_advantage():
    """Test home advantage application."""
    elo = MLBEloRating(home_advantage=50)

    # Test with home advantage
    prob_home = elo.predict("TeamA", "TeamB", is_neutral=False)

    # Test neutral site (no home advantage)
    prob_neutral = elo.predict("TeamA", "TeamB", is_neutral=True)

    # Home team should have higher probability at home
    assert prob_home > prob_neutral

    # With equal ratings and no home advantage, should be 50%
    assert prob_neutral == pytest.approx(0.5, abs=0.001)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
