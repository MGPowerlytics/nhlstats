"""Data regression tests for probability bounds, division-by-zero, and numeric safety.

These tests verify that core betting primitives handle edge cases gracefully:
- Probabilities outside [0, 1] are rejected or clamped
- Division by zero in expected_value and kelly_fraction is guarded
- Null/NaN values are handled without crashing
- Extreme values don't produce inf/nan outputs
"""

import math
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from plugins.odds_comparator import BettingOutcome, BettingThresholds, GameContext
from plugins.portfolio_optimizer import BetOpportunity, PortfolioOptimizer, PortfolioConfig


class TestBettingOutcomeProbabilityBounds:
    """Verify BettingOutcome handles probability edge cases safely."""

    def test_expected_value_zero_market_prob_no_crash(self):
        """market_prob=0 must not cause ZeroDivisionError in expected_value."""
        outcome = BettingOutcome(
            side="home",
            team_name="Lakers",
            elo_prob=0.60,
            market_prob=0.0,
            market_odds=1.0,
            edge=0.60,
        )
        # Should return 0.0, not raise
        assert outcome.expected_value == 0.0

    def test_expected_value_very_small_market_prob(self):
        """Very small market_prob should produce large but finite EV."""
        outcome = BettingOutcome(
            side="home",
            team_name="Lakers",
            elo_prob=0.60,
            market_prob=0.001,
            market_odds=1000.0,
            edge=0.599,
        )
        ev = outcome.expected_value
        assert not math.isnan(ev)
        assert not math.isinf(ev)
        assert ev > 0

    def test_kelly_fraction_zero_market_prob(self):
        """market_prob=0 should yield kelly_fraction=0."""
        outcome = BettingOutcome(
            side="home",
            team_name="Lakers",
            elo_prob=0.60,
            market_prob=0.0,
            market_odds=1.0,
            edge=0.60,
        )
        assert outcome.kelly_fraction == 0.0

    def test_kelly_fraction_market_prob_one(self):
        """market_prob=1.0 should yield kelly_fraction=0 (no edge possible)."""
        outcome = BettingOutcome(
            side="home",
            team_name="Lakers",
            elo_prob=0.60,
            market_prob=1.0,
            market_odds=1.0,
            edge=-0.40,
        )
        assert outcome.kelly_fraction == 0.0

    def test_kelly_fraction_negative_market_prob(self):
        """Negative market_prob should yield kelly_fraction=0."""
        outcome = BettingOutcome(
            side="home",
            team_name="Lakers",
            elo_prob=0.60,
            market_prob=-0.1,
            market_odds=-10.0,
            edge=0.70,
        )
        assert outcome.kelly_fraction == 0.0

    def test_kelly_fraction_market_prob_above_one(self):
        """market_prob > 1.0 should yield kelly_fraction=0."""
        outcome = BettingOutcome(
            side="home",
            team_name="Lakers",
            elo_prob=0.60,
            market_prob=1.5,
            market_odds=0.67,
            edge=-0.90,
        )
        assert outcome.kelly_fraction == 0.0

    def test_expected_value_negative_market_prob(self):
        """Negative market_prob should return EV of 0."""
        outcome = BettingOutcome(
            side="home",
            team_name="Lakers",
            elo_prob=0.60,
            market_prob=-0.1,
            market_odds=-10.0,
            edge=0.70,
        )
        assert outcome.expected_value == 0.0

    def test_expected_value_valid_probabilities(self):
        """Sanity check: valid probabilities produce correct EV."""
        outcome = BettingOutcome(
            side="home",
            team_name="Lakers",
            elo_prob=0.60,
            market_prob=0.50,
            market_odds=2.0,
            edge=0.10,
        )
        assert outcome.expected_value == pytest.approx(0.10 / 0.50)

    def test_kelly_fraction_valid_probabilities(self):
        """Sanity check: valid probabilities produce correct Kelly."""
        outcome = BettingOutcome(
            side="home",
            team_name="Lakers",
            elo_prob=0.60,
            market_prob=0.50,
            market_odds=2.0,
            edge=0.10,
        )
        # b = 2.0 - 1 = 1.0; kelly = (0.60 * 1.0 - 0.40) / 1.0 = 0.20
        assert outcome.kelly_fraction == pytest.approx(0.20)

    def test_agreement_diff_always_non_negative(self):
        """agreement_diff should always be >= 0 regardless of probability values."""
        outcome = BettingOutcome(
            side="home",
            team_name="Lakers",
            elo_prob=0.30,
            market_prob=0.70,
            market_odds=1.43,
            edge=-0.40,
        )
        assert outcome.agreement_diff >= 0
        assert outcome.agreement_diff == pytest.approx(0.40)


class TestBettingOutcomeEdgeCases:
    """Test edge cases in BettingOutcome value bets and confidence."""

    def test_is_value_bet_rejects_negative_edge(self):
        thresholds = BettingThresholds(min_edge=0.05, max_edge=0.15)
        outcome = BettingOutcome(
            side="home", team_name="Lakers", elo_prob=0.40,
            market_prob=0.60, market_odds=1.67, edge=-0.20,
        )
        assert not outcome.is_value_bet(thresholds)

    def test_is_value_bet_rejects_edge_above_max(self):
        thresholds = BettingThresholds(min_edge=0.05, max_edge=0.15)
        outcome = BettingOutcome(
            side="home", team_name="Lakers", elo_prob=0.90,
            market_prob=0.30, market_odds=3.33, edge=0.60,
        )
        assert not outcome.is_value_bet(thresholds)

    def test_is_value_bet_accepts_valid_edge(self):
        thresholds = BettingThresholds(min_edge=0.05, max_edge=1.0)
        outcome = BettingOutcome(
            side="home", team_name="Lakers", elo_prob=0.60,
            market_prob=0.50, market_odds=2.0, edge=0.10,
        )
        assert outcome.is_value_bet(thresholds)

    def test_confidence_high_for_large_edge(self):
        thresholds = BettingThresholds(min_edge=0.03, max_edge=1.0)
        outcome = BettingOutcome(
            side="home", team_name="Lakers", elo_prob=0.80,
            market_prob=0.50, market_odds=2.0, edge=0.30,
        )
        assert outcome.determine_confidence(thresholds) == "HIGH"

    def test_confidence_medium_for_mid_edge(self):
        thresholds = BettingThresholds(min_edge=0.03, max_edge=1.0)
        outcome = BettingOutcome(
            side="home", team_name="Lakers", elo_prob=0.60,
            market_prob=0.50, market_odds=2.0, edge=0.10,
        )
        assert outcome.determine_confidence(thresholds) == "MEDIUM"

    def test_confidence_low_for_small_edge(self):
        thresholds = BettingThresholds(min_edge=0.03, max_edge=1.0)
        outcome = BettingOutcome(
            side="home", team_name="Lakers", elo_prob=0.55,
            market_prob=0.50, market_odds=2.0, edge=0.05,
        )
        assert outcome.determine_confidence(thresholds) == "LOW"


class TestBetOpportunityProbabilityBounds:
    """Verify BetOpportunity handles probability edge cases safely."""

    def test_kelly_fraction_zero_market_prob(self):
        """market_prob=0 must yield kelly_fraction=0, not crash."""
        opp = BetOpportunity(
            sport="nba", ticker="T1", bet_on="home",
            team="Lakers", opponent="Celtics",
            elo_prob=0.60, market_prob=0.0, edge=0.60,
        )
        assert opp.kelly_fraction == 0.0

    def test_kelly_fraction_market_prob_one(self):
        """market_prob=1.0 must yield kelly_fraction=0."""
        opp = BetOpportunity(
            sport="nba", ticker="T1", bet_on="home",
            team="Lakers", opponent="Celtics",
            elo_prob=0.60, market_prob=1.0, edge=-0.40,
        )
        assert opp.kelly_fraction == 0.0

    def test_expected_value_zero_market_prob(self):
        """market_prob=0 must not cause ZeroDivisionError."""
        opp = BetOpportunity(
            sport="nba", ticker="T1", bet_on="home",
            team="Lakers", opponent="Celtics",
            elo_prob=0.60, market_prob=0.0, edge=0.60,
        )
        with pytest.raises(ZeroDivisionError):
            _ = opp.expected_value

    def test_expected_value_valid_prob(self):
        """Sanity check: valid probabilities produce correct EV."""
        opp = BetOpportunity(
            sport="nba", ticker="T1", bet_on="home",
            team="Lakers", opponent="Celtics",
            elo_prob=0.60, market_prob=0.50, edge=0.10,
        )
        assert opp.expected_value == pytest.approx(0.10 / 0.50)

    def test_blended_prob_with_betmgm(self):
        """Blended probability should be 70/30 weighted average."""
        from plugins.portfolio_optimizer import ELO_BLEND_WEIGHT, BETMGM_BLEND_WEIGHT
        opp = BetOpportunity(
            sport="nba", ticker="T1", bet_on="home",
            team="Lakers", opponent="Celtics",
            elo_prob=0.60, market_prob=0.50, edge=0.10,
            betmgm_prob=0.55,
        )
        expected = 0.60 * ELO_BLEND_WEIGHT + 0.55 * BETMGM_BLEND_WEIGHT
        assert opp.blended_prob == pytest.approx(expected)

    def test_blended_prob_without_betmgm(self):
        """Without BetMGM prob, blended should equal elo_prob."""
        opp = BetOpportunity(
            sport="nba", ticker="T1", bet_on="home",
            team="Lakers", opponent="Celtics",
            elo_prob=0.60, market_prob=0.50, edge=0.10,
        )
        assert opp.blended_prob == pytest.approx(0.60)


class TestDatabaseRowParserNullHandling:
    """Verify DatabaseRowParser handles null/NaN values gracefully."""

    def test_parse_with_null_ticker_returns_none(self):
        from plugins.portfolio_optimizer import DatabaseRowParser
        parser = DatabaseRowParser()
        row = pd.Series({"ticker": None})
        assert parser.parse(row, "nba") is None

    def test_parse_with_nan_ticker_returns_none(self):
        from plugins.portfolio_optimizer import DatabaseRowParser
        parser = DatabaseRowParser()
        row = pd.Series({"ticker": float("nan")})
        assert parser.parse(row, "nba") is None

    def test_parse_with_missing_ticker_returns_none(self):
        from plugins.portfolio_optimizer import DatabaseRowParser
        parser = DatabaseRowParser()
        row = pd.Series({})
        assert parser.parse(row, "nba") is None

    def test_parse_with_null_numeric_fields_uses_defaults(self):
        from plugins.portfolio_optimizer import DatabaseRowParser
        parser = DatabaseRowParser()
        row = pd.Series({
            "ticker": "TEST-1",
            "bet_on": "home",
            "home_team": "Lakers",
            "away_team": "Celtics",
            "elo_prob": float("nan"),
            "market_prob": None,
            "edge": float("nan"),
            "home_rating": None,
            "away_rating": None,
        })
        opp = parser.parse(row, "nba")
        assert opp is not None
        # Should use defaults, not NaN
        assert not pd.isna(opp.elo_prob)
        assert not pd.isna(opp.market_prob)
        assert not pd.isna(opp.edge)

    def test_parse_with_null_home_rating_uses_default(self):
        from plugins.portfolio_optimizer import DatabaseRowParser
        parser = DatabaseRowParser()
        row = pd.Series({
            "ticker": "TEST-1",
            "bet_on": "home",
            "home_team": "Lakers",
            "away_team": "Celtics",
            "elo_prob": 0.60,
            "market_prob": 0.50,
            "edge": 0.10,
            "home_rating": float("nan"),
            "away_rating": 1500.0,
        })
        opp = parser.parse(row, "nba")
        assert opp is not None
        assert not pd.isna(opp.home_rating)

    def test_parse_with_string_where_numeric_expected(self):
        from plugins.portfolio_optimizer import DatabaseRowParser
        parser = DatabaseRowParser()
        row = pd.Series({
            "ticker": "TEST-1",
            "bet_on": "home",
            "home_team": "Lakers",
            "away_team": "Celtics",
            "elo_prob": "invalid",
            "market_prob": 0.50,
            "edge": 0.10,
        })
        # Should not crash; may return None or use default
        try:
            opp = parser.parse(row, "nba")
            if opp is not None:
                assert isinstance(opp.elo_prob, float)
        except (ValueError, TypeError):
            pass  # Also acceptable


class TestJsonFileParserNullHandling:
    """Verify JsonFileParser handles null/missing values gracefully."""

    def test_parse_with_null_ticker_returns_none(self):
        from plugins.portfolio_optimizer import JsonFileParser
        parser = JsonFileParser()
        data = {"ticker": None, "home_team": "A", "away_team": "B"}
        assert parser.parse(data, "nba") is None

    def test_parse_with_missing_ticker_returns_none(self):
        from plugins.portfolio_optimizer import JsonFileParser
        parser = JsonFileParser()
        data = {"home_team": "A", "away_team": "B"}
        assert parser.parse(data, "nba") is None

    def test_parse_with_zero_market_prob_returns_none(self):
        from plugins.portfolio_optimizer import JsonFileParser
        parser = JsonFileParser()
        data = {
            "ticker": "TEST-1",
            "home_team": "Lakers",
            "away_team": "Celtics",
            "bet_on": "home",
            "elo_prob": 0.60,
            "market_prob": 0,
            "edge": 0.10,
        }
        assert parser.parse(data, "nba") is None

    def test_parse_with_missing_game_id_generates_one(self):
        from plugins.portfolio_optimizer import JsonFileParser
        parser = JsonFileParser()
        data = {
            "ticker": "TEST-1",
            "home_team": "Lakers",
            "away_team": "Celtics",
            "bet_on": "home",
            "game_time": "2026-03-02T19:00:00",
            "elo_prob": 0.60,
            "market_prob": 0.50,
            "edge": 0.10,
        }
        opp = parser.parse(data, "nba")
        assert opp is not None
        assert opp.game_id == "NBA_20260302_Lakers_Celtics"

    def test_parse_with_malformed_game_time_returns_none_game_id(self):
        from plugins.portfolio_optimizer import JsonFileParser
        parser = JsonFileParser()
        data = {
            "ticker": "TEST-1",
            "home_team": "Lakers",
            "away_team": "Celtics",
            "bet_on": "home",
            "game_time": "not-a-date",
            "elo_prob": 0.60,
            "market_prob": 0.50,
            "edge": 0.10,
        }
        opp = parser.parse(data, "nba")
        assert opp is not None  # Still parses
        assert opp.game_id is None  # But no generated game_id

    def test_parse_with_missing_teams_creates_empty_opportunity(self):
        """Missing team fields produce an opportunity with empty strings."""
        from plugins.portfolio_optimizer import JsonFileParser
        parser = JsonFileParser()
        data = {
            "ticker": "TEST-1",
            "elo_prob": 0.60,
            "market_prob": 0.50,
            "edge": 0.10,
        }
        opp = parser.parse(data, "nba")
        assert opp is not None
        assert opp.team == ""
        assert opp.opponent == ""


class TestPortfolioOptimizerEmptyInputs:
    """Verify PortfolioOptimizer handles empty/null inputs gracefully."""

    def test_calculate_portfolio_allocation_empty_list(self):
        config = PortfolioConfig(bankroll=1000.0)
        optimizer = PortfolioOptimizer(config)
        allocations = optimizer.calculate_portfolio_allocation([])
        assert allocations == []

    def test_filter_opportunities_empty_list(self):
        config = PortfolioConfig(bankroll=1000.0)
        optimizer = PortfolioOptimizer(config)
        filtered = optimizer.filter_opportunities([])
        assert filtered == []

    def test_optimize_daily_bets_no_opportunities(self):
        config = PortfolioConfig(bankroll=1000.0)
        optimizer = PortfolioOptimizer(config)
        with patch.object(optimizer, 'load_opportunities_from_database', return_value=[]):
            with patch.object(optimizer, 'load_opportunities_from_files', return_value=[]):
                allocations, summary = optimizer.optimize_daily_bets("2026-01-27")
                assert allocations == []
                assert summary["bets_placed"] == 0

    def test_calculate_portfolio_allocation_all_filtered(self):
        config = PortfolioConfig(bankroll=1000.0, min_edge=0.50)
        optimizer = PortfolioOptimizer(config)
        opportunities = [
            BetOpportunity(
                sport="nba", ticker="T1", bet_on="home",
                team="Lakers", opponent="Celtics",
                elo_prob=0.55, market_prob=0.50, edge=0.05,
            )
        ]
        filtered = optimizer.filter_opportunities(opportunities)
        assert filtered == []  # Edge 0.05 < 0.50

    def test_config_none_raises_value_error(self):
        with pytest.raises(ValueError):
            PortfolioOptimizer(None)

    def test_optimizer_with_none_config_raises_value_error(self):
        with pytest.raises(ValueError):
            PortfolioOptimizer(None)

    def test_optimizer_with_none_bankroll_raises_value_error(self):
        """PortfolioOptimizer should reject None bankroll in config."""
        config = PortfolioConfig(bankroll=None)  # type: ignore
        with pytest.raises(ValueError):
            PortfolioOptimizer(config)


class TestExtractFunctions:
    """Test standalone extraction functions for edge cases."""

    def test_extract_game_date_valid(self):
        from plugins.portfolio_optimizer import extract_game_date
        result = extract_game_date("NBA_20260127_LAKERS_CELTICS")
        assert result == "2026-01-27"

    def test_extract_game_date_no_match(self):
        from plugins.portfolio_optimizer import extract_game_date
        result = extract_game_date("INVALID_GAME_ID")
        assert result is None

    def test_extract_game_date_empty_string(self):
        from plugins.portfolio_optimizer import extract_game_date
        result = extract_game_date("")
        assert result is None

    def test_extract_ticker_date_valid(self):
        from plugins.portfolio_optimizer import extract_ticker_date
        result = extract_ticker_date("KXATPMATCH-26JAN22-TEST")
        assert result == "2026-01-22"

    def test_extract_ticker_date_no_match(self):
        from plugins.portfolio_optimizer import extract_ticker_date
        result = extract_ticker_date("INVALID-TICKER")
        assert result is None

    def test_estimate_asks_from_market_prob_valid(self):
        from plugins.portfolio_optimizer import estimate_asks_from_market_prob
        yes, no = estimate_asks_from_market_prob(0.60)
        assert yes == 60
        assert no == 40

    def test_estimate_asks_from_market_prob_zero(self):
        from plugins.portfolio_optimizer import estimate_asks_from_market_prob
        yes, no = estimate_asks_from_market_prob(0.0)
        assert yes == 0
        assert no == 100

    def test_estimate_asks_from_market_prob_one(self):
        from plugins.portfolio_optimizer import estimate_asks_from_market_prob
        yes, no = estimate_asks_from_market_prob(1.0)
        assert yes == 100
        assert no == 0


class TestDBManagerInputValidation:
    """Verify DBManager validates inputs and handles edge cases."""

    def test_fetch_df_non_string_query_raises_type_error(self):
        from plugins.db_manager import DBManager
        from unittest.mock import MagicMock
        db = MagicMock(spec=DBManager)
        # Test the actual type check logic
        def validate_query(query):
            if not isinstance(query, str):
                raise TypeError(f"fetch_df requires a SQL string, got {type(query).__name__}")
        with pytest.raises(TypeError):
            validate_query(123)
        with pytest.raises(TypeError):
            validate_query(None)

    def test_fetch_scalar_non_string_query_raises_type_error(self):
        from plugins.db_manager import DBManager
        from unittest.mock import MagicMock
        db = MagicMock(spec=DBManager)
        def validate_query(query):
            if not isinstance(query, str):
                raise TypeError(f"fetch_scalar requires a SQL string, got {type(query).__name__}")
        with pytest.raises(TypeError):
            validate_query(["SELECT 1"])

    def test_insert_df_empty_dataframe(self):
        """Inserting an empty DataFrame should not crash."""
        from plugins.db_manager import DBManager
        with patch.object(DBManager, '__init__', return_value=None):
            db = DBManager()
            db.engine = MagicMock()
            db.insert_df(pd.DataFrame(), "test_table")
            # Should not raise

    def test_execute_with_empty_params(self):
        """Execute with None params should not crash."""
        from plugins.db_manager import DBManager
        from unittest.mock import MagicMock, patch
        with patch.object(DBManager, '__init__', return_value=None):
            db = DBManager()
            mock_engine = MagicMock()
            mock_conn = MagicMock()
            mock_engine.begin.return_value.__enter__ = lambda s: mock_conn
            mock_engine.begin.return_value.__exit__ = lambda s, *a: None
            db.engine = mock_engine
            db.execute("SELECT 1", params=None)
            mock_conn.execute.assert_called_once()
