"""Tests for MLB, NFL, Tennis, NCAAB, EPL, and Ligue1 Elo Rating Systems."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))

from mlb_elo_rating import MLBEloRating
from nfl_elo_rating import NFLEloRating
from tennis_elo_rating import TennisEloRating
from ncaab_elo_rating import NCAABEloRating
from epl_elo_rating import EPLEloRating
from ligue1_elo_rating import Ligue1EloRating


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
        
        elo.update("Yankees", "Red Sox", home_score=5, away_score=3)
        
        assert elo.ratings["Yankees"] > 1500
        assert elo.ratings["Red Sox"] < 1500
    
    def test_update_away_win(self):
        """Test rating update when away team wins."""
        elo = MLBEloRating(k_factor=20)
        elo.ratings["Yankees"] = 1500
        elo.ratings["Red Sox"] = 1500
        
        elo.update("Yankees", "Red Sox", home_score=2, away_score=6)
        
        assert elo.ratings["Yankees"] < 1500
        assert elo.ratings["Red Sox"] > 1500
    
    def test_update_conserves_points(self):
        """Test that rating updates conserve total points."""
        elo = MLBEloRating(k_factor=20)
        elo.ratings["Yankees"] = 1550
        elo.ratings["Red Sox"] = 1450
        
        total_before = sum(elo.ratings.values())
        elo.update("Yankees", "Red Sox", home_score=5, away_score=3)
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
        
        elo.update("Chiefs", "Bills", home_score=31, away_score=24)
        
        assert elo.ratings["Chiefs"] > 1500
        assert elo.ratings["Bills"] < 1500
    
    def test_update_away_win(self):
        """Test rating update when away team wins."""
        elo = NFLEloRating(k_factor=20)
        elo.ratings["Chiefs"] = 1500
        elo.ratings["Bills"] = 1500
        
        elo.update("Chiefs", "Bills", home_score=17, away_score=28)
        
        assert elo.ratings["Chiefs"] < 1500
        assert elo.ratings["Bills"] > 1500


class TestTennisEloRating:
    """Test the TennisEloRating class."""
    
    def test_init_default_values(self):
        """Test initialization with default values."""
        elo = TennisEloRating()
        assert elo.k_factor == 32
        assert elo.initial_rating == 1500
        assert elo.ratings == {}
        assert elo.matches_played == {}
    
    def test_init_custom_values(self):
        """Test initialization with custom values."""
        elo = TennisEloRating(k_factor=40, initial_rating=1600)
        assert elo.k_factor == 40
        assert elo.initial_rating == 1600
    
    def test_get_rating_new_player(self):
        """Test getting rating for a new player."""
        elo = TennisEloRating()
        rating = elo.get_rating("Djokovic")
        assert rating == 1500
        assert "Djokovic" in elo.ratings
        assert elo.matches_played["Djokovic"] == 0
    
    def test_get_rating_existing_player(self):
        """Test getting rating for an existing player."""
        elo = TennisEloRating()
        elo.ratings["Djokovic"] = 1700
        elo.matches_played["Djokovic"] = 50
        rating = elo.get_rating("Djokovic")
        assert rating == 1700
    
    def test_predict_equal_players(self):
        """Test prediction with equal players."""
        elo = TennisEloRating()
        prob = elo.predict("Djokovic", "Nadal")
        assert prob == pytest.approx(0.5, abs=0.001)
    
    def test_predict_stronger_player(self):
        """Test prediction with stronger player."""
        elo = TennisEloRating()
        elo.ratings["Djokovic"] = 1700
        elo.ratings["Nadal"] = 1500
        prob = elo.predict("Djokovic", "Nadal")
        assert prob > 0.5
    
    def test_update_winner_rating_increases(self):
        """Test that winner's rating increases."""
        elo = TennisEloRating(k_factor=32)
        elo.ratings["Djokovic"] = 1500
        elo.ratings["Nadal"] = 1500
        elo.matches_played["Djokovic"] = 50
        elo.matches_played["Nadal"] = 50
        
        elo.update("Djokovic", "Nadal")
        
        assert elo.ratings["Djokovic"] > 1500
        assert elo.ratings["Nadal"] < 1500
    
    def test_update_increments_matches_played(self):
        """Test that update increments matches played."""
        elo = TennisEloRating()
        elo.update("Djokovic", "Nadal")
        
        assert elo.matches_played["Djokovic"] == 1
        assert elo.matches_played["Nadal"] == 1
    
    def test_update_new_player_higher_k_factor(self):
        """Test that new players have higher k-factor effect."""
        elo1 = TennisEloRating(k_factor=32)
        elo1.ratings["Djokovic"] = 1500
        elo1.ratings["Nadal"] = 1500
        elo1.matches_played["Djokovic"] = 0  # New player
        elo1.matches_played["Nadal"] = 0  # New player
        
        elo2 = TennisEloRating(k_factor=32)
        elo2.ratings["Djokovic"] = 1500
        elo2.ratings["Nadal"] = 1500
        elo2.matches_played["Djokovic"] = 50  # Veteran
        elo2.matches_played["Nadal"] = 50  # Veteran
        
        elo1.update("Djokovic", "Nadal")
        elo2.update("Djokovic", "Nadal")
        
        # New player should have larger rating change
        change1 = abs(elo1.ratings["Djokovic"] - 1500)
        change2 = abs(elo2.ratings["Djokovic"] - 1500)
        assert change1 > change2
    
    def test_get_rankings(self):
        """Test getting top rankings."""
        elo = TennisEloRating()
        elo.ratings = {"Djokovic": 1700, "Nadal": 1650, "Federer": 1600, "Murray": 1550}
        
        rankings = elo.get_rankings(top_n=2)
        
        assert len(rankings) == 2
        assert rankings[0] == ("Djokovic", 1700)
        assert rankings[1] == ("Nadal", 1650)


class TestNCAABEloRating:
    """Test the NCAABEloRating class."""
    
    def test_init_default_values(self):
        """Test initialization with default values."""
        elo = NCAABEloRating()
        assert elo.k_factor == 20
        assert elo.home_advantage == 100
        assert elo.initial_rating == 1500
        assert elo.ratings == {}
    
    def test_init_custom_values(self):
        """Test initialization with custom values."""
        elo = NCAABEloRating(k_factor=25, home_advantage=120, initial_rating=1600)
        assert elo.k_factor == 25
        assert elo.home_advantage == 120
        assert elo.initial_rating == 1600
    
    def test_get_rating_new_team(self):
        """Test getting rating for a new team."""
        elo = NCAABEloRating()
        rating = elo.get_rating("Duke")
        assert rating == 1500
        assert "Duke" in elo.ratings
    
    def test_predict_with_home_advantage(self):
        """Test prediction includes home advantage."""
        elo = NCAABEloRating(home_advantage=100)
        prob = elo.predict("Duke", "UNC", is_neutral=False)
        assert prob > 0.5
    
    def test_predict_neutral_court(self):
        """Test prediction on neutral court."""
        elo = NCAABEloRating(home_advantage=100)
        prob = elo.predict("Duke", "UNC", is_neutral=True)
        # With equal ratings and neutral court, should be 50%
        assert prob == pytest.approx(0.5, abs=0.001)
    
    def test_update_home_win(self):
        """Test rating update when home team wins."""
        elo = NCAABEloRating(k_factor=20)
        elo.ratings["Duke"] = 1500
        elo.ratings["UNC"] = 1500
        
        result = elo.update("Duke", "UNC", home_win=1.0)
        
        assert elo.ratings["Duke"] > 1500
        assert elo.ratings["UNC"] < 1500
        assert result != 0
    
    def test_update_away_win(self):
        """Test rating update when away team wins."""
        elo = NCAABEloRating(k_factor=20)
        elo.ratings["Duke"] = 1500
        elo.ratings["UNC"] = 1500
        
        elo.update("Duke", "UNC", home_win=0.0)
        
        assert elo.ratings["Duke"] < 1500
        assert elo.ratings["UNC"] > 1500
    
    def test_update_neutral_court(self):
        """Test rating update on neutral court."""
        elo = NCAABEloRating(k_factor=20)
        elo.ratings["Duke"] = 1500
        elo.ratings["UNC"] = 1500
        
        # Win on neutral court (expected = 50%)
        elo.update("Duke", "UNC", home_win=1.0, is_neutral=True)
        
        assert elo.ratings["Duke"] > 1500


class TestEPLEloRating:
    """Test the EPLEloRating class."""
    
    def test_init_default_values(self):
        """Test initialization with default values."""
        elo = EPLEloRating()
        assert elo.k_factor == 20
        assert elo.home_advantage == 60
        assert elo.initial_rating == 1500
        assert elo.ratings == {}
    
    def test_init_custom_values(self):
        """Test initialization with custom values."""
        elo = EPLEloRating(k_factor=25, home_advantage=70, initial_rating=1600)
        assert elo.k_factor == 25
        assert elo.home_advantage == 70
        assert elo.initial_rating == 1600
    
    def test_get_rating_new_team(self):
        """Test getting rating for a new team."""
        elo = EPLEloRating()
        rating = elo.get_rating("Man City")
        assert rating == 1500
        assert "Man City" in elo.ratings
    
    def test_predict_probs_sums_to_one(self):
        """Test that 3-way probabilities sum to 1."""
        elo = EPLEloRating()
        probs = elo.predict_probs("Man City", "Liverpool")
        total = sum(probs)
        assert total == pytest.approx(1.0, abs=0.001)
    
    def test_predict_probs_equal_teams(self):
        """Test 3-way probabilities with equal teams."""
        elo = EPLEloRating()
        p_home, p_draw, p_away = elo.predict_probs("Man City", "Liverpool")
        
        # With equal ratings, home should have slight advantage
        assert p_home > p_away
        # Draw should be between 0 and 0.3
        assert 0 < p_draw < 0.3
    
    def test_predict_probs_stronger_home_team(self):
        """Test 3-way probabilities with stronger home team."""
        elo = EPLEloRating()
        elo.ratings["Man City"] = 1700
        elo.ratings["Liverpool"] = 1400
        
        p_home, p_draw, p_away = elo.predict_probs("Man City", "Liverpool")
        
        assert p_home > p_away
        assert p_home > p_draw
    
    def test_predict_3way_returns_dict(self):
        """Test that predict_3way returns a dictionary."""
        elo = EPLEloRating()
        probs = elo.predict_3way("Man City", "Liverpool")
        
        assert isinstance(probs, dict)
        assert 'home' in probs
        assert 'draw' in probs
        assert 'away' in probs
    
    def test_predict_returns_home_prob(self):
        """Test that predict returns just home probability."""
        elo = EPLEloRating()
        prob = elo.predict("Man City", "Liverpool")
        
        assert 0 < prob < 1
    
    def test_update_home_win(self):
        """Test rating update with home win."""
        elo = EPLEloRating(k_factor=20)
        elo.ratings["Man City"] = 1500
        elo.ratings["Liverpool"] = 1500
        
        elo.update("Man City", "Liverpool", 'H')
        
        assert elo.ratings["Man City"] > 1500
        assert elo.ratings["Liverpool"] < 1500
    
    def test_update_draw(self):
        """Test rating update with draw."""
        elo = EPLEloRating(k_factor=20)
        elo.ratings["Man City"] = 1500
        elo.ratings["Liverpool"] = 1500
        
        initial_city = elo.ratings["Man City"]
        elo.update("Man City", "Liverpool", 'D')
        
        # Draw = 0.5, so home expected was > 0.5, so home loses rating
        assert elo.ratings["Man City"] < initial_city
    
    def test_update_away_win(self):
        """Test rating update with away win."""
        elo = EPLEloRating(k_factor=20)
        elo.ratings["Man City"] = 1500
        elo.ratings["Liverpool"] = 1500
        
        elo.update("Man City", "Liverpool", 'A')
        
        assert elo.ratings["Man City"] < 1500
        assert elo.ratings["Liverpool"] > 1500
    
    def test_update_with_integer_result(self):
        """Test rating update with integer result (1 for win)."""
        elo = EPLEloRating(k_factor=20)
        elo.ratings["Man City"] = 1500
        elo.ratings["Liverpool"] = 1500
        
        elo.update("Man City", "Liverpool", 1)  # Home win
        
        assert elo.ratings["Man City"] > 1500


class TestLigue1EloRating:
    """Test the Ligue1EloRating class."""
    
    def test_init_default_values(self):
        """Test initialization with default values."""
        elo = Ligue1EloRating()
        assert elo.k_factor == 20
        assert elo.home_advantage == 60
        assert elo.initial_rating == 1500
        assert elo.ratings == {}
    
    def test_init_custom_values(self):
        """Test initialization with custom values."""
        elo = Ligue1EloRating(k_factor=25, home_advantage=70, initial_rating=1600)
        assert elo.k_factor == 25
        assert elo.home_advantage == 70
        assert elo.initial_rating == 1600
    
    def test_get_rating_new_team(self):
        """Test getting rating for a new team."""
        elo = Ligue1EloRating()
        rating = elo.get_rating("PSG")
        assert rating == 1500
        assert "PSG" in elo.ratings
    
    def test_expected_score_equal_ratings(self):
        """Test expected score with equal ratings."""
        elo = Ligue1EloRating()
        score = elo.expected_score(1500, 1500)
        assert score == pytest.approx(0.5, abs=0.001)
    
    def test_predict_with_home_advantage(self):
        """Test prediction includes home advantage."""
        elo = Ligue1EloRating(home_advantage=60)
        prob = elo.predict("PSG", "Marseille")
        assert prob > 0.5
    
    def test_predict_3way_sums_to_one(self):
        """Test that 3-way probabilities sum to 1."""
        elo = Ligue1EloRating()
        probs = elo.predict_3way("PSG", "Marseille")
        total = probs['home'] + probs['draw'] + probs['away']
        assert total == pytest.approx(1.0, abs=0.001)
    
    def test_predict_3way_returns_dict(self):
        """Test that predict_3way returns a dictionary."""
        elo = Ligue1EloRating()
        probs = elo.predict_3way("PSG", "Marseille")
        
        assert isinstance(probs, dict)
        assert 'home' in probs
        assert 'draw' in probs
        assert 'away' in probs
    
    def test_predict_3way_draw_probability_range(self):
        """Test that draw probability is clamped to valid range."""
        elo = Ligue1EloRating()
        probs = elo.predict_3way("PSG", "Marseille")
        
        assert 0.05 <= probs['draw'] <= 0.30
    
    def test_predict_probs_alias(self):
        """Test that predict_probs is alias for predict_3way."""
        elo = Ligue1EloRating()
        probs1 = elo.predict_3way("PSG", "Marseille")
        probs2 = elo.predict_probs("PSG", "Marseille")
        
        assert probs1 == probs2
    
    def test_update_home_win(self):
        """Test rating update with home win."""
        elo = Ligue1EloRating(k_factor=20)
        elo.ratings["PSG"] = 1500
        elo.ratings["Marseille"] = 1500
        
        result = elo.update("PSG", "Marseille", 'home')
        
        assert elo.ratings["PSG"] > 1500
        assert elo.ratings["Marseille"] < 1500
        assert 'home_rating_change' in result
        assert 'away_rating_change' in result
    
    def test_update_draw(self):
        """Test rating update with draw."""
        elo = Ligue1EloRating(k_factor=20)
        elo.ratings["PSG"] = 1500
        elo.ratings["Marseille"] = 1500
        
        result = elo.update("PSG", "Marseille", 'draw')
        
        # Draw = 0.5 points, expected > 0.5 for home, so home loses rating
        assert elo.ratings["PSG"] < 1500
    
    def test_update_away_win(self):
        """Test rating update with away win."""
        elo = Ligue1EloRating(k_factor=20)
        elo.ratings["PSG"] = 1500
        elo.ratings["Marseille"] = 1500
        
        result = elo.update("PSG", "Marseille", 'away')
        
        assert elo.ratings["PSG"] < 1500
        assert elo.ratings["Marseille"] > 1500
    
    def test_update_returns_detailed_result(self):
        """Test that update returns detailed result dictionary."""
        elo = Ligue1EloRating()
        result = elo.update("PSG", "Marseille", 'home')
        
        assert 'home_team' in result
        assert 'away_team' in result
        assert 'home_rating_change' in result
        assert 'away_rating_change' in result
        assert 'home_new_rating' in result
        assert 'away_new_rating' in result
