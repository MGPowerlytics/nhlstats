"""Tests for MLB, NFL, Tennis, NCAAB, EPL, and Ligue1 Elo Rating Systems."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))

from elo import MLBEloRating, NFLEloRating, TennisEloRating, NCAABEloRating, EPLEloRating, Ligue1EloRating


class TestMLBEloRating:
    """Test the MLBEloRating class."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        elo = MLBEloRating()
        assert elo.k_factor == 20
        assert elo.home_advantage == 50
        assert elo.initial_rating == 1500
        assert elo.ratings == {}

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        elo = MLBEloRating(k_factor=30, home_advantage=75, initial_rating=1600)
        assert elo.k_factor == 30
        assert elo.home_advantage == 75
        assert elo.initial_rating == 1600

    def test_get_rating_new_team(self):
        """Test getting rating for a new team."""
        elo = MLBEloRating()
        rating = elo.get_rating("Yankees")
        assert rating == 1500
        assert "Yankees" in elo.ratings

    def test_get_rating_existing_team(self):
        """Test getting rating for an existing team."""
        elo = MLBEloRating()
        elo.ratings["Yankees"] = 1600
        rating = elo.get_rating("Yankees")
        assert rating == 1600

    def test_expected_score_equal_ratings(self):
        """Test expected score with equal ratings."""
        elo = MLBEloRating()
        score = elo.expected_score(1500, 1500)
        assert score == pytest.approx(0.5, abs=0.001)

    def test_expected_score_higher_rating(self):
        """Test expected score with higher rating for team A."""
        elo = MLBEloRating()
        score = elo.expected_score(1600, 1400)
        assert score > 0.5
        assert score == pytest.approx(0.76, abs=0.01)

    def test_predict_equal_teams(self):
        """Test prediction with equal teams (home advantage applies)."""
        elo = MLBEloRating(home_advantage=50)
        prob = elo.predict("Yankees", "Red Sox")
        assert prob > 0.5

    def test_update_home_win(self):
        """Test rating update when home team wins."""
        elo = MLBEloRating(k_factor=20)
        elo.ratings["Yankees"] = 1500
        elo.ratings["Red Sox"] = 1500

        elo.update_legacy("Yankees", "Red Sox", home_score=5, away_score=3)

        assert elo.ratings["Yankees"] > 1500
        assert elo.ratings["Red Sox"] < 1500

    def test_update_away_win(self):
        """Test rating update when away team wins."""
        elo = MLBEloRating(k_factor=20)
        elo.ratings["Yankees"] = 1500
        elo.ratings["Red Sox"] = 1500

        elo.update_legacy("Yankees", "Red Sox", home_score=2, away_score=6)

        assert elo.ratings["Yankees"] < 1500
        assert elo.ratings["Red Sox"] > 1500

    def test_update_conserves_points(self):
        """Test that rating updates conserve total points."""
        elo = MLBEloRating(k_factor=20)
        elo.ratings["Yankees"] = 1550
        elo.ratings["Red Sox"] = 1450

        total_before = sum(elo.ratings.values())
        elo.update_legacy("Yankees", "Red Sox", home_score=5, away_score=3)
        total_after = sum(elo.ratings.values())

        assert total_before == pytest.approx(total_after, abs=0.001)


class TestNFLEloRating:
    """Test the NFLEloRating class."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        elo = NFLEloRating()
        assert elo.k_factor == 20
        assert elo.home_advantage == 65
        assert elo.initial_rating == 1500
        assert elo.ratings == {}

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        elo = NFLEloRating(k_factor=25, home_advantage=80, initial_rating=1600)
        assert elo.k_factor == 25
        assert elo.home_advantage == 80
        assert elo.initial_rating == 1600

    def test_get_rating_new_team(self):
        """Test getting rating for a new team."""
        elo = NFLEloRating()
        rating = elo.get_rating("Chiefs")
        assert rating == 1500
        assert "Chiefs" in elo.ratings

    def test_expected_score_equal_ratings(self):
        """Test expected score with equal ratings."""
        elo = NFLEloRating()
        score = elo.expected_score(1500, 1500)
        assert score == pytest.approx(0.5, abs=0.001)

    def test_predict_with_home_advantage(self):
        """Test prediction includes home advantage."""
        elo = NFLEloRating(home_advantage=65)
        prob = elo.predict("Chiefs", "Bills")
        assert prob > 0.5

    def test_update_home_win(self):
        """Test rating update when home team wins."""
        elo = NFLEloRating(k_factor=20)
        elo.ratings["Chiefs"] = 1500
        elo.ratings["Bills"] = 1500

        elo.update_legacy("Chiefs", "Bills", home_score=31, away_score=24)

        assert elo.ratings["Chiefs"] > 1500
        assert elo.ratings["Bills"] < 1500

    def test_update_away_win(self):
        """Test rating update when away team wins."""
        elo = NFLEloRating(k_factor=20)
        elo.ratings["Chiefs"] = 1500
        elo.ratings["Bills"] = 1500

        elo.update_legacy("Chiefs", "Bills", home_score=17, away_score=28)

        assert elo.ratings["Chiefs"] < 1500
        assert elo.ratings["Bills"] > 1500


# Note: Other test classes (Tennis, NCAAB, EPL, Ligue1) would be here
# For now, focusing on MLB and NFL for TDD refactoring
