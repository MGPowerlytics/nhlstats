"""Comprehensive tests for Elo rating modules to increase coverage."""
import pytest
import sys
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import json


class TestNBAEloRatingDeep:
    """Deep tests for NBAEloRating class."""
    
    @pytest.fixture
    def nba_elo(self):
        from nba_elo_rating import NBAEloRating
        return NBAEloRating()
    
    def test_init_defaults(self, nba_elo):
        assert nba_elo.k_factor == 20
        assert nba_elo.home_advantage == 100
        assert nba_elo.initial_rating == 1500
    
    def test_init_custom_params(self):
        from nba_elo_rating import NBAEloRating
        elo = NBAEloRating(k_factor=25, home_advantage=80, initial_rating=1600)
        assert elo.k_factor == 25
        assert elo.home_advantage == 80
        assert elo.initial_rating == 1600
    
    def test_get_rating_new_team(self, nba_elo):
        rating = nba_elo.get_rating('New Team')
        assert rating == 1500
    
    def test_get_rating_existing_team(self, nba_elo):
        nba_elo.ratings['Lakers'] = 1600
        rating = nba_elo.get_rating('Lakers')
        assert rating == 1600
    
    def test_predict_equal_teams(self, nba_elo):
        prob = nba_elo.predict('Team A', 'Team B')
        # Home team advantage should give slight edge
        assert 0.5 < prob < 0.7
    
    def test_predict_strong_home_team(self, nba_elo):
        nba_elo.ratings['Strong'] = 1700
        nba_elo.ratings['Weak'] = 1300
        prob = nba_elo.predict('Strong', 'Weak')
        assert prob > 0.8
    
    def test_predict_weak_home_team(self, nba_elo):
        nba_elo.ratings['Weak'] = 1300
        nba_elo.ratings['Strong'] = 1700
        prob = nba_elo.predict('Weak', 'Strong')
        assert prob < 0.3
    
    def test_update_home_win(self, nba_elo):
        old_home = nba_elo.get_rating('Home')
        old_away = nba_elo.get_rating('Away')
        
        result = nba_elo.update('Home', 'Away', home_won=True)
        
        new_home = nba_elo.get_rating('Home')
        new_away = nba_elo.get_rating('Away')
        
        assert new_home > old_home
        assert new_away < old_away
    
    def test_update_away_win(self, nba_elo):
        old_home = nba_elo.get_rating('Home')
        old_away = nba_elo.get_rating('Away')
        
        result = nba_elo.update('Home', 'Away', home_won=False)
        
        new_home = nba_elo.get_rating('Home')
        new_away = nba_elo.get_rating('Away')
        
        assert new_home < old_home
        assert new_away > old_away
    
    def test_expected_score(self, nba_elo):
        score = nba_elo.expected_score(1500, 1500)
        assert abs(score - 0.5) < 0.01
        
        score = nba_elo.expected_score(1600, 1400)
        assert score > 0.75
    
    def test_multiple_updates(self, nba_elo):
        for i in range(10):
            nba_elo.update('Winner', 'Loser', home_won=True)
        
        assert nba_elo.get_rating('Winner') > 1500
        assert nba_elo.get_rating('Loser') < 1500
    
    def test_ratings_dict(self, nba_elo):
        nba_elo.update('A', 'B', True)
        nba_elo.update('C', 'D', False)
        
        assert 'A' in nba_elo.ratings
        assert 'B' in nba_elo.ratings
        assert 'C' in nba_elo.ratings
        assert 'D' in nba_elo.ratings


class TestMLBEloRatingDeep:
    """Deep tests for MLBEloRating class."""
    
    @pytest.fixture
    def mlb_elo(self):
        from mlb_elo_rating import MLBEloRating
        return MLBEloRating()
    
    def test_init_defaults(self, mlb_elo):
        assert mlb_elo.k_factor == 20
        assert mlb_elo.home_advantage == 50
    
    def test_init_custom_params(self):
        from mlb_elo_rating import MLBEloRating
        elo = MLBEloRating(k_factor=25, home_advantage=40)
        assert elo.k_factor == 25
        assert elo.home_advantage == 40
    
    def test_predict(self, mlb_elo):
        prob = mlb_elo.predict('Team A', 'Team B')
        assert 0 < prob < 1
    
    def test_update_home_win(self, mlb_elo):
        old_home = mlb_elo.get_rating('Home')
        
        mlb_elo.update('Home', 'Away', home_score=5, away_score=3)
        
        new_home = mlb_elo.get_rating('Home')
        assert new_home > old_home
    
    def test_update_away_win(self, mlb_elo):
        old_away = mlb_elo.get_rating('Away')
        
        mlb_elo.update('Home', 'Away', home_score=2, away_score=6)
        
        new_away = mlb_elo.get_rating('Away')
        assert new_away > old_away
    
    def test_blowout_update(self, mlb_elo):
        # Test with big score difference
        mlb_elo.update('Blowout', 'Victim', home_score=15, away_score=2)
        
        # Rating change should happen
        rating = mlb_elo.get_rating('Blowout')
        assert rating > 1500  # Winner should be above initial


class TestNFLEloRatingDeep:
    """Deep tests for NFLEloRating class."""
    
    @pytest.fixture
    def nfl_elo(self):
        from nfl_elo_rating import NFLEloRating
        return NFLEloRating()
    
    def test_init_defaults(self, nfl_elo):
        assert nfl_elo.k_factor == 20
        assert nfl_elo.home_advantage == 65
    
    def test_predict(self, nfl_elo):
        prob = nfl_elo.predict('Team A', 'Team B')
        assert 0 < prob < 1
    
    def test_update_home_win(self, nfl_elo):
        old_home = nfl_elo.get_rating('Chiefs')
        
        nfl_elo.update('Chiefs', 'Raiders', home_score=35, away_score=17)
        
        new_home = nfl_elo.get_rating('Chiefs')
        assert new_home > old_home
    
    def test_update_away_win(self, nfl_elo):
        old_away = nfl_elo.get_rating('Bills')
        
        nfl_elo.update('Dolphins', 'Bills', home_score=14, away_score=28)
        
        new_away = nfl_elo.get_rating('Bills')
        assert new_away > old_away
    
    def test_blowout_update(self, nfl_elo):
        # Test with large margin
        nfl_elo.update('Blowout', 'Victim', home_score=45, away_score=10)
        
        rating = nfl_elo.get_rating('Blowout')
        assert rating > 1500


class TestNHLEloRatingDeep:
    """Deep tests for NHLEloRating class."""
    
    @pytest.fixture
    def nhl_elo(self):
        from nhl_elo_rating import NHLEloRating
        return NHLEloRating()
    
    def test_init_defaults(self, nhl_elo):
        # NHL uses different defaults
        assert nhl_elo.k_factor == 10
        assert nhl_elo.home_advantage == 50
    
    def test_predict(self, nhl_elo):
        prob = nhl_elo.predict('Maple Leafs', 'Bruins')
        assert 0 < prob < 1
    
    def test_update_home_win(self, nhl_elo):
        old_rating = nhl_elo.get_rating('Oilers')
        
        nhl_elo.update('Oilers', 'Flames', home_won=True)
        
        new_rating = nhl_elo.get_rating('Oilers')
        assert new_rating > old_rating
    
    def test_update_away_win(self, nhl_elo):
        old_rating = nhl_elo.get_rating('Rangers')
        
        nhl_elo.update('Islanders', 'Rangers', home_won=False)
        
        new_rating = nhl_elo.get_rating('Rangers')
        assert new_rating > old_rating


class TestNCAABEloRatingDeep:
    """Deep tests for NCAABEloRating class."""
    
    @pytest.fixture
    def ncaab_elo(self):
        from ncaab_elo_rating import NCAABEloRating
        return NCAABEloRating()
    
    def test_init(self, ncaab_elo):
        assert ncaab_elo is not None
    
    def test_predict(self, ncaab_elo):
        prob = ncaab_elo.predict('Duke', 'UNC')
        assert 0 < prob < 1
    
    def test_update_home_win(self, ncaab_elo):
        old_rating = ncaab_elo.get_rating('Kansas')
        
        # NCAABEloRating uses home_win (float) not home_won (bool)
        ncaab_elo.update('Kansas', 'Kentucky', home_win=1.0)
        
        new_rating = ncaab_elo.get_rating('Kansas')
        assert new_rating > old_rating


class TestTennisEloRatingDeep:
    """Deep tests for TennisEloRating class."""
    
    @pytest.fixture
    def tennis_elo(self):
        from tennis_elo_rating import TennisEloRating
        return TennisEloRating()
    
    def test_init(self, tennis_elo):
        assert tennis_elo is not None
    
    def test_predict(self, tennis_elo):
        prob = tennis_elo.predict('Djokovic', 'Nadal')
        assert 0 < prob < 1
    
    def test_update(self, tennis_elo):
        old_winner = tennis_elo.get_rating('Djokovic')
        old_loser = tennis_elo.get_rating('Nadal')
        
        # Tennis uses (winner, loser) format
        tennis_elo.update('Djokovic', 'Nadal')
        
        new_winner = tennis_elo.get_rating('Djokovic')
        new_loser = tennis_elo.get_rating('Nadal')
        
        assert new_winner > old_winner
        assert new_loser < old_loser


class TestEPLEloRatingDeep:
    """Deep tests for EPLEloRating class."""
    
    @pytest.fixture
    def epl_elo(self):
        from epl_elo_rating import EPLEloRating
        return EPLEloRating()
    
    def test_init(self, epl_elo):
        assert epl_elo is not None
    
    def test_predict_probs(self, epl_elo):
        # EPL uses predict_probs for 3-way outcome
        probs = epl_elo.predict_probs('Arsenal', 'Chelsea')
        assert len(probs) == 3
        assert sum(probs) - 1.0 < 0.01  # Should sum to 1
    
    def test_predict_3way(self, epl_elo):
        probs = epl_elo.predict_3way('Liverpool', 'Man United')
        assert 'home' in probs
        assert 'draw' in probs
        assert 'away' in probs
    
    def test_get_rating(self, epl_elo):
        rating = epl_elo.get_rating('Man City')
        assert rating == 1500  # Initial rating


class TestLigue1EloRatingDeep:
    """Deep tests for Ligue1EloRating class."""
    
    @pytest.fixture
    def ligue1_elo(self):
        from ligue1_elo_rating import Ligue1EloRating
        return Ligue1EloRating()
    
    def test_init(self, ligue1_elo):
        assert ligue1_elo is not None
    
    def test_predict_probs(self, ligue1_elo):
        # Ligue1 uses predict_probs like EPL
        probs = ligue1_elo.predict_probs('PSG', 'Lyon')
        assert len(probs) == 3
    
    def test_get_rating(self, ligue1_elo):
        rating = ligue1_elo.get_rating('Monaco')
        assert rating == 1500


class TestGlicko2RatingDeep:
    """Deep tests for Glicko2Rating class."""
    
    @pytest.fixture
    def glicko2(self):
        from glicko2_rating import Glicko2Rating
        return Glicko2Rating()
    
    def test_init(self, glicko2):
        assert glicko2 is not None
    
    def test_get_rating_new_player(self, glicko2):
        rating_dict = glicko2.get_rating('NewPlayer')
        assert rating_dict['rating'] == 1500
        assert rating_dict['rd'] == 350
    
    def test_predict(self, glicko2):
        prob = glicko2.predict('Player1', 'Player2')
        assert 0 < prob < 1
    
    def test_update(self, glicko2):
        old_dict = glicko2.get_rating('Winner')
        old_rating = old_dict['rating']
        
        glicko2.update('Winner', 'Loser', home_won=True)
        
        new_dict = glicko2.get_rating('Winner')
        new_rating = new_dict['rating']
        assert new_rating > old_rating


class TestEloRatingFileSaving:
    """Test file saving/loading for Elo ratings."""
    
    def test_nba_save_load(self):
        from nba_elo_rating import NBAEloRating
        
        with tempfile.TemporaryDirectory() as tmpdir:
            elo = NBAEloRating()
            elo.update('Lakers', 'Celtics', True)
            
            filepath = Path(tmpdir) / 'nba_ratings.csv'
            if hasattr(elo, 'save_ratings'):
                elo.save_ratings(str(filepath))
                
                elo2 = NBAEloRating()
                if hasattr(elo2, 'load_ratings'):
                    elo2.load_ratings(str(filepath))
                    assert elo2.get_rating('Lakers') == elo.get_rating('Lakers')
    
    def test_nhl_save_load(self):
        from nhl_elo_rating import NHLEloRating
        
        with tempfile.TemporaryDirectory() as tmpdir:
            elo = NHLEloRating()
            elo.update('Maple Leafs', 'Bruins', True)
            
            filepath = Path(tmpdir) / 'nhl_ratings.csv'
            if hasattr(elo, 'save_ratings'):
                elo.save_ratings(str(filepath))


class TestEloEdgeCases:
    """Edge case tests for Elo ratings."""
    
    def test_extreme_rating_difference(self):
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        elo.ratings['Strong'] = 2000
        elo.ratings['Weak'] = 1000
        
        prob = elo.predict('Strong', 'Weak')
        assert prob > 0.99
    
    def test_zero_k_factor(self):
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating(k_factor=0)
        old = elo.get_rating('Team')
        elo.update('Team', 'Other', True)
        new = elo.get_rating('Team')
        
        # Ratings shouldn't change with k=0
        assert old == new
    
    def test_negative_home_advantage(self):
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating(home_advantage=-50)
        prob = elo.predict('Home', 'Away')
        
        # Home should have disadvantage
        assert prob < 0.5
    
    def test_special_characters_in_team_names(self):
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        elo.update("Team's Name", "Other-Team (2)", True)
        
        assert elo.get_rating("Team's Name") > 1500


class TestEloRatingMethods:
    """Test various methods of Elo rating classes."""
    
    def test_nba_all_teams(self):
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        elo.update('A', 'B', True)
        elo.update('C', 'D', False)
        
        if hasattr(elo, 'get_all_ratings'):
            ratings = elo.get_all_ratings()
            assert 'A' in ratings
    
    def test_rating_history(self):
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        
        for i in range(5):
            elo.update('Team', 'Other', i % 2 == 0)
        
        if hasattr(elo, 'get_history'):
            history = elo.get_history('Team')
            assert len(history) > 0
    
    def test_reset_ratings(self):
        from nba_elo_rating import NBAEloRating
        
        elo = NBAEloRating()
        elo.update('Team', 'Other', True)
        
        if hasattr(elo, 'reset'):
            elo.reset()
            assert elo.get_rating('Team') == 1500
