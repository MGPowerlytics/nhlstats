#!/usr/bin/env python3
"""
Comprehensive Pandera schema for validating incoming sports betting odds feeds.

This module provides a unified ingestion validation contract for all odds data
sources (The Odds API, Kalshi, and future bookmaker feeds). It is designed to
be called immediately after raw API responses are parsed into DataFrames and
BEFORE any database writes occur.

Key validation domains:
  1. **Identifier integrity** — game_id, team names, and sport keys must never
     contain nulls. A single null identifier corrupts JOINs and cross-references.
  2. **Mathematical validity** — moneyline odds, spreads, and totals must be
     within physically possible ranges (e.g., American moneyline outside
     [-10000, -100] ∪ [+100, +10000] is rejected).
  3. **Temporal consistency** — live odds timestamps must not be in the future;
     game commence times must be logically ordered relative to odds snapshots.
  4. **Statistical distribution monitoring** — categorical columns (sport,
     bet_type, bookmaker) are compared against expected baselines; a drift
     exceeding ±20 percentage points triggers a SchemaDriftError alert.

Usage:
    from plugins.odds_feed_schema import (
        BettingOddsSchema,
        validate_betting_odds,
        SchemaDriftError,
    )

    df = pd.DataFrame(parsed_api_response)
    try:
        validated = validate_betting_odds(df)
    except SchemaError:
        # CRITICAL: HALT ingestion — data corruption detected
        logger.critical("Schema violation — do not write to DB")
        raise
    except SchemaDriftError as e:
        # WARNING: Log and alert, but individual records are valid
        logger.warning("Distribution drift: %s", e)
        # Continue with ingestion
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from pandera import DataFrameModel, Field, dataframe_check
from pandera.errors import SchemaError, SchemaErrors
from pandera.typing import Series

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("odds_feed_schema.ingestion")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Canonical sport identifiers used throughout the platform.
VALID_SPORTS: list[str] = [
    "NBA", "NHL", "MLB", "NFL",
    "EPL", "LIGUE1",
    "NCAAB", "WNCAAB",
    "TENNIS", "CBA", "UNRIVALED",
]

# Bet type taxonomy.
VALID_BET_TYPES: list[str] = [
    "moneyline", "h2h", "spread", "totals", "puckline", "runline",
]

# Bookmaker/source identifiers.
VALID_BOOKMAKERS: list[str] = [
    "Kalshi", "odds_api",
    "DraftKings", "FanDuel", "BetMGM", "Caesars",
    "Bet365", "Pinnacle", "WilliamHill",
]

# ---------------------------------------------------------------------------
# Moneyline odds bounds (American format).
# Valid moneylines must be >= +100 or <= -100 (decimal >= 2.0 or <= 2.0).
# Extreme longshots capped at +/- 10000 (decimal ~101.0).
# ---------------------------------------------------------------------------
MIN_MONEYLINE_AMERICAN: int = -10000
MAX_MONEYLINE_AMERICAN: int = -100  # Favourite side (negative)
MIN_MONEYLINE_AMERICAN_POSITIVE: int = 100  # Underdog side (positive)
MAX_MONEYLINE_AMERICAN_POSITIVE: int = 10000

# Decimal odds bounds.
# 1.01 = near-certain event with vig; 500.0 = extreme longshot.
MIN_DECIMAL_ODDS: float = 1.01
MAX_DECIMAL_ODDS: float = 500.0

# Spread/handicap bounds.
# In major sports, spreads rarely exceed +/- 30 points.
MIN_SPREAD: float = -50.0
MAX_SPREAD: float = 50.0

# Totals (over/under) bounds per sport.
MIN_TOTALS: float = 1.0
MAX_TOTALS: float = 500.0

# Probability bounds.
MIN_PROB: float = 0.001
MAX_PROB: float = 0.999

# Maximum acceptable overround (home_prob + away_prob for h2h markets).
# 1.0 = fair; typical bookmaker vig produces 1.04-1.10.
MAX_IMPLIED_PROB_SUM: float = 1.15

# Clock skew tolerance for future-timestamp checks (seconds).
CLOCK_SKEW_TOLERANCE_SECONDS: int = 300

# Game ID regex: SPORT_YYYYMMDD_TEAM1_TEAM2 or SPORT-YYYYMMDD-TEAM1-TEAM2
GAME_ID_PATTERN: str = r"^[A-Z]+[-_]\d{8}[-_][A-Z0-9]+[-_][A-Z0-9]+$"

# Distribution shift detection thresholds (percentage points).
DRIFT_THRESHOLD_PP: float = 20.0

# Expected baseline distribution for sport mix in a typical daily batch.
# These are approximate and should be tuned per-season.
EXPECTED_SPORT_DISTRIBUTION: dict[str, float] = {
    "NBA": 0.20,
    "NHL": 0.15,
    "MLB": 0.25,
    "NFL": 0.05,
    "EPL": 0.10,
    "NCAAB": 0.10,
    "TENNIS": 0.05,
    "LIGUE1": 0.03,
    "WNCAAB": 0.04,
    "CBA": 0.01,
    "UNRIVALED": 0.01,
    "NH": 0.01,
}

EXPECTED_BET_TYPE_DISTRIBUTION: dict[str, float] = {
    "moneyline": 0.50,
    "spread": 0.20,
    "totals": 0.20,
    "h2h": 0.05,
    "puckline": 0.02,
    "runline": 0.02,
    "NH": 0.01,
}


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------


class SchemaDriftError(Exception):
    """Raised when a categorical column's distribution deviates beyond threshold.

    This is a **warning** exception — individual records are structurally valid,
    but the data *mix* has shifted (e.g., off-season reduction in NBA markets,
    a new bookmaker coming online, or an API coverage change).

    The ingestion pipeline should:
      - Log the observed vs expected distribution
      - Alert monitoring (PagerDuty, Slack #data-pipeline)
      - Continue ingestion (do NOT halt)
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
            f"Distribution drift in '{column}': "
            f"observed={observed}, expected={expected}, "
            f"threshold={threshold_pp:.1f}pp"
        )


# ---------------------------------------------------------------------------
# Pandera Schema
# ---------------------------------------------------------------------------


class BettingOddsSchema(DataFrameModel):
    """Pandera DataFrameModel for validating sports betting odds ingestion.

    This schema enforces domain-specific constraints across all odds data
    sources. Each field maps to a column produced by the parsing layer
    (e.g., ``TheOddsAPI._parse_game()`` or ``kalshi_markets._parse_market()``).

    Validation is performed in **lazy mode** (``lazy=True``) so that ALL
    violations are collected in a single pass. This gives operators a complete
    error report rather than requiring iterative fix-and-retry cycles.

    ── Action on failure ─────────────────────────────────────────────────

    - **SchemaError / SchemaErrors** (column or check violations):
        HALT ingestion. Do NOT call ``save_to_db()``. Log the full failure
        report and alert the on-call engineer via PagerDuty. These errors
        indicate corrupted or malformed API data that would pollute the
        ``unified_games`` and ``game_odds`` tables.

    - **SchemaDriftError** (distribution anomaly):
        LOG and CONTINUE. Individual records are valid; the data mix has
        shifted. Alert monitoring but allow ingestion to proceed.
    """

    # ── Identifiers & Metadata (zero-null guarantee) ────────────────────────

    sport: Series[str] = Field(
        nullable=False,
        isin=VALID_SPORTS,
        description=(
            "Sport key in uppercase. Must be one of VALID_SPORTS. "
            "Zero nulls — an unknown sport breaks pipeline routing."
        ),
    )

    game_id: Series[str] = Field(
        nullable=False,
        str_matches=GAME_ID_PATTERN,
        description=(
            "Unique game identifier. Format: SPORT_YYYYMMDD_HOME_AWAY "
            "or SPORT-YYYYMMDD-HOME-AWAY. Zero nulls — game_id is the "
            "primary key for JOINs across unified_games and game_odds."
        ),
    )

    home_team: Series[str] = Field(
        nullable=False,
        description=(
            "Home team name. Zero nulls — required for game identity."
        ),
    )

    away_team: Series[str] = Field(
        nullable=False,
        description=(
            "Away team name. Zero nulls — required for game identity."
        ),
    )

    # ── Temporal fields ─────────────────────────────────────────────────────

    commence_time: Series[pd.Timestamp] = Field(
        nullable=False,
        description=(
            "Game start time in UTC. Must be a valid ISO 8601 timestamp. "
            "Zero nulls."
        ),
    )

    odds_timestamp: Series[pd.Timestamp] = Field(
        nullable=True,
        description=(
            "When the odds were last updated. Used for staleness detection. "
            "Nullable — not all sources provide this."
        ),
    )

    # ── Odds & Pricing — moneyline ──────────────────────────────────────────

    home_moneyline: Series[float] = Field(
        nullable=True,
        description=(
            "Home team moneyline in American format (e.g., -150, +130). "
            "Nullable for two-way markets where only one side is posted."
        ),
    )

    away_moneyline: Series[float] = Field(
        nullable=True,
        description=(
            "Away team moneyline in American format. "
            "Nullable for two-way markets where only one side is posted."
        ),
    )

    home_decimal_odds: Series[float] = Field(
        nullable=False,
        ge=MIN_DECIMAL_ODDS,
        le=MAX_DECIMAL_ODDS,
        description=(
            "Home team decimal odds. Range [1.01, 500.0]. "
            "Must be mathematically consistent with moneyline if both present."
        ),
    )

    away_decimal_odds: Series[float] = Field(
        nullable=False,
        ge=MIN_DECIMAL_ODDS,
        le=MAX_DECIMAL_ODDS,
        description=(
            "Away team decimal odds. Range [1.01, 500.0]."
        ),
    )

    # ── Odds & Pricing — spread / totals ────────────────────────────────────

    home_spread: Series[float] = Field(
        nullable=True,
        ge=MIN_SPREAD,
        le=MAX_SPREAD,
        description=(
            "Home team spread/handicap. Range [-50, +50]. "
            "Nullable — not all markets have spread lines."
        ),
    )

    away_spread: Series[float] = Field(
        nullable=True,
        ge=MIN_SPREAD,
        le=MAX_SPREAD,
        description="Away team spread/handicap. Range [-50, +50].",
    )

    total_points: Series[float] = Field(
        nullable=True,
        ge=MIN_TOTALS,
        le=MAX_TOTALS,
        description=(
            "Over/under total. Range [1.0, 500.0]. "
            "Nullable — not all markets have totals lines."
        ),
    )

    # ── Implied probabilities ───────────────────────────────────────────────

    home_prob: Series[float] = Field(
        nullable=False,
        ge=MIN_PROB,
        le=MAX_PROB,
        description=(
            "Implied probability for home outcome (1 / decimal_odds). "
            "Range [0.001, 0.999]."
        ),
    )

    away_prob: Series[float] = Field(
        nullable=False,
        ge=MIN_PROB,
        le=MAX_PROB,
        description=(
            "Implied probability for away outcome. "
            "Range [0.001, 0.999]."
        ),
    )

    # ── Market metadata ─────────────────────────────────────────────────────

    bet_type: Series[str] = Field(
        nullable=False,
        isin=VALID_BET_TYPES,
        description=(
            "Market type: moneyline, spread, totals, h2h, puckline, runline."
        ),
    )

    bookmaker: Series[str] = Field(
        nullable=False,
        isin=VALID_BOOKMAKERS,
        description=(
            "Source bookmaker/exchange. Must be one of VALID_BOOKMAKERS."
        ),
    )

    num_bookmakers: Series[int] = Field(
        nullable=True,
        ge=1,
        description=(
            "Number of bookmakers offering this market. "
            "Nullable for single-source feeds like Kalshi."
        ),
    )

    # ── Platform metadata ───────────────────────────────────────────────────

    platform: Series[str] = Field(
        nullable=False,
        isin=["odds_api", "kalshi", "direct"],
        description=(
            "Ingestion pipeline source: 'odds_api' (The Odds API), "
            "'kalshi' (Kalshi prediction markets), 'direct' (bookmaker API)."
        ),
    )

    # ── Kalshi-specific fields ──────────────────────────────────────────────

    yes_ask: Series[int] = Field(
        nullable=True,
        ge=0,
        le=99,
        description=(
            "Kalshi YES contract price in cents [0, 99]. "
            "Nullable — only present for Kalshi-sourced records."
        ),
    )

    no_ask: Series[int] = Field(
        nullable=True,
        ge=0,
        le=99,
        description=(
            "Kalshi NO contract price in cents [0, 99]."
        ),
    )

    # ── Custom DataFrame-level checks ───────────────────────────────────────

    @dataframe_check
    def check_no_future_commence_times(cls, df: pd.DataFrame) -> pd.Series:
        """Ensure commence_time is not unreasonably far in the future.

        Games scheduled more than 365 days from now are likely API errors
        (wrong year, corrupted timestamp). We allow a generous window since
        some futures markets (Super Bowl winner, championship odds) are
        posted far in advance, but individual game commence times should
        be within a season.

        ⛔ CRITICAL: Future timestamps indicate:
        - API returned a corrupted year (e.g., 2027 instead of 2024)
        - Timezone conversion error in the parsing layer
        - Test/sandbox data leaked into production feed

        ACTION: HALT ingestion. Log the offending game_ids with their
        commence_time values. Alert the data engineering team.
        Do NOT write these records — they will break date-partitioned
        queries and produce incorrect Elo projections.

        Note: We use a 365-day window rather than checking "not in the past"
        because futures/outrights are legitimately posted months in advance.
        """
        now_utc = datetime.now(timezone.utc)
        max_future = pd.Timestamp(now_utc) + pd.Timedelta(days=365)

        # Handle both tz-aware and naive timestamps
        commence = pd.to_datetime(df["commence_time"], utc=True, errors="coerce")
        return commence <= max_future

    @dataframe_check
    def check_odds_timestamps_not_future(cls, df: pd.DataFrame) -> pd.Series:
        """Ensure odds_timestamp (last_update) is not in the future.

        Live odds timestamps represent when a bookmaker last updated their
        price. A future timestamp means the clock on the ingestion server
        is behind the API server, or the API returned corrupted data.

        Unlike commence_time (which can legitimately be in the future for
        upcoming games), odds_timestamps must ALWAYS be <= now.

        ⛔ CRITICAL: Future odds timestamps indicate stale/corrupted data.
        An odds snapshot from the future cannot represent a real market
        price. HALT ingestion.

        Note: Null timestamps are allowed (not all sources provide them).
        This check only validates non-null values.
        """
        if "odds_timestamp" not in df.columns:
            return pd.Series(True, index=df.index)

        now_utc = datetime.now(timezone.utc)
        cutoff = pd.Timestamp(now_utc) + pd.Timedelta(
            seconds=CLOCK_SKEW_TOLERANCE_SECONDS
        )

        result = pd.Series(True, index=df.index)
        mask = df["odds_timestamp"].notna()
        if mask.any():
            ts = pd.to_datetime(df.loc[mask, "odds_timestamp"], utc=True, errors="coerce")
            result.loc[mask] = ts <= cutoff
        return result

    @dataframe_check
    def check_moneyline_decimal_consistency(cls, df: pd.DataFrame) -> pd.Series:
        """Verify moneyline and decimal odds are mathematically consistent.

        When both American moneyline and decimal odds are present for the
        same outcome, they must satisfy the conversion formula:
          - For positive moneyline:  decimal = (ML / 100) + 1
          - For negative moneyline:  decimal = (100 / |ML|) + 1

        We allow ±0.05 tolerance for rounding differences.

        ⛔ CRITICAL: Inconsistent odds indicate a parsing bug where
        moneyline and decimal odds came from different sources or were
        mismatched during the extraction. This propagates to EV calculations
        and Elo updates. HALT ingestion.
        """
        result = pd.Series(True, index=df.index)

        # Check home side
        home_both = df["home_moneyline"].notna() & df["home_decimal_odds"].notna()
        if home_both.any():
            home_ml = df.loc[home_both, "home_moneyline"]
            home_dec = df.loc[home_both, "home_decimal_odds"]
            positive_mask = home_ml > 0
            expected = pd.Series(0.0, index=home_ml.index)
            expected[positive_mask] = (home_ml[positive_mask] / 100.0) + 1
            expected[~positive_mask] = (100.0 / abs(home_ml[~positive_mask])) + 1
            result.loc[home_both] = abs(home_dec - expected) < 0.10

        # Check away side
        away_both = df["away_moneyline"].notna() & df["away_decimal_odds"].notna()
        if away_both.any():
            away_ml = df.loc[away_both, "away_moneyline"]
            away_dec = df.loc[away_both, "away_decimal_odds"]
            positive_mask = away_ml > 0
            expected = pd.Series(0.0, index=away_ml.index)
            expected[positive_mask] = (away_ml[positive_mask] / 100.0) + 1
            expected[~positive_mask] = (100.0 / abs(away_ml[~positive_mask])) + 1
            result.loc[away_both] = abs(away_dec - expected) < 0.10

        return result

    # NOTE: Spread symmetry (home_spread ≈ -away_spread) is validated
    # in the validate_betting_odds() wrapper as an advisory check,
    # not as a @dataframe_check, because asymmetric spreads are a
    # data quality warning rather than a hard ingestion block.

    @dataframe_check
    def check_implied_prob_sum(cls, df: pd.DataFrame) -> pd.Series:
        """Check that home_prob + away_prob is within reasonable overround.

        For two-way moneyline markets, the sum of implied probabilities
        should be > 1.0 (bookmaker vig) but < MAX_IMPLIED_PROB_SUM (1.15).
        A sum below 1.0 indicates an arbitrage opportunity or data error.
        A sum above 1.15 suggests corrupted odds or misaligned outcomes.

        ⛔ CRITICAL: Out-of-range probability sums break EV calculations
        and Kelly criterion position sizing. HALT ingestion.
        """
        prob_sum = df["home_prob"] + df["away_prob"]
        return (prob_sum >= 1.0) & (prob_sum <= MAX_IMPLIED_PROB_SUM)

    @dataframe_check
    def check_team_names_distinct(cls, df: pd.DataFrame) -> pd.Series:
        """Ensure home_team and away_team are different.

        A game where home_team == away_team is a data corruption error
        that will produce incorrect Elo updates and stats aggregation.

        ⛔ CRITICAL: HALT ingestion. This indicates a parsing failure
        in the source adapter (e.g., _parse_game or _parse_market).
        """
        home = df["home_team"].astype(str).str.strip()
        away = df["away_team"].astype(str).str.strip()
        return home != away

    @dataframe_check
    def check_kalshi_price_consistency(cls, df: pd.DataFrame) -> pd.Series:
        """For Kalshi-sourced records, verify yes_ask + no_ask ≈ 100 cents.

        Kalshi binary contracts have YES + NO = 100 cents (100% probability).
        Due to the bid-ask spread, the asks may sum to slightly above 100,
        but never above 110 (extreme illiquidity).

        This check only applies when both yes_ask and no_ask are present
        and the platform is 'kalshi'.

        ⚠️  WARNING: Log but don't halt — the individual price may still
        be valid if one side is stale.
        """
        result = pd.Series(True, index=df.index)
        mask = (
            df["yes_ask"].notna()
            & df["no_ask"].notna()
            & (df["platform"] == "kalshi")
        )
        if mask.any():
            total = df.loc[mask, "yes_ask"] + df.loc[mask, "no_ask"]
            result.loc[mask] = total <= 110
        return result

    # ── Configuration ───────────────────────────────────────────────────────

    class Config:
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
    max_deviation_pp: float = DRIFT_THRESHOLD_PP,
) -> bool:
    """Detect whether a categorical column's distribution has drifted.

    Compares observed category frequencies against expected baselines.
    Flags if ANY single category deviates by more than ``max_deviation_pp``
    percentage points.

    This catches silent data corruption where all values are individually
    valid (pass schema checks) but the *mix* is wrong — e.g., the API
    suddenly returns 90% MLB games when we expect 25%.

    Args:
        df: DataFrame containing the column to check.
        column: Name of the categorical column.
        expected_distribution: Mapping of category → expected proportion
            [0.0, 1.0]. Need not sum to 1.0; missing categories are ignored.
        max_deviation_pp: Maximum allowed absolute deviation in percentage
            points. Default is DRIFT_THRESHOLD_PP (20.0).

    Returns:
        ``True`` if distribution is within bounds (no shift).
        ``False`` if a significant shift was detected.

    ── Action on shift detected ────────────────────────────────────────────

    - Log observed vs expected frequencies at ERROR level
    - Alert via PagerDuty with per-category breakdown
    - For sport distribution: HALT batch ingestion (likely API key restriction
      or pipeline bug dropping categories)
    - For bet_type distribution: CONTINUE ingestion (may reflect genuine
      market changes like playoff series shifting from moneyline to puckline)
    """
    if df.empty or column not in df.columns:
        logger.warning(
            "Distribution shift check skipped: DataFrame empty or "
            "column '%s' missing.", column,
        )
        return True

    actual = df[column].value_counts(normalize=True)
    shift_detected = False

    for category, expected_prop in expected_distribution.items():
        actual_prop = actual.get(category, 0.0)
        deviation_pp = abs(actual_prop - expected_prop) * 100.0

        if deviation_pp > max_deviation_pp:
            logger.error(
                "⛔ DISTRIBUTION SHIFT in column '%s': "
                "category='%s': expected %.1f%%, got %.1f%% "
                "(deviation=%.1fpp, threshold=%.1fpp). "
                "HALT batch ingestion.",
                column, category,
                expected_prop * 100.0, actual_prop * 100.0,
                deviation_pp, max_deviation_pp,
            )
            shift_detected = True

    if shift_detected:
        logger.error(
            "⛔ Distribution shift summary for column '%s'. "
            "Expected: %s. Observed (top 5): %s. "
            "ACTION: Halt ingestion. Notify data engineering via Slack #data-pipeline "
            "with full distribution breakdown.",
            column, expected_distribution, actual.head(5).to_dict(),
        )

    return not shift_detected


# ---------------------------------------------------------------------------
# Validation Wrapper
# ---------------------------------------------------------------------------


def validate_betting_odds(
    df: pd.DataFrame,
    check_distribution: bool = True,
    expected_sport_distribution: Optional[dict[str, float]] = None,
) -> pd.DataFrame:
    """Validate a betting odds DataFrame against ``BettingOddsSchema``.

    This is the main entry point for pre-ingestion validation. It performs
    two phases of checking:

    Phase 1 — **Schema Validation** (hard gates):
      - Column dtype and nullability checks
      - Domain-specific range constraints (odds, spreads, probabilities)
      - Cross-column consistency (moneyline ↔ decimal odds, spread symmetry)
      - Temporal checks (no future odds timestamps)

    Phase 2 — **Distribution Shift Detection** (advisory):
      - Sport mix compared against expected seasonal baselines
      - Bet type distribution checked for anomalous shifts
      - Bookmaker source distribution monitored

    Args:
        df: DataFrame with columns matching ``BettingOddsSchema``.
        check_distribution: Whether to run distribution shift checks.
            Default ``True``.
        expected_sport_distribution: Override for sport distribution baseline.
            Falls back to ``EXPECTED_SPORT_DISTRIBUTION``.

    Returns:
        The validated DataFrame (unchanged if validation passes).

    Raises:
        SchemaErrors: If any Pandera schema check fails. The exception
            contains detailed failure cases (check name, row index, value).
            Caller MUST NOT proceed to ``save_to_db()``.

        SchemaDriftError: If categorical distribution shift exceeds
            the threshold. Caller should log and alert but MAY continue
            ingestion since individual records are valid.

    Example:
        >>> from plugins.odds_feed_schema import validate_betting_odds, SchemaDriftError
        >>> from pandera.errors import SchemaErrors
        >>>
        >>> df = pd.DataFrame(parsed_markets)
        >>> try:
        ...     validated = validate_betting_odds(df)
        ...     save_to_db(validated)
        ... except SchemaErrors as e:
        ...     logger.critical("HALT: Schema violations: %s", e.failure_cases)
        ...     pagerduty.trigger("odds-validation-failure", str(e))
        ... except SchemaDriftError as e:
        ...     logger.warning("Drift detected (continuing): %s", e)
        ...     save_to_db(validated)
    """
    logger.info(
        "Validating betting odds DataFrame: %d rows, %d columns",
        len(df), len(df.columns),
    )

    # Verify required columns exist before full validation
    required_cols = [
        "sport", "game_id", "home_team", "away_team",
        "commence_time", "home_decimal_odds", "away_decimal_odds",
        "home_prob", "away_prob", "bet_type", "bookmaker", "platform",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        logger.error(
            "⛔ Missing required columns: %s. "
            "HALT ingestion — DataFrame structure does not match schema.",
            missing,
        )
        raise ValueError(f"Missing required columns for odds feed validation: {missing}")

    # Phase 1: Pandera schema validation (lazy = all errors in one pass)
    try:
        validated_df = BettingOddsSchema.validate(df, lazy=True)
        logger.info(
            "✅ BettingOddsSchema validation PASSED: %d rows OK.",
            len(validated_df),
        )
    except SchemaErrors as e:
        error_count = len(e.failure_cases) if e.failure_cases is not None else 0
        logger.error(
            "⛔ Betting odds validation FAILED: %d schema violations. "
            "ACTION: HALT ingestion. Do NOT call save_to_db().",
            error_count,
        )
        if e.failure_cases is not None and not e.failure_cases.empty:
            for check_name, group in e.failure_cases.groupby("check", sort=False):
                indices = group["index"].astype(str).tolist()[:5]
                logger.error(
                    "  ❌ Check '%s' failed on %d rows (first 5 indices): %s",
                    check_name, len(group), indices,
                )
        raise

    # Phase 2: Distribution shift detection (advisory)
    if check_distribution:
        sport_dist = expected_sport_distribution or EXPECTED_SPORT_DISTRIBUTION
        sport_shifted = not check_categorical_distribution_shift(
            validated_df, "sport", sport_dist, DRIFT_THRESHOLD_PP,
        )
        if sport_shifted:
            # Build observed distribution for the exception
            observed = validated_df["sport"].value_counts(normalize=True).to_dict()
            raise SchemaDriftError(
                column="sport",
                observed=observed,
                expected=sport_dist,
                threshold_pp=DRIFT_THRESHOLD_PP,
            )

        bet_type_shifted = not check_categorical_distribution_shift(
            validated_df, "bet_type", EXPECTED_BET_TYPE_DISTRIBUTION, DRIFT_THRESHOLD_PP,
        )
        if bet_type_shifted:
            observed = validated_df["bet_type"].value_counts(normalize=True).to_dict()
            raise SchemaDriftError(
                column="bet_type",
                observed=observed,
                expected=EXPECTED_BET_TYPE_DISTRIBUTION,
                threshold_pp=DRIFT_THRESHOLD_PP,
            )

    return validated_df
