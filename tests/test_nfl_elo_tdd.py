"""
TDD test for NFLEloRating refactoring to inherit from BaseEloRating.
"""

import pytest
import sys
from pathlib import Path

# Add plugins directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))

from elo import NFLEloRating, BaseEloRating


def test_nfl_elo_inheritance():
    """Test that NFLEloRating inherits from BaseEloRating (will fail initially)."""
    # This test should fail before refactoring, pass after
    assert BaseEloRating in NFLEloRating.__bases__, \
        f"NFLEloRating does not inherit from BaseEloRating. Bases: {NFLEloRating.__bases__}"


def test_nfl_elo_abstract_methods():
    """Test that NFLEloRating implements all required abstract methods."""
    # Create instance to check methods
    elo = NFLEloRating()

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


def test_nfl_elo_backward_compatibility():
    """Test that NFLEloRating maintains backward compatibility."""
    elo = NFLEloRating(k_factor=20, home_advantage=65, initial_rating=1500)

    # Test default values
    assert elo.k_factor == 20
    assert elo.home_advantage == 65
    assert elo.initial_rating == 1500

    # Test basic functionality still works
    assert elo.get_rating("Chiefs") == 1500
    prob = elo.predict("Chiefs", "Bills")
    assert 0 <= prob <= 1

    # Test update with new interface (home_won boolean)
    elo.update("Chiefs", "Bills", home_won=True)
    assert "Chiefs" in elo.ratings
    assert "Bills" in elo.ratings

    # Test backward compatibility method update_with_scores
    elo2 = NFLEloRating()
    elo2.update_with_scores("Chiefs", "Bills", home_score=31, away_score=24)
    assert "Chiefs" in elo2.ratings
    assert "Bills" in elo2.ratings
    # Chiefs should have higher rating after win
    assert elo2.get_rating("Chiefs") > 1500
    assert elo2.get_rating("Bills") < 1500

    # Test legacy update_legacy method
    elo3 = NFLEloRating()
    elo3.update_legacy("Chiefs", "Bills", home_score=17, away_score=28)
    assert "Chiefs" in elo3.ratings
    assert "Bills" in elo3.ratings
    # Chiefs lost, so should have lower rating
    assert elo3.get_rating("Chiefs") < 1500
    assert elo3.get_rating("Bills") > 1500


def test_nfl_elo_expected_score():
    """Test expected_score method implementation."""
    elo = NFLEloRating()

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


def test_nfl_elo_get_all_ratings():
    """Test get_all_ratings method."""
    elo = NFLEloRating()

    # Initially empty
    ratings = elo.get_all_ratings()
    assert isinstance(ratings, dict)
    assert len(ratings) == 0

    # After getting a rating
    elo.get_rating("Chiefs")
    ratings = elo.get_all_ratings()
    assert "Chiefs" in ratings
    assert ratings["Chiefs"] == 1500

    # After update
    elo.update("Chiefs", "Bills", home_won=True)
    ratings = elo.get_all_ratings()
    assert "Chiefs" in ratings
    assert "Bills" in ratings
    assert len(ratings) == 2


def test_nfl_elo_home_advantage():
    """Test home advantage application."""
    elo = NFLEloRating(home_advantage=65)

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
