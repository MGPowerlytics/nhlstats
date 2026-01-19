"""Tests for Elo rating modules - actual functions"""

import pytest
import pandas as pd
import numpy as np


class TestNBAEloRating:
    """Test NBAEloRating class"""
    
    def test_init(self):
        from nba_elo_rating import NBAEloRating
        elo = NBAEloRating()
        assert elo.k_factor == 20
        assert elo.home_advantage == 100
    
    def test_predict(self):
        from nba_elo_rating import NBAEloRating
        elo = NBAEloRating()
        prob = elo.predict('Lakers', 'Celtics')
        assert 0 < prob < 1
    
    def test_update(self):
        from nba_elo_rating import NBAEloRating
        elo = NBAEloRating()
        elo.update('Lakers', 'Celtics', home_won=True)
        assert elo.get_rating('Lakers') > 1500


class TestNHLEloRating:
    """Test NHLEloRating class"""
    
    def test_init(self):
        from nhl_elo_rating import NHLEloRating
        elo = NHLEloRating()
        assert elo.home_advantage == 50
    
    def test_predict(self):
        from nhl_elo_rating import NHLEloRating
        elo = NHLEloRating()
        prob = elo.predict('Boston Bruins', 'Toronto Maple Leafs')
        assert 0 < prob < 1


class TestMLBEloRating:
    """Test MLBEloRating class"""
    
    def test_init(self):
        from mlb_elo_rating import MLBEloRating
        elo = MLBEloRating()
        assert elo.k_factor == 20
    
    def test_predict(self):
        from mlb_elo_rating import MLBEloRating
        elo = MLBEloRating()
        prob = elo.predict('Red Sox', 'Yankees')
        assert 0 < prob < 1
    
    def test_update(self):
        from mlb_elo_rating import MLBEloRating
        elo = MLBEloRating()
        elo.update('Red Sox', 'Yankees', 5, 3)
        assert elo.get_rating('Red Sox') > 1500


class TestNFLEloRating:
    """Test NFLEloRating class"""
    
    def test_init(self):
        from nfl_elo_rating import NFLEloRating
        elo = NFLEloRating()
        assert elo.k_factor == 20
    
    def test_predict(self):
        from nfl_elo_rating import NFLEloRating
        elo = NFLEloRating()
        prob = elo.predict('Chiefs', '49ers')
        assert 0 < prob < 1
    
    def test_update(self):
        from nfl_elo_rating import NFLEloRating
        elo = NFLEloRating()
        elo.update('Chiefs', '49ers', 31, 24)
        assert elo.get_rating('Chiefs') > 1500


class TestNCAABEloRating:
    """Test NCAABEloRating class"""
    
    def test_init(self):
        from ncaab_elo_rating import NCAABEloRating
        elo = NCAABEloRating()
        assert elo.k_factor == 20
    
    def test_predict(self):
        from ncaab_elo_rating import NCAABEloRating
        elo = NCAABEloRating()
        prob = elo.predict('Duke', 'UNC')
        assert 0 < prob < 1


class TestTennisEloRating:
    """Test TennisEloRating class"""
    
    def test_init(self):
        from tennis_elo_rating import TennisEloRating
        elo = TennisEloRating()
        assert elo.k_factor > 0
    
    def test_predict(self):
        from tennis_elo_rating import TennisEloRating
        elo = TennisEloRating()
        prob = elo.predict('Djokovic', 'Federer')
        assert 0 < prob < 1
    
    def test_update(self):
        from tennis_elo_rating import TennisEloRating
        elo = TennisEloRating()
        elo.update('Djokovic', 'Federer')
        assert elo.get_rating('Djokovic') > 1500


class TestEPLEloRating:
    """Test EPLEloRating class"""
    
    def test_init(self):
        from epl_elo_rating import EPLEloRating
        elo = EPLEloRating()
        assert elo.k_factor == 20
    
    def test_predict(self):
        from epl_elo_rating import EPLEloRating
        elo = EPLEloRating()
        prob = elo.predict('Man City', 'Liverpool')
        assert 0 < prob < 1


class TestLigue1EloRating:
    """Test Ligue1EloRating class"""
    
    def test_init(self):
        from ligue1_elo_rating import Ligue1EloRating
        elo = Ligue1EloRating()
        assert elo.k_factor == 20
    
    def test_predict(self):
        from ligue1_elo_rating import Ligue1EloRating
        elo = Ligue1EloRating()
        prob = elo.predict('PSG', 'Marseille')
        assert 0 < prob < 1


class TestGlicko2Rating:
    """Test Glicko2Rating class"""
    
    def test_init(self):
        from glicko2_rating import Glicko2Rating
        rating = Glicko2Rating()
        assert rating is not None


class TestModuleImports:
    """Test all Elo rating modules can be imported"""
    
    def test_all_modules(self):
        import nba_elo_rating
        import nhl_elo_rating
        import mlb_elo_rating
        import nfl_elo_rating
        import ncaab_elo_rating
        import tennis_elo_rating
        import epl_elo_rating
        import ligue1_elo_rating
        import glicko2_rating
        
        assert True  # All imports succeeded
