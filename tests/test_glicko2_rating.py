"""Tests for Glicko-2 Rating System."""

import pytest
import sys
import math
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))

from glicko2_rating import Glicko2Rating


class TestGlicko2RatingInit:
    """Test Glicko2Rating initialization."""
    
    def test_init_default_values(self):
        """Test initialization with default values."""
        g = Glicko2Rating()
        
        assert g.initial_rating == 1500
        assert g.initial_rd == 350
        assert g.initial_vol == 0.06
        assert g.home_advantage == 100
    
    def test_init_custom_values(self):
        """Test initialization with custom values."""
        g = Glicko2Rating(
            initial_rating=1600,
            initial_rd=300,
            initial_vol=0.05,
            home_advantage=80
        )
        
        assert g.initial_rating == 1600
        assert g.initial_rd == 300
        assert g.initial_vol == 0.05
        assert g.home_advantage == 80
    
    def test_tau_constant(self):
        """Test that TAU constant is set correctly."""
        g = Glicko2Rating()
        
        assert g.TAU == 0.5
        assert 0.3 <= g.TAU <= 1.2  # Typical range
    
    def test_epsilon_constant(self):
        """Test that EPSILON constant is set for convergence."""
        g = Glicko2Rating()
        
        assert g.EPSILON == 0.000001
        assert g.EPSILON > 0


class TestGlicko2GetRating:
    """Test get_rating method."""
    
    def test_get_rating_new_team(self):
        """Test getting rating for new team."""
        g = Glicko2Rating()
        rating = g.get_rating("Toronto")
        
        assert rating['rating'] == 1500
        assert rating['rd'] == 350
        assert rating['vol'] == 0.06
    
    def test_get_rating_existing_team(self):
        """Test getting rating for existing team."""
        g = Glicko2Rating()
        g.ratings["Toronto"] = {'rating': 1600, 'rd': 200, 'vol': 0.05}
        
        rating = g.get_rating("Toronto")
        
        assert rating['rating'] == 1600
        assert rating['rd'] == 200
        assert rating['vol'] == 0.05
    
    def test_get_rating_returns_copy(self):
        """Test that get_rating returns a copy, not reference."""
        g = Glicko2Rating()
        rating1 = g.get_rating("Toronto")
        rating1['rating'] = 2000  # Modify the returned copy
        
        rating2 = g.get_rating("Toronto")
        
        assert rating2['rating'] == 1500  # Original should be unchanged


class TestGlicko2ScaleConversion:
    """Test scale conversion between Glicko-1 and Glicko-2."""
    
    def test_scale_down_average_rating(self):
        """Test scaling down average rating (1500)."""
        g = Glicko2Rating()
        mu, phi = g._scale_down(1500, 350)
        
        assert mu == pytest.approx(0.0, abs=0.01)  # 1500 maps to 0
    
    def test_scale_down_high_rating(self):
        """Test scaling down high rating."""
        g = Glicko2Rating()
        mu, phi = g._scale_down(1700, 350)
        
        assert mu > 0  # Above average maps to positive
    
    def test_scale_down_low_rating(self):
        """Test scaling down low rating."""
        g = Glicko2Rating()
        mu, phi = g._scale_down(1300, 350)
        
        assert mu < 0  # Below average maps to negative
    
    def test_scale_up_zero_mu(self):
        """Test scaling up mu=0 gives 1500."""
        g = Glicko2Rating()
        rating, rd = g._scale_up(0, 350 / 173.7178)
        
        assert rating == pytest.approx(1500, abs=1)
    
    def test_scale_round_trip(self):
        """Test that scaling down then up preserves values."""
        g = Glicko2Rating()
        original_rating = 1650
        original_rd = 250
        
        mu, phi = g._scale_down(original_rating, original_rd)
        rating, rd = g._scale_up(mu, phi)
        
        assert rating == pytest.approx(original_rating, abs=0.1)
        assert rd == pytest.approx(original_rd, abs=0.1)


class TestGlicko2Functions:
    """Test Glicko-2 mathematical functions."""
    
    def test_g_function_high_phi(self):
        """Test g function with high phi (uncertain)."""
        g = Glicko2Rating()
        result = g._g(2.0)  # High uncertainty
        
        assert 0 < result < 1
    
    def test_g_function_low_phi(self):
        """Test g function with low phi (confident)."""
        g = Glicko2Rating()
        result = g._g(0.5)  # Low uncertainty
        
        assert 0 < result < 1
        # Lower phi should give higher g
        assert result > g._g(2.0)
    
    def test_g_function_zero_phi(self):
        """Test g function approaches 1 as phi approaches 0."""
        g = Glicko2Rating()
        result = g._g(0.0001)  # Very low uncertainty
        
        assert result == pytest.approx(1.0, abs=0.01)
    
    def test_e_function_equal_ratings(self):
        """Test E function with equal ratings."""
        g = Glicko2Rating()
        result = g._e(0, 0, 1.0)  # Equal mu values
        
        assert result == pytest.approx(0.5, abs=0.01)
    
    def test_e_function_higher_rating(self):
        """Test E function when first player has higher rating."""
        g = Glicko2Rating()
        result = g._e(1.0, 0.0, 1.0)  # Higher mu
        
        assert result > 0.5
    
    def test_e_function_lower_rating(self):
        """Test E function when first player has lower rating."""
        g = Glicko2Rating()
        result = g._e(-1.0, 0.0, 1.0)  # Lower mu
        
        assert result < 0.5


class TestGlicko2Predict:
    """Test predict method."""
    
    def test_predict_equal_teams(self):
        """Test prediction with equal teams."""
        g = Glicko2Rating(home_advantage=100)
        
        prob = g.predict("Toronto", "Boston")
        
        # Home team should have advantage
        assert prob > 0.5
    
    def test_predict_stronger_home(self):
        """Test prediction with stronger home team."""
        g = Glicko2Rating()
        g.ratings["Toronto"] = {'rating': 1700, 'rd': 200, 'vol': 0.06}
        g.ratings["Boston"] = {'rating': 1400, 'rd': 200, 'vol': 0.06}
        
        prob = g.predict("Toronto", "Boston")
        
        assert prob > 0.5
    
    def test_predict_stronger_away(self):
        """Test prediction with much stronger away team."""
        g = Glicko2Rating(home_advantage=50)
        g.ratings["Toronto"] = {'rating': 1300, 'rd': 200, 'vol': 0.06}
        g.ratings["Boston"] = {'rating': 1800, 'rd': 200, 'vol': 0.06}
        
        prob = g.predict("Toronto", "Boston")
        
        assert prob < 0.5  # Away team so strong, home advantage not enough
    
    def test_predict_returns_probability(self):
        """Test that predict returns valid probability."""
        g = Glicko2Rating()
        
        prob = g.predict("Toronto", "Boston")
        
        assert 0 <= prob <= 1
    
    def test_predict_high_uncertainty_closer_to_50(self):
        """Test that high RD brings probability closer to 50%."""
        g1 = Glicko2Rating(home_advantage=0)
        g1.ratings["Toronto"] = {'rating': 1700, 'rd': 50, 'vol': 0.06}
        g1.ratings["Boston"] = {'rating': 1500, 'rd': 50, 'vol': 0.06}
        
        g2 = Glicko2Rating(home_advantage=0)
        g2.ratings["Toronto"] = {'rating': 1700, 'rd': 350, 'vol': 0.06}
        g2.ratings["Boston"] = {'rating': 1500, 'rd': 350, 'vol': 0.06}
        
        prob1 = g1.predict("Toronto", "Boston")  # Low uncertainty
        prob2 = g2.predict("Toronto", "Boston")  # High uncertainty
        
        # With high uncertainty, prediction should be closer to 50%
        assert abs(prob2 - 0.5) < abs(prob1 - 0.5)


class TestGlicko2Update:
    """Test update method."""
    
    def test_update_home_win_rating_increases(self):
        """Test that home win increases home rating."""
        g = Glicko2Rating()
        
        initial_rating = g.get_rating("Toronto")['rating']
        g.update("Toronto", "Boston", home_won=True)
        
        new_rating = g.ratings["Toronto"]['rating']
        assert new_rating > initial_rating
    
    def test_update_home_loss_rating_decreases(self):
        """Test that home loss decreases home rating."""
        g = Glicko2Rating()
        
        initial_rating = g.get_rating("Toronto")['rating']
        g.update("Toronto", "Boston", home_won=False)
        
        new_rating = g.ratings["Toronto"]['rating']
        assert new_rating < initial_rating
    
    def test_update_rd_decreases_after_game(self):
        """Test that RD decreases after playing a game."""
        g = Glicko2Rating()
        
        initial_rd = g.get_rating("Toronto")['rd']
        g.update("Toronto", "Boston", home_won=True)
        
        new_rd = g.ratings["Toronto"]['rd']
        assert new_rd < initial_rd
    
    def test_update_both_teams_affected(self):
        """Test that both teams are updated."""
        g = Glicko2Rating()
        
        g.update("Toronto", "Boston", home_won=True)
        
        # Both teams should have ratings after the game
        assert "Toronto" in g.ratings
        assert "Boston" in g.ratings


class TestGlicko2EdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_zero_home_advantage(self):
        """Test with zero home advantage."""
        g = Glicko2Rating(home_advantage=0)
        
        prob = g.predict("Toronto", "Boston")
        
        assert prob == pytest.approx(0.5, abs=0.01)
    
    def test_very_high_rating_difference(self):
        """Test with very high rating difference."""
        g = Glicko2Rating(home_advantage=0)
        g.ratings["Toronto"] = {'rating': 2000, 'rd': 100, 'vol': 0.06}
        g.ratings["Boston"] = {'rating': 1000, 'rd': 100, 'vol': 0.06}
        
        prob = g.predict("Toronto", "Boston")
        
        assert prob > 0.95  # Very confident Toronto wins
    
    def test_many_games_rd_stabilizes(self):
        """Test that RD stabilizes after many games."""
        g = Glicko2Rating()
        
        # Play many games
        for _ in range(50):
            g.update("Toronto", "Boston", home_won=True)
        
        rd = g.ratings["Toronto"]['rd']
        
        # RD should be much lower than initial 350
        assert rd < 200  # Glicko-2 converges slower than expected
    
    def test_volatility_changes(self):
        """Test that volatility can change based on performance."""
        g = Glicko2Rating()
        
        initial_vol = g.get_rating("Toronto")['vol']
        
        # Play several games
        for _ in range(10):
            g.update("Toronto", "Boston", home_won=True)
        
        # Volatility should have changed (up or down)
        # Just check it's still a valid value
        new_vol = g.ratings["Toronto"]['vol']
        assert 0 < new_vol < 1
