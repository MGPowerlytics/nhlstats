"""
CBA Integration Tests - Chinese Basketball Association

Tests for the full CBA betting pipeline integration:
- Elo factory registration
- Games downloader functionality
- Kalshi markets integration
- DAG configuration
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

# Add plugins directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))


class TestCBAEloFactoryIntegration:
    """Test CBA Elo integration with factory/registry."""

    def test_cba_in_elo_class_registry(self):
        """Test that CBA is registered in ELO_CLASS_REGISTRY."""
        from elo import ELO_CLASS_REGISTRY

        assert "cba" in ELO_CLASS_REGISTRY, "CBA not in ELO_CLASS_REGISTRY"

    def test_get_elo_class_for_cba(self):
        """Test that get_elo_class returns CBAEloRating."""
        from elo import get_elo_class, CBAEloRating

        cls = get_elo_class("cba")
        assert cls is CBAEloRating

    def test_create_elo_instance_for_cba(self):
        """Test that create_elo_instance works for CBA."""
        from elo import create_elo_instance, CBAEloRating

        elo = create_elo_instance("cba")
        assert isinstance(elo, CBAEloRating)

    def test_create_elo_instance_with_custom_params(self):
        """Test creating CBA Elo with custom parameters."""
        from elo import create_elo_instance

        elo = create_elo_instance("cba", k_factor=30, home_advantage=100)
        assert elo.config.k_factor == 30
        assert elo.config.home_advantage == 100

    def test_get_elo_for_sport_alias(self):
        """Test get_elo_for_sport alias works for CBA."""
        from elo import get_elo_for_sport, CBAEloRating

        elo = get_elo_for_sport("cba")
        assert isinstance(elo, CBAEloRating)


class TestCBAGamesIntegration:
    """Test CBA games downloader integration."""

    def test_cba_games_class_exists(self):
        """Test that CBAGames class can be imported."""
        from cba_games import CBAGames

        assert CBAGames is not None

    def test_cba_games_data_dir_creation(self):
        """Test that CBAGames creates data directory."""
        from cba_games import CBAGames
        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()
        try:
            cba = CBAGames(data_dir=f"{temp_dir}/cba")
            assert cba.data_dir.exists()
        finally:
            shutil.rmtree(temp_dir)

    def test_cba_games_team_mapping_loaded(self):
        """Test that team mapping is loaded."""
        from cba_games import CBAGames

        cba = CBAGames()
        # Check that some team mapping exists
        assert cba.team_mapping is not None

    def test_cba_games_normalize_team_name(self):
        """Test team name normalization."""
        from cba_games import CBAGames

        cba = CBAGames()
        # Test canonical name returns unchanged
        result = cba.normalize_team_name("Guangdong Southern Tigers")
        assert result == "Guangdong Southern Tigers"

        # Test alias normalization (if mapping exists)
        if "Guangdong" in cba.team_mapping.get("name_to_canonical", {}):
            result = cba.normalize_team_name("Guangdong")
            assert result == "Guangdong Southern Tigers"

    @patch("requests.get")
    def test_cba_games_download_handles_api_response(self, mock_get):
        """Test download_games handles API responses."""
        from cba_games import CBAGames
        import tempfile
        import shutil

        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {"events": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        temp_dir = tempfile.mkdtemp()
        try:
            cba = CBAGames(data_dir=f"{temp_dir}/cba")
            result = cba.download_games()
            assert result is True
        finally:
            shutil.rmtree(temp_dir)

    def test_cba_games_load_returns_dataframe(self):
        """Test that load_games returns a DataFrame."""
        from cba_games import CBAGames
        import tempfile
        import shutil
        import pandas as pd

        temp_dir = tempfile.mkdtemp()
        try:
            cba = CBAGames(data_dir=f"{temp_dir}/cba")

            # Create a mock games file
            mock_games = [
                {
                    "idEvent": "123456",
                    "dateEvent": "2025-12-15",
                    "strHomeTeam": "Guangdong Southern Tigers",
                    "strAwayTeam": "Beijing Ducks",
                    "intHomeScore": 110,
                    "intAwayScore": 95,
                    "strSeason": "2025-2026",
                    "strStatus": "Match Finished",
                }
            ]
            with open(cba.data_dir / "games_2026.json", "w") as f:
                json.dump(mock_games, f)

            df = cba.load_games()
            assert isinstance(df, pd.DataFrame)
            assert len(df) > 0
            assert "home_team" in df.columns
            assert "away_team" in df.columns
        finally:
            shutil.rmtree(temp_dir)


class TestCBAKalshiIntegration:
    """Test CBA Kalshi markets integration."""

    def test_cba_in_sport_series(self):
        """Test that CBA is in SPORT_SERIES."""
        from kalshi_markets import SPORT_SERIES

        assert "cba" in SPORT_SERIES

    def test_fetch_cba_markets_function_exists(self):
        """Test that fetch_cba_markets function exists."""
        from kalshi_markets import fetch_cba_markets

        assert callable(fetch_cba_markets)

    @patch("kalshi_markets._fetch_sport_markets")
    def test_fetch_cba_markets_calls_internal(self, mock_fetch):
        """Test fetch_cba_markets calls internal function correctly."""
        from kalshi_markets import fetch_cba_markets

        mock_fetch.return_value = []
        fetch_cba_markets("2026-02-01")

        mock_fetch.assert_called_once_with("cba")


class TestCBATeamMappingIntegration:
    """Test CBA team mapping file."""

    def test_team_mapping_file_exists(self):
        """Test that team mapping file exists."""
        mapping_file = Path("data/cba_team_mapping.json")
        assert mapping_file.exists(), "CBA team mapping file not found"

    def test_team_mapping_valid_json(self):
        """Test that team mapping is valid JSON."""
        mapping_file = Path("data/cba_team_mapping.json")
        with open(mapping_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, dict)

    def test_team_mapping_has_required_sections(self):
        """Test that team mapping has required sections."""
        mapping_file = Path("data/cba_team_mapping.json")
        with open(mapping_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "teams" in data
        assert "abbreviation_mapping" in data
        assert "name_to_canonical" in data
        assert "metadata" in data

    def test_team_mapping_has_20_teams(self):
        """Test that team mapping has all 20 CBA teams."""
        mapping_file = Path("data/cba_team_mapping.json")
        with open(mapping_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert len(data["teams"]) == 20, f"Expected 20 teams, got {len(data['teams'])}"
        assert (
            len(data["abbreviation_mapping"]) == 20
        ), f"Expected 20 abbreviations, got {len(data['abbreviation_mapping'])}"

    def test_team_mapping_abbreviations_map_to_teams(self):
        """Test that all abbreviations map to valid teams."""
        mapping_file = Path("data/cba_team_mapping.json")
        with open(mapping_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        for abbrev, team_name in data["abbreviation_mapping"].items():
            assert (
                team_name in data["teams"]
            ), f"Abbreviation {abbrev} maps to unknown team: {team_name}"


class TestCBADagConfigIntegration:
    """Test CBA DAG configuration."""

    def test_cba_in_sports_config(self):
        """Test that CBA is in SPORTS_CONFIG."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "dags"))
        from multi_sport_betting_workflow import SPORTS_CONFIG

        assert "cba" in SPORTS_CONFIG

    def test_cba_config_has_required_fields(self):
        """Test that CBA config has all required fields."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "dags"))
        from multi_sport_betting_workflow import SPORTS_CONFIG

        required_fields = [
            "elo_module",
            "games_module",
            "kalshi_function",
            "series_ticker",
            "team_mapping",
        ]

        cba_config = SPORTS_CONFIG["cba"]
        for field in required_fields:
            assert field in cba_config, f"Missing required field: {field}"

    def test_cba_config_values(self):
        """Test that CBA config has expected values."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "dags"))
        from multi_sport_betting_workflow import SPORTS_CONFIG

        cba_config = SPORTS_CONFIG["cba"]

        assert cba_config["elo_module"] == "elo"
        assert cba_config["games_module"] == "cba_games"
        assert cba_config["kalshi_function"] == "fetch_cba_markets"
        assert len(cba_config["team_mapping"]) == 20


class TestCBAEndToEndIntegration:
    """End-to-end integration tests for CBA pipeline."""

    def test_full_elo_workflow(self):
        """Test complete Elo workflow: create, predict, update, save."""
        from elo import create_elo_instance

        elo = create_elo_instance("cba")

        # Simulate a game
        home_team = "Guangdong Southern Tigers"
        away_team = "Beijing Ducks"

        # Initial prediction
        prob = elo.predict(home_team, away_team)
        assert 0.0 < prob < 1.0

        # Update with result
        elo.update(home_team, away_team, home_won=True)

        # Check ratings changed
        assert elo.get_rating(home_team) > 1500  # Winner rating increased
        assert elo.get_rating(away_team) < 1500  # Loser rating decreased

        # Get all ratings
        all_ratings = elo.get_all_ratings()
        assert len(all_ratings) == 2
        assert home_team in all_ratings
        assert away_team in all_ratings

    def test_elo_with_multiple_games(self):
        """Test Elo system with multiple games."""
        from elo import create_elo_instance

        elo = create_elo_instance("cba")

        # Simulate a mini-season
        games = [
            ("Guangdong Southern Tigers", "Beijing Ducks", True),
            ("Liaoning Flying Leopards", "Shanghai Sharks", True),
            ("Guangdong Southern Tigers", "Liaoning Flying Leopards", True),
            ("Beijing Ducks", "Shanghai Sharks", False),
            ("Guangdong Southern Tigers", "Shanghai Sharks", True),
        ]

        for home, away, home_won in games:
            elo.update(home, away, home_won=home_won)

        all_ratings = elo.get_all_ratings()

        # Guangdong won 3 games, should have highest rating
        guangdong_rating = all_ratings.get("Guangdong Southern Tigers", 0)
        for team, rating in all_ratings.items():
            if team != "Guangdong Southern Tigers":
                assert (
                    guangdong_rating >= rating
                ), f"Guangdong should have highest rating, but {team} has {rating}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
