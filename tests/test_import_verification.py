"""
Import Verification Tests

These tests verify that all critical plugin modules and their dependencies
can be imported successfully. This prevents deployment of code with missing
transitive dependencies (like lazy_imports, appdirs, fastparquet).

Run these tests BEFORE deploying to catch missing dependencies early.
"""

import sys
import importlib
from unittest.mock import patch, MagicMock
import pytest


class TestCriticalDependencies:
    """Test that critical transitive dependencies are installed."""

    def test_lazy_imports_available(self):
        """lazy_imports must be installed (required by kalshi-python)."""
        import lazy_imports
        assert lazy_imports is not None

    def test_appdirs_available(self):
        """appdirs must be installed (required by nfl_data_py)."""
        import appdirs
        assert appdirs is not None

    @pytest.mark.skip(reason="fastparquet requires pandas<2.0 which conflicts with other deps")
    def test_fastparquet_available(self):
        """fastparquet should be installed (used by nfl_data_py caching)."""
        import fastparquet
        assert fastparquet is not None


class TestKalshiModuleImports:
    """Test that Kalshi-related modules can be imported."""

    def test_kalshi_python_package(self):
        """kalshi-python package should import without errors."""
        # The kalshi package is kalshi_python (not kalshi)
        try:
            from kalshi_python import Configuration, ApiClient, MarketsApi
            assert Configuration is not None
        except ImportError:
            # kalshi_python may not be installed in test environment
            import pytest
            pytest.skip("kalshi_python not installed")

    def test_kalshi_markets_module(self):
        """kalshi_markets plugin should import successfully."""
        from plugins import kalshi_markets
        assert kalshi_markets is not None

    def test_kalshi_markets_exports(self):
        """kalshi_markets should export all required fetch functions."""
        from plugins.kalshi_markets import (
            fetch_nba_markets,
            fetch_nhl_markets,
            fetch_mlb_markets,
            fetch_nfl_markets,
            fetch_epl_markets,
            fetch_tennis_markets,
            fetch_ncaab_markets,
            fetch_wncaab_markets,
            fetch_ligue1_markets,
        )
        # All functions should be callable
        assert callable(fetch_nba_markets)
        assert callable(fetch_nhl_markets)
        assert callable(fetch_mlb_markets)
        assert callable(fetch_nfl_markets)
        assert callable(fetch_epl_markets)
        assert callable(fetch_tennis_markets)
        assert callable(fetch_ncaab_markets)
        assert callable(fetch_wncaab_markets)
        assert callable(fetch_ligue1_markets)

    def test_kalshi_betting_module(self):
        """kalshi_betting plugin should import successfully."""
        from plugins.kalshi_betting import KalshiBetting
        assert KalshiBetting is not None


class TestEloModuleImports:
    """Test that all Elo rating modules can be imported."""

    def test_base_elo_rating(self):
        """BaseEloRating abstract class should import."""
        from plugins.elo.base_elo_rating import BaseEloRating
        assert BaseEloRating is not None

    def test_nba_elo_rating(self):
        """NBAEloRating should import and inherit from BaseEloRating."""
        from plugins.elo import NBAEloRating
        from plugins.elo.base_elo_rating import BaseEloRating
        assert issubclass(NBAEloRating, BaseEloRating)

    def test_nhl_elo_rating(self):
        """NHLEloRating should import and inherit from BaseEloRating."""
        from plugins.elo import NHLEloRating
        from plugins.elo.base_elo_rating import BaseEloRating
        assert issubclass(NHLEloRating, BaseEloRating)

    def test_mlb_elo_rating(self):
        """MLBEloRating should import and inherit from BaseEloRating."""
        from plugins.elo import MLBEloRating
        from plugins.elo.base_elo_rating import BaseEloRating
        assert issubclass(MLBEloRating, BaseEloRating)

    def test_nfl_elo_rating(self):
        """NFLEloRating should import and inherit from BaseEloRating."""
        from plugins.elo import NFLEloRating
        from plugins.elo.base_elo_rating import BaseEloRating
        assert issubclass(NFLEloRating, BaseEloRating)

    def test_epl_elo_rating(self):
        """EPLEloRating should import and inherit from BaseEloRating."""
        from plugins.elo import EPLEloRating
        from plugins.elo.base_elo_rating import BaseEloRating
        assert issubclass(EPLEloRating, BaseEloRating)

    def test_ligue1_elo_rating(self):
        """Ligue1EloRating should import and inherit from BaseEloRating."""
        from plugins.elo import Ligue1EloRating
        from plugins.elo.base_elo_rating import BaseEloRating
        assert issubclass(Ligue1EloRating, BaseEloRating)

    def test_tennis_elo_rating(self):
        """TennisEloRating should import and inherit from BaseEloRating."""
        from plugins.elo import TennisEloRating
        from plugins.elo.base_elo_rating import BaseEloRating
        assert issubclass(TennisEloRating, BaseEloRating)

    def test_ncaab_elo_rating(self):
        """NCAABEloRating should import and inherit from BaseEloRating."""
        from plugins.elo import NCAABEloRating
        from plugins.elo.base_elo_rating import BaseEloRating
        assert issubclass(NCAABEloRating, BaseEloRating)

    def test_wncaab_elo_rating(self):
        """WNCAABEloRating should import and inherit from BaseEloRating."""
        from plugins.elo import WNCAABEloRating
        from plugins.elo.base_elo_rating import BaseEloRating
        assert issubclass(WNCAABEloRating, BaseEloRating)

    def test_elo_module_exports_all_classes(self):
        """The elo module should export all sport-specific classes."""
        from plugins.elo import (
            BaseEloRating,
            NBAEloRating,
            NHLEloRating,
            MLBEloRating,
            NFLEloRating,
            EPLEloRating,
            Ligue1EloRating,
            TennisEloRating,
            NCAABEloRating,
            WNCAABEloRating,
        )
        # All should be classes
        assert all(isinstance(cls, type) for cls in [
            BaseEloRating, NBAEloRating, NHLEloRating, MLBEloRating,
            NFLEloRating, EPLEloRating, Ligue1EloRating, TennisEloRating,
            NCAABEloRating, WNCAABEloRating
        ])


class TestGameModuleImports:
    """Test that game data modules can be imported."""

    def test_nba_games_module(self):
        """nba_games module should import successfully."""
        from plugins import nba_games
        assert nba_games is not None

    def test_nhl_games_module(self):
        """nhl_game_events module should import successfully."""
        from plugins import nhl_game_events
        assert nhl_game_events is not None

    def test_mlb_games_module(self):
        """mlb_games module should import successfully."""
        from plugins import mlb_games
        assert mlb_games is not None

    def test_nfl_games_module(self):
        """nfl_games module should import (nfl_data_py may not be available)."""
        from plugins import nfl_games
        assert nfl_games is not None
        # Check if the module loaded successfully (even without nfl_data_py)
        assert hasattr(nfl_games, 'NFLGames')

    def test_epl_games_module(self):
        """epl_games module should import successfully."""
        from plugins import epl_games
        assert epl_games is not None

    def test_tennis_games_module(self):
        """tennis_games module should import successfully."""
        from plugins import tennis_games
        assert tennis_games is not None

    def test_ncaab_games_module(self):
        """ncaab_games module should import successfully."""
        from plugins import ncaab_games
        assert ncaab_games is not None

    def test_wncaab_games_module(self):
        """wncaab_games module should import successfully."""
        from plugins import wncaab_games
        assert wncaab_games is not None

    def test_ligue1_games_module(self):
        """ligue1_games module should import successfully."""
        from plugins import ligue1_games
        assert ligue1_games is not None


class TestDatabaseModuleImports:
    """Test that database modules can be imported."""

    def test_db_manager_module(self):
        """db_manager should import and provide DBManager class."""
        from plugins.db_manager import DBManager, default_db
        assert DBManager is not None
        assert default_db is not None

    def test_db_loader_module(self):
        """db_loader should import successfully."""
        from plugins import db_loader
        assert db_loader is not None


class TestBettingModuleImports:
    """Test that betting-related modules can be imported."""

    def test_bet_tracker_module(self):
        """bet_tracker should import successfully."""
        from plugins import bet_tracker
        assert bet_tracker is not None

    def test_portfolio_betting_module(self):
        """portfolio_betting should import successfully."""
        from plugins import portfolio_betting
        assert portfolio_betting is not None


class TestDAGImports:
    """Test that DAG files can be imported without errors."""

    def test_multi_sport_betting_workflow_parses(self):
        """Main DAG should parse without import errors."""
        # Import the DAG module - this will fail if dependencies are missing
        import dags.multi_sport_betting_workflow as dag_module
        assert dag_module is not None

    def test_bet_sync_hourly_parses(self):
        """bet_sync_hourly DAG should parse without import errors."""
        import dags.bet_sync_hourly as dag_module
        assert dag_module is not None

    def test_portfolio_hourly_snapshot_parses(self):
        """portfolio_hourly_snapshot DAG should parse without import errors."""
        import dags.portfolio_hourly_snapshot as dag_module
        assert dag_module is not None


class TestGlicko2ModuleImports:
    """Test that Glicko-2 rating modules can be imported."""

    def test_glicko2_rating_module(self):
        """glicko2_rating module should import successfully."""
        from plugins import glicko2_rating
        assert glicko2_rating is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
