"""
Tests for NHLEloRating class.
"""

import json
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.elo import NHLEloRating


class TestNHLEloRatingBasic:
    """Basic tests for NHLEloRating."""

    def test_initialization(self):
        """Test default initialization."""
        elo = NHLEloRating()
        assert elo.k_factor == 20
        assert elo.home_advantage == 100
        assert elo.initial_rating == 1500
        assert elo.ratings == {}
        assert elo.game_history == []
        assert elo.last_game_date is None

    def test_custom_initialization(self):
        """Test initialization with custom parameters."""
        elo = NHLEloRating(k_factor=25, home_advantage=80, initial_rating=1600)
        assert elo.k_factor == 25
        assert elo.home_advantage == 80
        assert elo.initial_rating == 1600

    def test_get_rating_new_team(self):
        """Test getting rating for a new team."""
        elo = NHLEloRating(initial_rating=1600)
        assert elo.get_rating("Maple Leafs") == 1600
        assert "Maple Leafs" in elo.ratings

    def test_predict_with_recency_weighting(self):
        """Test prediction with NHL's recency weighting."""
        elo = NHLEloRating()
        elo.ratings = {"Maple Leafs": 1600, "Bruins": 1400}

        prob = elo.predict("Maple Leafs", "Bruins", is_neutral=False)
        assert 0 < prob < 1

    def test_update_with_game_history(self):
        """Test that updates add to game history."""
        elo = NHLEloRating()

        initial_history_len = len(elo.game_history)
        elo.update("Maple Leafs", "Bruins", home_win=1.0, is_neutral=False)

        assert len(elo.game_history) == initial_history_len + 1
        game_record = elo.game_history[-1]
        assert game_record["home_team"] == "Maple Leafs"
        assert game_record["away_team"] == "Bruins"
        assert game_record["home_won"]


class TestNHLSpecificFeatures:
    """Test NHL-specific features."""

    def test_load_ratings(self, tmp_path):
        """Test loading ratings from file."""
        filepath = tmp_path / "ratings.json"
        data = {
            "parameters": {
                "k_factor": 25,
                "home_advantage": 80,
                "initial_rating": 1500,
            },
            "ratings": {"Toronto": 1650, "Boston": 1350},
            "last_updated": "2024-01-01T00:00:00",
        }

        with open(filepath, "w") as f:
            json.dump(data, f)

        elo = NHLEloRating()
        result = elo.load_ratings(str(filepath))

        assert result
        assert elo.k_factor == 25
        assert elo.home_advantage == 80
        assert elo.ratings["Toronto"] == 1650
        assert elo.ratings["Boston"] == 1350

    def test_load_ratings_file_not_found(self, tmp_path):
        """Test loading when file doesn't exist."""
        elo = NHLEloRating()
        filepath = tmp_path / "nonexistent.json"

        result = elo.load_ratings(str(filepath))

        assert not result
        assert elo.ratings == {}

    def test_export_history(self, tmp_path):
        """Test exporting game history."""
        elo = NHLEloRating()
        elo.update("Toronto", "Boston", home_win=1.0, is_neutral=False)
        elo.update("Montreal", "Ottawa", home_win=0.0, is_neutral=False)

        filepath = tmp_path / "history.json"
        elo.export_history(str(filepath))

        assert filepath.exists()

        with open(filepath) as f:
            history = json.load(f)

        assert len(history) == 2

    def test_save_ratings(self, tmp_path):
        """Test saving ratings to file."""
        elo = NHLEloRating(k_factor=25, home_advantage=80)
        elo.ratings = {"Toronto": 1650, "Boston": 1350}

        filepath = tmp_path / "save_test.json"
        result = elo.save_ratings(str(filepath))

        assert result
        assert filepath.exists()

        with open(filepath) as f:
            saved_data = json.load(f)

        assert saved_data["parameters"]["k_factor"] == 25
        assert saved_data["parameters"]["home_advantage"] == 80
        assert saved_data["ratings"]["Toronto"] == 1650

    def test_apply_season_reversion(self):
        """Test season reversion logic."""
        elo = NHLEloRating()
        elo.ratings = {
            "Toronto": 1650,
            "Boston": 1350,
            "Montreal": 1550,
            "Ottawa": 1450,
        }

        # Store initial ratings
        initial_ratings = elo.ratings.copy()

        # Apply season reversion
        elo.apply_season_reversion()

        # Ratings should move toward 1500
        for team in initial_ratings:
            if initial_ratings[team] > 1500:
                assert elo.ratings[team] < initial_ratings[team]
            elif initial_ratings[team] < 1500:
                assert elo.ratings[team] > initial_ratings[team]

    def test_get_recent_games(self):
        """Test getting recent games."""
        elo = NHLEloRating()

        # Add some games with timestamps
        elo.update("Toronto", "Boston", home_win=1.0, is_neutral=False)
        elo.update("Montreal", "Ottawa", home_win=0.0, is_neutral=False)
        elo.update("Vancouver", "Calgary", home_win=1.0, is_neutral=False)

        recent_games = elo.get_recent_games(n=2)
        assert len(recent_games) == 2
        assert recent_games[0]["home_team"] == "Vancouver"  # Most recent
        assert recent_games[1]["home_team"] == "Montreal"  # Second most recent


class TestNHLIntegration:
    """Integration tests for NHLEloRating."""

    def test_full_cycle(self, tmp_path):
        """Test full cycle: update, save, load, continue updating."""
        elo = NHLEloRating()

        # Initial updates
        elo.update("Toronto", "Boston", home_win=1.0, is_neutral=False)
        elo.update("Montreal", "Ottawa", home_win=0.0, is_neutral=False)

        # Save
        save_path = tmp_path / "test_cycle.json"
        elo.save_ratings(str(save_path))

        # Create new instance and load
        elo2 = NHLEloRating()
        elo2.load_ratings(str(save_path))

        # Continue updating
        elo2.update("Vancouver", "Calgary", home_win=1.0, is_neutral=False)

        # Verify continuity
        assert "Toronto" in elo2.ratings
        assert "Montreal" in elo2.ratings
        assert "Vancouver" in elo2.ratings
        assert len(elo2.game_history) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
