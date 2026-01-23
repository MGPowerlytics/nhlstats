"""Targeted tests for nba_elo_rating.py code paths"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import json


class TestNBAEloRatingBasics:
    """Test basic NBAEloRating functionality"""

    def test_init_default(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating()
        assert elo.k_factor == 20
        assert elo.home_advantage == 100
        assert elo.initial_rating == 1500

    def test_init_custom(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating(k_factor=30, home_advantage=80, initial_rating=1400)
        assert elo.k_factor == 30
        assert elo.home_advantage == 80
        assert elo.initial_rating == 1400

    def test_get_rating_new_team(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating()
        rating = elo.get_rating('Boston Celtics')
        assert rating == 1500

    def test_get_rating_existing_team(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating()
        elo.ratings['Boston Celtics'] = 1600
        rating = elo.get_rating('Boston Celtics')
        assert rating == 1600


class TestNBAEloPredict:
    """Test predict method"""

    def test_predict_equal_teams(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating()
        # Equal rated teams - home should have ~64% due to home advantage of 100
        prob = elo.predict('Boston Celtics', 'Lakers')
        assert 0.5 < prob < 0.7  # Home advantage gives slight edge

    def test_predict_strong_home(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating()
        elo.ratings['Boston Celtics'] = 1700
        elo.ratings['Lakers'] = 1400
        prob = elo.predict('Boston Celtics', 'Lakers')
        assert prob > 0.8

    def test_predict_strong_away(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating()
        elo.ratings['Boston Celtics'] = 1300
        elo.ratings['Lakers'] = 1700
        prob = elo.predict('Boston Celtics', 'Lakers')
        assert prob < 0.3


class TestNBAEloUpdate:
    """Test update method"""

    def test_update_home_win(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating()
        initial_home = elo.get_rating('Boston Celtics')
        initial_away = elo.get_rating('Lakers')

        elo.update('Boston Celtics', 'Lakers', True)

        # Winner gains, loser loses
        assert elo.get_rating('Boston Celtics') > initial_home
        assert elo.get_rating('Lakers') < initial_away

    def test_update_away_win(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating()
        initial_home = elo.get_rating('Boston Celtics')
        initial_away = elo.get_rating('Lakers')

        elo.update('Boston Celtics', 'Lakers', False)

        # Home loses rating, away gains
        assert elo.get_rating('Boston Celtics') < initial_home
        assert elo.get_rating('Lakers') > initial_away

    def test_update_zero_sum(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating()
        initial_home = elo.get_rating('Boston Celtics')
        initial_away = elo.get_rating('Lakers')

        elo.update('Boston Celtics', 'Lakers', True)

        final_home = elo.get_rating('Boston Celtics')
        final_away = elo.get_rating('Lakers')

        # Total rating change should sum to zero
        home_change = final_home - initial_home
        away_change = final_away - initial_away
        assert abs(home_change + away_change) < 0.001


class TestExpectedScore:
    """Test expected score calculation"""

    def test_expected_score_equal(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating()
        # Use formula: 1 / (1 + 10^((rb - ra) / 400))
        expected = elo.expected_score(1500, 1500)
        assert abs(expected - 0.5) < 0.001

    def test_expected_score_better_a(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating()
        expected = elo.expected_score(1600, 1400)
        assert expected > 0.5

    def test_expected_score_better_b(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating()
        expected = elo.expected_score(1400, 1600)
        assert expected < 0.5


class TestKFactorImpact:
    """Test k-factor impacts"""

    def test_high_k_factor(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating(k_factor=50)

        initial = elo.get_rating('Celtics')
        elo.update('Celtics', 'Lakers', True)
        change = elo.get_rating('Celtics') - initial

        assert abs(change) > 10

    def test_low_k_factor(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating(k_factor=5)

        initial = elo.get_rating('Celtics')
        elo.update('Celtics', 'Lakers', True)
        change = elo.get_rating('Celtics') - initial

        assert abs(change) < 5


class TestHomeAdvantageImpact:
    """Test home advantage impacts"""

    def test_no_home_advantage(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating(home_advantage=0)

        prob = elo.predict('Celtics', 'Lakers')
        assert abs(prob - 0.5) < 0.01

    def test_high_home_advantage(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating(home_advantage=200)

        prob = elo.predict('Celtics', 'Lakers')
        assert prob > 0.7


class TestMultipleGames:
    """Test rating stability over multiple games"""

    def test_ratings_converge(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating()

        # Simulate many games
        for _ in range(100):
            elo.update('Celtics', 'Lakers', True)

        # Celtics should be rated much higher
        assert elo.get_rating('Celtics') > elo.get_rating('Lakers') + 300

    def test_ratings_balance(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating()

        # Alternate wins
        for i in range(100):
            elo.update('Celtics', 'Lakers', i % 2 == 0)

        # Ratings should be relatively close (within 150 points)
        diff = abs(elo.get_rating('Celtics') - elo.get_rating('Lakers'))
        assert diff < 150


class TestModuleImports:
    """Test module imports and structure"""

    def test_import_module(self):
        from plugins.elo import NBAEloRating
        assert NBAEloRating is not None

    def test_class_interface(self):
        from plugins.elo import NBAEloRating
        elo = NBAEloRating()

        assert hasattr(elo, 'predict')
        assert hasattr(elo, 'update')
        assert hasattr(elo, 'get_rating')
        assert hasattr(elo, 'expected_score')
        assert hasattr(elo, 'ratings')
