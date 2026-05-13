#!/usr/bin/env python3
"""Tests for the comprehensive BettingOddsSchema validation contract."""

import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta

from pandera.errors import SchemaErrors

from plugins.odds_feed_schema import (
    BettingOddsSchema,
    validate_betting_odds,
    SchemaDriftError,
    check_categorical_distribution_shift,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_row():
    """Template for a single valid odds record."""
    return {
        "sport": "NBA",
        "game_id": "NBA_20260426_LAL_GSW",
        "home_team": "Golden State Warriors",
        "away_team": "Los Angeles Lakers",
        "commence_time": pd.Timestamp(datetime.now(timezone.utc) + timedelta(hours=2)),
        "odds_timestamp": pd.Timestamp(datetime.now(timezone.utc) - timedelta(minutes=5)),
        "home_moneyline": -150.0,
        "away_moneyline": 130.0,
        "home_decimal_odds": 1.67,
        "away_decimal_odds": 2.30,
        "home_spread": -3.5,
        "away_spread": 3.5,
        "total_points": 220.5,
        "home_prob": 0.60,
        "away_prob": 0.43,
        "bet_type": "moneyline",
        "bookmaker": "DraftKings",
        "num_bookmakers": 5,
        "platform": "odds_api",
        "yes_ask": None,
        "no_ask": None,
    }


def make_df(rows):
    """Build a DataFrame from a list of row dicts."""
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Happy path — valid data passes
# ---------------------------------------------------------------------------

class TestValidData:
    def test_single_valid_row_passes(self, valid_row):
        df = make_df([valid_row])
        result = validate_betting_odds(df, check_distribution=False)
        assert len(result) == 1

    def test_multiple_valid_rows_pass(self, valid_row):
        rows = [dict(valid_row) for _ in range(10)]
        df = make_df(rows)
        result = validate_betting_odds(df, check_distribution=False)
        assert len(result) == 10


# ---------------------------------------------------------------------------
# Identifier integrity — zero nulls
# ---------------------------------------------------------------------------

class TestIdentifierIntegrity:

    def test_null_game_id_fails(self, valid_row):
        valid_row["game_id"] = None
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)

    def test_null_home_team_fails(self, valid_row):
        valid_row["home_team"] = None
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)

    def test_null_away_team_fails(self, valid_row):
        valid_row["away_team"] = None
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)

    def test_null_sport_fails(self, valid_row):
        valid_row["sport"] = None
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)

    def test_unknown_sport_fails(self, valid_row):
        valid_row["sport"] = "UNKNOWN"
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)

    def test_malformed_game_id_fails(self, valid_row):
        valid_row["game_id"] = "invalid-game-id"
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)

    def test_same_home_away_team_fails(self, valid_row):
        valid_row["home_team"] = "Lakers"
        valid_row["away_team"] = "Lakers"
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)


# ---------------------------------------------------------------------------
# Mathematical validity — odds ranges
# ---------------------------------------------------------------------------

class TestOddsRanges:

    def test_decimal_odds_below_minimum_fails(self, valid_row):
        valid_row["home_decimal_odds"] = 1.00
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)

    def test_decimal_odds_above_maximum_fails(self, valid_row):
        valid_row["away_decimal_odds"] = 600.0
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)

    def test_probability_below_minimum_fails(self, valid_row):
        valid_row["home_prob"] = 0.0
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)

    def test_probability_above_maximum_fails(self, valid_row):
        valid_row["away_prob"] = 1.5
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)

    def test_implied_prob_sum_below_one_fails(self, valid_row):
        # Sum must be >= 1.0 (bookmaker vig ensures > 1.0 in real markets)
        valid_row["home_prob"] = 0.30
        valid_row["away_prob"] = 0.30
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)

    def test_implied_prob_sum_above_max_fails(self, valid_row):
        valid_row["home_prob"] = 0.80
        valid_row["away_prob"] = 0.80
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)

    def test_spread_out_of_range_fails(self, valid_row):
        valid_row["home_spread"] = 60.0
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)

    def test_totals_out_of_range_fails(self, valid_row):
        valid_row["total_points"] = -5.0
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)


# ---------------------------------------------------------------------------
# Temporal consistency
# ---------------------------------------------------------------------------

class TestTemporalConsistency:

    def test_odds_timestamp_in_future_fails(self, valid_row):
        valid_row["odds_timestamp"] = pd.Timestamp(
            datetime.now(timezone.utc) + timedelta(hours=1)
        )
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)

    def test_commence_time_far_future_fails(self, valid_row):
        # More than 365 days in the future
        valid_row["commence_time"] = pd.Timestamp(
            datetime.now(timezone.utc) + timedelta(days=400)
        )
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)

    def test_null_odds_timestamp_allowed(self, valid_row):
        valid_row["odds_timestamp"] = None
        df = make_df([valid_row])
        result = validate_betting_odds(df, check_distribution=False)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Cross-column consistency
# ---------------------------------------------------------------------------

class TestCrossColumnConsistency:

    def test_asymmetric_spreads_warning(self, valid_row):
        """Asymmetric spreads should still pass (warning-level check)."""
        valid_row["home_spread"] = -3.5
        valid_row["away_spread"] = 5.0  # Should be +3.5
        df = make_df([valid_row])
        # This should still pass validation (it's a warning check, not hard block)
        result = validate_betting_odds(df, check_distribution=False)
        assert len(result) == 1

    def test_kalshi_price_sum_exceeding_110_fails(self, valid_row):
        valid_row["platform"] = "kalshi"
        valid_row["yes_ask"] = 70
        valid_row["no_ask"] = 60  # Sum = 130, exceeds 110
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)

    def test_valid_kalshi_prices_pass(self, valid_row):
        valid_row["platform"] = "kalshi"
        valid_row["yes_ask"] = 55
        valid_row["no_ask"] = 47  # Sum = 102, within tolerance
        df = make_df([valid_row])
        result = validate_betting_odds(df, check_distribution=False)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Invalid bookmaker / bet_type
# ---------------------------------------------------------------------------

class TestCategoricalValidity:

    def test_unknown_bookmaker_fails(self, valid_row):
        valid_row["bookmaker"] = "UnknownBookie"
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)

    def test_unknown_bet_type_fails(self, valid_row):
        valid_row["bet_type"] = "prop"
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)

    def test_unknown_platform_fails(self, valid_row):
        valid_row["platform"] = "unknown_source"
        df = make_df([valid_row])
        with pytest.raises(SchemaErrors):
            validate_betting_odds(df, check_distribution=False)


# ---------------------------------------------------------------------------
# Distribution shift detection
# ---------------------------------------------------------------------------

class TestDistributionShift:

    def test_balanced_distribution_passes(self):
        """Sport distribution matching baseline should pass."""
        rows = [
            {"sport": "NBA"},
            {"sport": "MLB"},
            {"sport": "MLB"},
            {"sport": "NHL"},
            {"sport": "EPL"},
        ]
        df = pd.DataFrame(rows)
        expected = {"NBA": 0.25, "MLB": 0.35, "NHL": 0.20, "EPL": 0.20}
        result = check_categorical_distribution_shift(df, "sport", expected, 30.0)
        assert result is True  # No shift detected

    def test_skewed_distribution_detected(self):
        """A category dominating >threshold above baseline should be flagged."""
        rows = [{"sport": "NBA"} for _ in range(9)] + [{"sport": "MLB"}]
        df = pd.DataFrame(rows)
        expected = {"NBA": 0.20, "MLB": 0.20, "NHL": 0.20}
        result = check_categorical_distribution_shift(df, "sport", expected, 20.0)
        assert result is False  # Shift detected: NBA is 90% vs expected 20%

    def test_empty_dataframe_skips_check(self):
        df = pd.DataFrame(columns=["sport"])
        result = check_categorical_distribution_shift(df, "sport", {"NBA": 0.5})
        assert result is True  # Skipped, no shift

    def test_missing_column_skips_check(self):
        df = pd.DataFrame({"other_col": [1, 2, 3]})
        result = check_categorical_distribution_shift(df, "sport", {"NBA": 0.5})
        assert result is True  # Skipped


# ---------------------------------------------------------------------------
# Lazy validation — all errors collected
# ---------------------------------------------------------------------------

class TestLazyValidation:

    def test_multiple_errors_collected(self, valid_row):
        """Lazy mode should report ALL violations, not just the first."""
        bad_row = dict(valid_row)
        bad_row["game_id"] = None
        bad_row["home_team"] = None
        bad_row["home_decimal_odds"] = 0.5  # Below minimum
        bad_row["sport"] = "INVALID"

        df = make_df([bad_row])
        with pytest.raises(SchemaErrors) as exc_info:
            validate_betting_odds(df, check_distribution=False)

        # Multiple distinct checks should have failed
        failure_checks = set(exc_info.value.failure_cases["check"].unique())
        assert len(failure_checks) >= 3


# ---------------------------------------------------------------------------
# Integration: validate_betting_odds wrapper
# ---------------------------------------------------------------------------

class TestValidateBettingOddsWrapper:

    def test_missing_required_columns_raises(self):
        df = pd.DataFrame({"foo": [1], "bar": [2]})
        with pytest.raises(ValueError, match="Missing required columns"):
            validate_betting_odds(df, check_distribution=False)

    def test_distribution_check_can_be_disabled(self, valid_row):
        """With check_distribution=False, sport imbalance should not raise."""
        rows = [dict(valid_row) for _ in range(20)]  # All NBA
        df = make_df(rows)
        # Should NOT raise SchemaDriftError because distribution check is off
        result = validate_betting_odds(df, check_distribution=False)
        assert len(result) == 20
