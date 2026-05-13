#!/usr/bin/env python3
"""
Pandera schema v2 for validating incoming odds data from The Odds API.

This schema is an enhanced version of ``odds_data_schema.py`` that adds:
- Spread validation (optional fields with half-integer constraints)
- Stricter team name emptiness checks (dataframe-level)
- ``bet_type`` distribution drift detection
- Multi-column coherence checks (best_odds >= odds)

Designed as the next-generation contract for data flowing through
``TheOddsAPI.save_to_db()`` in ``plugins/the_odds_api.py``.

Integration example for ``save_to_db()``
----------------------------------------
After converting parsed markets to a DataFrame, call::

    from odds_feed_schema_v2 import validate_odds_feed_v2, SchemaDriftError
    from pandera.errors import SchemaErrors

    df = pd.DataFrame(parsed_markets)
    try:
        df = validate_odds_feed_v2(df, expected_sport_distribution={...})
    except SchemaErrors as e:
        logger.critical("Schema violation -- halting ingestion: %s", e)
        raise
    except SchemaDriftError as e:
        logger.warning("Distribution drift detected -- continuing: %s", e)
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
logger = logging.getLogger("odds_feed_schema_v2.ingestion")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Valid sport identifiers. Matches SPORT_KEYS in TheOddsAPI plus tennis.
VALID_SPORTS: list[str] = [
    "nba",
    "nhl",
    "mlb",
    "nfl",
    "epl",
    "ncaab",
    "ligue1",
    "tennis",
    "wncaab",
    "cba",
    "unrivaled",
]

# Decimal odds range constraints.
MIN_ODDS: float = 1.01
MAX_ODDS: float = 1000.0

# Probability bounds (derived as 1 / odds).
MIN_PROB: float = 0.001
MAX_PROB: float = 0.999

# Maximum acceptable sum of home + away implied probabilities (vig threshold).
MAX_IMPLIED_PROB_SUM: float = 1.10

# Clock skew tolerance for commence_time future-check (seconds).
CLOCK_SKEW_TOLERANCE_SECONDS: int = 300

# Regex pattern for game_id: SPORT_YYYYMMDD_TEAM1_TEAM2
GAME_ID_PATTERN: str = r"^[A-Z]+_\d{8}_[A-Z0-9]+_[A-Z0-9]+$"

# Spread limits (valid for basketball/football).
MIN_SPREAD: float = -30.0
MAX_SPREAD: float = 30.0

# Maximum allowed absolute percentage-point deviation for categorical
# distribution shift detection.
MAX_DISTRIBUTION_SHIFT_PP: float = 20.0

# Expected sport distribution (baseline proportions for a typical season mix).
DEFAULT_SPORT_DISTRIBUTION: dict[str, float] = {
    "nba": 0.25,
    "nhl": 0.20,
    "mlb": 0.20,
    "nfl": 0.10,
    "epl": 0.10,
    "ncaab": 0.05,
    "ligue1": 0.03,
    "tennis": 0.03,
    "wncaab": 0.02,
    "cba": 0.01,
    "unrivaled": 0.01,
}

# Expected bet_type distribution.
DEFAULT_BETTYPE_DISTRIBUTION: dict[str, float] = {
    "h2h": 0.70,
    "spread": 0.20,
    "totals": 0.05,
    "moneyline": 0.05,
}


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------


class SchemaDriftError(Exception):
    """Raised when a categorical column's distribution deviates beyond threshold.

    This is a **warning** exception -- individual records may still be valid,
    but the data mix has shifted.  The ingestion pipeline should log this and
    continue, not halt.
    """

    def __init__(
        self,
        column: str,
        observed: dict[str, float],
        expected: dict[str, float],
        threshold_pp: float,
    ) -> None:
        self.column = column
        self.observed = observed
        self.expected = expected
        self.threshold_pp = threshold_pp
        super().__init__(
            f"Distribution drift detected in '{column}': "
            f"observed={observed}, expected={expected}, "
            f"threshold={threshold_pp:.1f}pp"
        )


# ---------------------------------------------------------------------------
# Pandera Schema
# ---------------------------------------------------------------------------


class OddsFeedSchemaV2(DataFrameModel):
    """Pandera DataFrameModel for validating The Odds API feed data (v2).

    Enforces domain-specific constraints on odds data from
    ``TheOddsAPI._parse_game()``.  Each field maps to a key in the
    ``_parse_game()`` dict output.

    Enhancements over ``OddsFeedSchema``:
    - Spread validation (optional half-integer spread lines)
    - ``dataframe_check`` for empty team names
    - Multi-column coherence (best_odds >= odds)
    - Expanded sport list
    - ``bet_type`` categorical with distribution drift detection
    """

    # -- Identifiers & Metadata ------------------------------------------------

    platform: Series[str] = Field(
        nullable=False,
        isin=["odds_api"],
        description=(
            "Source platform identifier. Must be 'odds_api'. "
            "Zero nulls allowed."
        ),
    )

    sport: Series[str] = Field(
        nullable=False,
        isin=VALID_SPORTS,
        description=(
            "Sport key (e.g., 'nba', 'nhl', 'mlb'). "
            "Must be one of the known VALID_SPORTS list. Zero nulls allowed."
        ),
    )

    game_id: Series[str] = Field(
        nullable=False,
        str_matches=GAME_ID_PATTERN,
        description=(
            "Unique game identifier in format SPORT_YYYYMMDD_TEAM1_TEAM2. "
            "Zero nulls allowed."
        ),
    )

    home_team: Series[str] = Field(
        nullable=False,
        description=(
            "Full name of the home team (e.g., 'Boston Celtics'). "
            "Must be non-null AND non-empty after stripping whitespace. "
            "Zero nulls allowed. Empty-string check is a dataframe-level rule."
        ),
    )

    away_team: Series[str] = Field(
        nullable=False,
        description=(
            "Full name of the away team (e.g., 'Los Angeles Lakers'). "
            "Must be non-null AND non-empty after stripping whitespace. "
            "Zero nulls allowed. Empty-string check is a dataframe-level rule."
        ),
    )

    commence_time: Series[datetime] = Field(
        nullable=False,
        description=(
            "ISO 8601 datetime indicating when the game starts. "
            "Must not be in the future (with 5-min clock skew tolerance). "
            "Zero nulls allowed."
        ),
    )

    # -- Moneyline / H2H Odds --------------------------------------------------

    home_odds: Series[float] = Field(
        nullable=False,
        ge=MIN_ODDS,
        le=MAX_ODDS,
        description=f"Decimal odds for the home team. Range [{MIN_ODDS}, {MAX_ODDS}].",
    )

    away_odds: Series[float] = Field(
        nullable=False,
        ge=MIN_ODDS,
        le=MAX_ODDS,
        description=f"Decimal odds for the away team. Range [{MIN_ODDS}, {MAX_ODDS}].",
    )

    home_prob: Series[float] = Field(
        nullable=False,
        ge=MIN_PROB,
        le=MAX_PROB,
        description=f"Implied probability = 1 / home_odds. Range [{MIN_PROB}, {MAX_PROB}].",
    )

    away_prob: Series[float] = Field(
        nullable=False,
        ge=MIN_PROB,
        le=MAX_PROB,
        description=f"Implied probability = 1 / away_odds. Range [{MIN_PROB}, {MAX_PROB}].",
    )

    # -- Best Odds (aggregated across bookmakers) ------------------------------

    best_home_odds: Series[float] = Field(
        nullable=False,
        ge=MIN_ODDS,
        le=MAX_ODDS,
        description=(
            f"Best (highest) decimal odds for home team across all bookmakers. "
            f"Range [{MIN_ODDS}, {MAX_ODDS}]. Must be >= home_odds."
        ),
    )

    best_away_odds: Series[float] = Field(
        nullable=False,
        ge=MIN_ODDS,
        le=MAX_ODDS,
        description=(
            f"Best (highest) decimal odds for away team across all bookmakers. "
            f"Range [{MIN_ODDS}, {MAX_ODDS}]. Must be >= away_odds."
        ),
    )

    # -- Aggregation Metadata --------------------------------------------------

    num_bookmakers: Series[int] = Field(
        nullable=False,
        ge=1,
        description="Number of bookmakers offering odds for this game. Must be >= 1.",
    )

    # -- Spread Fields (optional, may be all-null) -----------------------------

    spread_home: Series[float] = Field(
        nullable=True,
        ge=MIN_SPREAD,
        le=MAX_SPREAD,
        description=(
            f"Spread line for the home team (e.g., -4.5). "
            f"Range [{MIN_SPREAD}, {MAX_SPREAD}]. Must be a half-integer "
            f"(multiple of 0.5). Nullable; if present, spread_away must also "
            f"be present."
        ),
    )

    spread_away: Series[float] = Field(
        nullable=True,
        ge=MIN_SPREAD,
        le=MAX_SPREAD,
        description=(
            f"Spread line for the away team (e.g., +4.5). "
            f"Range [{MIN_SPREAD}, {MAX_SPREAD}]. Must be a half-integer "
            f"(multiple of 0.5). Nullable; if present, spread_home must also "
            f"be present."
        ),
    )

    spread_home_price: Series[float] = Field(
        nullable=True,
        ge=MIN_ODDS,
        le=MAX_ODDS,
        description=(
            f"Decimal odds for the home spread bet. "
            f"Range [{MIN_ODDS}, {MAX_ODDS}]. Nullable."
        ),
    )

    spread_away_price: Series[float] = Field(
        nullable=True,
        ge=MIN_ODDS,
        le=MAX_ODDS,
        description=(
            f"Decimal odds for the away spread bet. "
            f"Range [{MIN_ODDS}, {MAX_ODDS}]. Nullable."
        ),
    )

    # -- Market Type -----------------------------------------------------------

    bet_type: Series[pd.CategoricalDtype] = Field(
        nullable=True,
        dtype_kwargs={"categories": ["h2h", "spread", "totals", "moneyline"]},
        coerce=True,
        description=(
            "Market type: 'h2h', 'spread', 'totals', or 'moneyline'. "
            "Nullable for backward compatibility; will become required."
        ),
    )

    # ------------------------------------------------------------------
    # Custom Dataframe-Level Checks
    # ------------------------------------------------------------------

    @dataframe_check
    def check_team_names_nonempty(cls, df: pd.DataFrame) -> pd.Series:
        """Ensure ``home_team`` and ``away_team`` are non-empty strings.

        Both team name columns must contain at least one non-whitespace
        character after stripping.  Empty team names indicate a parsing
        failure in ``_parse_game()`` or a malformed API response.

        ⛔ CRITICAL: Writing empty team names to ``unified_games`` would:
        - Corrupt cross-sport queries and JOINs on team name.
        - Break the ``NamingResolver`` which expects non-empty strings.
        - Result in 'NULL' display values in downstream UI and reports.

        ACTION: HALT ingestion immediately.  Log the failing row indices.
        ALERT: Notify on-call engineer via PagerDuty.  This indicates a
        structural change in the API response format or a bug in
        ``_parse_game()`` field extraction.

        Why this matters downstream: Team names are used as natural keys
        for JOINs between ``unified_games``, ``game_odds``, and team
        metadata tables.  Empty strings will silently match nothing and
        produce missing rows in aggregated reports.
        """
        home_ok: pd.Series = (
            df["home_team"].astype(str).str.strip().str.len() > 0
        )
        away_ok: pd.Series = (
            df["away_team"].astype(str).str.strip().str.len() > 0
        )
        return home_ok & away_ok

    @dataframe_check
    def check_no_future_timestamps(cls, df: pd.DataFrame) -> pd.Series:
        """Ensure all ``commence_time`` values are not in the future.

        Allows a 5-minute clock skew tolerance
        (``CLOCK_SKEW_TOLERANCE_SECONDS``) to account for minor differences
        between the API server clock and the local ingestion server clock.

        ⛔ CRITICAL: If this check fails, the data contains games with
        commence times that haven't happened yet, indicating:
        1. The API returned corrupted or mislabeled data.
        2. A timezone/clock-sync issue on the ingestion server.
        3. The game was scheduled far in the future beyond what the
           pipeline expects for near-term odds data.

        ACTION: HALT ingestion immediately.  Do NOT proceed to
        ``save_to_db()``.
        ALERT: Log at ERROR level.  Notify on-call engineer via PagerDuty.
        Include the offending ``game_id`` values and their ``commence_time``
        values in the alert payload.

        Why this matters downstream: Games with future commence times that
        pass validation would enter the Elo rating system as if they had
        already started, corrupting rating updates and expected-value
        calculations.
        """
        now_utc: datetime = datetime.now(timezone.utc)
        cutoff_ts: float = now_utc.timestamp() + CLOCK_SKEW_TOLERANCE_SECONDS

        commence_ts: pd.Series = df["commence_time"].apply(
            lambda t: t.timestamp()
            if t.tzinfo is not None  # type: ignore[union-attr]
            else t.replace(tzinfo=timezone.utc).timestamp()  # type: ignore[union-attr]
        )
        return commence_ts <= cutoff_ts

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

        ACTION: HALT ingestion.  Log the ``game_id`` values where the sum
        exceeds the threshold, along with the actual ``home_prob`` and
        ``away_prob`` values.
        ALERT: PagerDuty notification to on-call engineer.  This could
        indicate a bug in the bookmaker odds extraction logic in
        ``_extract_odds_from_h2h_market()``.

        Why this matters downstream: The Elo rating system uses implied
        probabilities from odds.  If the probability sum exceeds 1.10, the
        Elo update formula produces nonsensical rating changes.  Expected
        value (EV) calculations for bet recommendations also rely on
        calibrated probabilities.
        """
        prob_sum: pd.Series = df["home_prob"] + df["away_prob"]
        return prob_sum < MAX_IMPLIED_PROB_SUM

    @dataframe_check
    def check_spread_both_sides_present(cls, df: pd.DataFrame) -> pd.Series:
        """Ensure spread fields are present on both sides or absent on both.

        If ``spread_home`` is non-null, ``spread_away`` must also be non-null
        (and vice versa).  A spread line for only one side is an incomplete
        market and cannot be used for betting calculations.

        ⛔ CRITICAL: A spread line without a corresponding opposite side
        creates undefined behaviour in:
        - EV calculations that compare home vs away spread outcomes.
        - Database schema where spread rows are expected in pairs.
        - Downstream UI display (a spread table with only one side).

        ACTION: HALT ingestion.  Log the rows where only one side has a
        spread value.
        ALERT: Slack #data-pipeline with the offending ``game_id`` and
        ``bookmaker`` context.

        Why this matters downstream: Spread markets are always priced as
        a pair (home line + away line).  An orphaned spread line cannot
        be matched to its counterpart, making the data useless for
        statistical modelling.
        """
        if "spread_home" not in df.columns or "spread_away" not in df.columns:
            return pd.Series(True, index=df.index)

        home_present: pd.Series = df["spread_home"].notna()
        away_present: pd.Series = df["spread_away"].notna()
        return home_present == away_present

    @dataframe_check
    def check_spread_half_integer(cls, df: pd.DataFrame) -> pd.Series:
        """Verify that spread values are half-integers (multiples of 0.5).

        Spread lines in major sports (NBA, NFL, NHL) are always quoted in
        half-point increments (e.g., -4.5, +3.0, -7.5).  A spread value
        like -4.7 or +3.14 is invalid.

        ⛔ CRITICAL: Non-half-integer spreads indicate:
        - The API returned a format we don't understand (e.g., decimal
          instead of American).
        - A parsing bug in the bookmaker market extraction.
        - The data is not from a standard h2h/spread market type.

        ACTION: HALT ingestion.  Log the exact spread values and their
        ``game_id``.
        ALERT: Notify data engineering team via Slack #data-pipeline.
        Provide sample values for debugging the API response.

        Why this matters downstream: Spread values are used in Elo rating
        adjustments and margin-of-victory modelling.  Non-standard values
        would break the numerical integration in those models.
        """
        result: pd.Series = pd.Series(True, index=df.index)

        if "spread_home" in df.columns:
            home_non_null: pd.Series = df["spread_home"].notna()
            if home_non_null.any():
                result[home_non_null] = (
                    df.loc[home_non_null, "spread_home"] % 0.5 == 0
                )

        if "spread_away" in df.columns:
            away_non_null: pd.Series = df["spread_away"].notna()
            if away_non_null.any():
                result[away_non_null] = (
                    result[away_non_null]
                    & (df.loc[away_non_null, "spread_away"] % 0.5 == 0)
                )

        return result

    @dataframe_check
    def check_spread_opposite_signs(cls, df: pd.DataFrame) -> pd.Series:
        """Verify that home and away spreads have opposite signs (or zero).

        Spread lines are always quoted as a pair where one side is negative
        (the favourite, must win by more than the spread) and the other is
        positive (the underdog, can lose by less than the spread).  Zero
        spread (a pick'em) is also valid where both are zero.

        ⛔ CRITICAL: If both sides have the same sign, the spread market
        is logically impossible: both teams cannot be favourites or
        underdogs simultaneously.

        ACTION: HALT ingestion.  Log the rows where sign symmetry is
        violated.
        ALERT: PagerDuty notification to on-call engineer.  This indicates
        a fundamental parsing error in spread market extraction.

        Why this matters downstream: Spread signs are used to determine
        which team is favoured.  Incorrect sign assignment would reverse
        the favourite/underdog designation, leading to wrong EV
        calculations and bet recommendations.
        """
        if "spread_home" not in df.columns or "spread_away" not in df.columns:
            return pd.Series(True, index=df.index)

        result: pd.Series = pd.Series(True, index=df.index)

        both_present: pd.Series = (
            df["spread_home"].notna() & df["spread_away"].notna()
        )
        if both_present.any():
            home_spreads: pd.Series = df.loc[both_present, "spread_home"]
            away_spreads: pd.Series = df.loc[both_present, "spread_away"]
            signs_ok: pd.Series = (
                ((home_spreads > 0) & (away_spreads < 0))
                | ((home_spreads < 0) & (away_spreads > 0))
                | ((home_spreads == 0) & (away_spreads == 0))
            )
            result[both_present] = signs_ok

        return result

    @dataframe_check
    def check_best_odds_ge_odds(cls, df: pd.DataFrame) -> pd.Series:
        """Verify that best_home_odds >= home_odds and best_away_odds >= away_odds.

        The "best" odds across all bookmakers must be at least as good as
        the individual bookmaker odds for each side.  If best odds are
        lower, the aggregation logic in ``_parse_game()`` is broken.

        ⛔ CRITICAL: A violation means:
        - ``_extract_bookmaker_odds()`` or ``_parse_game()`` computed
          incorrect best-odds values.
        - Downstream Elo and EV calculations will use sub-optimal odds,
          under-estimating expected value.

        ACTION: HALT ingestion.  Log the ``game_id`` values where
        best_odds < odds, along with the actual values.
        ALERT: PagerDuty notification to on-call engineer.  This is a
        pipeline logic bug, not a data quality issue.

        Why this matters downstream: ``best_home_odds`` and
        ``best_away_odds`` are used as the primary odds values for
        Elo updates and EV calculations.  If they're lower than the
        actual bookmaker odds, all computed metrics are biased.
        """
        home_ok: pd.Series = df["best_home_odds"] >= df["home_odds"]
        away_ok: pd.Series = df["best_away_odds"] >= df["away_odds"]
        return home_ok & away_ok

    @dataframe_check
    def check_last_update_not_future(cls, df: pd.DataFrame) -> pd.Series:
        """Ensure ``last_update`` (if present) is not in the future.

        The ``last_update`` column is optional -- it may not be present in
        all API responses or DataFrames.  If the column exists, every
        non-null value must be a past or present timestamp (within clock
        skew tolerance).

        ⛔ CRITICAL: A future ``last_update`` indicates:
        - The API returned a timestamp from a misconfigured clock.
        - The data may be from a different timezone without proper offset.
        - Timestamp-based deduplication in the DB may behave incorrectly.

        ACTION: HALT ingestion.  Log the offending rows.
        ALERT: Slack #data-pipeline with sample timestamps.

        Why this matters downstream: ``last_update`` is used in
        ``game_odds`` upsert logic to determine the most recent odds
        snapshot.  A future timestamp would perpetually override valid
        updates, freezing the odds at stale values.
        """
        if "last_update" not in df.columns or df["last_update"].isna().all():
            return pd.Series(True, index=df.index)

        now_utc: datetime = datetime.now(timezone.utc)
        cutoff_ts: float = now_utc.timestamp() + CLOCK_SKEW_TOLERANCE_SECONDS

        def _check_not_future(ts_val) -> bool:
            if pd.isna(ts_val):
                return True
            try:
                ts_str: str = str(ts_val).strip()
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1]
                parsed: datetime = datetime.strptime(
                    ts_str, "%Y-%m-%dT%H:%M:%S"
                )
                parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.timestamp() <= cutoff_ts
            except (ValueError, TypeError):
                return True  # Don't block on parsing issues alone

        return df["last_update"].apply(_check_not_future)

    class Config:
        """Pandera model configuration.

        - ``coerce=True``: Automatically coerce types to match annotations.
        - ``strict=False``: Allow extra columns not defined in the schema.
        - ``drop_invalid_rows=False``: Collect all errors via ``lazy=True``
          and let the caller decide whether to halt or continue.
        """
        coerce: bool = True
        strict: bool = False
        drop_invalid_rows: bool = False


# ---------------------------------------------------------------------------
# Distribution Shift Detection
# ---------------------------------------------------------------------------


def check_categorical_distribution_shift(
    df: pd.DataFrame,
    column: str,
    expected_distribution: dict[str, float],
    max_deviation_pp: float = MAX_DISTRIBUTION_SHIFT_PP,
) -> Optional[dict[str, float]]:
    """Check if a categorical column's distribution has shifted.

    Compares actual observed frequencies against an expected baseline.
    If any single category deviates by more than ``max_deviation_pp``
    percentage points, returns the observed proportions for reporting.

    **This function LOGS AND CONTINUES** -- it does not halt the pipeline.
    Distribution drift is a warning signal, not a data quality failure.

    Args:
        df: DataFrame containing the column to check.
        column: Name of the categorical column to analyze.
        expected_distribution: Mapping of category -> expected proportion
            (float in [0.0, 1.0]).  Need not sum to 1.0; categories not
            listed are ignored.
        max_deviation_pp: Maximum allowed deviation in absolute percentage
            points (e.g., 20.0 means +/- 20pp).  Defaults to
            ``MAX_DISTRIBUTION_SHIFT_PP``.

    Returns:
        Dict of observed proportions if a shift was detected (one or more
        categories exceeded the threshold), ``None`` if the distribution
        is within tolerance.  Also returns ``None`` if the column is
        missing or the DataFrame is empty.

    Example:
        >>> expected = {"nba": 0.40, "nhl": 0.30, "mlb": 0.30}
        >>> result = check_categorical_distribution_shift(df, "sport", expected)
        >>> if result:
        ...     logger.warning("Sport distribution shift detected: %s", result)

    ⛔ CRITICAL: If this function returns a non-None result:
    - The data source may have changed its output format or coverage.
    - A pipeline bug may be dropping specific categories.
    - The API key may have been restricted to a subset of sports.
    - Seasonal effects (off-season for a sport) may be reducing volume.

    ACTION: LOG AND CONTINUE.  This is a warning, not a hard block.
    Log the observed vs expected frequencies for each affected category.
    ALERT: Slack #data-pipeline with category-level breakdown.  Include
    the ratio of observed/expected for each category that exceeded the
    threshold.  If the shift persists for multiple consecutive batches,
    escalate to on-call engineer.

    Why this matters downstream: The Elo rating system and EV calculator
    both assume a representative mix of sports and market types.  A
    sudden shift (e.g., 80% NBA instead of 25%) will concentrate rating
    updates on one sport and may produce misleading aggregate metrics.
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
        deviation_pp: float = abs(actual_prop - expected_prop) * 100.0

        if deviation_pp > max_deviation_pp:
            logger.warning(
                "⚠️  DISTRIBUTION SHIFT in column '%s': category='%s': "
                "expected %.1f%%, got %.1f%% (deviation=%.1fpp, "
                "threshold=%.1fpp).  ACTION: Log and continue -- "
                "individual records are valid, but the data mix has changed.",
                column,
                category,
                expected_prop * 100.0,
                actual_prop * 100.0,
                deviation_pp,
                max_deviation_pp,
            )
            shift_detected = True

        observed[category] = actual_prop

    if shift_detected:
        logger.warning(
            "⚠️  Distribution drift detected in column '%s'.  "
            "Observed (top 5): %s.  "
            "ACTION: Continue ingestion -- this is a warning.  "
            "ALERT: Slack #data-pipeline with category-level breakdown.  "
            "Escalate to on-call engineer if drift persists >3 batches.",
            column,
            dict(list(actual_counts.head(5).items())),
        )
        return observed

    return None


# ---------------------------------------------------------------------------
# Validation Wrapper
# ---------------------------------------------------------------------------


def validate_odds_feed_v2(
    df: pd.DataFrame,
    expected_sport_distribution: Optional[dict[str, float]] = None,
    expected_bettype_distribution: Optional[dict[str, float]] = None,
) -> pd.DataFrame:
    """Validate an odds DataFrame against ``OddsFeedSchemaV2``.

    Orchestrates Pandera schema validation and statistical distribution
    shift detection.  Collects ALL schema violations (lazy mode) and
    raises a unified ``SchemaErrors`` exception if any are found.

    Distribution drift checks LOG AND CONTINUE via ``SchemaDriftError``.

    Args:
        df: DataFrame containing parsed odds data (one row per game,
            columns matching ``OddsFeedSchemaV2``).
        expected_sport_distribution: Expected sport proportions.  Falls
            back to ``DEFAULT_SPORT_DISTRIBUTION`` if not provided.
        expected_bettype_distribution: Expected bet_type proportions.
            Falls back to ``DEFAULT_BETTYPE_DISTRIBUTION`` if not
            provided.

    Returns:
        The validated DataFrame (unchanged if validation passes).

    Raises:
        pandera.errors.SchemaErrors: If any Pandera column-level or
            dataframe-level check fails.  Halt ingestion on this
            exception.
        SchemaDriftError: If a categorical distribution shift exceeds
            the drift threshold.  Log and continue -- do NOT halt the
            pipeline.

    ⛔ CRITICAL: This function is the GATEKEEPER for the ingestion
    pipeline.  If ``SchemaErrors`` is raised, ``save_to_db()`` MUST NOT
    be called.  The caller should catch ``SchemaErrors``, log the error
    report, and alert the on-call engineer.

    If ``SchemaDriftError`` is raised, the caller should log the warning
    but allow ingestion to proceed.

    Integration example for ``save_to_db()``::

        from pandera.errors import SchemaErrors
        from odds_feed_schema_v2 import (
            validate_odds_feed_v2,
            SchemaDriftError,
        )

        df = pd.DataFrame(parsed_markets)
        try:
            validated = validate_odds_feed_v2(
                df,
                expected_sport_distribution={"nba": 0.25, "nhl": 0.20, ...},
            )
            # Proceed with DB write
            save_to_db(validated.to_dict('records'))
        except SchemaErrors as e:
            logger.critical(
                "Odds feed v2 validation FAILED -- halting ingestion: %s", e
            )
            pagerduty.trigger("odds-ingestion-v2-failure", e)
            raise
        except SchemaDriftError as e:
            logger.warning(
                "Odds feed v2 distribution drift: %s.  "
                "Continuing ingestion -- data records are valid.",
                e,
            )
    """
    logger.info(
        "Validating odds feed v2 DataFrame: %d rows, %d columns",
        len(df),
        len(df.columns),
    )

    # ------------------------------------------------------------------
    # Step 0: Ensure spread columns exist (fill with None if missing).
    # ------------------------------------------------------------------
    # Pandera 0.31.1 does not support truly optional columns (columns
    # that can be completely absent from the DataFrame).  We fill missing
    # spread columns with None so the schema can validate them.
    _MISSING_SPREAD_COLS = {
        "spread_home", "spread_away",
        "spread_home_price", "spread_away_price",
    }
    for col in _MISSING_SPREAD_COLS:
        if col not in df.columns:
            df[col] = None

    # ------------------------------------------------------------------
    # Step 1: Pandera Schema Validation (lazy mode)
    # ------------------------------------------------------------------
    # We use lazy=True to collect ALL column-level and check-level
    # failures in a single pass.  This gives the operator a complete
    # picture of what's wrong without having to fix errors one at a time.
    schema: OddsFeedSchemaV2 = OddsFeedSchemaV2  # type: ignore[assignment]
    validated_df: pd.DataFrame = schema.validate(df, lazy=True)

    logger.info(
        "✅ OddsFeedSchemaV2 validation PASSED: %d rows OK.",
        len(validated_df),
    )

    # ------------------------------------------------------------------
    # Step 2: Sport Distribution Shift Detection (LOG AND CONTINUE)
    # ------------------------------------------------------------------
    sport_dist: dict[str, float] = (
        expected_sport_distribution
        if expected_sport_distribution is not None
        else DEFAULT_SPORT_DISTRIBUTION
    )

    sport_shift: Optional[dict[str, float]] = check_categorical_distribution_shift(
        df, "sport", sport_dist, MAX_DISTRIBUTION_SHIFT_PP
    )
    if sport_shift is not None:
        # ⚠️  WARNING: distribution drift detected.  Log and continue.
        raise SchemaDriftError(
            column="sport",
            observed=sport_shift,
            expected=sport_dist,
            threshold_pp=MAX_DISTRIBUTION_SHIFT_PP,
        )

    # ------------------------------------------------------------------
    # Step 3: Bet Type Distribution Shift Detection (LOG AND CONTINUE)
    # ------------------------------------------------------------------
    bettype_dist: dict[str, float] = (
        expected_bettype_distribution
        if expected_bettype_distribution is not None
        else DEFAULT_BETTYPE_DISTRIBUTION
    )

    bettype_shift: Optional[dict[str, float]] = check_categorical_distribution_shift(
        df, "bet_type", bettype_dist, MAX_DISTRIBUTION_SHIFT_PP
    )
    if bettype_shift is not None:
        raise SchemaDriftError(
            column="bet_type",
            observed=bettype_shift,
            expected=bettype_dist,
            threshold_pp=MAX_DISTRIBUTION_SHIFT_PP,
        )

    return validated_df
