"""
Simple test for NBAEloRating before refactoring.
"""

import sys
from pathlib import Path

# Add plugins directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from elo import NBAEloRating


def test_nba_elo_current_state():
    """Test current NBAEloRating functionality."""
    # This test will help us understand the current interface
    elo = NBAEloRating()

    # Check basic attributes
    assert hasattr(elo, "k_factor")
    assert hasattr(elo, "home_advantage")
    assert hasattr(elo, "initial_rating")
    assert hasattr(elo, "ratings")

    # Check methods
    assert hasattr(elo, "predict")
    assert hasattr(elo, "update")
    assert hasattr(elo, "get_rating")
    assert hasattr(elo, "expected_score")

    # Test basic functionality
    rating = elo.get_rating("Test Team")
    assert rating == elo.initial_rating

    # Test prediction
    prob = elo.predict("Team A", "Team B")
    assert 0 <= prob <= 1

    print("✓ NBAEloRating current interface check passed")
    return True


if __name__ == "__main__":
    test_nba_elo_current_state()
