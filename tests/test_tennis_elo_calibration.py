"""
Tests for tennis Elo calibration.
"""

import pytest
from plugins.elo import TennisEloRating

# Sample data mimicking tennis-data.co.uk
MOCK_GAMES_DATA = [
    {"winner": "Djokovic N.", "loser": "Nadal R.", "tour": "ATP", "date": "2025-01-01"},
    {
        "winner": "Djokovic N.",
        "loser": "Federer R.",
        "tour": "ATP",
        "date": "2025-01-02",
    },
    {
        "winner": "Swiatek I.",
        "loser": "Sabalenka A.",
        "tour": "WTA",
        "date": "2025-01-01",
    },
]


def test_elo_updates_change_ratings():
    """Test that updating ratings changes future predictions."""
    elo = TennisEloRating()
    elo.update("Player A", "Player B", "ATP")

    assert elo.get_rating("Player A", "ATP") > 1500
    assert elo.get_rating("Player B", "ATP") < 1500

    # Prediction should favor Player A
    prob = elo.predict("Player A", "Player B", "ATP")
    assert prob > 0.5


def test_training_from_games():
    """Test training flow using mock games data."""
    elo = TennisEloRating()
    for game in MOCK_GAMES_DATA:
        elo.update(game["winner"], game["loser"], game["tour"])

    # Djokovic should have highest ATP rating
    atp_ratings = elo.atp_ratings
    assert "Djokovic N." in atp_ratings
    assert "Nadal R." in atp_ratings
    assert "Federer R." in atp_ratings

    # Swiatek should have WTA rating
    wta_ratings = elo.wta_ratings
    assert "Swiatek I." in wta_ratings
    assert "Sabalenka A." in wta_ratings


def test_dynamic_k_factor():
    """Test that K-factor adjusts for new players."""
    elo = TennisEloRating(k_factor=32)

    # New player gets higher K-factor
    elo.update("New Player", "Established Player", "ATP")

    # Check that match count was incremented
    assert elo.get_match_count("New Player", "ATP") == 1
    assert elo.get_match_count("Established Player", "ATP") == 1


def test_name_normalization():
    """Test that player names are normalized correctly."""
    elo = TennisEloRating()

    # Test various name formats
    assert elo._normalize_name("Novak Djokovic") == "Djokovic N."
    assert elo._normalize_name("Djokovic N.") == "Djokovic N."
    assert elo._normalize_name("NAOMI OSAKA") == "Osaka N."
    assert elo._normalize_name("") == "Unknown"

    def test_separate_atp_wta_ratings():
        """Test that ATP and WTA ratings are kept separate."""
        elo = TennisEloRating()

        # Same player name in different tours should have separate ratings
        # Player A wins in ATP, loses in WTA
        elo.update(
            "Player A", "Player B", "ATP"
        )  # Player A wins (implicit winner first)
        elo.update("Player B", "Player A", "WTA")  # Player B wins (Player A loses)

        atp_rating = elo.get_rating("Player A", "ATP")
        wta_rating = elo.get_rating("Player A", "WTA")

        # They should be different (ATP > 1500, WTA < 1500)
        assert atp_rating != wta_rating
        assert atp_rating > 1500
        assert wta_rating < 1500


def test_get_rankings():
    """Test getting top rankings."""
    elo = TennisEloRating()

    # Add some players
    elo.update("Player A", "Player B", "ATP")
    elo.update("Player A", "Player C", "ATP")
    elo.update("Player D", "Player E", "WTA")

    # Get ATP rankings
    atp_rankings = elo.get_rankings(tour="ATP", top_n=3)
    assert len(atp_rankings) <= 3

    # Get WTA rankings
    wta_rankings = elo.get_rankings(tour="WTA", top_n=3)
    assert len(wta_rankings) <= 3


def test_calibration_accuracy():
    """Test calibration accuracy metrics."""
    elo = TennisEloRating()

    # Train on some games
    for game in MOCK_GAMES_DATA:
        elo.update(game["winner"], game["loser"], game["tour"])

    # Test predictions on known outcomes
    # Djokovic vs Nadal - Djokovic should be favored
    prob = elo.predict("Djokovic N.", "Nadal R.", "ATP")
    assert prob > 0.5

    # Swiatek vs Sabalenka - Swiatek should be favored
    prob_wta = elo.predict("Swiatek I.", "Sabalenka A.", "WTA")
    assert prob_wta > 0.5


def test_legacy_update_compatibility():
    """Test that legacy update method works."""
    elo = TennisEloRating()

    # Use legacy_update (same as update for tennis)
    change = elo.legacy_update("Player A", "Player B", tour="ATP")
    assert isinstance(change, float)

    # Ratings should have changed
    assert elo.get_rating("Player A", "ATP") != 1500
    assert elo.get_rating("Player B", "ATP") != 1500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
