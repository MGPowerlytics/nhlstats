"""
TDD tests for TennisEloRating refactoring to inherit from BaseEloRating.
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.elo import BaseEloRating, TennisEloRating


class TestTennisEloInheritance:
    """Test that TennisEloRating properly inherits from BaseEloRating."""

    def test_tennis_elo_inherits_from_base(self):
        """Verify TennisEloRating is a subclass of BaseEloRating."""
        assert issubclass(TennisEloRating, BaseEloRating)

    def test_tennis_elo_can_be_instantiated(self):
        """Test that TennisEloRating can be instantiated with default parameters."""
        elo = TennisEloRating()
        assert elo is not None
        assert isinstance(elo, BaseEloRating)
        assert elo.k_factor == 32
        # Tennis doesn't use home_advantage, but BaseEloRating has it (should be 0)
        assert elo.home_advantage == 0
        assert elo.initial_rating == 1500

    def test_tennis_elo_has_required_methods(self):
        """Test that TennisEloRating implements all required abstract methods."""
        elo = TennisEloRating()

        # Check all abstract methods exist
        assert hasattr(elo, 'predict')
        assert hasattr(elo, 'update')
        assert hasattr(elo, 'get_rating')
        assert hasattr(elo, 'expected_score')
        assert hasattr(elo, 'get_all_ratings')

        # Check method signatures (basic check)
        import inspect
        predict_sig = inspect.signature(elo.predict)
        # Tennis predict has different parameters than base
        assert 'player_a' in predict_sig.parameters
        assert 'player_b' in predict_sig.parameters
        assert 'tour' in predict_sig.parameters

        update_sig = inspect.signature(elo.update)
        # Tennis update has different parameters than base
        assert 'winner' in update_sig.parameters
        assert 'loser' in update_sig.parameters
        assert 'tour' in update_sig.parameters


class TestTennisEloFunctionality:
    """Test the core functionality of TennisEloRating."""

    def test_get_rating_returns_initial_for_new_player(self):
        """Test get_rating returns initial rating for new player."""
        elo = TennisEloRating(initial_rating=1600)
        # Note: normalize_name will convert "Djokovic N." format
        assert elo.get_rating("Djokovic N.", tour='ATP') == 1600

    def test_predict_basic(self):
        """Test basic prediction functionality."""
        elo = TennisEloRating()
        # Use normalized names (as get_rating will normalize them)
        elo.atp_ratings = {"Playera": 1600, "Playerb": 1400}

        # PlayerA should have higher win probability
        prob = elo.predict("Playera", "Playerb", tour='ATP')
        # With ratings 1600 vs 1400, probability should be > 0.5
        # Expected: 1 / (1 + 10^((1400-1600)/400)) = 1 / (1 + 10^(-0.5)) ≈ 0.76
        assert prob > 0.5
        assert prob < 1

        # Reverse order - PlayerB should have lower probability
        prob_reverse = elo.predict("Playerb", "Playera", tour='ATP')
        assert prob_reverse < 0.5
        assert prob_reverse > 0

    def test_update_basic(self):
        """Test basic update functionality."""
        elo = TennisEloRating(k_factor=32)
        # Use normalized names
        elo.atp_ratings = {"Playera": 1600, "Playerb": 1400}
        elo.atp_matches_played = {"Playera": 10, "Playerb": 10}

        initial_rating_a = elo.get_rating("Playera", tour='ATP')
        initial_rating_b = elo.get_rating("Playerb", tour='ATP')

        # PlayerA wins
        change = elo.update("Playera", "Playerb", tour='ATP')

        assert elo.get_rating("Playera", tour='ATP') > initial_rating_a  # Winner's rating increases
        assert elo.get_rating("Playerb", tour='ATP') < initial_rating_b  # Loser's rating decreases
        assert abs(change) > 0  # Some change occurred

    def test_expected_score_method(self):
        """Test the expected_score method."""
        elo = TennisEloRating()
        elo.atp_ratings = {"Playera": 1600, "Playerb": 1400}

        # expected_score should return the same as predict for player_a win probability
        expected = elo.expected_score("Playera", "Playerb", is_neutral=True)
        predicted = elo.predict("Playera", "Playerb", tour='ATP', is_neutral=True)

        # They should be very close
        assert abs(expected - predicted) < 0.0001

    def test_get_all_ratings_method(self):
        """Test get_all_ratings returns dictionary of ratings."""
        elo = TennisEloRating()
        elo.atp_ratings = {"Playera": 1600, "Playerb": 1400}
        elo.wta_ratings = {"Playerc": 1550, "Playerd": 1450}

        all_ratings = elo.get_all_ratings()
        assert isinstance(all_ratings, dict)
        assert len(all_ratings) == 4
        assert all_ratings["ATP:Playera"] == 1600
        assert all_ratings["ATP:Playerb"] == 1400
        assert all_ratings["WTA:Playerc"] == 1550
        assert all_ratings["WTA:Playerd"] == 1450

    def test_tennis_specific_methods(self):
        """Test tennis-specific methods still work."""
        elo = TennisEloRating()

        # Test get_match_count
        elo.update("Playera", "Playerb", tour='ATP')
        assert elo.get_match_count("Playera", tour='ATP') == 1
        assert elo.get_match_count("Playerb", tour='ATP') == 1

        # Test get_rankings
        rankings = elo.get_rankings(tour='ATP', top_n=5)
        assert isinstance(rankings, list)

        # Test get_all_players
        players = elo.get_all_players(tour='ATP')
        assert isinstance(players, list)
        # Names are normalized
        assert "Playera" in players
        assert "Playerb" in players

    def test_base_interface_adaptation_methods(self):
        """Test the adaptation methods for BaseEloRating interface."""
        elo = TennisEloRating()
        elo.atp_ratings = {"Playera": 1600, "Playerb": 1400}

        # Test predict_team (adapts team interface to tennis)
        prob = elo.predict_team("Playera", "Playerb", is_neutral=True)
        assert 0 < prob < 1

        # Test update_team (adapts team interface to tennis)
        initial_a = elo.get_rating("Playera", tour='ATP')
        initial_b = elo.get_rating("Playerb", tour='ATP')

        # home_team (Playera) wins
        change = elo.update_team("Playera", "Playerb", home_win=1.0, is_neutral=True)
        assert elo.get_rating("Playera", tour='ATP') > initial_a
        assert elo.get_rating("Playerb", tour='ATP') < initial_b


class TestTennisEloBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_legacy_update_method(self):
        """Test that legacy update method works for backward compatibility."""
        elo = TennisEloRating()
        elo.atp_ratings = {"Playera": 1600, "Playerb": 1400}
        elo.atp_matches_played = {"Playera": 10, "Playerb": 10}

        # The legacy_update method should work
        change = elo.legacy_update("Playera", "Playerb", tour='ATP')
        assert isinstance(change, float)
        assert abs(change) > 0

    def test_normalize_name_function(self):
        """Test the name normalization function."""
        elo = TennisEloRating()

        # Test various name formats
        assert elo._normalize_name("Novak Djokovic") == "Djokovic N."
        assert elo._normalize_name("Djokovic N.") == "Djokovic N."
        assert elo._normalize_name("NAOMI OSAKA") == "Osaka N."
        assert elo._normalize_name("") == "Unknown"
        assert elo._normalize_name("Federer") == "Federer"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
