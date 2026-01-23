"""
Simple test to verify NHLEloRating works after refactoring.
"""

import pytest
from plugins.elo import NHLEloRating, BaseEloRating


def test_nhl_elo_inherits_from_base():
    """Test that NHLEloRating inherits from BaseEloRating."""
    assert BaseEloRating in NHLEloRating.__bases__, \
        f"NHLEloRating does not inherit from BaseEloRating. Bases: {NHLEloRating.__bases__}"


def test_nhl_elo_can_be_instantiated():
    """Test that NHLEloRating can be instantiated."""
    elo = NHLEloRating()
    assert elo is not None
    assert elo.k_factor == 20.0  # Default value
    assert elo.home_advantage == 100.0  # Default value
    assert elo.initial_rating == 1500  # Default value

def test_nhl_elo_basic_functionality():
    """Test basic Elo functionality."""
    elo = NHLEloRating()

    # Test get_rating for new team
    assert elo.get_rating("New Team") == 1500.0

    # Test expected_score calculation
    assert abs(elo.expected_score(1500, 1500) - 0.5) < 0.001
    assert elo.expected_score(1600, 1400) > 0.5
    assert elo.expected_score(1400, 1600) < 0.5

    # Test predict
    prob = elo.predict("Team A", "Team B")
    assert 0 <= prob <= 1

    # Test update
    elo.update("Team A", "Team B", home_won=True)
    assert "Team A" in elo.ratings
    assert "Team B" in elo.ratings
    assert elo.ratings["Team A"] != 1500.0  # Should have changed
    assert elo.ratings["Team B"] != 1500.0  # Should have changed


def test_nhl_elo_method_signatures():
    """Test that NHLEloRating implements all required methods."""
    elo = NHLEloRating()

    # Check required methods exist
    required_methods = ['predict', 'update', 'get_rating', 'expected_score', 'get_all_ratings']
    for method_name in required_methods:
        assert hasattr(elo, method_name), f"Missing method: {method_name}"

    # Check method signatures (basic check)
    # predict should accept is_neutral parameter
    import inspect
    sig = inspect.signature(elo.predict)
    params = list(sig.parameters.keys())
    assert 'home_team' in params
    assert 'away_team' in params
    assert 'is_neutral' in params  # From BaseEloRating interface


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
