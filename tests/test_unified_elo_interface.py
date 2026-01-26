"""
Test unified Elo interface implementation.
Verifies all sport-specific Elo classes properly inherit from BaseEloRating.
"""

import pytest
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

# List of all sport Elo classes to test
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


def test_all_classes_inherit_from_base():
    """Verify all sport Elo classes inherit from BaseEloRating."""
    for elo_class in ELO_CLASSES:
        assert issubclass(elo_class, BaseEloRating), (
            f"{elo_class.__name__} does not inherit from BaseEloRating"
        )


def test_all_classes_have_required_methods():
    """Verify all sport Elo classes implement required abstract methods."""
    required_methods = {
        "predict",
        "update",
        "get_rating",
        "expected_score",
        "get_all_ratings",
    }

    for elo_class in ELO_CLASSES:
        instance = elo_class()
        for method_name in required_methods:
            assert hasattr(instance, method_name), (
                f"{elo_class.__name__} missing {method_name}"
            )
            method = getattr(instance, method_name)
            assert callable(method), (
                f"{elo_class.__name__}.{method_name} is not callable"
            )


def test_predict_method_signature():
    """Verify predict method has correct signature."""
    # Test with NBA as example
    nba_elo = NBAEloRating()
    # Should accept home_team, away_team, is_neutral=False
    result = nba_elo.predict("Lakers", "Celtics")
    assert isinstance(result, float), "predict should return float"
    assert 0 <= result <= 1, "predict should return probability between 0 and 1"


def test_update_method_signature():
    """Verify update method has correct signature."""
    nba_elo = NBAEloRating()
    # Should accept home_team, away_team, home_won, is_neutral=False
    # This should not raise TypeError
    nba_elo.update("Lakers", "Celtics", True)


def test_get_rating_method():
    """Verify get_rating method works."""
    nba_elo = NBAEloRating()
    rating = nba_elo.get_rating("Lakers")
    # Initial rating should be 1500.0 or whatever default
    assert isinstance(rating, float), "get_rating should return float"


def test_expected_score_method():
    """Verify expected_score method works."""
    nba_elo = NBAEloRating()
    expected = nba_elo.expected_score(1600.0, 1400.0)
    assert isinstance(expected, float), "expected_score should return float"
    assert 0 <= expected <= 1, "expected_score should return probability"


def test_get_all_ratings_method():
    """Verify get_all_ratings method works."""
    nba_elo = NBAEloRating()
    ratings = nba_elo.get_all_ratings()
    assert isinstance(ratings, dict), "get_all_ratings should return dict"


def test_sport_specific_parameters():
    """Verify sport-specific parameters are set correctly."""
    # Test NHL has recency_weight parameter
    nhl_elo = NHLEloRating(recency_weight=0.5)
    assert hasattr(nhl_elo, "recency_weight")

    # Test soccer classes (EPL, Ligue1) have draw probability support
    epl_elo = EPLEloRating()
    # EPLEloRating should have methods for 3-way outcomes
    assert hasattr(epl_elo, "predict_3way") or "draw" in dir(epl_elo)


def test_backward_compatibility():
    """Verify backward compatibility methods exist where needed."""
    # Check for legacy_update methods
    nba_elo = NBAEloRating()
    if hasattr(nba_elo, "legacy_update"):
        # Should be callable
        assert callable(nba_elo.legacy_update)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
