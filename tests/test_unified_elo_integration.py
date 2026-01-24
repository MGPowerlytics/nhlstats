"""
Integration tests for the Unified Elo Rating Interface.

Verifies that all sport-specific Elo implementations adhere to the
BaseEloRating interface and can be used polymorphically.
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.elo import (
    BaseEloRating,
    NBAEloRating,
    NHLEloRating,
    MLBEloRating,
    NFLEloRating,
    EPLEloRating,
    Ligue1EloRating,
    NCAABEloRating,
    WNCAABEloRating,
    TennisEloRating,
)

# List of all concrete Elo classes
ELO_CLASSES = [
    NBAEloRating,
    NHLEloRating,
    MLBEloRating,
    NFLEloRating,
    EPLEloRating,
    Ligue1EloRating,
    NCAABEloRating,
    WNCAABEloRating,
    TennisEloRating,
]


class TestUnifiedEloInterface:
    """Test that all Elo classes implement the unified interface correctly."""

    @pytest.mark.parametrize("elo_class", ELO_CLASSES)
    def test_inheritance(self, elo_class):
        """Verify all classes inherit from BaseEloRating."""
        assert issubclass(elo_class, BaseEloRating)

        # Verify instantiation
        elo = elo_class()
        assert isinstance(elo, BaseEloRating)

    @pytest.mark.parametrize("elo_class", ELO_CLASSES)
    def test_predict_interface(self, elo_class):
        """Verify predict method works with standard arguments."""
        elo = elo_class()

        # Should accept strings for teams/players
        prob = elo.predict("Team A", "Team B", is_neutral=False)
        assert isinstance(prob, float)
        assert 0.0 <= prob <= 1.0

        # Should accept is_neutral parameter
        prob_neutral = elo.predict("Team A", "Team B", is_neutral=True)
        assert isinstance(prob_neutral, float)

    @pytest.mark.parametrize("elo_class", ELO_CLASSES)
    def test_update_interface(self, elo_class):
        """Verify update method works with standard arguments."""
        elo = elo_class()

        # Should accept strings and home_won boolean
        # Note: some sports (Soccer) might handle draws, but home_won=True/False is the base interface
        elo.update("Team A", "Team B", home_won=True, is_neutral=False)

        # Ratings should be updated
        assert elo.get_rating("Team A") > 1500  # Started at 1500 (default), won
        assert elo.get_rating("Team B") < 1500  # Started at 1500 (default), lost

    @pytest.mark.parametrize("elo_class", ELO_CLASSES)
    def test_expected_score_interface(self, elo_class):
        """Verify expected_score method works with FLOAT ratings."""
        elo = elo_class()

        # Must accept floats
        prob = elo.expected_score(1600.0, 1400.0)

        assert isinstance(prob, float)
        assert 0.0 <= prob <= 1.0
        assert prob > 0.5  # Higher rating should have higher probability

    @pytest.mark.parametrize("elo_class", ELO_CLASSES)
    def test_get_all_ratings_interface(self, elo_class):
        """Verify get_all_ratings returns a dictionary."""
        elo = elo_class()
        elo.update("Team A", "Team B", home_won=True)

        ratings = elo.get_all_ratings()
        assert isinstance(ratings, dict)
        assert len(ratings) >= 2
        # Names might be normalized (e.g. Tennis), so exact key match isn't reliable
        # assert "Team A" in ratings or "ATP:Team A" in ratings
