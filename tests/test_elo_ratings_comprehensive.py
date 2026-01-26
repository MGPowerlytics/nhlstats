"""More tests for elo rating modules (mlb, nfl, ncaab)"""


class TestMLBEloRating:
    """Test MLBEloRating class"""

    def test_init_default(self):
        from plugins.elo import MLBEloRating

        elo = MLBEloRating()
        assert elo.k_factor == 20
        assert elo.home_advantage == 50

    def test_init_custom(self):
        from plugins.elo import MLBEloRating

        elo = MLBEloRating(k_factor=30, home_advantage=40)
        assert elo.k_factor == 30
        assert elo.home_advantage == 40

    def test_get_rating_new_team(self):
        from plugins.elo import MLBEloRating

        elo = MLBEloRating()
        rating = elo.get_rating("Yankees")
        assert rating == 1500

    def test_predict_equal_teams(self):
        from plugins.elo import MLBEloRating

        elo = MLBEloRating()
        prob = elo.predict("Yankees", "Red Sox")
        assert 0.4 < prob < 0.7

    def test_update(self):
        from plugins.elo import MLBEloRating

        elo = MLBEloRating()
        initial = elo.get_rating("Yankees")

        # Home win
        elo.update("Yankees", "Red Sox", 5, 2)

        # Winner should gain rating
        assert elo.get_rating("Yankees") > initial

    def test_update_away_win(self):
        from plugins.elo import MLBEloRating

        elo = MLBEloRating()
        initial_away = elo.get_rating("Red Sox")

        # Away win
        elo.update("Yankees", "Red Sox", 2, 5)

        # Away team should gain rating
        assert elo.get_rating("Red Sox") > initial_away


class TestNFLEloRating:
    """Test NFLEloRating class"""

    def test_init_default(self):
        from plugins.elo import NFLEloRating

        elo = NFLEloRating()
        assert elo.k_factor == 20
        assert elo.home_advantage == 65

    def test_init_custom(self):
        from plugins.elo import NFLEloRating

        elo = NFLEloRating(k_factor=25, home_advantage=55)
        assert elo.k_factor == 25
        assert elo.home_advantage == 55

    def test_get_rating_new_team(self):
        from plugins.elo import NFLEloRating

        elo = NFLEloRating()
        rating = elo.get_rating("Patriots")
        assert rating == 1500

    def test_predict_equal_teams(self):
        from plugins.elo import NFLEloRating

        elo = NFLEloRating()
        prob = elo.predict("Patriots", "Bills")
        assert 0.4 < prob < 0.7

    def test_update(self):
        from plugins.elo import NFLEloRating

        elo = NFLEloRating()
        initial = elo.get_rating("Patriots")

        # Home win
        elo.update("Patriots", "Bills", 28, 21)

        assert elo.get_rating("Patriots") > initial

    def test_update_away_win(self):
        from plugins.elo import NFLEloRating

        elo = NFLEloRating()
        initial_away = elo.get_rating("Bills")

        # Away win
        elo.update("Patriots", "Bills", 14, 35)

        assert elo.get_rating("Bills") > initial_away


class TestNCAABEloRating:
    """Test NCAABEloRating class"""

    def test_init_default(self):
        from plugins.elo import NCAABEloRating

        elo = NCAABEloRating()
        assert elo.k_factor == 20

    def test_get_rating_new_team(self):
        from plugins.elo import NCAABEloRating

        elo = NCAABEloRating()
        rating = elo.get_rating("Duke")
        assert rating == 1500

    def test_predict(self):
        from plugins.elo import NCAABEloRating

        elo = NCAABEloRating()
        prob = elo.predict("Duke", "Kentucky")
        assert 0 < prob < 1

    def test_update(self):
        from plugins.elo import NCAABEloRating

        elo = NCAABEloRating()
        initial = elo.get_rating("Duke")

        # Home win
        elo.update("Duke", "Kentucky", 1.0)

        assert elo.get_rating("Duke") > initial


class TestEloFormula:
    """Test Elo formula calculations"""

    def test_expected_score_equal(self):
        from plugins.elo import MLBEloRating

        elo = MLBEloRating()
        # Use formula: 1 / (1 + 10^((rb - ra) / 400))
        expected = elo.expected_score(1500, 1500)
        assert abs(expected - 0.5) < 0.01

    def test_expected_score_higher_rating(self):
        from plugins.elo import NFLEloRating

        elo = NFLEloRating()
        expected = elo.expected_score(1600, 1400)
        assert expected > 0.5

    def test_expected_score_lower_rating(self):
        from plugins.elo import MLBEloRating

        elo = MLBEloRating()
        expected = elo.expected_score(1400, 1600)
        assert expected < 0.5


class TestKFactorImpact:
    """Test k-factor impact on rating changes"""

    def test_high_k_factor_bigger_changes(self):
        from plugins.elo import MLBEloRating

        elo_low_k = MLBEloRating(k_factor=10)
        elo_high_k = MLBEloRating(k_factor=40)

        # Same update
        elo_low_k.update("Team A", "Team B", 5, 2)
        elo_high_k.update("Team A", "Team B", 5, 2)

        change_low = abs(elo_low_k.get_rating("Team A") - 1500)
        change_high = abs(elo_high_k.get_rating("Team A") - 1500)

        assert change_high > change_low


class TestHomeAdvantageImpact:
    """Test home advantage impact on predictions"""

    def test_no_home_advantage(self):
        from plugins.elo import MLBEloRating

        elo = MLBEloRating(home_advantage=0)
        prob = elo.predict("Team A", "Team B")

        # Should be close to 50%
        assert abs(prob - 0.5) < 0.01

    def test_large_home_advantage(self):
        from plugins.elo import NFLEloRating

        elo = NFLEloRating(home_advantage=200)
        prob = elo.predict("Team A", "Team B")

        # Should favor home team
        assert prob > 0.6


class TestMultipleGames:
    """Test rating stability over multiple games"""

    def test_ratings_converge_mlb(self):
        from plugins.elo import MLBEloRating

        elo = MLBEloRating()

        for _ in range(50):
            elo.update("Team A", "Team B", 5, 2)

        # Team A should be rated higher
        assert elo.get_rating("Team A") > elo.get_rating("Team B")

    def test_ratings_converge_nfl(self):
        from plugins.elo import NFLEloRating

        elo = NFLEloRating()

        for _ in range(20):
            elo.update("Team A", "Team B", 28, 14)

        assert elo.get_rating("Team A") > elo.get_rating("Team B")


class TestModuleImports:
    """Test module imports."""

    def test_mlb_elo_import(self):
        from plugins.elo import MLBEloRating

        assert MLBEloRating is not None

    def test_nfl_elo_import(self):
        from plugins.elo import NFLEloRating

        assert NFLEloRating is not None

    def test_ncaab_elo_import(self):
        from plugins.elo import NCAABEloRating

        assert NCAABEloRating is not None


class TestClassInterface:
    """Test class interface consistency"""

    def test_mlb_elo_interface(self):
        from plugins.elo import MLBEloRating

        elo = MLBEloRating()
        assert hasattr(elo, "predict")
        assert hasattr(elo, "update")
        assert hasattr(elo, "get_rating")
        assert hasattr(elo, "expected_score")

    def test_nfl_elo_interface(self):
        from plugins.elo import NFLEloRating

        elo = NFLEloRating()
        assert hasattr(elo, "predict")
        assert hasattr(elo, "update")
        assert hasattr(elo, "get_rating")

    def test_ncaab_elo_interface(self):
        from plugins.elo import NCAABEloRating

        elo = NCAABEloRating()
        assert hasattr(elo, "predict")
        assert hasattr(elo, "update")
        assert hasattr(elo, "get_rating")


class TestEdgeCases:
    """Test edge cases"""

    def test_tied_game_mlb(self):
        from plugins.elo import MLBEloRating

        elo = MLBEloRating()
        # Tied game (rare in MLB but should handle)
        try:
            elo.update("Team A", "Team B", 5, 5)
        except Exception:
            pass  # May not support ties

    def test_very_high_score(self):
        from plugins.elo import MLBEloRating

        elo = MLBEloRating()
        elo.update("Team A", "Team B", 20, 0)

        # Should still work
        assert elo.get_rating("Team A") > 1500

    def test_negative_rating_prevention(self):
        from plugins.elo import NFLEloRating

        elo = NFLEloRating()

        # Many losses
        for _ in range(100):
            elo.update("Loser", "Winner", 0, 50)

        # Rating should still be positive
        assert elo.get_rating("Loser") > 0
