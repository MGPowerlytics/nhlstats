"""
TDD test for NBAEloRating refactoring to inherit from BaseEloRating.
"""

import pytest
import sys
from pathlib import Path

# Add plugins directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))

from elo import NBAEloRating, BaseEloRating


def test_nba_elo_inheritance():
    """Test that NBAEloRating inherits from BaseEloRating (will fail initially)."""
    # This test should fail before refactoring, pass after
    assert BaseEloRating in NBAEloRating.__bases__, \
        f"NBAEloRating does not inherit from BaseEloRating. Bases: {NBAEloRating.__bases__}"


def test_nba_elo_abstract_methods():
    """Test that NBAEloRating implements all required abstract methods."""
    # Create instance to check methods
    elo = NBAEloRating()

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
    update_params = ['home_team', 'away_team', 'home_won']
    for param in update_params:
        assert param in params or param in str(sig), \
            f"update method missing {param} parameter. Signature: {sig}"


def test_nba_elo_backward_compatibility():
    """Test that NBAEloRating maintains backward compatibility."""
    elo = NBAEloRating(k_factor=25, home_advantage=75, initial_rating=1400)

    # Test default values
    assert elo.k_factor == 25
    assert elo.home_advantage == 75
    assert elo.initial_rating == 1400

    # Test basic functionality still works
    assert elo.get_rating("Lakers") == 1400
    prob = elo.predict("Lakers", "Celtics")
    assert 0 <= prob <= 1

    # Test update
    elo.update("Lakers", "Celtics", home_won=True)
    assert "Lakers" in elo.ratings
    assert "Celtics" in elo.ratings


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
