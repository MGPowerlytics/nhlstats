"""
Pandera schemas for validating sports league stats ingestion DataFrames.

These schemas act as a data contract at the boundary between external API
responses and internal persistence. They are designed to be called immediately
after the raw fetcher methods (e.g. ``fetch_game_stats``, ``fetch_date_range``)
return, before any rows are upserted to Postgres.

Usage
-----
>>> from plugins.stats.ingestion_schema import TeamGameStatsSchema
>>> df = pd.DataFrame(rows)  # rows from a BoxScoreFetcher
>>> TeamGameStatsSchema.validate(df)  # raises SchemaError on violation

The ``validate_ingestion`` helper wraps this with sport-aware baselines for
categorical distribution checks and returns a structured result.

Alerting
--------
When validation fails, the caller (typically an Airflow task) should:

1. **Log** the full ``SchemaError`` or ``IngestionValidationError`` message.
2. **Raise** the error to fail the task — this halts ingestion and triggers
   Airflow alerting (email/Slack/PagerDuty depending on the DAG config).
3. For categorical drift warnings (severity=warning), log but allow ingestion
   to proceed — these are early-warning signals, not hard blockers.

A ``SchemaError`` means the incoming data violates the contract (null IDs,
impossible scores, future timestamps) and should **never** be persisted.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)

try:
    import pandera as pa
    from pandera.typing import Series
except ImportError as exc:
    raise ImportError(
        "pandera is required for ingestion validation. "
        "Install it: pip install pandera"
    ) from exc


# ---------------------------------------------------------------------------
# Core schema — validates the normalised team_game_stats row contract
# ---------------------------------------------------------------------------

class TeamGameStatsSchema(pa.DataFrameModel):
    """Pandera schema for the canonical ``team_game_stats`` ingestion DataFrame.

    Every ``BoxScoreFetcher`` (NHL, MLB, EPL, etc.) should produce rows that
    validate against this schema before upsert.

    The schema enforces:
    - **No nulls** on critical identifiers (game_id, team, opponent, sport)
    - **Valid ranges** on scores (non-negative, mathematically bounded)
    - **Temporal sanity** (game_date not in the future)
    - **Boolean integrity** (won is True/False, not null or numeric)
    - **Home/away** is_home is boolean
    """

    # -- Critical identifiers (never null) --------------------------------
    game_id: Series[str] = pa.Field(
        nullable=False,
        description="Unique game identifier — must never be null. "
                    "A null game_id would create FK violations in Postgres.",
    )
    sport: Series[str] = pa.Field(
        nullable=False,
        description="Sport/league code (e.g. 'NHL', 'MLB', 'EPL'). "
                    "Null values indicate a fetcher bug — the sport context was lost.",
    )
    team: Series[str] = pa.Field(
        nullable=False,
        description="Team name/abbreviation — must never be null. "
                    "Required for the (game_id, team) composite key.",
    )
    opponent: Series[str] = pa.Field(
        nullable=False,
        description="Opponent name/abbreviation — must never be null. "
                    "A null opponent breaks downstream Elo calculations.",
    )

    # -- Temporal fields --------------------------------------------------
    game_date: Series[Any] = pa.Field(
        nullable=False,
        coerce=True,
        description="Game date — must be parseable and not in the future. "
                    "Future game dates indicate the fetcher pulled unplayed fixtures.",
    )
    season: Series[Any] = pa.Field(
        nullable=True,
        coerce=True,
        description="Season identifier (format varies by sport). Nullable because "
                    "some fetchers derive it from game_date.",
    )

    # -- Game outcome fields ----------------------------------------------
    is_home: Series[bool] = pa.Field(
        nullable=False,
        description="Whether this row represents the home team. "
                    "Must be a strict boolean — no nulls or truthy integers.",
    )
    points_for: Series[int] = pa.Field(
        ge=0,
        nullable=False,
        description="Scored points/goals/runs. Must be non-negative — "
                    "negative scores are physically impossible.",
    )
    points_against: Series[int] = pa.Field(
        ge=0,
        nullable=False,
        description="Conceded points/goals/runs. Must be non-negative.",
    )
    won: Series[bool] = pa.Field(
        nullable=False,
        description="Game outcome boolean. Must be True/False — "
                    "no nulls (OT/shootout losses are still losses).",
    )
    margin: Series[int] = pa.Field(
        description="points_for - points_against. Can be negative for losses.",
    )

    # -- Optional rating fields -------------------------------------------
    off_rating: Series[Any] = pa.Field(
        nullable=True,
        coerce=True,
        description="Offensive rating (nullable — not all sports compute this).",
    )
    def_rating: Series[Any] = pa.Field(
        nullable=True,
        coerce=True,
        description="Defensive rating (nullable).",
    )
    pace: Series[Any] = pa.Field(
        nullable=True,
        coerce=True,
        description="Pace factor (nullable — sport-specific).",
    )

    # -- Cross-field validators (dataframe-level checks) ------------------
    @pa.dataframe_check
    def _scores_reasonable(cls, df: pd.DataFrame) -> Series[bool]:
        """Scores in real sports never exceed 200 in any major league.

        This catches API response corruption (e.g. string "null" parsed as
        a large integer) or unit errors (cents vs dollars equivalent).
        """
        max_score = 200
        return (df["points_for"] <= max_score) & (df["points_against"] <= max_score)

    @pa.dataframe_check
    def _game_date_not_future(cls, df: pd.DataFrame) -> Series[bool]:
        """Game dates must not be in the future.

        Future dates indicate the fetcher pulled scheduled fixtures rather
        than completed games. The historical stats DAG should only ingest
        finished games.
        """
        now = pd.Timestamp.now(tz=timezone.utc)
        dates = pd.to_datetime(df["game_date"], errors="coerce")
        if dates.dt.tz is None:
            dates = dates.dt.tz_localize("UTC")
        return dates <= now

    @pa.dataframe_check
    def _margin_consistent(cls, df: pd.DataFrame) -> Series[bool]:
        """Margin must equal points_for - points_against.

        Catches fetcher bugs where margin is computed from un-normalised
        data or the wrong team's score.
        """
        expected = df["points_for"] - df["points_against"]
        return df["margin"] == expected

    @pa.dataframe_check
    def _won_consistent(cls, df: pd.DataFrame) -> Series[bool]:
        """won must be consistent with the score differential.

        points_for > points_against iff won == True. Catches fetcher bugs
        where the outcome flag is derived from the wrong side.
        """
        return df["won"] == (df["points_for"] > df["points_against"])

    class Config:
        strict = True  # Reject columns not declared in the schema
        coerce = True  # Attempt type coercion before validation
        title = "Team Game Stats Ingestion Schema"
        description = (
            "Data contract for sports league stats ingestion. "
            "Violations should halt the ingestion pipeline."
        )


# ---------------------------------------------------------------------------
# Sport-specific extension schemas
# ---------------------------------------------------------------------------

class NHLStatsExtSchema(pa.DataFrameModel):
    """Schema for ``nhl_team_game_stats_ext`` rows.

    Validates hockey-specific metrics: shots, hits, blocks, PIM, faceoff %,
    power-play, and penalty-kill stats.
    """

    game_id: Series[str] = pa.Field(nullable=False)
    team: Series[str] = pa.Field(nullable=False)
    shots: Series[int] = pa.Field(ge=0, nullable=True)
    sog: Series[int] = pa.Field(ge=0, nullable=True)
    hits: Series[int] = pa.Field(ge=0, nullable=True)
    blocks: Series[int] = pa.Field(ge=0, nullable=True)
    pim: Series[int] = pa.Field(ge=0, nullable=True)
    faceoff_pct: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=True)
    pp_goals: Series[int] = pa.Field(ge=0, nullable=True)
    pp_opportunities: Series[int] = pa.Field(ge=0, nullable=True)
    pp_pct: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=True)
    pk_goals_against: Series[int] = pa.Field(ge=0, nullable=True)
    pk_opportunities: Series[int] = pa.Field(ge=0, nullable=True)
    pk_pct: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=True)
    shooting_pct: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=True)

    @pa.dataframe_check
    def _goals_not_exceed_opportunities(cls, df: pd.DataFrame) -> Series[bool]:
        """Goals cannot exceed opportunities — a PP goal requires an opportunity."""
        return (
            (df["pp_goals"] <= df["pp_opportunities"]) &
            (df["pk_goals_against"] <= df["pk_opportunities"])
        )

    class Config:
        coerce = True


class MLBStatsExtSchema(pa.DataFrameModel):
    """Schema for ``mlb_team_game_stats_ext`` rows.

    Validates baseball-specific metrics: batting (AVG, OBP, SLG, wOBA),
    pitching (ERA), and fielding.
    """

    game_id: Series[str] = pa.Field(nullable=False)
    team: Series[str] = pa.Field(nullable=False)
    hits: Series[int] = pa.Field(ge=0, nullable=True)
    errors: Series[int] = pa.Field(ge=0, nullable=True)
    lob: Series[int] = pa.Field(ge=0, nullable=True)
    doubles: Series[int] = pa.Field(ge=0, nullable=True)
    triples: Series[int] = pa.Field(ge=0, nullable=True)
    home_runs: Series[int] = pa.Field(ge=0, nullable=True)
    rbi: Series[int] = pa.Field(ge=0, nullable=True)
    stolen_bases: Series[int] = pa.Field(ge=0, nullable=True)
    strikeouts: Series[int] = pa.Field(ge=0, nullable=True)
    walks: Series[int] = pa.Field(ge=0, nullable=True)
    at_bats: Series[int] = pa.Field(ge=0, nullable=True)
    obp: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=True)
    slg: Series[float] = pa.Field(ge=0.0, le=4.0, nullable=True)
    ops: Series[float] = pa.Field(ge=0.0, le=5.0, nullable=True)
    woba: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=True)
    era: Series[float] = pa.Field(ge=0.0, nullable=True)

    @pa.dataframe_check
    def _hit_types_not_exceed_total(cls, df: pd.DataFrame) -> Series[bool]:
        """Doubles, triples, HR cannot exceed total hits."""
        return (
            (df["doubles"] <= df["hits"]) &
            (df["triples"] <= df["hits"]) &
            (df["home_runs"] <= df["hits"])
        )

    class Config:
        coerce = True


class SoccerStatsExtSchema(pa.DataFrameModel):
    """Schema for ``soccer_team_game_stats_ext`` rows.

    Validates soccer-specific metrics: shots, corners, cards, fouls, xG.
    """

    game_id: Series[str] = pa.Field(nullable=False)
    team: Series[str] = pa.Field(nullable=False)
    shots: Series[int] = pa.Field(ge=0, nullable=True)
    shots_on_target: Series[int] = pa.Field(ge=0, nullable=True)
    fouls: Series[int] = pa.Field(ge=0, nullable=True)
    yellow_cards: Series[int] = pa.Field(ge=0, nullable=True)
    red_cards: Series[int] = pa.Field(ge=0, nullable=True)
    corners: Series[int] = pa.Field(ge=0, nullable=True)
    xg: Series[float] = pa.Field(ge=0.0, nullable=True)
    xga: Series[float] = pa.Field(ge=0.0, nullable=True)

    @pa.dataframe_check
    def _sot_not_exceed_shots(cls, df: pd.DataFrame) -> Series[bool]:
        """Shots on target cannot exceed total shots."""
        valid = df["shots"].notna() & df["shots_on_target"].notna()
        result = pd.Series(True, index=df.index)
        result[valid] = df.loc[valid, "shots_on_target"] <= df.loc[valid, "shots"]
        return result

    class Config:
        coerce = True


# ---------------------------------------------------------------------------
# Categorical distribution baselines
# ---------------------------------------------------------------------------

# Expected sport/league distribution baselines for drift detection.
# These represent the historical proportion of each sport in the
# team_game_stats table. A drastic change signals a fetcher bug
# (e.g. ingesting only one league when multiple were expected).
_SPORT_BASELINES: dict[str, float] = {
    "NHL": 0.25,
    "NBA": 0.25,
    "MLB": 0.20,
    "NFL": 0.05,
    "EPL": 0.10,
    "Ligue1": 0.05,
    "NCAAB": 0.05,
    "WNCAAB": 0.03,
    "Tennis": 0.02,
}

# How far the observed proportion can deviate before flagging drift.
# 50% relative tolerance: if NHL baseline is 25%, warn when observed
# is < 12.5% or > 37.5%.
_DRIFT_TOLERANCE_PCT: float = 0.50


# ---------------------------------------------------------------------------
# Structured validation result
# ---------------------------------------------------------------------------

@dataclass
class IngestionValidationResult:
    """Structured result from ``validate_ingestion``.

    Attributes:
        passed: True if all hard checks passed (no SchemaError raised).
        sport: Which sport/league was validated.
        row_count: Number of rows in the validated DataFrame.
        errors: List of human-readable error messages.
        warnings: List of drift/concern warnings (non-blocking).
        field_failures: Details on which schema fields failed and why.
    """

    passed: bool
    sport: str
    row_count: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    field_failures: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_ingestion(
    df: pd.DataFrame,
    sport: Optional[str] = None,
    check_drift: bool = True,
) -> IngestionValidationResult:
    """Validate a freshly-fetched ingestion DataFrame against the contract.

    This is the primary entry point for data validation at ingestion boundaries.
    It performs three layers of checks:

    1. **Schema validation** (hard block): Enforces the ``TeamGameStatsSchema``
       contract — null IDs, impossible scores, future dates, inconsistent
       win/loss flags. A failure here means the data is corrupt and must
       NOT be persisted. The caller should raise an error and halt ingestion.

    2. **Categorical drift** (warning): Compares the distribution of the
       ``sport`` column against historical baselines. A drastic shift
       (e.g. 90% NHL when the baseline is 25%) signals a fetcher bug
       such as filtering the wrong league or a missing data source.

    3. **Statistical sanity** (warning): Flags if any single team appears
       in more than 4 rows (likely duplicate ingestion) or if all rows
       have the same game_date (stale fetch).

    Args:
        df: DataFrame of freshly-fetched rows, as returned by a
            ``BoxScoreFetcher.fetch_game_stats`` or ``fetch_date_range``.
        sport: Optional sport hint for drift detection. If provided,
            the function checks whether the ``sport`` column matches
            the expected value.
        check_drift: Whether to run categorical drift checks. Set to
            ``False`` for single-sport fetchers where drift is impossible.

    Returns:
        :class:`IngestionValidationResult` with all check outcomes.

    Raises:
        IngestionValidationError: If any hard schema check fails.
            The caller should catch this, log the details, and fail
            the Airflow task to halt ingestion.

    Example:
        >>> rows = fetcher.fetch_date_range(start, end)
        >>> df = pd.DataFrame(rows)
        >>> try:
        ...     result = validate_ingestion(df, sport="NHL")
        ... except IngestionValidationError as exc:
        ...     logger.error("Ingestion blocked: %s", exc)
        ...     raise  # Fail the Airflow task
    """
    errors: list[str] = []
    warnings: list[str] = []
    field_failures: dict[str, str] = {}

    # -- Layer 1: Schema validation (hard block) --------------------------
    try:
        validated_df = TeamGameStatsSchema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        # Extract per-field failure details from the lazy validation report.
        # failure_cases is a DataFrame with columns:
        #   schema_context, column, check, check_number, failure_case, index
        failures_df = exc.failure_cases
        for _, row in failures_df.iterrows():
            col = row.get("column")
            check = row.get("check")
            value = row.get("failure_case")
            key = f"{col}.{check}" if col and check else str(row.to_dict())
            if key not in field_failures:
                field_failures[key] = (
                    f"Column '{col}' failed check '{check}': "
                    f"saw value {value!r}"
                )

        error_msg = (
            f"Schema validation failed for {len(df)} rows. "
            f"Failures: {len(field_failures)}. "
            f"Details: {'; '.join(field_failures.values())}"
        )
        raise IngestionValidationError(error_msg, field_failures=field_failures) from exc

    # -- Layer 2: Categorical drift detection -----------------------------
    if check_drift and "sport" in validated_df.columns and len(validated_df) > 0:
        observed = validated_df["sport"].value_counts(normalize=True)
        for sport_name, baseline in _SPORT_BASELINES.items():
            actual = observed.get(sport_name, 0.0)
            if baseline > 0:
                deviation = abs(actual - baseline) / baseline
                if deviation > _DRIFT_TOLERANCE_PCT:
                    warnings.append(
                        f"Sport distribution drift detected for {sport_name}: "
                        f"baseline={baseline:.1%}, observed={actual:.1%} "
                        f"(deviation={deviation:.1%}). "
                        f"This may indicate a fetcher filtering bug."
                    )

        # If a specific sport was expected, check it dominates
        if sport is not None:
            sport_upper = sport.upper()
            actual = observed.get(sport_upper, 0.0)
            if actual < 0.90 and len(validated_df) > 10:
                warnings.append(
                    f"Expected sport '{sport_upper}' to dominate (>90%) "
                    f"but observed only {actual:.1%}. "
                    f"Multiple sports in a single-sport fetch may indicate "
                    f"a join or filter bug."
                )

    # -- Layer 3: Statistical sanity checks -------------------------------
    if len(validated_df) > 0:
        # Check for duplicate team appearances (same team > 4 times = likely dup)
        team_counts = validated_df.groupby(["game_date", "team"]).size()
        max_team_games = team_counts.max()
        if max_team_games > 4:
            worst = team_counts.idxmax()
            warnings.append(
                f"Team {worst[1]} appears {max_team_games} times on {worst[0]}. "
                f"A team can't play more than ~2 games per day — "
                f"this likely indicates duplicate ingestion."
            )

        # Check for single-date ingestion (stale fetch — should span a range)
        unique_dates = validated_df["game_date"].nunique()
        if unique_dates == 1 and len(validated_df) > 20:
            warnings.append(
                f"All {len(validated_df)} rows are for a single date. "
                f"If this was a date-range fetch, the fetcher may be "
                f"stuck on one date."
            )

    result = IngestionValidationResult(
        passed=True,
        sport=sport or "unknown",
        row_count=len(df),
        errors=errors,
        warnings=warnings,
        field_failures=field_failures,
    )

    if warnings:
        for w in warnings:
            logger.warning("Ingestion drift warning: %s", w)

    return result


class IngestionValidationError(Exception):
    """Raised when ingestion schema validation fails.

    The caller should catch this, log the details, and halt the Airflow task.
    Do NOT persist any rows when this exception is raised — the data contract
    has been violated and the rows are untrustworthy.

    Attributes:
        field_failures: Dict mapping field.check keys to human-readable messages.
    """

    def __init__(
        self,
        message: str,
        field_failures: Optional[dict[str, str]] = None,
    ):
        super().__init__(message)
        self.field_failures = field_failures or {}
