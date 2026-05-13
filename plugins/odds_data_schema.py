#!/usr/bin/env python3
"""
Pandera schema for validating incoming odds data from The Odds API.

This module defines a pre-ingestion contract that validates odds DataFrame
fields BEFORE they reach the database. It is meant to be called between
_parse_game() output conversion and save_to_db().

Usage:
    from odds_data_schema import OddsFeedSchema, validate_odds_dataframe
    import pandas as pd

    df = pd.DataFrame(parsed_markets)
    validated_df = validate_odds_dataframe(df)
    api.save_to_db(validated_df.to_dict('records'))
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
from pandera import (
    DataFrameModel,
    Field,
    dataframe_check,
)
from pandera.errors import SchemaErrors
from pandera.typing import Series

# ⛔ CRITICAL: Logger for ingestion pipeline alerts.
# All critical validation failures MUST be logged at ERROR level
# so that monitoring systems (DataDog, Grafana, PagerDuty) can pick them up.
logger = logging.getLogger("odds_data_schema.ingestion")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Known sport identifiers that the system supports.
# Must match the keys in TheOddsAPI.SPORT_KEYS plus tennis.
VALID_SPORTS: list[str] = [
    "nba",
    "nhl",
    "mlb",
    "nfl",
    "epl",
    "ncaab",
    "ligue1",
    "tennis",
]

# Decimal odds range constraints (standard for The Odds API).
# Minimum 1.01 accounts for the bookmaker's commission on near-certain events.
# Maximum 1000.0 is a generous upper bound for extreme longshots.
MIN_ODDS: float = 1.01
MAX_ODDS: float = 1000.0

# Probability bounds derived from odds.
MIN_PROB: float = 0.001
MAX_PROB: float = 0.999

# Maximum acceptable sum of home + away implied probabilities for h2h markets.
# 1.0 = fair market; values above this represent bookmaker vig (overround).
# 1.10 allows up to ~10% overround, which is typical for retail sportsbooks.
MAX_IMPLIED_PROB_SUM: float = 1.10

# Clock skew tolerance for commence_time future-check (seconds).
# Allows up to 5 minutes of clock drift between API server and local machine.
CLOCK_SKEW_TOLERANCE_SECONDS: int = 300

# Regex pattern for game_id format: SPORT_YYYYMMDD_TEAM1_TEAM2
GAME_ID_PATTERN: str = r"^[A-Z]+_\d{8}_[A-Z0-9]+_[A-Z0-9]+$"

# Maximum allowed absolute percentage-point deviation for categorical
# distribution shift detection.
MAX_DISTRIBUTION_SHIFT_PP: float = 20.0


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class OddsFeedSchema(DataFrameModel):
    """Pandera DataFrameModel that validates incoming odds feed data.

    This schema enforces domain-specific constraints on odds data parsed from
    The Odds API. Each field maps to a key in the ``_parse_game()`` dict output.

    The schema is designed to be used with ``schema.validate(df, lazy=True)``
    to collect ALL validation errors before deciding whether to halt ingestion.
    """

    # -- Identifiers & Metadata ------------------------------------------------

    sport: Series[str] = Field(
        nullable=False,
        isin=VALID_SPORTS,
        description=(
            "Sport key (e.g., 'nba', 'nhl', 'mlb'). "
            "Must be one of the known VALID_SPORTS list."
        ),
    )

    game_id: Series[str] = Field(
        nullable=False,
        str_matches=GAME_ID_PATTERN,
        description=("Unique game identifier in format SPORT_YYYYMMDD_TEAM1_TEAM2."),
    )

    home_team: Series[str] = Field(
        nullable=False,
        description="Full name of the home team (e.g., 'Boston Celtics').",
    )

    away_team: Series[str] = Field(
        nullable=False,
        description="Full name of the away team (e.g., 'Los Angeles Lakers').",
    )

    commence_time: Series[datetime] = Field(
        nullable=False,
        description=(
            "ISO 8601 datetime string indicating when the game starts. "
            "Must not be in the future (with 5-min clock skew tolerance)."
        ),
    )

    # -- Odds & Probabilities --------------------------------------------------

    home_odds: Series[float] = Field(
        nullable=False,
        ge=MIN_ODDS,
        le=MAX_ODDS,
        description="Decimal odds for the home team outcome.",
    )

    away_odds: Series[float] = Field(
        nullable=False,
        ge=MIN_ODDS,
        le=MAX_ODDS,
        description="Decimal odds for the away team outcome.",
    )

    home_prob: Series[float] = Field(
        nullable=False,
        ge=MIN_PROB,
        le=MAX_PROB,
        description="Implied probability = 1 / home_odds.",
    )

    away_prob: Series[float] = Field(
        nullable=False,
        ge=MIN_PROB,
        le=MAX_PROB,
        description="Implied probability = 1 / away_odds.",
    )

    # -- Aggregation / Platform Metadata ---------------------------------------

    num_bookmakers: Series[int] = Field(
        nullable=False,
        ge=1,
        description="Number of bookmakers offering odds for this game.",
    )

    platform: Series[str] = Field(
        nullable=False,
        isin=["odds_api"],
        description="Source platform identifier. Must be 'odds_api'.",
    )

    best_home_odds: Series[float] = Field(
        nullable=False,
        ge=MIN_ODDS,
        le=MAX_ODDS,
        description="Best (highest) decimal odds for home team across all bookmakers.",
    )

    best_away_odds: Series[float] = Field(
        nullable=False,
        ge=MIN_ODDS,
        le=MAX_ODDS,
        description="Best (highest) decimal odds for away team across all bookmakers.",
    )

    bet_type: Series[pd.CategoricalDtype] = Field(
        nullable=True,
        dtype_kwargs={"categories": ["h2h", "spread", "totals", "moneyline"]},
        coerce=True,
        description=(
            "Market type (h2h, spread, totals, moneyline). "
            "Nullable for backward compatibility; will become required."
        ),
    )

    # ------------------------------------------------------------------
    # Custom Checks
    # ------------------------------------------------------------------

    @dataframe_check
    def check_no_future_timestamps(cls, df: pd.DataFrame) -> pd.Series:
        """Ensure all ``commence_time`` values are not in the future.

        Allows a 5-minute clock skew tolerance (``CLOCK_SKEW_TOLERANCE_SECONDS``)
        to account for minor differences between the API server clock and the
        local ingestion server clock.

        ⛔ CRITICAL: If this check fails, the data contains games with
        commence times that haven't happened yet but the timestamps suggest
        they've already started or finished. This indicates:
        1. The API returned corrupted/incorrect data.
        2. There is a timezone/clock-sync issue on the ingestion server.
        3. The data was mislabeled.

        ACTION: HALT ingestion immediately. Do NOT proceed to save_to_db().
        ALERT: Log at ERROR level. Notify on-call engineer via PagerDuty/SMS.
        Include the offending game_ids and their commence_time values in the alert payload.
        """
        now_utc: datetime = datetime.now(timezone.utc)
        # Use Unix timestamp for the comparison to avoid datetime subtraction issues.
        cutoff_ts: float = now_utc.timestamp() + CLOCK_SKEW_TOLERANCE_SECONDS

        # Convert commence_time to UTC timestamps for comparison.
        # Handle both timezone-aware and naive datetime objects.
        commence_ts: pd.Series = df["commence_time"].apply(
            lambda t: t.timestamp()
            if t.tzinfo is not None  # type: ignore[union-attr]
            else t.replace(tzinfo=timezone.utc).timestamp()  # type: ignore[union-attr]
        )

        return commence_ts <= cutoff_ts

    # ⛔ CRITICAL (cont.): The Series-level Field check for sport values is
    # handled by the Field(isin=VALID_SPORTS) decorator above.  If that check
    # fails, ingestion MUST halt — an unknown sport key means we don't know
    # which pipeline logic applies, and writing it to unified_games with an
    # unexpected sport value will corrupt cross-sport queries.  Log the
    # unexpected sport values and alert the data engineering team via the
    # #data-pipeline Slack channel.

    # ⛔ CRITICAL (cont.): The regex check on game_id (Field(regex=...))
    # ensures format compliance.  A malformed game_id will break downstream
    # JOINs in unified_games and game_odds tables.  If this fails, halt
    # ingestion and log the invalid game_ids so the source data can be
    # traced back to the API response.

    # ⛔ CRITICAL (cont.): Null checks on home_team, away_team, home_odds,
    # away_odds, commence_time, and num_bookmakers are enforced by
    # Field(nullable=False).  Any null in these fields means the API returned
    # an incomplete game object.  Halt ingestion, log the row index and
    # game_id, and alert monitoring.  Do not allow partial records into the DB.

    # ⛔ CRITICAL (cont.): Numeric range checks (ge/le on odds and prob
    # fields) prevent arithmetic errors in downstream Elo and expected-value
    # calculations.  An odds value outside [1.01, 1000.0] will produce
    # nonsensical implied probabilities and break bet EV calculations.
    # Halt ingestion and alert.

    # ------------------------------------------------------------------
    # Multi-column checks
    # ------------------------------------------------------------------

    @dataframe_check
    def check_game_id_format(cls, df: pd.DataFrame) -> pd.Series:
        """Validate that ``game_id`` matches the expected regex pattern.

        Pattern: ``^[A-Z]+_\\d{8}_[A-Z0-9]+_[A-Z0-9]+$``
        Example: ``NBA_20260425_CELTICS_LAKERS``

        ⛔ CRITICAL: If this check fails, malformed game_ids will break:
        - JOIN operations between unified_games and game_odds tables.
        - Deduplication logic that relies on game_id as a natural key.
        - Cross-referencing with external data sources.

        ACTION: Halt ingestion. Log the failing game_id values.
        ALERT: Notify data engineering team. Provide the first 3 failing
        game_ids as samples for debugging the API response format.
        """
        return df["game_id"].str.match(GAME_ID_PATTERN, na=False)

    @dataframe_check
    def check_probability_sum_reasonable(cls, df: pd.DataFrame) -> pd.Series:
        """Check that ``home_prob + away_prob`` is below the vig threshold.

        For head-to-head (h2h) markets, the sum of implied probabilities
        for both outcomes should be < 1.10 (allowing up to ~10% overround
        for bookmaker commission).  A sum >= 1.10 indicates an arbitrage
        opportunity or data corruption.

        ⛔ CRITICAL: If this check fails:
        - A sum > 1.10 with normal odds suggests the API returned overlapping
          or contradictory odds data.
        - A sum < 0.01 (near-zero) suggests missing or zeroed-out odds.
        - A sum exactly 1.0 is theoretically possible but rare in retail odds.

        ACTION: Halt ingestion. Log the game_ids where the sum exceeds the
        threshold, along with the actual home_prob and away_prob values.
        ALERT: PagerDuty notification to on-call engineer.  This could indicate
        a bug in the bookmaker odds extraction logic in _extract_odds_from_h2h_market.
        """
        prob_sum: pd.Series = df["home_prob"] + df["away_prob"]
        return prob_sum < MAX_IMPLIED_PROB_SUM

    # ⚠️ WARNING (non-critical, but important): The bet_type column is
    # nullable for now to support backward compatibility with older ingestion
    # runs.  Once all downstream consumers have been updated to handle the
    # bet_type field, this should be changed to nullable=False.
    # Tracked in: https://github.com/orgs/nhlstats/issues/142

    class Config:
        """Pandera model configuration."""

        coerce: bool = True
        strict: bool = False
        # ⛔ CRITICAL: We use lazy validation so that ALL errors are collected
        # in a single pass.  This allows the ingestion pipeline to log every
        # failing row before deciding to halt — critical for debugging API
        # response issues without multiple retry cycles.
        drop_invalid_rows: bool = False


# ---------------------------------------------------------------------------
# Distribution Shift Detection
# ---------------------------------------------------------------------------


def check_categorical_distribution_shift(
    df: pd.DataFrame,
    column: str,
    expected_distribution: dict[str, float],
    max_deviation_pp: float = MAX_DISTRIBUTION_SHIFT_PP,
) -> bool:
    """Detect whether a categorical column's distribution has shifted.

    Compares the actual observed frequency of each category in ``column``
    against an ``expected_distribution``.  Flags if any single category
    deviates by more than ``max_deviation_pp`` percentage points.

    This is designed to catch silent data corruption where all values are
    technically valid (pass the schema check) but the *distribution* of
    values is wrong — e.g., the API suddenly returns 80% NHL games when
    we expect a 50/50 NBA/NHL split.

    Args:
        df: DataFrame containing the column to check.
        column: Name of the categorical column to analyze.
        expected_distribution: Mapping of category -> expected proportion
            (as a float in [0.0, 1.0]).  Need not sum to 1.0; categories
            not listed are ignored.
        max_deviation_pp: Maximum allowed deviation in absolute percentage
            points (e.g., 20.0 means ±20pp). Defaults to
            ``MAX_DISTRIBUTION_SHIFT_PP``.

    Returns:
        ``True`` if the distribution is within expected bounds (no shift
        detected).  ``False`` if a significant shift was detected.

    Example:
        >>> expected = {"nba": 0.40, "nhl": 0.30, "mlb": 0.30}
        >>> check_categorical_distribution_shift(df, "sport", expected)
        True  # distribution is within tolerance

    ⛔ CRITICAL: If this check returns ``False``:
    - The data source may have changed its output format or coverage.
    - A pipeline bug may be dropping specific categories.
    - The API key may have been restricted to a subset of sports.

    ACTION: Halt ingestion if the shift exceeds 20pp for any category.
    Log the observed vs expected frequencies for each affected category.
    ALERT: PagerDuty with category-level breakdown.  Include the ratio of
    observed/expected for each category that exceeded the threshold.
    This check is particularly important for batch ingestion that expects
    a balanced sport mix.
    """
    if df.empty or column not in df.columns:
        logger.warning(
            "Distribution shift check skipped: DataFrame empty or column '%s' missing.",
            column,
        )
        return True

    # Compute actual frequencies as proportions.
    actual_counts: pd.Series = df[column].value_counts(normalize=True)

    shift_detected: bool = False
    for category, expected_prop in expected_distribution.items():
        actual_prop: float = actual_counts.get(category, 0.0)
        deviation_pp: float = abs(actual_prop - expected_prop) * 100.0

        if deviation_pp > max_deviation_pp:
            logger.error(
                "⚠️  DISTRIBUTION SHIFT: category='%s': "
                "expected %.1f%%, got %.1f%% (deviation=%.1fpp, threshold=%.1fpp). "
                "HALT ingestion and notify on-call.",
                category,
                expected_prop * 100.0,
                actual_prop * 100.0,
                deviation_pp,
                max_deviation_pp,
            )
            shift_detected = True

    if shift_detected:
        logger.error(
            "⚠️  Distribution shift detected in column '%s'. "
            "Expected: %s. Actual (top 5): %s. "
            "ACTION: Halt ingestion. Log full distribution to monitoring dashboard. "
            "ALERT: Notify data engineering team via Slack #data-pipeline.",
            column,
            expected_distribution,
            actual_counts.head(5).to_dict(),
        )

    return not shift_detected


# ---------------------------------------------------------------------------
# Validation Wrapper
# ---------------------------------------------------------------------------


def validate_odds_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Validate an odds DataFrame against ``OddsFeedSchema``.

    Collects ALL schema violations (lazy mode) and raises a unified
    ``SchemaErrors`` exception if any are found.  This ensures that
    ingestion is halted before bad data reaches the database.

    Args:
        df: DataFrame containing parsed odds data (one row per game,
            columns matching ``OddsFeedSchema``).

    Returns:
        The validated DataFrame (unchanged if validation passes).

    Raises:
        pandera.errors.SchemaErrors: If any validation checks fail.
            The exception contains detailed error information including
            which columns/checks failed and on which rows.

    ⛔ CRITICAL: This function is the GATEKEEPER for the ingestion pipeline.
    If it raises, ``save_to_db()`` MUST NOT be called.  The caller should
    catch ``SchemaErrors``, log the error report, and alert the on-call
    engineer via the incident management system.

    Example:
        >>> from odds_data_schema import validate_odds_dataframe
        >>> try:
        ...     validated = validate_odds_dataframe(raw_df)
        ...     api.save_to_db(validated.to_dict('records'))
        ... except SchemaErrors as e:
        ...     logger.critical("Odds data validation failed: %s", e)
        ...     pagerduty.trigger("odds-ingestion-validation-failure", e)
        ...     raise
    """
    logger.info(
        "Validating odds DataFrame: %d rows, %d columns",
        len(df),
        len(df.columns),
    )

    # Log column presence for debugging.
    required_cols: list[str] = [
        "sport",
        "game_id",
        "home_team",
        "away_team",
        "commence_time",
        "home_odds",
        "away_odds",
        "home_prob",
        "away_prob",
        "num_bookmakers",
        "platform",
        "best_home_odds",
        "best_away_odds",
    ]
    missing_cols: list[str] = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        logger.error(
            "⚠️  Missing required columns: %s. "
            "ACTION: Halt ingestion. The DataFrame structure does not match "
            "the expected schema. Check that _parse_game() output was "
            "correctly converted to a DataFrame.",
            missing_cols,
        )

    schema: OddsFeedSchema = OddsFeedSchema  # type: ignore[assignment]

    try:
        # ⛔ CRITICAL: lazy=True collects ALL errors in one pass.
        # This is intentional: we want a complete error report so the
        # on-call engineer has full context for debugging.
        validated_df: pd.DataFrame = schema.validate(df, lazy=True)
        logger.info(
            "✅ Odds DataFrame validation PASSED: %d rows OK.",
            len(validated_df),
        )
        return validated_df

    except SchemaErrors as e:
        # ⛔ CRITICAL: SchemaErrors contains ALL failures.
        # Log every error with full context before raising.
        error_count: int = len(e.failure_cases) if e.failure_cases is not None else 0
        logger.error(
            "❌ Odds DataFrame validation FAILED: %d schema violations detected. "
            "ACTION: HALT ingestion. Do NOT call save_to_db(). "
            "ALERT: Notify on-call engineer via PagerDuty with the following "
            "error summary.",
            error_count,
        )

        # Log individual failure cases for debugging.
        if e.failure_cases is not None and not e.failure_cases.empty:
            # Group by check name for a structured report.
            failure_groups = e.failure_cases.groupby("check", sort=False)
            for check_name, group in failure_groups:
                indices: list[str] = group["index"].astype(str).tolist()[:10]
                logger.error(
                    "  ❌ Check '%s' failed on %d rows (showing first 10 indices): %s",
                    check_name,
                    len(group),
                    indices,
                )

        # ⛔ CRITICAL: Re-raise to halt the calling pipeline.
        raise
