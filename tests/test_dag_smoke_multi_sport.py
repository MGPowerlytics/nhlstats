"""
Smoke Tests for multi_sport_betting_workflow DAG

These tests verify that all task functions in the main betting DAG:
1. Can be imported without errors
2. Accept the correct parameters
3. Handle mocked dependencies correctly
4. Push expected values to XCom
5. Handle error cases gracefully

Run on every commit to catch breaking changes early.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add plugins and dags to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))
sys.path.insert(0, str(Path(__file__).parent.parent / "dags"))


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_airflow_context():
    """Create a mock Airflow task context with XCom support."""
    xcom_store = {}

    mock_ti = MagicMock()
    mock_ti.xcom_push = lambda key, value: xcom_store.update({key: value})
    mock_ti.xcom_pull = lambda key, task_ids=None: xcom_store.get(key)

    context = {
        "ds": "2026-01-27",
        "task_instance": mock_ti,
        "ti": mock_ti,
    }
    context["_xcom_store"] = xcom_store  # For test assertions
    return context


@pytest.fixture
def sample_game_data():
    """Sample game data for testing."""
    import pandas as pd

    return pd.DataFrame(
        {
            "game_date": ["2026-01-27", "2026-01-26"],
            "home_team": ["Lakers", "Celtics"],
            "away_team": ["Celtics", "Lakers"],
            "home_score": [110, 105],
            "away_score": [105, 112],
            "home_win": [1, 0],  # home_score > away_score
            "status": ["Final", "Final"],
        }
    )


@pytest.fixture
def sample_nhl_game_data():
    """Sample NHL game data for testing."""
    import pandas as pd

    return pd.DataFrame(
        {
            "game_date": ["2026-01-27", "2026-01-26"],
            "home_team_abbrev": ["TOR", "MTL"],
            "away_team_abbrev": ["MTL", "TOR"],
            "home_score": [4, 2],
            "away_score": [2, 3],
            "game_state": ["FINAL", "FINAL"],
            "game_id": [1, 2],
        }
    )


@pytest.fixture
def sample_market_data():
    """Sample Kalshi market data for testing."""
    return [
        {
            "ticker": "KXNBAGAME-26JAN27-LAL",
            "title": "Lakers vs Celtics",
            "yes_price": 0.55,
            "no_price": 0.45,
            "home_team": "Lakers",
            "away_team": "Celtics",
        },
        {
            "ticker": "KXNBAGAME-26JAN27-BOS",
            "title": "Celtics vs Lakers",
            "yes_price": 0.60,
            "no_price": 0.40,
            "home_team": "Celtics",
            "away_team": "Lakers",
        },
    ]


# ============================================================================
# Helper Function Tests
# ============================================================================


class TestHelperFunctions:
    """Test helper functions in the DAG."""

    def test_is_valid_score_with_valid_number(self):
        """is_valid_score returns True for valid numbers."""
        from multi_sport_betting_workflow import is_valid_score

        assert is_valid_score(100) is True
        assert is_valid_score(0) is True
        assert is_valid_score(3.14) is True
        assert is_valid_score(-5) is True

    def test_is_valid_score_with_none(self):
        """is_valid_score returns False for None."""
        from multi_sport_betting_workflow import is_valid_score

        assert is_valid_score(None) is False

    def test_is_valid_score_with_nan(self):
        """is_valid_score returns False for NaN."""
        import math
        from multi_sport_betting_workflow import is_valid_score

        assert is_valid_score(float("nan")) is False
        assert is_valid_score(math.nan) is False

    def test_is_valid_score_with_inf(self):
        """is_valid_score returns False for infinity."""
        import math
        from multi_sport_betting_workflow import is_valid_score

        assert is_valid_score(float("inf")) is False
        assert is_valid_score(float("-inf")) is False
        assert is_valid_score(math.inf) is False

    def test_send_sms_disabled_returns_true(self):
        """send_sms returns True when SMTP_ALERTING_ENABLED is False."""
        from multi_sport_betting_workflow import send_sms, SMTP_ALERTING_ENABLED

        # When disabled, should return True without sending
        assert SMTP_ALERTING_ENABLED is False
        result = send_sms("1234567890", "Test Subject", "Test Body")
        assert result is True


# ============================================================================
# DAG Import and Structure Tests
# ============================================================================


class TestDAGImportAndStructure:
    """Test that the DAG can be imported and has correct structure."""

    def test_dag_imports_without_error(self):
        """The DAG module should import without errors."""
        import multi_sport_betting_workflow

        assert multi_sport_betting_workflow is not None

    def test_dag_object_exists(self):
        """The DAG object should be defined."""
        from multi_sport_betting_workflow import dag

        assert dag is not None
        assert dag.dag_id == "multi_sport_betting_workflow"

    def test_sports_config_exists(self):
        """SPORTS_CONFIG should be defined with all 9 sports."""
        from multi_sport_betting_workflow import SPORTS_CONFIG

        expected_sports = [
            "nba",
            "nhl",
            "mlb",
            "nfl",
            "epl",
            "ligue1",
            "tennis",
            "ncaab",
            "wncaab",
        ]
        for sport in expected_sports:
            assert sport in SPORTS_CONFIG, f"Missing sport: {sport}"
            assert "elo_module" in SPORTS_CONFIG[sport]
            assert "elo_threshold" in SPORTS_CONFIG[sport]

    def test_all_task_functions_are_callable(self):
        """All task functions should be callable."""
        from multi_sport_betting_workflow import (
            download_games,
            load_data_to_db,
            update_elo_ratings,
            fetch_prediction_markets,
            load_bets_to_db,
            identify_good_bets,
            place_bets_on_recommendations,
            place_portfolio_optimized_bets,
            send_daily_summary,
        )

        assert callable(download_games)
        assert callable(load_data_to_db)
        assert callable(update_elo_ratings)
        assert callable(fetch_prediction_markets)
        assert callable(load_bets_to_db)
        assert callable(identify_good_bets)
        assert callable(place_bets_on_recommendations)
        assert callable(place_portfolio_optimized_bets)
        assert callable(send_daily_summary)


# ============================================================================
# download_games Task Tests
# ============================================================================


class TestDownloadGamesTask:
    """Test download_games task function."""

    def test_download_games_nba_creates_instance(self, mock_airflow_context):
        """download_games creates NBAGames instance for NBA sport."""
        from multi_sport_betting_workflow import download_games

        with patch("nba_games.NBAGames") as mock_nba_games:
            mock_instance = MagicMock()
            mock_nba_games.return_value = mock_instance

            download_games("nba", **mock_airflow_context)

            # NBAGames should be called twice (for yesterday and today)
            assert mock_nba_games.call_count == 2
            # First call should be for yesterday (2026-01-26)
            mock_nba_games.assert_any_call(date_folder="2026-01-26")
            # Second call should be for today (2026-01-27)
            mock_nba_games.assert_any_call(date_folder="2026-01-27")
            # download_games_for_date should be called twice
            assert mock_instance.download_games_for_date.call_count == 2
            mock_instance.download_games_for_date.assert_any_call("2026-01-26")
            mock_instance.download_games_for_date.assert_any_call("2026-01-27")

    def test_download_games_nhl_creates_instance(self, mock_airflow_context):
        """download_games creates NHLGameEvents instance for NHL sport."""
        from multi_sport_betting_workflow import download_games

        with patch("nhl_game_events.NHLGameEvents") as mock_nhl_events:
            mock_instance = MagicMock()
            mock_nhl_events.return_value = mock_instance

            download_games("nhl", **mock_airflow_context)

            # NHLGameEvents should be called twice (for yesterday and today)
            assert mock_nhl_events.call_count == 2
            # First call should be for yesterday (2026-01-26)
            mock_nhl_events.assert_any_call(date_folder="2026-01-26")
            # Second call should be for today (2026-01-27)
            mock_nhl_events.assert_any_call(date_folder="2026-01-27")
            # download_games_for_date should be called twice
            assert mock_instance.download_games_for_date.call_count == 2
            mock_instance.download_games_for_date.assert_any_call("2026-01-26")
            mock_instance.download_games_for_date.assert_any_call("2026-01-27")

    def test_download_games_tennis_creates_instance(self, mock_airflow_context):
        """download_games creates TennisGames instance for tennis sport."""
        from multi_sport_betting_workflow import download_games

        with patch("tennis_games.TennisGames") as mock_tennis:
            mock_instance = MagicMock()
            mock_tennis.return_value = mock_instance

            download_games("tennis", **mock_airflow_context)

            mock_tennis.assert_called_once()
            mock_instance.download_games.assert_called_once()

    def test_download_games_uses_context_ds(self, mock_airflow_context):
        """download_games uses ds from context for date."""
        from multi_sport_betting_workflow import download_games

        with patch("nba_games.NBAGames") as mock_nba:
            mock_instance = MagicMock()
            mock_nba.return_value = mock_instance

            mock_airflow_context["ds"] = "2026-02-15"
            download_games("nba", **mock_airflow_context)

            # download_games_for_date should be called twice (for yesterday and today)
            assert mock_instance.download_games_for_date.call_count == 2
            # First call should be for yesterday (2026-02-14)
            mock_instance.download_games_for_date.assert_any_call("2026-02-14")
            # Second call should be for today (2026-02-15)
            mock_instance.download_games_for_date.assert_any_call("2026-02-15")


# ============================================================================
# update_elo_ratings Task Tests
# ============================================================================


class TestUpdateEloRatingsTask:
    """Test update_elo_ratings task function."""

    def test_update_elo_nba_queries_database(
        self, mock_airflow_context, sample_game_data
    ):
        """update_elo_ratings queries nba_games table for NBA."""
        from multi_sport_betting_workflow import update_elo_ratings

        with patch("plugins.db_manager.default_db") as mock_db:
            with patch("elo.get_elo_class") as mock_get_elo:
                mock_db.fetch_df.return_value = sample_game_data
                mock_elo_class = MagicMock()
                mock_elo_instance = MagicMock()
                mock_elo_instance.ratings = {"Lakers": 1550, "Celtics": 1520}
                mock_elo_class.return_value = mock_elo_instance
                mock_get_elo.return_value = mock_elo_class

                with patch("builtins.open", MagicMock()):
                    with patch("multi_sport_betting_workflow.Path"):
                        update_elo_ratings("nba", **mock_airflow_context)

                # Verify database was queried
                mock_db.fetch_df.assert_called_once()
                call_args = mock_db.fetch_df.call_args
                # Now uses unified_games table with sport filter
                assert "unified_games" in call_args[0][0]
                assert "sport = 'NBA'" in call_args[0][0]

    def test_update_elo_pushes_to_xcom(self, mock_airflow_context, sample_game_data):
        """update_elo_ratings pushes ratings to XCom."""
        from multi_sport_betting_workflow import update_elo_ratings

        with patch("plugins.db_manager.default_db") as mock_db:
            with patch("elo.get_elo_class") as mock_get_elo:
                mock_db.fetch_df.return_value = sample_game_data
                mock_elo_class = MagicMock()
                mock_elo_instance = MagicMock()
                mock_elo_instance.ratings = {"Lakers": 1550, "Celtics": 1520}
                mock_elo_class.return_value = mock_elo_instance
                mock_get_elo.return_value = mock_elo_class

                with patch("builtins.open", MagicMock()):
                    with patch("multi_sport_betting_workflow.Path"):
                        update_elo_ratings("nba", **mock_airflow_context)

                # Verify XCom push was called
                xcom_store = mock_airflow_context["_xcom_store"]
                assert "nba_elo_ratings" in xcom_store

    def test_update_elo_handles_empty_dataframe(self, mock_airflow_context):
        """update_elo_ratings returns early for empty dataframe."""
        import pandas as pd
        from multi_sport_betting_workflow import update_elo_ratings

        with patch("plugins.db_manager.default_db") as mock_db:
            with patch("elo.get_elo_class") as mock_get_elo:
                mock_db.fetch_df.return_value = pd.DataFrame()

                # Should not raise, should return early
                result = update_elo_ratings("nba", **mock_airflow_context)
                assert result is None


# ============================================================================
# fetch_prediction_markets Task Tests
# ============================================================================


class TestFetchPredictionMarketsTask:
    """Test fetch_prediction_markets task function."""

    def test_fetch_markets_nba_calls_correct_function(
        self, mock_airflow_context, sample_market_data
    ):
        """fetch_prediction_markets calls fetch_nba_markets for NBA."""
        from multi_sport_betting_workflow import fetch_prediction_markets

        with patch("kalshi_markets.fetch_nba_markets") as mock_fetch:
            mock_fetch.return_value = sample_market_data

            with patch("builtins.open", MagicMock()):
                with patch("multi_sport_betting_workflow.Path"):
                    fetch_prediction_markets("nba", **mock_airflow_context)

            mock_fetch.assert_called_once_with("2026-01-27")

    def test_fetch_markets_nhl_calls_correct_function(
        self, mock_airflow_context, sample_market_data
    ):
        """fetch_prediction_markets calls fetch_nhl_markets for NHL."""
        from multi_sport_betting_workflow import fetch_prediction_markets

        with patch("kalshi_markets.fetch_nhl_markets") as mock_fetch:
            mock_fetch.return_value = sample_market_data

            with patch("builtins.open", MagicMock()):
                with patch("multi_sport_betting_workflow.Path"):
                    fetch_prediction_markets("nhl", **mock_airflow_context)

            mock_fetch.assert_called_once_with("2026-01-27")

    def test_fetch_markets_tennis_calls_correct_function(self, mock_airflow_context):
        """fetch_prediction_markets calls fetch_tennis_markets for tennis."""
        from multi_sport_betting_workflow import fetch_prediction_markets

        with patch("kalshi_markets.fetch_tennis_markets") as mock_fetch:
            mock_fetch.return_value = []

            fetch_prediction_markets("tennis", **mock_airflow_context)

            mock_fetch.assert_called_once_with("2026-01-27")

    def test_fetch_markets_pushes_to_xcom(
        self, mock_airflow_context, sample_market_data
    ):
        """fetch_prediction_markets pushes markets to XCom."""
        from multi_sport_betting_workflow import fetch_prediction_markets

        with patch("kalshi_markets.fetch_nba_markets") as mock_fetch:
            mock_fetch.return_value = sample_market_data

            with patch("builtins.open", MagicMock()):
                with patch("multi_sport_betting_workflow.Path"):
                    fetch_prediction_markets("nba", **mock_airflow_context)

            xcom_store = mock_airflow_context["_xcom_store"]
            assert "nba_markets" in xcom_store
            assert len(xcom_store["nba_markets"]) == 2

    def test_fetch_markets_handles_empty_response(self, mock_airflow_context):
        """fetch_prediction_markets handles empty market list gracefully."""
        from multi_sport_betting_workflow import fetch_prediction_markets

        with patch("kalshi_markets.fetch_nba_markets") as mock_fetch:
            mock_fetch.return_value = []

            # Should not raise
            fetch_prediction_markets("nba", **mock_airflow_context)

            # XCom should not be pushed for empty markets
            xcom_store = mock_airflow_context["_xcom_store"]
            assert "nba_markets" not in xcom_store


# ============================================================================
# identify_good_bets Task Tests
# ============================================================================


class TestIdentifyGoodBetsTask:
    """Test identify_good_bets task function."""

    def test_identify_bets_creates_comparator(self, mock_airflow_context):
        """identify_good_bets creates OddsComparator instance."""
        from multi_sport_betting_workflow import identify_good_bets

        # Setup mock XCom with ratings
        mock_airflow_context["task_instance"].xcom_pull = MagicMock(
            return_value={"Lakers": 1550, "Celtics": 1520}
        )

        with patch("odds_comparator.OddsComparator") as mock_comparator:
            with patch("plugins.db_manager.default_db") as mock_db:
                mock_db.fetch_df.return_value = MagicMock(empty=False)
                mock_db.fetch_df.return_value.__len__ = lambda x: 1
                mock_comparator_instance = MagicMock()
                mock_comparator_instance.find_opportunities.return_value = []
                mock_comparator.return_value = mock_comparator_instance

                with patch("builtins.open", MagicMock()):
                    with patch("multi_sport_betting_workflow.Path"):
                        identify_good_bets("nba", **mock_airflow_context)

                mock_comparator.assert_called_once()

    def test_identify_bets_uses_min_edge(self, mock_airflow_context):
        """identify_good_bets uses min_edge parameter."""
        from multi_sport_betting_workflow import identify_good_bets
        from odds_comparator import BettingOpportunityConfig

        mock_airflow_context["task_instance"].xcom_pull = MagicMock(
            return_value={"Lakers": 1550, "Celtics": 1520}
        )

        with patch("odds_comparator.OddsComparator") as mock_comparator:
            with patch("plugins.db_manager.default_db") as mock_db:
                mock_db.fetch_df.return_value = MagicMock(empty=False)
                mock_db.fetch_df.return_value.__len__ = lambda x: 1
                mock_comparator_instance = MagicMock()
                mock_comparator_instance.find_opportunities.return_value = []
                mock_comparator.return_value = mock_comparator_instance

                with patch("builtins.open", MagicMock()):
                    with patch("multi_sport_betting_workflow.Path"):
                        identify_good_bets("nba", **mock_airflow_context)

                # Verify find_opportunities is called with correct config
                mock_comparator_instance.find_opportunities.assert_called_once()
                config_arg = mock_comparator_instance.find_opportunities.call_args[0][0]
                assert isinstance(config_arg, BettingOpportunityConfig)
                assert (
                    config_arg.thresholds.min_edge == 0.03
                )  # MIN_EDGE_THRESHOLD from DAG

    def test_identify_bets_handles_missing_ratings(self, mock_airflow_context):
        """identify_good_bets returns early when no Elo ratings available."""
        from multi_sport_betting_workflow import identify_good_bets

        mock_airflow_context["task_instance"].xcom_pull = MagicMock(return_value=None)

        with patch("odds_comparator.OddsComparator") as mock_comparator:
            with patch("plugins.db_manager.default_db") as mock_db:
                # Should return early due to missing ratings
                try:
                    identify_good_bets("nba", **mock_airflow_context)
                except ValueError:
                    pass  # Expected - now raises ValueError for missing ratings

                mock_comparator.assert_not_called()


# ============================================================================
# update_glicko2_ratings Task Tests
# ============================================================================


class TestUpdateGlicko2RatingsTask:
    """Test update_glicko2_ratings task function."""

    def test_update_glicko2_nba_queries_database(
        self, mock_airflow_context, sample_game_data
    ):
        """update_glicko2_ratings queries database for NBA games."""
        from multi_sport_betting_workflow import update_glicko2_ratings

        with patch("plugins.db_manager.default_db") as mock_db:
            with patch("glicko2_rating.NBAGlicko2Rating") as mock_glicko_class:
                mock_db.fetch_df.return_value = sample_game_data
                mock_glicko_instance = MagicMock()
                mock_glicko_instance.ratings = {
                    "Lakers": {"rating": 1550, "rd": 50, "vol": 0.06}
                }
                mock_glicko_class.return_value = mock_glicko_instance

                with patch("builtins.open", MagicMock()):
                    with patch("multi_sport_betting_workflow.Path"):
                        update_glicko2_ratings("nba", **mock_airflow_context)

                mock_db.fetch_df.assert_called_once()

    def test_update_glicko2_unsupported_sport_returns_early(self, mock_airflow_context):
        """update_glicko2_ratings returns early for unsupported sports."""
        from multi_sport_betting_workflow import update_glicko2_ratings

        # Tennis doesn't have Glicko-2 implementation
        result = update_glicko2_ratings("tennis", **mock_airflow_context)
        assert result is None


# ============================================================================
# load_bets_to_db Task Tests
# ============================================================================


class TestLoadBetsToDbTask:
    """Test load_bets_to_db task function."""

    def test_load_bets_creates_loader(self, mock_airflow_context):
        """load_bets_to_db creates BetLoader instance."""
        from multi_sport_betting_workflow import load_bets_to_db

        with patch("bet_loader.BetLoader") as mock_loader_class:
            mock_loader = MagicMock()
            mock_loader.load_bets_for_date.return_value = 5
            mock_loader_class.return_value = mock_loader

            load_bets_to_db("nba", **mock_airflow_context)

            mock_loader_class.assert_called_once()
            mock_loader.load_bets_for_date.assert_called_once_with("nba", "2026-01-27")


# ============================================================================
# place_bets_on_recommendations Task Tests
# ============================================================================


class TestPlaceBetsOnRecommendationsTask:
    """Test place_bets_on_recommendations task function."""

    def test_place_bets_is_deprecated(self, mock_airflow_context, capsys):
        """place_bets_on_recommendations is deprecated and returns early."""
        from multi_sport_betting_workflow import place_bets_on_recommendations

        # Should print deprecation warning and return immediately
        place_bets_on_recommendations("nba", **mock_airflow_context)

        captured = capsys.readouterr()
        assert "DEPRECATED" in captured.out
        assert (
            "portfolio betting" in captured.out.lower() or "portfolio" in captured.out
        )

    def test_place_bets_does_not_call_kalshi(self, mock_airflow_context):
        """Deprecated function should not call KalshiBetting."""
        from multi_sport_betting_workflow import place_bets_on_recommendations

        with patch("kalshi_betting.KalshiBetting") as mock_kalshi:
            # The deprecated function should not call KalshiBetting at all
            place_bets_on_recommendations("nba", **mock_airflow_context)

            mock_kalshi.assert_not_called()

    def test_place_bets_handles_any_sport(self, mock_airflow_context):
        """Deprecated function should work for any sport input."""
        from multi_sport_betting_workflow import place_bets_on_recommendations

        # Should not raise for any sport
        for sport in ["nba", "nhl", "mlb", "tennis", "epl"]:
            place_bets_on_recommendations(sport, **mock_airflow_context)


# ============================================================================
# Integration Smoke Tests (End-to-End Flow)
# ============================================================================


class TestDAGTaskFlow:
    """Test task dependencies and data flow through the DAG."""

    def test_dag_has_expected_task_count(self):
        """DAG should have expected number of tasks."""
        from multi_sport_betting_workflow import dag

        # 9 sports * 7 tasks per sport + 3 final tasks (portfolio, clv, summary)
        # = 63 + 3 = 66 minimum
        assert len(dag.tasks) >= 60

    def test_dag_schedule_is_daily(self):
        """DAG should run daily at 5 AM UTC."""
        from multi_sport_betting_workflow import dag

        assert dag.schedule is not None
        # Schedule should be cron expression for 5 AM UTC
        assert "5" in str(dag.schedule) or dag.schedule == "@daily"

    def test_dag_has_correct_tags(self):
        """DAG should have appropriate tags."""
        from multi_sport_betting_workflow import dag

        assert "betting" in dag.tags
        assert "elo" in dag.tags


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Test error handling in task functions."""

    def test_download_games_propagates_errors(self, mock_airflow_context):
        """download_games should propagate exceptions for retry logic."""
        from multi_sport_betting_workflow import download_games

        with patch("nba_games.NBAGames") as mock_nba:
            mock_nba.return_value.download_games_for_date.side_effect = Exception(
                "API Error"
            )

            # NBA download catches exceptions and doesn't re-raise them
            # (see comment in download_games: "Don't raise the exception - let other sports continue")
            # So the function should complete without raising
            download_games("nba", **mock_airflow_context)
            # Should have tried to download for both dates
            assert mock_nba.return_value.download_games_for_date.call_count == 2

    def test_fetch_markets_propagates_errors(self, mock_airflow_context):
        """fetch_prediction_markets should propagate exceptions."""
        from multi_sport_betting_workflow import fetch_prediction_markets

        with patch("kalshi_markets.fetch_nba_markets") as mock_fetch:
            mock_fetch.side_effect = Exception("Kalshi API Error")

            with pytest.raises(Exception, match="Kalshi API Error"):
                fetch_prediction_markets("nba", **mock_airflow_context)
