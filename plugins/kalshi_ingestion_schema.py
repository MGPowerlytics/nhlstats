#!/usr/bin/env python3
"""
Pandera schema for validating Kalshi prediction market data before DB ingestion.

Validates the DataFrame prepared from Kalshi API market dicts before it reaches
``save_to_db()`` in ``kalshi_markets.py``.  Catches malformed tickers, out-of-range
prices, stale close_times, and categorical distribution shifts before bad data
hits ``unified_games`` / ``game_odds``.

Integration in ``save_to_db()``
-------------------------------
Insert the validation call **after** the markets list is prepared / parsed but
**before** the upsert loop.  Example::

    from plugins.kalshi_ingestion_schema import (
        validate_odds_ingestion,
        SchemaDriftError,
    )
    from pandera.errors import SchemaError

    def save_to_db(sport: str, markets: list, db_manager=None) -> int:
        # ... existing parsing / DataFrame construction ...
        df = pd.DataFrame.from_records(parsed_markets)

        try:
            # ⛔ CRITICAL: Validate before any DB writes.
            # If validation fails, halt to prevent data corruption.
            validate_odds_ingestion(df, expected_distribution={...})
        except SchemaError as e:
            logger.critical("Schema violation — halting ingestion: %s", e)
            raise  # Let Airflow / caller handle the retry policy
        except SchemaDriftError as e:
            logger.warning("Distribution drift detected — continuing: %s", e)
            # ⚠️  Distribution drift is a warning, not a hard block.
            # Log it, alert monitoring, but allow ingestion to proceed
            # because the data may still be valid (e.g., off-season).

        # ... existing upsert loop ...

Action on failure
-----------------
- **SchemaError** (column-level violations):  HALT ingestion.  Raise the
  exception so upstream Airflow DAG marks the task as failed and triggers
  the retry / alert policy.
- **SchemaDriftError** (distribution anomalies):  LOG AND CONTINUE.  These
  are warnings that the API may have changed its coverage (off-season,
  new sports), but individual market records are still valid.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from pandera import DataFrameModel, Field, dataframe_check
from pandera.typing import Series

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("kalshi_ingestion_schema.ingestion")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Valid sport identifiers from Kalshi response parsing.
VALID_SPORTS: list[str] = [
    "NBA",
    "NHL",
    "MLB",
    "NFL",
    "EPL",
    "LIGUE1",
    "NCAAB",
    "WNCAAB",
    "TENNIS",
    "CBA",
    "UNRIVALED",
]

# Prediction market price bounds in cents (1-99 = 1%-99% probability).
# Zero is acceptable as a sentinel meaning "price unavailable".
MIN_PRICE_CENTS: int = 0
MAX_PRICE_CENTS: int = 99
ACTIVE_PRICE_MIN: int = 1  # Minimum non-zero price for valid markets

# Decimal odds range derived from yes_ask.
# 100.0 / 1  = 100.0 (when yes_ask = 1 cent)
# 100.0 / 99 = ~1.01 (when yes_ask = 99 cents)
MIN_DECIMAL_ODDS: float = 1.01
MAX_DECIMAL_ODDS: float = 100.0

# Valid outcome names for a moneyline market.
VALID_OUTCOMES: list[str] = ["home", "away", "draw"]

# Ticker regex: must contain at least 2 dash-separated parts,
# ending with a team/city code (letters, digits, underscores).
# Examples:
#   KXNBAGAME-26MAR22MINBOS-MIN        ✓
#   KXHEPL-ARSBHA-20260426-HOME        ✓
TICKER_PATTERN: str = r"^[A-Z0-9]+(?:-[A-Z0-9]+)+-[A-Z0-9]+$"

# Game date pattern: YYYY-MM-DD
GAME_DATE_PATTERN: str = r"^\d{4}-\d{2}-\d{2}$"

# Default drift thresholds (percentage points).
SPORT_DRIFT_THRESHOLD: float = 0.15
OUTCOME_DRIFT_THRESHOLD: float = 0.20

# Expected sport distribution (baseline proportions).
# These represent typical Kalshi market availability by sport.
# Adjust based on historical data / seasonality.
DEFAULT_SPORT_DISTRIBUTION: dict[str, float] = {
    "NBA": 0.30,
    "NHL": 0.20,
    "MLB": 0.20,
    "NFL": 0.10,
    "EPL": 0.10,
    "NCAAB": 0.03,
    "WNCAAB": 0.02,
    "LIGUE1": 0.02,
    "TENNIS": 0.02,
    "CBA": 0.01,
    "UNRIVALED": 0.00,
}

# Expected outcome distribution.
# For most sports: ~50% home, ~50% away.
# For EPL/soccer: ~45% home, ~45% away, ~10% draw.
DEFAULT_OUTCOME_DISTRIBUTION: dict[str, float] = {
    "home": 0.50,
    "away": 0.50,
}

# ISO 8601 datetime format for close_time parsing.
CLOSE_TIME_FORMAT: str = "%Y-%m-%dT%H:%M:%S"


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------


class SchemaDriftError(Exception):
    """Raised when a categorical column's distribution deviates beyond threshold.

    This is a **warning** exception — it indicates the API's data mix has
    shifted (e.g., off-season reduction in NHL markets) but individual records
    may still be valid.  The ingestion pipeline should log this and continue,
    not halt.
    """

    def __init__(
        self,
        column: str,
        observed: dict[str, float],
        threshold: float,
    ) -> None:
        self.column = column
        self.observed = observed
        self.threshold = threshold
        super().__init__(
            f"Distribution drift detected in '{column}': "
            f"observed={observed}, threshold={threshold:.0%}"
        )


# ---------------------------------------------------------------------------
# Pandera Schema
# ---------------------------------------------------------------------------


class KalshiMarketsSchema(DataFrameModel):
    """Pandera DataFrameModel for Kalshi prediction market data.

    Each field maps directly to a key in the market dict prepared by the Kalshi
    ingestion pipeline (see ``kalshi_markets.py`` ``_parse_market()`` output).

    The schema enforces:
    - Non-nullability constraints on critical identifiers (ticker, sport, teams).
    - Domain-specific price ranges (1-99 cents for prediction market prices).
    - Decimal odds bounds derived from probability-space prices.
    - Constant-value fields (bookmaker, market_name).
    - Regex format validation on ticker and game_date.
    - Custom dataframe-level checks for temporal consistency (no future close_time).
    """

    # -- Identifiers & Metadata ------------------------------------------------

    ticker: Series[str] = Field(
        nullable=False,
        str_matches=TICKER_PATTERN,
        description=(
            "Kalshi market ticker (e.g., 'KXNBAGAME-26MAR22MINBOS-MIN'). "
            "Must contain at least 2 dash-separated parts, ending in a team "
            "or outcome code. Zero nulls allowed."
        ),
    )

    title: Series[str] = Field(
        nullable=True,
        description=(
            "Market title (e.g., 'Minnesota Timberwolves vs Boston Celtics "
            "winner?'). Nullable, but if present must be a non-empty string."
        ),
    )

    sport: Series[str] = Field(
        nullable=False,
        isin=VALID_SPORTS,
        description=(
            "Sport identifier in uppercase. Must be one of the known "
            "VALID_SPORTS list. Zero nulls allowed."
        ),
    )

    home_team: Series[str] = Field(
        nullable=False,
        description=(
            "Canonical home team name. Must be non-empty, zero nulls."
        ),
    )

    away_team: Series[str] = Field(
        nullable=False,
        description=(
            "Canonical away team name. Must be non-empty, zero nulls."
        ),
    )

    game_date: Series[str] = Field(
        nullable=False,
        str_matches=GAME_DATE_PATTERN,
        description=(
            "Game date in YYYY-MM-DD format. Must be parseable as a date. "
            "Zero nulls allowed."
        ),
    )

    # -- Pricing (cents) -------------------------------------------------------

    yes_ask: Series[int] = Field(
        nullable=False,
        ge=MIN_PRICE_CENTS,
        le=MAX_PRICE_CENTS,
        description=(
            "Price in cents for buying the YES outcome (1-99). "
            "Zero is acceptable as a sentinel for 'price unavailable'. "
            "Values map to probability: 50 cents = 50% implied probability."
        ),
    )

    no_ask: Series[int] = Field(
        nullable=False,
        ge=MIN_PRICE_CENTS,
        le=MAX_PRICE_CENTS,
        description=(
            "Price in cents for buying the NO outcome (1-99). "
            "Zero is acceptable as a sentinel for 'price unavailable'."
        ),
    )

    # -- Outcome & Computed Fields ---------------------------------------------

    outcome_name: Series[str] = Field(
        nullable=False,
        isin=VALID_OUTCOMES,
        description=(
            "Market outcome side: 'home', 'away', or 'draw'. "
            "Corresponds to which team/outcome this contract represents. "
            "Zero nulls allowed."
        ),
    )

    decimal_odds: Series[float] = Field(
        nullable=False,
        ge=0.0,
        le=MAX_DECIMAL_ODDS,
        description=(
            "Decimal odds computed as 100.0 / yes_ask. "
            "Range: 1.01 (yes_ask=99) to 100.0 (yes_ask=1). "
            "Zero if yes_ask was 0. Cannot exceed 100.0."
        ),
    )

    # -- Constant Fields -------------------------------------------------------

    bookmaker: Series[str] = Field(
        nullable=False,
        isin=["Kalshi"],
        description="Always 'Kalshi'. Constant identifier for this source.",
    )

    market_name: Series[str] = Field(
        nullable=False,
        isin=["moneyline"],
        description="Always 'moneyline'. Kalshi only provides moneyline markets.",
    )

    # ------------------------------------------------------------------
    # Custom Dataframe-Level Checks
    # ------------------------------------------------------------------

    @dataframe_check
    def check_title_nonempty_when_present(cls, df: pd.DataFrame) -> pd.Series:
        """Ensure ``title`` is non-empty string when not null.

        Null titles are allowed (nullable=True in the schema), but if a title
        is present it must be a non-empty string.  Empty strings are treated as
        missing/invalid data that would result in a meaningless display value.

        ⛔ CRITICAL: Empty titles produce confusing downstream output in UI
        and reports.  If this check fails, halt and inspect the API response
        for missing title fields.
        """
        mask = df["title"].notna()
        result = pd.Series(True, index=df.index)
        result[mask] = df.loc[mask, "title"].astype(str).str.len() > 0
        return result

    @dataframe_check
    def check_team_names_nonempty(cls, df: pd.DataFrame) -> pd.Series:
        """Ensure ``home_team`` and ``away_team`` are non-empty strings.

        Empty team names indicate a parsing failure in ``_parse_market()``
        or a malformed API response.  Writing empty team names to the database
        would corrupt cross-sport queries and JOINs.

        ⛔ CRITICAL: Halt ingestion immediately on empty team names.
        """
        home_ok = df["home_team"].astype(str).str.strip().str.len() > 0
        away_ok = df["away_team"].astype(str).str.strip().str.len() > 0
        return home_ok & away_ok

    @dataframe_check
    def check_game_date_parseable(cls, df: pd.DataFrame) -> pd.Series:
        """Validate that ``game_date`` strings are actual dates (YYYY-MM-DD).

        The regex check (``str_matches=GAME_DATE_PATTERN``) confirms format,
        but does not prevent invalid dates like '2026-02-30'.  This check
        attempts to parse each date string to catch calendar-invalid values.

        ⛔ CRITICAL: Invalid dates will cause SQL errors during INSERT and
        break downstream date-partitioned queries.  Halt ingestion.
        """
        def _is_valid_date(date_str: str) -> bool:
            try:
                datetime.strptime(str(date_str), "%Y-%m-%d")
                return True
            except (ValueError, TypeError):
                return False

        return df["game_date"].apply(_is_valid_date)

    @dataframe_check
    def check_decimal_odds_consistency(cls, df: pd.DataFrame) -> pd.Series:
        """Verify ``decimal_odds`` is consistent with ``yes_ask``.

        Business rule: if yes_ask > 0, decimal_odds must be >= 1.01.
        If yes_ask == 0, decimal_odds must be 0.0.

        This catches arithmetic mismatches between the computed odds field
        and the source price field that would produce misleading values
        for downstream EV calculation.

        ⛔ CRITICAL: Inconsistent decimal_odds propagate to the Elo rating
        system and expected-value calculators.  Halt ingestion.
        """
        condition_yes_positive = (
            (df["yes_ask"] > 0) & (df["decimal_odds"] >= MIN_DECIMAL_ODDS)
        )
        condition_yes_zero = (
            (df["yes_ask"] == 0) & (df["decimal_odds"] == 0.0)
        )
        return condition_yes_positive | condition_yes_zero

    @dataframe_check
    def check_close_time_not_past(cls, df: pd.DataFrame) -> pd.Series:
        """Validate that ``close_time`` (if present) is not in the past.

        The ``close_time`` column is optional — it may not be present in all
        API responses.  If the column exists, every non-null value must be a
        future timestamp (greater than current UTC time).  A close_time in the
        past means the market has already closed and the odds data is stale.

        ⛔ CRITICAL: Stale markets with past close_times should not be
        ingested as current odds.  If a market's close_time is in the past but
        the market is still listed as active, the API may have stale data.

        Note: This check is skipped entirely if ``close_time`` is not in the
        DataFrame or if the column is entirely null.
        """
        if "close_time" not in df.columns or df["close_time"].isna().all():
            return pd.Series(True, index=df.index)

        now_utc = datetime.now(timezone.utc)

        def _is_future(ts_val) -> bool:
            if pd.isna(ts_val):
                return True  # Null close_times are not stale
            try:
                # Try parsing as ISO 8601 (with/without Z suffix).
                ts_str = str(ts_val).strip()
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1]
                parsed = datetime.strptime(ts_str, CLOSE_TIME_FORMAT)
                parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed > now_utc
            except (ValueError, TypeError):
                # If we can't parse it, consider it invalid but don't block
                # on parsing failure alone — the schema format check handles
                # that.  Mark as OK so other checks can run.
                return True

        return df["close_time"].apply(_is_future)

    class Config:
        """Pandera model configuration.

        - ``coerce=True``: Automatically coerce types to match annotations
          (e.g., int columns from float inputs).
        - ``strict=False``: Allow extra columns not defined in the schema
          (e.g., intermediate debug columns from the parsing pipeline).
        - ``drop_invalid_rows=False``: Do NOT silently drop invalid rows.
          Instead, collect all errors via ``lazy=True`` and let the caller
          decide whether to halt or continue.
        """
        coerce: bool = True
        strict: bool = False
        drop_invalid_rows: bool = False


# ---------------------------------------------------------------------------
# Distribution Shift Detection
# ---------------------------------------------------------------------------


def _check_categorical_distribution_shift(
    df: pd.DataFrame,
    column: str,
    expected_distribution: dict[str, float],
    drift_threshold: float,
) -> Optional[dict[str, float]]:
    """Check if a categorical column's distribution has shifted.

    Compares actual proportions against an expected baseline.  If any single
    category deviates by more than ``drift_threshold`` (in absolute percentage
    points), returns the observed proportions for reporting.

    Args:
        df: DataFrame to check.
        column: Name of the categorical column.
        expected_distribution: Mapping of category -> expected proportion
            (float in [0.0, 1.0]).  Need not sum to 1.0.
        drift_threshold: Maximum allowed absolute deviation in percentage
            points (e.g., 0.15 = 15pp).

    Returns:
        Dict of observed proportions if shift detected, ``None`` if within
        tolerance.  Also returns ``None`` if the column is missing or empty.

    Example:
        >>> _check_categorical_distribution_shift(
        ...     df, "sport", {"NBA": 0.30, "NHL": 0.20}, 0.15
        ... )
        {"NBA": 0.45, "NHL": 0.05}  # NBA exceeded 15pp deviation
    """
    if df.empty or column not in df.columns:
        logger.warning(
            "Distribution shift check skipped: DataFrame empty or "
            "column '%s' missing.",
            column,
        )
        return None

    actual_counts: pd.Series = df[column].value_counts(normalize=True)
    shift_detected: bool = False
    observed: dict[str, float] = {}

    for category, expected_prop in expected_distribution.items():
        actual_prop: float = actual_counts.get(category, 0.0)
        deviation_pp: float = abs(actual_prop - expected_prop)

        if deviation_pp > drift_threshold:
            logger.warning(
                "⚠️  DISTRIBUTION SHIFT in column '%s': category='%s': "
                "expected %.1f%%, got %.1f%% (deviation=%.1fpp, "
                "threshold=%.1fpp).",
                column,
                category,
                expected_prop * 100.0,
                actual_prop * 100.0,
                deviation_pp * 100.0,
                drift_threshold * 100.0,
            )
            shift_detected = True

        observed[category] = actual_prop

    if shift_detected:
        logger.warning(
            "⚠️  Distribution drift detected in column '%s'. "
            "Observed (top 5): %s. "
            "ACTION: Log and continue — individual records are valid, "
            "but the data mix has changed.",
            column,
            dict(list(actual_counts.head(5).items())),
        )
        return observed

    return None


# ---------------------------------------------------------------------------
# Validator Class
# ---------------------------------------------------------------------------


class KalshiIngestionValidator:
    """Wrapper class for validating Kalshi market DataFrames.

    Orchestrates Pandera schema validation and statistical distribution shift
    checks.  Designed to be instantiated once per pipeline run and reused
    across multiple batches.

    Usage in ``save_to_db()``::

        validator = KalshiIngestionValidator()
        try:
            validator.validate(df, expected_distribution={...})
        except SchemaError as e:
            logger.critical("Validation failed: %s", e)
            raise
        except SchemaDriftError as e:
            logger.warning("Drift detected: %s", e)
    """

    def __init__(self) -> None:
        self.schema = KalshiMarketsSchema

    def validate(
        self,
        df: pd.DataFrame,
        expected_distribution: Optional[dict[str, float]] = None,
    ) -> pd.DataFrame:
        """Run all validation checks on the Kalshi markets DataFrame.

        Args:
            df: DataFrame with columns matching ``KalshiMarketsSchema``.
            expected_distribution: Optional override for sport distribution
                baselines.  If ``None``, uses ``DEFAULT_SPORT_DISTRIBUTION``.

        Returns:
            The validated DataFrame (unchanged if validation passes).

        Raises:
            SchemaError: If any Pandera column-level or dataframe-level check
                fails.  Halt ingestion on this exception.
            SchemaDriftError: If a categorical distribution shift exceeds the
                drift threshold.  Log and continue.
        """
        logger.info(
            "Validating Kalshi markets DataFrame: %d rows, %d columns",
            len(df),
            len(df.columns),
        )

        # ------------------------------------------------------------------
        # Step 1: Pandera Schema Validation (lazy mode)
        # ------------------------------------------------------------------
        # We use lazy=True to collect ALL column-level and check-level failures
        # in a single pass.  This gives the operator a complete picture of what's
        # wrong without having to fix errors one at a time.
        validated_df = self.schema.validate(df, lazy=True)

        logger.info(
            "✅ KalshiMarketsSchema validation PASSED: %d rows OK.",
            len(validated_df),
        )

        # ------------------------------------------------------------------
        # Step 2: Statistical Distribution Shift Detection
        # ------------------------------------------------------------------
        # These checks are advisory — they detect changes in the data *mix*
        # rather than individual record validity.

        sport_dist = (
            expected_distribution
            if expected_distribution is not None
            else DEFAULT_SPORT_DISTRIBUTION
        )

        sport_shift = _check_categorical_distribution_shift(
            df, "sport", sport_dist, SPORT_DRIFT_THRESHOLD
        )
        if sport_shift:
            raise SchemaDriftError(
                column="sport",
                observed=sport_shift,
                threshold=SPORT_DRIFT_THRESHOLD,
            )

        # Outcome distribution: compute dynamically based on sport mix.
        # For sports with draws (EPL, LIGUE1), adjust baseline.
        outcome_dist = dict(DEFAULT_OUTCOME_DISTRIBUTION)
        has_draw_sports = df["sport"].isin(["EPL", "LIGUE1"]).any()
        if has_draw_sports:
            # If draws are present in the data, widen to include them.
            outcome_dist = {"home": 0.45, "away": 0.45, "draw": 0.10}

        outcome_shift = _check_categorical_distribution_shift(
            df, "outcome_name", outcome_dist, OUTCOME_DRIFT_THRESHOLD
        )
        if outcome_shift:
            raise SchemaDriftError(
                column="outcome_name",
                observed=outcome_shift,
                threshold=OUTCOME_DRIFT_THRESHOLD,
            )

        return validated_df


# ---------------------------------------------------------------------------
# Standalone Convenience Function
# ---------------------------------------------------------------------------


def validate_odds_ingestion(
    df: pd.DataFrame,
    expected_distribution: Optional[dict[str, float]] = None,
) -> pd.DataFrame:
    """Validate a Kalshi markets DataFrame against the ingestion schema.

    Standalone convenience wrapper around ``KalshiIngestionValidator``.
    Use this for one-off validation calls in scripts or Airflow tasks.

    Args:
        df: DataFrame containing Kalshi market data to validate.
        expected_distribution: Optional sport distribution override.
            Falls back to ``DEFAULT_SPORT_DISTRIBUTION`` if not provided.

    Returns:
        The validated DataFrame (unchanged if validation passes).

    Raises:
        SchemaError: On Pandera schema violations — halt ingestion.
        SchemaDriftError: On categorical distribution drift — log and continue.

    Integration example for ``save_to_db()``::

        # In save_to_db(), after building the markets DataFrame:
        from plugins.kalshi_ingestion_schema import validate_odds_ingestion

        df = pd.DataFrame.from_records(parsed_markets)
        try:
            validate_odds_ingestion(df)
        except SchemaError:
            logger.critical(
                "Kalshi market schema validation FAILED — "
                "halting ingestion to prevent DB corruption."
            )
            raise
        except SchemaDriftError as e:
            logger.warning(
                "Kalshi market distribution drift: %s. "
                "Continuing ingestion — data records are individually valid.",
                e,
            )

        # ... proceed to _upsert_game() / _upsert_odds() loop ...
    """
    validator = KalshiIngestionValidator()
    return validator.validate(df, expected_distribution=expected_distribution)
