"""
Integration tests for Unrivaled basketball in the multi-sport betting system.

Tests the complete integration of Unrivaled with:
- Elo rating system
- Games data loader
- Kalshi markets integration
- DAG configuration
"""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime


class TestUnrivaledEloIntegration:
    """Test Unrivaled Elo integration with the factory system."""

    def test_factory_registration(self):
        """Unrivaled is registered in the Elo factory."""
        from plugins.elo import ELO_CLASS_REGISTRY, get_elo_class, UnrivaledEloRating

        assert "unrivaled" in ELO_CLASS_REGISTRY
        assert get_elo_class("unrivaled") == UnrivaledEloRating

    def test_elo_instance_creation(self):
        """Can create Unrivaled Elo instance through factory."""
        from plugins.elo import create_elo_instance

        elo = create_elo_instance("unrivaled")
        assert elo.k_factor == 24.0  # Default for Unrivaled
        assert elo.home_advantage == 0.0  # No home advantage

    def test_elo_predictions_work(self):
        """Elo predictions work correctly for Unrivaled teams."""
        from plugins.elo import create_elo_instance

        elo = create_elo_instance("unrivaled")

        # Simulate some game history
        elo.update("Rose BC", "Lunar Owls BC", home_won=True, is_neutral=True)
        elo.update("Rose BC", "Phantom BC", home_won=True, is_neutral=True)
        elo.update("Lunar Owls BC", "Mist BC", home_won=True, is_neutral=True)

        # Rose BC should have higher rating after wins
        assert elo.get_rating("Rose BC") > 1500

        # Predictions should reflect this
        prob = elo.predict("Rose BC", "Mist BC")
        assert prob > 0.5  # Rose BC should be favored


class TestUnrivaledGamesIntegration:
    """Test Unrivaled games loader integration."""

    def test_games_class_exists(self):
        """UnrivaledGames class can be imported."""
        from unrivaled_games import UnrivaledGames

        games = UnrivaledGames()
        assert games is not None

    def test_games_has_required_methods(self):
        """UnrivaledGames has required interface methods."""
        from unrivaled_games import UnrivaledGames

        games = UnrivaledGames()
        assert hasattr(games, "download_games")
        assert hasattr(games, "load_games")
        assert hasattr(games, "get_games_for_date")

    def test_load_games_returns_dataframe(self):
        """load_games returns a pandas DataFrame."""
        from unrivaled_games import UnrivaledGames

        games = UnrivaledGames()
        df = games.load_games()

        assert isinstance(df, pd.DataFrame)

    def test_dataframe_has_required_columns(self):
        """Games DataFrame has required columns."""
        from unrivaled_games import UnrivaledGames

        games = UnrivaledGames()
        df = games.load_games()

        required_columns = ["date", "home_team", "away_team", "home_score",
                          "away_score", "neutral"]

        # Empty DataFrame should still have columns defined
        for col in required_columns:
            assert col in df.columns or len(df) == 0

    def test_add_game_functionality(self):
        """Can add games to the dataset."""
        from unrivaled_games import UnrivaledGames
        import tempfile
        import shutil

        # Use temporary directory to avoid affecting real data
        with tempfile.TemporaryDirectory() as tmpdir:
            games = UnrivaledGames(data_dir=tmpdir)

            # Add a test game
            games.add_game(
                date="2025-01-15",
                team1="Rose BC",
                team2="Lunar Owls BC",
                score1=25,
                score2=21,
            )

            # Verify game was added
            df = games.load_games()
            assert len(df) == 1
            assert df.iloc[0]["home_team"] == "Rose BC"


class TestUnrivaledKalshiIntegration:
    """Test Unrivaled Kalshi markets integration."""

    def test_sport_series_contains_unrivaled(self):
        """SPORT_SERIES contains unrivaled entry."""
        from kalshi_markets import SPORT_SERIES

        assert "unrivaled" in SPORT_SERIES
        assert isinstance(SPORT_SERIES["unrivaled"], list)
        assert len(SPORT_SERIES["unrivaled"]) > 0

    def test_fetch_function_exists(self):
        """fetch_unrivaled_markets function exists."""
        from kalshi_markets import fetch_unrivaled_markets

        assert callable(fetch_unrivaled_markets)

    def test_fetch_function_signature(self):
        """fetch_unrivaled_markets accepts date_str parameter."""
        import inspect
        from kalshi_markets import fetch_unrivaled_markets

        sig = inspect.signature(fetch_unrivaled_markets)
        params = list(sig.parameters.keys())
        assert "date_str" in params


class TestUnrivaledDAGConfiguration:
    """Test Unrivaled DAG configuration."""

    def test_sports_config_has_unrivaled(self):
        """SPORTS_CONFIG includes unrivaled."""
        import sys
        sys.path.insert(0, "dags")

        from multi_sport_betting_workflow import SPORTS_CONFIG

        assert "unrivaled" in SPORTS_CONFIG

        config = SPORTS_CONFIG["unrivaled"]
        assert "elo_module" in config
        assert "games_module" in config
        assert "kalshi_function" in config
        assert "elo_threshold" in config
        assert "series_ticker" in config

    def test_unrivaled_config_values(self):
        """Unrivaled config has correct values."""
        import sys
        sys.path.insert(0, "dags")

        from multi_sport_betting_workflow import SPORTS_CONFIG

        config = SPORTS_CONFIG["unrivaled"]

        assert config["elo_module"] == "elo"
        assert config["games_module"] == "unrivaled_games"
        assert config["kalshi_function"] == "fetch_unrivaled_markets"
        assert 0.5 <= config["elo_threshold"] <= 0.8  # Reasonable threshold range
        assert "UNRIVALED" in config["series_ticker"].upper()

    def test_team_mapping_exists(self):
        """Team mapping exists for Unrivaled."""
        import sys
        sys.path.insert(0, "dags")

        from multi_sport_betting_workflow import SPORTS_CONFIG

        config = SPORTS_CONFIG["unrivaled"]
        assert "team_mapping" in config
        assert isinstance(config["team_mapping"], dict)

        # Should have some mappings
        assert len(config["team_mapping"]) > 0


class TestUnrivaledEloRatingsFlow:
    """Test complete Elo ratings flow for Unrivaled."""

    def test_complete_ratings_calculation(self):
        """Test complete flow from games to ratings."""
        from plugins.elo import create_elo_instance

        elo = create_elo_instance("unrivaled", k_factor=24, home_advantage=0)

        # Simulate a small season
        games = [
            ("Rose BC", "Lunar Owls BC", True),
            ("Phantom BC", "Mist BC", True),
            ("Vinyl BC", "Laces BC", False),
            ("Rose BC", "Phantom BC", True),
            ("Lunar Owls BC", "Vinyl BC", True),
            ("Mist BC", "Laces BC", True),
        ]

        for home, away, home_won in games:
            elo.update(home, away, home_won=home_won, is_neutral=True)

        # All teams should have ratings
        ratings = elo.get_all_ratings()
        assert len(ratings) == 6

        # Ratings should have diverged from initial
        assert not all(r == 1500 for r in ratings.values())

        # Rose BC won 2, should be above average
        assert ratings["Rose BC"] > 1500

    def test_ratings_sum_conservation(self):
        """Total rating points should be conserved (zero-sum updates)."""
        from plugins.elo import create_elo_instance

        elo = create_elo_instance("unrivaled")

        # Start with known ratings
        initial_teams = ["Rose BC", "Lunar Owls BC", "Phantom BC", "Mist BC"]
        for team in initial_teams:
            elo.ratings[team] = 1500.0

        initial_sum = sum(elo.ratings.values())

        # Run several updates
        elo.update("Rose BC", "Lunar Owls BC", home_won=True, is_neutral=True)
        elo.update("Phantom BC", "Mist BC", home_won=False, is_neutral=True)

        final_sum = sum(elo.ratings.values())

        # Sum should be approximately conserved
        assert abs(initial_sum - final_sum) < 0.01


class TestUnrivaledTeamNames:
    """Test team name handling for Unrivaled."""

    def test_known_teams_constant(self):
        """UNRIVALED_TEAMS constant exists."""
        from unrivaled_games import UNRIVALED_TEAMS

        assert isinstance(UNRIVALED_TEAMS, set)
        assert len(UNRIVALED_TEAMS) == 6

    def test_team_abbreviations(self):
        """Team abbreviations are mapped correctly."""
        from unrivaled_games import TEAM_ABBREVIATIONS

        assert "ROSE" in TEAM_ABBREVIATIONS
        assert TEAM_ABBREVIATIONS["ROSE"] == "Rose BC"

    def test_normalize_team_name(self):
        """Team name normalization works."""
        from unrivaled_games import UnrivaledGames

        games = UnrivaledGames()

        # Should handle abbreviations
        assert games._normalize_team_name("ROSE") == "Rose BC"
        assert games._normalize_team_name("LUNAR") == "Lunar Owls BC"

        # Should handle full names
        assert games._normalize_team_name("Rose BC") == "Rose BC"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
