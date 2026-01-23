"""Deep tests for nba_elo_rating.py targeting uncovered lines"""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
import tempfile
from pathlib import Path
import pandas as pd
import json


class TestNBAEloRatingMethods:
    """More tests for NBAEloRating class"""

    def test_game_history_tracking(self):
        from plugins.elo import NBAEloRating

        elo = NBAEloRating()

        # Game history should exist
        assert hasattr(elo, 'game_history')
        assert isinstance(elo.game_history, list)

    def test_multiple_teams(self):
        from plugins.elo import NBAEloRating

        elo = NBAEloRating()

        teams = ['Celtics', 'Lakers', 'Bulls', 'Heat', 'Knicks']

        for team in teams:
            rating = elo.get_rating(team)
            assert rating == 1500

        assert len(elo.ratings) == 5

    def test_rating_changes_are_symmetric(self):
        from plugins.elo import NBAEloRating

        elo = NBAEloRating()

        # Get initial ratings
        home_before = elo.get_rating('Celtics')
        away_before = elo.get_rating('Lakers')

        # Update
        elo.update('Celtics', 'Lakers', True)

        home_after = elo.get_rating('Celtics')
        away_after = elo.get_rating('Lakers')

        # Changes should be equal and opposite
        home_change = home_after - home_before
        away_change = away_after - away_before

        assert abs(home_change + away_change) < 0.001

    def test_prediction_bounds(self):
        from plugins.elo import NBAEloRating

        elo = NBAEloRating()

        # Very strong home team
        elo.ratings['Celtics'] = 2000
        elo.ratings['Lakers'] = 1000

        prob = elo.predict('Celtics', 'Lakers')
        assert 0 < prob <= 1
        assert prob > 0.9  # Very high probability

    def test_prediction_very_strong_away(self):
        from plugins.elo import NBAEloRating

        elo = NBAEloRating()

        # Very strong away team
        elo.ratings['Celtics'] = 1000
        elo.ratings['Lakers'] = 2000

        prob = elo.predict('Celtics', 'Lakers')
        assert 0 <= prob < 1
        assert prob < 0.2  # Very low probability for home win


class TestExpectedScore:
    """Test expected score calculation edge cases"""

    def test_expected_score_100_point_diff(self):
        from plugins.elo import NBAEloRating

        elo = NBAEloRating()
        expected = elo.expected_score(1600, 1500)

        # 100 point difference should give ~64%
        assert 0.60 < expected < 0.68

    def test_expected_score_200_point_diff(self):
        from plugins.elo import NBAEloRating

        elo = NBAEloRating()
        expected = elo.expected_score(1700, 1500)

        # 200 point difference should give ~76%
        assert 0.70 < expected < 0.80

    def test_expected_score_400_point_diff(self):
        from plugins.elo import NBAEloRating

        elo = NBAEloRating()
        expected = elo.expected_score(1900, 1500)

        # 400 point difference should give ~90%
        assert 0.85 < expected < 0.95


class TestUpdateScenarios:
    """Test various update scenarios"""

    def test_upset_causes_bigger_change(self):
        from plugins.elo import NBAEloRating

        elo1 = NBAEloRating()
        elo2 = NBAEloRating()

        # Expected result
        elo1.ratings['StrongTeam'] = 1600
        elo1.ratings['WeakTeam'] = 1400
        elo1.update('StrongTeam', 'WeakTeam', True)
        expected_change = elo1.get_rating('StrongTeam') - 1600

        # Upset
        elo2.ratings['StrongTeam'] = 1600
        elo2.ratings['WeakTeam'] = 1400
        elo2.update('StrongTeam', 'WeakTeam', False)  # Upset!
        upset_change = elo2.get_rating('StrongTeam') - 1600

        # Upset should cause bigger loss
        assert abs(upset_change) > abs(expected_change)

    def test_many_consecutive_wins(self):
        from plugins.elo import NBAEloRating

        elo = NBAEloRating()

        for _ in range(50):
            elo.update('Winner', 'Loser', True)

        # Winner should have much higher rating
        assert elo.get_rating('Winner') > 1600
        assert elo.get_rating('Loser') < 1400


class TestModuleImports:
    """Test module imports"""

    def test_import_all(self):
        # We can't import the module directly because it's inside plugins.elo
        # But we can import the class from plugins.elo
        from plugins.elo import NBAEloRating
        assert NBAEloRating is not None

    def test_class_attributes(self):
        from plugins.elo import NBAEloRating

        elo = NBAEloRating()

        # Check all expected attributes
        assert hasattr(elo, 'k_factor')
        assert hasattr(elo, 'home_advantage')
        assert hasattr(elo, 'initial_rating')
        assert hasattr(elo, 'ratings')
        assert hasattr(elo, 'game_history')
