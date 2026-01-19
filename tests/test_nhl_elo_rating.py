"""Tests for NHL Elo Rating System."""

import pytest
import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))

from nhl_elo_rating import NHLEloRating


class TestNHLEloRating:
    """Test the NHLEloRating class."""
    
    def test_init_default_values(self):
        """Test initialization with default values."""
        elo = NHLEloRating()
        assert elo.k_factor == 10
        assert elo.home_advantage == 50
        assert elo.initial_rating == 1500
        assert elo.recency_weight == 0.2
        assert elo.ratings == {}
        assert elo.game_history == []
        assert elo.last_game_date == {}
    
    def test_init_custom_values(self):
        """Test initialization with custom values."""
        elo = NHLEloRating(k_factor=20, home_advantage=100, initial_rating=1600, recency_weight=0.3)
        assert elo.k_factor == 20
        assert elo.home_advantage == 100
        assert elo.initial_rating == 1600
        assert elo.recency_weight == 0.3
    
    def test_get_rating_new_team(self):
        """Test getting rating for a new team."""
        elo = NHLEloRating()
        rating = elo.get_rating("Toronto Maple Leafs")
        assert rating == 1500
        assert "Toronto Maple Leafs" in elo.ratings
    
    def test_get_rating_existing_team(self):
        """Test getting rating for an existing team."""
        elo = NHLEloRating()
        elo.ratings["Toronto Maple Leafs"] = 1600
        rating = elo.get_rating("Toronto Maple Leafs")
        assert rating == 1600
    
    def test_expected_score_equal_ratings(self):
        """Test expected score with equal ratings."""
        elo = NHLEloRating()
        score = elo.expected_score(1500, 1500)
        assert score == pytest.approx(0.5, abs=0.001)
    
    def test_expected_score_higher_rating(self):
        """Test expected score with higher rating for team A."""
        elo = NHLEloRating()
        score = elo.expected_score(1600, 1400)
        assert score > 0.5
        assert score == pytest.approx(0.76, abs=0.01)
    
    def test_expected_score_lower_rating(self):
        """Test expected score with lower rating for team A."""
        elo = NHLEloRating()
        score = elo.expected_score(1400, 1600)
        assert score < 0.5
        assert score == pytest.approx(0.24, abs=0.01)
    
    def test_predict_with_home_advantage(self):
        """Test prediction includes home advantage."""
        elo = NHLEloRating(home_advantage=50)
        prob = elo.predict("Toronto Maple Leafs", "Boston Bruins")
        # Home team should have slight advantage
        assert prob > 0.5
    
    def test_predict_stronger_home_team(self):
        """Test prediction with stronger home team."""
        elo = NHLEloRating()
        elo.ratings["Toronto Maple Leafs"] = 1600
        elo.ratings["Boston Bruins"] = 1400
        prob = elo.predict("Toronto Maple Leafs", "Boston Bruins")
        assert prob > 0.5
    
    def test_update_home_win(self):
        """Test rating update when home team wins."""
        elo = NHLEloRating(k_factor=20, recency_weight=0)
        elo.ratings["Toronto"] = 1500
        elo.ratings["Boston"] = 1500
        
        result = elo.update("Toronto", "Boston", home_won=True)
        
        assert elo.ratings["Toronto"] > 1500
        assert elo.ratings["Boston"] < 1500
        assert 'home_change' in result
        assert 'away_change' in result
        assert result['home_change'] > 0
        assert result['away_change'] < 0
    
    def test_update_away_win(self):
        """Test rating update when away team wins."""
        elo = NHLEloRating(k_factor=20, recency_weight=0)
        elo.ratings["Toronto"] = 1500
        elo.ratings["Boston"] = 1500
        
        result = elo.update("Toronto", "Boston", home_won=False)
        
        assert elo.ratings["Toronto"] < 1500
        assert elo.ratings["Boston"] > 1500
        assert result['home_change'] < 0
        assert result['away_change'] > 0
    
    def test_update_with_scores(self):
        """Test rating update with score recording."""
        elo = NHLEloRating()
        elo.update("Toronto", "Boston", home_won=True, home_score=4, away_score=2)
        
        assert len(elo.game_history) == 1
        assert elo.game_history[0]['home_score'] == 4
        assert elo.game_history[0]['away_score'] == 2
    
    def test_update_records_history(self):
        """Test that update records game history."""
        elo = NHLEloRating()
        elo.update("Toronto", "Boston", home_won=True)
        
        assert len(elo.game_history) == 1
        history = elo.game_history[0]
        assert history['home_team'] == "Toronto"
        assert history['away_team'] == "Boston"
        assert history['home_won'] == True
        assert 'prob_home_win' in history
        assert 'home_rating_before' in history
        assert 'home_rating_after' in history
    
    def test_update_with_recency_weight(self):
        """Test rating update with recency weighting."""
        elo = NHLEloRating(k_factor=10, recency_weight=0.2)
        
        # First game
        game_date1 = datetime(2024, 1, 1)
        elo.update("Toronto", "Boston", home_won=True, game_date=game_date1)
        
        # Game 10 days later - should have boosted k-factor
        game_date2 = datetime(2024, 1, 11)
        rating_before = elo.get_rating("Toronto")
        elo.update("Toronto", "Montreal", home_won=True, game_date=game_date2)
        
        # The change should be larger due to recency weighting
        assert elo.last_game_date["Toronto"] == game_date2
    
    def test_update_conserves_points(self):
        """Test that rating updates conserve total points."""
        elo = NHLEloRating(k_factor=20, recency_weight=0)
        elo.ratings["Toronto"] = 1550
        elo.ratings["Boston"] = 1450
        
        total_before = sum(elo.ratings.values())
        elo.update("Toronto", "Boston", home_won=True)
        total_after = sum(elo.ratings.values())
        
        assert total_before == pytest.approx(total_after, abs=0.001)
    
    def test_apply_season_reversion(self):
        """Test season reversion to mean."""
        elo = NHLEloRating()
        elo.ratings["Toronto"] = 1700
        elo.ratings["Boston"] = 1300
        
        elo.apply_season_reversion(factor=0.5)
        
        # Ratings should move towards 1500
        assert elo.ratings["Toronto"] < 1700
        assert elo.ratings["Toronto"] > 1500
        assert elo.ratings["Boston"] > 1300
        assert elo.ratings["Boston"] < 1500
        
        # With factor 0.5, should be exactly halfway
        assert elo.ratings["Toronto"] == pytest.approx(1600, abs=1)
        assert elo.ratings["Boston"] == pytest.approx(1400, abs=1)
    
    def test_apply_season_reversion_zero_factor(self):
        """Test season reversion with zero factor (no change)."""
        elo = NHLEloRating()
        elo.ratings["Toronto"] = 1700
        
        elo.apply_season_reversion(factor=0.0)
        
        assert elo.ratings["Toronto"] == 1700
    
    def test_apply_season_reversion_full_reset(self):
        """Test season reversion with factor=1 (full reset)."""
        elo = NHLEloRating()
        elo.ratings["Toronto"] = 1700
        elo.ratings["Boston"] = 1300
        
        elo.apply_season_reversion(factor=1.0)
        
        assert elo.ratings["Toronto"] == 1500
        assert elo.ratings["Boston"] == 1500
    
    def test_get_rankings_all(self):
        """Test getting all rankings."""
        elo = NHLEloRating()
        elo.ratings = {"Toronto": 1600, "Boston": 1550, "Montreal": 1450}
        
        rankings = elo.get_rankings()
        
        assert len(rankings) == 3
        assert rankings[0] == ("Toronto", 1600)
        assert rankings[1] == ("Boston", 1550)
        assert rankings[2] == ("Montreal", 1450)
    
    def test_get_rankings_top_n(self):
        """Test getting top N rankings."""
        elo = NHLEloRating()
        elo.ratings = {"Toronto": 1600, "Boston": 1550, "Montreal": 1450, "Ottawa": 1400}
        
        rankings = elo.get_rankings(top_n=2)
        
        assert len(rankings) == 2
        assert rankings[0] == ("Toronto", 1600)
        assert rankings[1] == ("Boston", 1550)
    
    def test_save_ratings(self, tmp_path):
        """Test saving ratings to file."""
        elo = NHLEloRating(k_factor=15, home_advantage=75)
        elo.ratings = {"Toronto": 1600, "Boston": 1400}
        elo.game_history = [{"test": "game"}]
        
        filepath = tmp_path / "ratings.json"
        elo.save_ratings(str(filepath))
        
        assert filepath.exists()
        
        with open(filepath) as f:
            data = json.load(f)
        
        assert data['parameters']['k_factor'] == 15
        assert data['parameters']['home_advantage'] == 75
        assert data['ratings']['Toronto'] == 1600
        assert data['num_teams'] == 2
        assert data['num_games'] == 1
    
    def test_load_ratings(self, tmp_path):
        """Test loading ratings from file."""
        filepath = tmp_path / "ratings.json"
        data = {
            'parameters': {
                'k_factor': 25,
                'home_advantage': 80,
                'initial_rating': 1500
            },
            'ratings': {"Toronto": 1650, "Boston": 1350},
            'last_updated': '2024-01-01T00:00:00'
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f)
        
        elo = NHLEloRating()
        result = elo.load_ratings(str(filepath))
        
        assert result == True
        assert elo.k_factor == 25
        assert elo.home_advantage == 80
        assert elo.ratings["Toronto"] == 1650
        assert elo.ratings["Boston"] == 1350
    
    def test_load_ratings_file_not_found(self, tmp_path):
        """Test loading when file doesn't exist."""
        elo = NHLEloRating()
        filepath = tmp_path / "nonexistent.json"
        
        result = elo.load_ratings(str(filepath))
        
        assert result == False
        assert elo.ratings == {}
    
    def test_export_history(self, tmp_path):
        """Test exporting game history."""
        elo = NHLEloRating()
        elo.update("Toronto", "Boston", home_won=True)
        elo.update("Montreal", "Ottawa", home_won=False)
        
        filepath = tmp_path / "history.json"
        elo.export_history(str(filepath))
        
        assert filepath.exists()
        
        with open(filepath) as f:
            history = json.load(f)
        
        assert len(history) == 2


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_very_high_k_factor(self):
        """Test with very high k-factor."""
        elo = NHLEloRating(k_factor=100, recency_weight=0)
        elo.ratings["Toronto"] = 1500
        elo.ratings["Boston"] = 1500
        
        elo.update("Toronto", "Boston", home_won=True)
        
        assert abs(elo.ratings["Toronto"] - 1500) > 20
    
    def test_zero_home_advantage(self):
        """Test with zero home advantage."""
        elo = NHLEloRating(home_advantage=0)
        prob = elo.predict("Toronto", "Boston")
        assert prob == pytest.approx(0.5, abs=0.001)
    
    def test_extreme_rating_difference(self):
        """Test with extreme rating difference."""
        elo = NHLEloRating()
        elo.ratings["Toronto"] = 2000
        elo.ratings["Boston"] = 1000
        
        prob = elo.predict("Toronto", "Boston")
        assert prob > 0.99
    
    def test_many_sequential_games(self):
        """Test many sequential games."""
        elo = NHLEloRating(k_factor=20, recency_weight=0)
        
        for i in range(100):
            elo.update("Toronto", "Boston", home_won=True)
        
        assert len(elo.game_history) == 100
        assert elo.ratings["Toronto"] > elo.ratings["Boston"]
    
    def test_alternating_wins(self):
        """Test alternating wins between teams."""
        elo = NHLEloRating(k_factor=20, recency_weight=0)
        
        for i in range(10):
            elo.update("Toronto", "Boston", home_won=(i % 2 == 0))
        
        # Ratings should stay relatively close to 1500
        assert abs(elo.ratings["Toronto"] - 1500) < 50
        assert abs(elo.ratings["Boston"] - 1500) < 50
