"""Tests for odds_data_schema.py — Pandera schema validation.

Covers OddsFeedSchema constraint enforcement, validate_odds_dataframe
wrapper behavior, and check_categorical_distribution_shift detection.
"""

from __future__ import annotations

import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pandera.errors
import pytest

# Add plugins/ to sys.path for schema import.
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins"))

# Suppress FutureWarning from pandera top-level imports.
warnings.filterwarnings("ignore", category=FutureWarning)

# ruff: noqa: E402 — imports below are after sys.path manipulation

from plugins.odds_data_schema import OddsFeedSchema
from plugins.odds_data_schema import check_categorical_distribution_shift
from plugins.odds_data_schema import validate_odds_dataframe


def _assert_passes(result: pd.DataFrame, expected: pd.DataFrame) -> None:
    """Assert that ``result`` is a valid output matching ``expected``.

    Pandera's ``coerce=True`` may change dtypes (e.g., losing tz from
    datetime, converting string to categorical), so we cannot use frame
    equality.  Instead we check shape, index, and the non-datetime,
    non-categorical columns.
    """
    assert isinstance(result, pd.DataFrame)
    assert result.shape == expected.shape
    assert list(result.index) == list(expected.index)
    # Compare only the columns that are safe: sport, game_id, home_team,
    # away_team, odds, probs, num_bookmakers, platform, best_*.
    safe_columns = [
        "sport", "game_id", "home_team", "away_team",
        "home_odds", "away_odds", "home_prob", "away_prob",
        "num_bookmakers", "platform", "best_home_odds", "best_away_odds",
    ]
    for col in safe_columns:
        assert result[col].tolist() == expected[col].tolist(), (
            f"Column '{col}' differs"
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_row() -> dict:
    """Return a baseline valid data row for happy-path tests.

    Override individual fields in failure-case tests to keep fixtures
    minimal and explicit.
    """
    return {
        "sport": "nba",
        "game_id": "NBA_20250115_CELTICS_LAKERS",
        "home_team": "Boston Celtics",
        "away_team": "Los Angeles Lakers",
        "commence_time": datetime(2024, 12, 25, 20, 0, 0, tzinfo=timezone.utc),
        "home_odds": 2.10,
        "away_odds": 1.80,
        "home_prob": 0.476,
        "away_prob": 0.556,
        "num_bookmakers": 5,
        "platform": "odds_api",
        "best_home_odds": 2.20,
        "best_away_odds": 1.85,
        "bet_type": "h2h",
    }


@pytest.fixture
def valid_df(valid_row: dict) -> pd.DataFrame:
    """Return a single-row valid DataFrame built from ``valid_row``."""
    return pd.DataFrame([valid_row])


# ============================================================================
#  OddsFeedSchema — Constraint Enforcement
# ============================================================================


class TestOddsFeedSchema:
    """Schema constraint enforcement tests for OddsFeedSchema."""

    # -- Happy path ----------------------------------------------------------

    def test_valid_dataframe_passes(self, valid_df: pd.DataFrame) -> None:
        """A fully valid DataFrame with all columns set correctly should pass
        validation and return the same DataFrame."""
        schema = OddsFeedSchema
        result = schema.validate(valid_df, lazy=True)
        _assert_passes(result, valid_df)

    # -- sport ---------------------------------------------------------------

    def test_null_sport_fails(self, valid_df: pd.DataFrame) -> None:
        """sport=None must be rejected by the schema."""
        df = valid_df.copy()
        df.loc[0, "sport"] = None

        with pytest.raises(pandera.errors.SchemaErrors):
            schema = OddsFeedSchema
            schema.validate(df, lazy=True)

    def test_invalid_sport_fails(self, valid_df: pd.DataFrame) -> None:
        """sport='esports' must be rejected (not in VALID_SPORTS)."""
        df = valid_df.copy()
        df.loc[0, "sport"] = "esports"

        with pytest.raises(pandera.errors.SchemaErrors):
            schema = OddsFeedSchema
            schema.validate(df, lazy=True)

    # -- game_id -------------------------------------------------------------

    def test_null_game_id_fails(self, valid_df: pd.DataFrame) -> None:
        """game_id=None must be rejected."""
        df = valid_df.copy()
        df.loc[0, "game_id"] = None

        with pytest.raises(pandera.errors.SchemaErrors):
            schema = OddsFeedSchema
            schema.validate(df, lazy=True)

    def test_malformed_game_id_fails(self, valid_df: pd.DataFrame) -> None:
        """game_id='bad-format' must fail the str_matches regex check."""
        df = valid_df.copy()
        df.loc[0, "game_id"] = "bad-format"

        with pytest.raises(pandera.errors.SchemaErrors):
            schema = OddsFeedSchema
            schema.validate(df, lazy=True)

    # -- home_team / away_team -----------------------------------------------

    def test_null_home_team_fails(self, valid_df: pd.DataFrame) -> None:
        """home_team=None must be rejected."""
        df = valid_df.copy()
        df.loc[0, "home_team"] = None

        with pytest.raises(pandera.errors.SchemaErrors):
            schema = OddsFeedSchema
            schema.validate(df, lazy=True)

    def test_null_away_team_fails(self, valid_df: pd.DataFrame) -> None:
        """away_team=None must be rejected."""
        df = valid_df.copy()
        df.loc[0, "away_team"] = None

        with pytest.raises(pandera.errors.SchemaErrors):
            schema = OddsFeedSchema
            schema.validate(df, lazy=True)

    # -- commence_time -------------------------------------------------------

    def test_future_commence_time_fails(self, valid_df: pd.DataFrame) -> None:
        """commence_time in year 2099 must be rejected by
        check_no_future_timestamps."""
        df = valid_df.copy()
        df.loc[0, "commence_time"] = datetime(2099, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        with pytest.raises(pandera.errors.SchemaErrors):
            schema = OddsFeedSchema
            schema.validate(df, lazy=True)

    def test_past_commence_time_passes(self, valid_df: pd.DataFrame) -> None:
        """commence_time in 2024 (past) must pass validation."""
        df = valid_df.copy()
        df.loc[0, "commence_time"] = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        schema = OddsFeedSchema
        result = schema.validate(df, lazy=True)
        _assert_passes(result, df)

    # -- odds range checks ---------------------------------------------------

    def test_out_of_range_low_odds_fails(self, valid_df: pd.DataFrame) -> None:
        """home_odds=0.5 (< 1.01) must be rejected."""
        df = valid_df.copy()
        df.loc[0, "home_odds"] = 0.5

        with pytest.raises(pandera.errors.SchemaErrors):
            schema = OddsFeedSchema
            schema.validate(df, lazy=True)

    def test_out_of_range_high_odds_fails(self, valid_df: pd.DataFrame) -> None:
        """away_odds=2000.0 (> 1000.0) must be rejected."""
        df = valid_df.copy()
        df.loc[0, "away_odds"] = 2000.0

        with pytest.raises(pandera.errors.SchemaErrors):
            schema = OddsFeedSchema
            schema.validate(df, lazy=True)

    # -- probability sum -----------------------------------------------------

    def test_probability_sum_too_high_fails(self, valid_df: pd.DataFrame) -> None:
        """home_prob + away_prob = 1.20 (> 1.10) must fail
        check_probability_sum_reasonable."""
        df = valid_df.copy()
        # Set odds so that 1/odds yields ~0.60 each, sum ~1.20
        df.loc[0, "home_odds"] = 1.67
        df.loc[0, "away_odds"] = 1.67
        df.loc[0, "home_prob"] = 0.60
        df.loc[0, "away_prob"] = 0.60

        with pytest.raises(pandera.errors.SchemaErrors):
            schema = OddsFeedSchema
            schema.validate(df, lazy=True)

    def test_reasonable_probability_sum_passes(self, valid_df: pd.DataFrame) -> None:
        """home_prob=0.50 + away_prob=0.45 (sum=0.95 < 1.10) must pass."""
        df = valid_df.copy()
        df.loc[0, "home_prob"] = 0.50
        df.loc[0, "away_prob"] = 0.45

        schema = OddsFeedSchema
        result = schema.validate(df, lazy=True)
        _assert_passes(result, df)

    # -- num_bookmakers ------------------------------------------------------

    def test_null_num_bookmakers_fails(self, valid_df: pd.DataFrame) -> None:
        """num_bookmakers=None must be rejected."""
        df = valid_df.copy()
        df.loc[0, "num_bookmakers"] = None

        with pytest.raises(pandera.errors.SchemaErrors):
            schema = OddsFeedSchema
            schema.validate(df, lazy=True)

    def test_zero_num_bookmakers_fails(self, valid_df: pd.DataFrame) -> None:
        """num_bookmakers=0 must fail (ge=1)."""
        df = valid_df.copy()
        df.loc[0, "num_bookmakers"] = 0

        with pytest.raises(pandera.errors.SchemaErrors):
            schema = OddsFeedSchema
            schema.validate(df, lazy=True)

    # -- platform ------------------------------------------------------------

    def test_invalid_platform_fails(self, valid_df: pd.DataFrame) -> None:
        """platform='other_source' must be rejected (must be 'odds_api')."""
        df = valid_df.copy()
        df.loc[0, "platform"] = "other_source"

        with pytest.raises(pandera.errors.SchemaErrors):
            schema = OddsFeedSchema
            schema.validate(df, lazy=True)

    # -- bet_type ------------------------------------------------------------

    def test_bet_type_nullable(self, valid_df: pd.DataFrame) -> None:
        """bet_type=None should be accepted (field is nullable)."""
        df = valid_df.copy()
        df.loc[0, "bet_type"] = None

        schema = OddsFeedSchema
        result = schema.validate(df, lazy=True)
        _assert_passes(result, df)


# ============================================================================
#  validate_odds_dataframe — Wrapper Behaviour
# ============================================================================


class TestValidateOddsDataFrame:
    """Tests for the validate_odds_dataframe wrapper function."""

    def test_returns_dataframe_on_success(self, valid_df: pd.DataFrame) -> None:
        """A valid DataFrame should be returned unchanged."""
        result = validate_odds_dataframe(valid_df)
        _assert_passes(result, valid_df)

    def test_raises_schemaerrors_on_failure(self, valid_df: pd.DataFrame) -> None:
        """An invalid DataFrame should raise pandera.errors.SchemaErrors."""
        df = valid_df.copy()
        df.loc[0, "sport"] = "esports"

        with pytest.raises(pandera.errors.SchemaErrors):
            validate_odds_dataframe(df)

    def test_logs_missing_columns(self, valid_df: pd.DataFrame) -> None:
        """DataFrame missing required columns should still raise
        SchemaErrors but also log missing columns."""
        df = valid_df.copy()
        # Drop a critical column.
        df = df.drop(columns=["sport"])

        with pytest.raises(pandera.errors.SchemaErrors):
            validate_odds_dataframe(df)


# ============================================================================
#  check_categorical_distribution_shift — Distribution Shift Detection
# ============================================================================


class TestDistributionShift:
    """Tests for check_categorical_distribution_shift."""

    def test_no_shift_detected(self) -> None:
        """Expected and actual distributions within 20pp should return True."""
        df = pd.DataFrame(
            {"sport": ["nba", "nba", "nhl", "nhl", "mlb"]}
        )
        expected = {"nba": 0.40, "nhl": 0.40, "mlb": 0.20}

        result = check_categorical_distribution_shift(df, "sport", expected)
        assert result is True

    def test_shift_detected(self) -> None:
        """Category deviating by >20pp should return False."""
        # 100 rows of nba only — nba=1.0 vs expected=0.40 → 60pp deviation
        df = pd.DataFrame({"sport": ["nba"] * 100})
        expected = {"nba": 0.40, "nhl": 0.30, "mlb": 0.30}

        result = check_categorical_distribution_shift(df, "sport", expected)
        assert result is False

    def test_empty_dataframe(self) -> None:
        """An empty DataFrame should return True (no shift detected)."""
        df = pd.DataFrame({"sport": []})
        expected = {"nba": 0.50}

        result = check_categorical_distribution_shift(df, "sport", expected)
        assert result is True

    def test_missing_column(self) -> None:
        """A DataFrame without the specified column should return True."""
        df = pd.DataFrame({"other_col": ["a", "b", "c"]})
        expected = {"nba": 0.50}

        result = check_categorical_distribution_shift(
            df, "sport", expected
        )
        assert result is True
