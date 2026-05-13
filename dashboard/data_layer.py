"""Governed dashboard data access.

Page modules import data from this module only. Every page-facing read goes
through a versioned governed read-model view and maps the contract rows into
the current Streamlit page shapes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from jsonschema import Draft202012Validator, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from plugins.db_manager import DBManager

_db = DBManager()

# Cache TTLs (seconds)
TTL_LIVE = 30
TTL_STANDARD = 300
TTL_LONG = 3600

DASHBOARD_SCHEMA_DIR = Path(__file__).resolve().parents[1] / "tests/contracts/schemas"

PORTFOLIO_VIEW = "dashboard_portfolio_v1"
LIVE_MARKETS_VIEW = "dashboard_live_markets_v1"
RANKINGS_VIEW = "dashboard_rankings_v1"
CALIBRATION_VIEW = "dashboard_calibration_v1"
DATA_QUALITY_VIEW = "dashboard_data_quality_v1"
BET_DETAIL_VIEW = "dashboard_bet_detail_v1"
TENNIS_PREDICTIONS_VIEW = "dashboard_tennis_predictions_v1"
TENNIS_MODEL_HEALTH_VIEW = "dashboard_tennis_model_health_v1"
MLB_MODEL_HEALTH_VIEW = "dashboard_mlb_model_health_v1"
SPORT_VALIDATION_VIEW = "sport_validation_state_v1"
GOVERNED_EVIDENCE_VIEW = "governed_evidence_record_v1"
GOVERNED_RECOMMENDATION_EXECUTION_LINK_VIEW = (
    "governed_recommendation_execution_link_v1"
)
GOVERNED_CLV_EVIDENCE_VIEW = "governed_clv_evidence_envelope_v1"
GOVERNED_PORTFOLIO_RISK_VIEW = "governed_portfolio_risk_state_v1"

PORTFOLIO_COLUMNS = (
    "snapshot_hour_utc",
    "balance_dollars",
    "portfolio_value_dollars",
    "cumulative_deposits_dollars",
    "realized_profit_dollars",
    "open_risk_dollars",
    "settled_bet_count",
    "open_bet_count",
    "roi",
    "created_at_utc",
)
LIVE_MARKET_COLUMNS = (
    "market_external_id",
    "game_date",
    "commence_time",
    "home_team_name",
    "away_team_name",
    "bookmaker",
    "market_name",
    "outcome_name",
    "price",
    "last_update",
    "recommendation_bet_id",
    "edge",
    "expected_value",
    "confidence",
    "ticker",
)
RANKING_COLUMNS = (
    "sport",
    "entity_type",
    "entity_id",
    "entity_name",
    "rating",
    "rank",
    "games_played",
    "valid_from",
    "valid_to",
    "created_at",
)
CALIBRATION_COLUMNS = (
    "bucket_start",
    "bucket_end",
    "prediction_count",
    "avg_elo_prob",
    "avg_market_prob",
    "observed_win_rate",
    "avg_edge",
    "avg_expected_value",
    "settled_count",
    "unsettled_count",
)
DATA_QUALITY_COLUMNS = (
    "check_name",
    "relation_name",
    "relation_type",
    "status",
    "row_count",
    "freshness_timestamp",
    "max_allowed_lag_minutes",
    "actual_lag_minutes",
    "message",
    "checked_at_utc",
)
BET_DETAIL_COLUMNS = (
    "bet_id",
    "recommendation_date",
    "placed_time_utc",
    "home_team",
    "away_team",
    "bet_on",
    "ticker",
    "elo_prob",
    "market_prob",
    "edge",
    "expected_value",
    "kelly_fraction",
    "confidence",
    "yes_ask",
    "no_ask",
    "status",
    "cost_dollars",
    "payout_dollars",
    "profit_dollars",
    "created_at",
)
TENNIS_PREDICTION_COLUMNS = (
    "bet_id",
    "sport",
    "recommendation_date",
    "commence_time",
    "home_team",
    "away_team",
    "bet_on",
    "ticker",
    "model_prob",
    "market_prob",
    "edge",
    "expected_value",
    "kelly_fraction",
    "confidence",
    "yes_ask",
    "no_ask",
    "created_at",
)
TENNIS_MODEL_HEALTH_COLUMNS = (
    "run_date",
    "model_version",
    "data_source",
    "rows",
    "holdout_rows",
    "betmgm_holdout_rows",
    "enabled",
    "beats_betmgm",
    "baseline_log_loss",
    "ensemble_log_loss",
    "ensemble_market_log_loss",
    "betmgm_log_loss",
    "baseline_brier",
    "ensemble_brier",
    "ensemble_market_brier",
    "betmgm_brier",
    "baseline_accuracy",
    "ensemble_accuracy",
    "ensemble_market_accuracy",
    "betmgm_accuracy",
    "baseline_actionable_count",
    "ensemble_actionable_count",
    "log_loss_delta",
    "brier_delta",
    "accuracy_delta",
    "ensemble_vs_betmgm_log_loss_delta",
    "ensemble_vs_betmgm_brier_delta",
    "ensemble_vs_betmgm_accuracy_delta",
    "created_at",
)
MLB_MODEL_HEALTH_COLUMNS = (
    "run_date",
    "model_version",
    "prediction_count",
    "abstention_count",
    "abstention_rate",
    "avg_model_prob",
    "avg_market_prob",
    "avg_edge",
    "avg_expected_value",
    "ece_at_train",
    "latest_prediction_at",
)
SPORT_VALIDATION_COLUMNS = (
    "sport",
    "market_type",
    "cohort_type",
    "evidence_dimension",
    "canonical_game_id",
    "market_ticker",
    "selection_key",
    "source_relation",
    "source_record_id",
    "evidence_state_scope",
    "evidence_state",
    "evidence_state_reason",
    "evidence_state_as_of",
    "evidence_state_source_artifact",
    "governance_status",
    "descriptive_only_flag",
    "contamination_flag",
    "contamination_reason",
    "excluded_from_approval_flag",
    "observed_at",
    "loaded_at",
    "last_updated_at",
    "review_timestamp",
    "runtime_consumer",
    "artifact_id",
    "artifact_version",
    "artifact_family",
    "artifact_available_flag",
    "placed_bet_only_flag",
    "synthetic_identity_flag",
    "backfill_flag",
)
GOVERNED_EVIDENCE_COLUMNS = (
    "sport",
    "market_type",
    "cohort_type",
    "evidence_dimension",
    "canonical_game_id",
    "market_ticker",
    "selection_key",
    "source_relation",
    "source_record_id",
    "evidence_state_scope",
    "evidence_state",
    "evidence_state_reason",
    "evidence_state_as_of",
    "evidence_state_source_artifact",
    "governance_status",
    "descriptive_only_flag",
    "contamination_flag",
    "contamination_reason",
    "excluded_from_approval_flag",
    "observed_at",
    "loaded_at",
    "last_updated_at",
    "recommendation_id",
    "recommendation_created_at",
    "recommendation_source_surface",
    "probability_source",
    "calibrated_probability",
    "market_probability",
    "edge",
    "expected_value",
    "kelly_fraction",
    "confidence_label",
    "quote_source_system",
    "quote_bookmaker",
    "quote_observed_at",
    "quote_loaded_at",
    "quote_payload_ref",
    "quote_lineage_status",
    "quote_price_cents",
    "quote_price_role",
    "quote_freshness_result",
    "quote_fallback_status",
)
GOVERNED_RECOMMENDATION_EXECUTION_LINK_COLUMNS = (
    "sport",
    "market_type",
    "cohort_type",
    "evidence_dimension",
    "canonical_game_id",
    "market_ticker",
    "selection_key",
    "source_relation",
    "source_record_id",
    "evidence_state_scope",
    "evidence_state",
    "evidence_state_reason",
    "evidence_state_as_of",
    "evidence_state_source_artifact",
    "governance_status",
    "descriptive_only_flag",
    "contamination_flag",
    "contamination_reason",
    "excluded_from_approval_flag",
    "observed_at",
    "loaded_at",
    "last_updated_at",
    "placed_bet_id",
    "recommendation_id",
    "execution_source_surface",
    "execution_status",
    "submitted_at",
    "filled_at",
    "contracts",
    "execution_cost_dollars",
    "notional_exposure",
    "entry_probability",
    "entry_quote_role",
    "entry_price_source",
    "linkage_status",
    "linkage_basis",
    "linked_canonical_game_id",
    "linked_market_ticker",
    "linked_selection_key",
    "entry_quote_source_system",
    "entry_quote_bookmaker",
    "entry_quote_observed_at",
    "entry_quote_loaded_at",
    "entry_quote_payload_ref",
    "entry_quote_lineage_status",
    "entry_price_cents",
    "entry_quote_freshness_result",
    "entry_quote_fallback_status",
)
GOVERNED_CLV_EVIDENCE_COLUMNS = (
    "sport",
    "market_type",
    "cohort_type",
    "evidence_dimension",
    "canonical_game_id",
    "market_ticker",
    "selection_key",
    "source_relation",
    "source_record_id",
    "evidence_state_scope",
    "evidence_state",
    "evidence_state_reason",
    "evidence_state_as_of",
    "evidence_state_source_artifact",
    "governance_status",
    "descriptive_only_flag",
    "contamination_flag",
    "contamination_reason",
    "excluded_from_approval_flag",
    "observed_at",
    "loaded_at",
    "last_updated_at",
    "placed_bet_id",
    "recommendation_id",
    "linked_canonical_game_id",
    "linked_market_ticker",
    "linked_selection_key",
    "clv_source_type",
    "clv_computed_at",
    "entry_probability",
    "entry_price_role",
    "closing_probability",
    "clv_delta",
    "clv_direction",
    "closing_quote_source",
    "closing_quote_at",
    "close_price_role",
    "close_freshness_result",
    "selected_close_rule",
    "selected_close_provenance",
    "clv_evidence_tier",
    "binary_result_placeholder_flag",
    "stale_close_flag",
    "proxy_close_flag",
    "clv_contaminated_flag",
    "entry_price_cents",
    "entry_price_source",
    "entry_quote_source_system",
    "entry_quote_bookmaker",
    "entry_quote_observed_at",
    "entry_quote_loaded_at",
    "entry_quote_payload_ref",
    "entry_freshness_result",
    "entry_fallback_status",
    "closing_quote_loaded_at",
    "closing_quote_payload_ref",
    "close_fallback_status",
)
GOVERNED_PORTFOLIO_RISK_COLUMNS = (
    "sport",
    "market_type",
    "cohort_type",
    "evidence_dimension",
    "canonical_game_id",
    "market_ticker",
    "selection_key",
    "source_relation",
    "source_record_id",
    "evidence_state_scope",
    "evidence_state",
    "evidence_state_reason",
    "evidence_state_as_of",
    "evidence_state_source_artifact",
    "governance_status",
    "descriptive_only_flag",
    "contamination_flag",
    "contamination_reason",
    "excluded_from_approval_flag",
    "observed_at",
    "loaded_at",
    "last_updated_at",
    "snapshot_hour_utc",
    "open_exposure_flag",
    "open_exposure_amount",
    "position_status",
    "exposure_inclusion_state",
    "sport_exposure_amount",
    "same_event_exposure_amount",
    "same_side_exposure_amount",
    "existing_position_flag",
    "resting_order_exposure_amount",
    "resting_order_count",
    "executed_unsettled_exposure_amount",
    "executed_unsettled_count",
    "exposure_state",
    "daily_risk_cap_dollars",
    "remaining_daily_risk_budget_dollars",
    "peak_portfolio_value_dollars",
    "current_portfolio_value_dollars",
    "drawdown_amount_dollars",
    "drawdown_ratio",
    "drawdown_state",
    "risk_of_ruin_state",
    "portfolio_guardrail_state",
    "portfolio_guardrail_reason_code",
    "portfolio_guardrail_reason_detail",
    "concentration_bucket",
    "concentration_state",
    "existing_position_state",
    "same_match_conflict",
    "rejection_reason_code",
    "rejection_reason_detail",
    "operator_semantics_version",
    "bankroll_source",
    "bankroll_amount",
    "bankroll_observed_at",
    "bankroll_snapshot_id",
)

VIEW_COLUMNS = {
    PORTFOLIO_VIEW: PORTFOLIO_COLUMNS,
    LIVE_MARKETS_VIEW: LIVE_MARKET_COLUMNS,
    RANKINGS_VIEW: RANKING_COLUMNS,
    CALIBRATION_VIEW: CALIBRATION_COLUMNS,
    DATA_QUALITY_VIEW: DATA_QUALITY_COLUMNS,
    BET_DETAIL_VIEW: BET_DETAIL_COLUMNS,
    TENNIS_PREDICTIONS_VIEW: TENNIS_PREDICTION_COLUMNS,
    TENNIS_MODEL_HEALTH_VIEW: TENNIS_MODEL_HEALTH_COLUMNS,
    MLB_MODEL_HEALTH_VIEW: MLB_MODEL_HEALTH_COLUMNS,
    SPORT_VALIDATION_VIEW: SPORT_VALIDATION_COLUMNS,
    GOVERNED_EVIDENCE_VIEW: GOVERNED_EVIDENCE_COLUMNS,
    GOVERNED_RECOMMENDATION_EXECUTION_LINK_VIEW: (
        GOVERNED_RECOMMENDATION_EXECUTION_LINK_COLUMNS
    ),
    GOVERNED_CLV_EVIDENCE_VIEW: GOVERNED_CLV_EVIDENCE_COLUMNS,
    GOVERNED_PORTFOLIO_RISK_VIEW: GOVERNED_PORTFOLIO_RISK_COLUMNS,
}


@dataclass(frozen=True)
class DashboardStatePayload:
    """Typed dashboard empty/error state matching the governed state contract."""

    kind: str
    title: str
    message: str | None
    action: str | None
    severity: str

    def as_dict(self) -> dict[str, str | None]:
        """Return the JSON-compatible state payload."""

        return {
            "kind": self.kind,
            "title": self.title,
            "message": self.message,
            "action": self.action,
            "severity": self.severity,
        }


class DashboardDataError(RuntimeError):
    """Typed sanitized dashboard data-layer failure."""

    def __init__(self, payload: DashboardStatePayload) -> None:
        self.payload = payload.as_dict()
        super().__init__(
            f"{payload.kind}: {payload.title}"
            + (f" - {payload.message}" if payload.message else "")
        )


class DashboardEmptyState(ValueError):
    """Typed empty state used where legacy pages expect exceptions."""

    def __init__(self, payload: DashboardStatePayload) -> None:
        self.payload = payload.as_dict()
        super().__init__(f"{payload.kind}: {payload.title}")


def _state(
    kind: str,
    title: str,
    message: str | None,
    action: str | None,
    severity: str,
) -> DashboardStatePayload:
    """Build a governed dashboard state payload."""

    return DashboardStatePayload(
        kind=kind,
        title=title,
        message=message,
        action=action,
        severity=severity,
    )


def _empty_state(kind: str) -> dict[str, str | None]:
    """Return a governed empty-state payload for a page read."""

    states = {
        "no_portfolio_snapshots": _state(
            "no_portfolio_snapshots",
            "No portfolio snapshots",
            "No governed portfolio snapshots are available yet.",
            "Run the portfolio snapshot ingestion before relying on dashboard KPIs.",
            "info",
        ),
        "no_live_markets": _state(
            "no_live_markets",
            "No live markets",
            "No governed live market rows are available right now.",
            "Wait for market ingestion to complete or refresh later.",
            "info",
        ),
        "no_rankings": _state(
            "no_rankings",
            "No rankings",
            "No governed active ranking rows are available for the selected sport.",
            "Run rating ingestion before comparing teams.",
            "info",
        ),
        "no_calibration_predictions": _state(
            "no_calibration_predictions",
            "No calibration predictions",
            "No governed calibration prediction rows are available yet.",
            "Run recommendation ingestion before reviewing calibration.",
            "info",
        ),
        "no_settled_calibration_outcomes": _state(
            "no_settled_calibration_outcomes",
            "No settled calibration outcomes",
            "Calibration predictions exist, but no governed settled outcomes are available yet.",
            "Wait for recommended bets to settle before evaluating observed win rates.",
            "info",
        ),
        "no_bet_details": _state(
            "no_bet_details",
            "No bet details",
            "No governed bet detail rows are available yet.",
            "Run recommendation ingestion before opening bet details.",
            "info",
        ),
        "bet_not_found": _state(
            "bet_not_found",
            "Bet not found",
            "The selected bet is not available in the governed dashboard detail view.",
            "Return to recent activity and choose an available bet.",
            "info",
        ),
        "no_upcoming_games": _state(
            "no_upcoming_games",
            "No upcoming games",
            "No upcoming games are scheduled for the selected sport in the next 48 hours.",
            "Check back later or select a different sport.",
            "info",
        ),
        "no_tennis_predictions": _state(
            "no_tennis_predictions",
            "No actionable tennis predictions",
            "No governed actionable TENNIS predictions are available for the current run date.",
            "Run tennis market ingestion and recommendation loading before placing bets.",
            "info",
        ),
        "no_tennis_model_health": _state(
            "no_tennis_model_health",
            "No production tennis model health snapshots",
            "No production PostgreSQL tennis model-vs-BetMGM evaluation rows are available yet.",
            "Ingest tennis BetMGM odds and player-match stats, then run scripts/train_tennis_probability_model.py without --evaluate-only to publish production evidence to PostgreSQL.",
            "info",
        ),
    }
    return states[kind].as_dict()


def _read_model_missing_error(view_name: str) -> DashboardDataError:
    """Build a sanitized missing-read-model error."""

    return DashboardDataError(
        _state(
            "dashboard_read_model_missing",
            "Dashboard read model unavailable",
            f"The governed read model {view_name} is unavailable.",
            "Apply dashboard read-model migrations and retry.",
            "error",
        )
    )


def _query_failed_error(view_name: str) -> DashboardDataError:
    """Build a sanitized query-failure error."""

    return DashboardDataError(
        _state(
            "dashboard_query_failed",
            "Dashboard query failed",
            f"The governed read model {view_name} could not be read.",
            "Check dashboard data-layer logs and read-model migrations.",
            "error",
        )
    )


def _contract_error(view_name: str, message: str) -> DashboardDataError:
    """Build a sanitized contract-mismatch error."""

    return DashboardDataError(
        _state(
            "dashboard_contract_mismatch",
            "Dashboard contract mismatch",
            f"{view_name} returned data outside its governed contract: {message}",
            "Update the read-model migration or dashboard mapper to match the contract.",
            "error",
        )
    )


def _format_validation_error(exc: ValidationError, row_position: int) -> str:
    """Return safe JSON Schema validation context without rejected values."""

    path = ".".join(str(part) for part in exc.path) or "<row>"
    schema_path = ".".join(str(part) for part in exc.schema_path) or "<schema>"
    category = str(exc.validator or "schema")
    return (
        f"row {row_position} field {path} failed contract category {category} "
        f"at path {path} schema {schema_path}"
    )


def _to_json_value(value: Any) -> Any:
    """Convert a database scalar to a JSON Schema-compatible value."""

    if value is None:
        return None
    if pd.isna(value) and not isinstance(value, (list, tuple, dict)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "item"):
        return value.item()
    return value


def _record_from_series(row: pd.Series) -> dict[str, Any]:
    """Convert a pandas row to a JSON-compatible dictionary."""

    return {key: _to_json_value(value) for key, value in row.to_dict().items()}


def _normalize_dashboard_sport(sport: str) -> str:
    """Normalize a dashboard sport filter to the governed uppercase sport code."""

    return sport.strip().upper()


def _load_schema(view_name: str) -> dict[str, Any] | None:
    """Load the canonical dashboard JSON Schema when available."""

    schema_path = DASHBOARD_SCHEMA_DIR / f"{view_name}.schema.json"
    try:
        return json.loads(schema_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        raise _contract_error(view_name, "canonical schema is not valid JSON") from None


def _validate_read_model_rows(view_name: str, df: pd.DataFrame) -> None:
    """Validate non-empty read-model rows against canonical contracts."""

    if df.empty:
        return

    expected_columns = list(VIEW_COLUMNS[view_name])
    actual_columns = list(df.columns)
    if actual_columns != expected_columns:
        raise _contract_error(view_name, "columns do not match the governed schema")

    schema = _load_schema(view_name)
    if schema is None:
        return

    validator = Draft202012Validator(schema)
    try:
        for row_position, (_, row) in enumerate(df.iterrows()):
            validator.validate(_record_from_series(row))
    except ValidationError as exc:
        raise _contract_error(
            view_name, _format_validation_error(exc, row_position)
        ) from None


def _is_missing_read_model_error(exc: SQLAlchemyError) -> bool:
    """Return True when a SQLAlchemy failure looks like a missing read model."""

    lowered = str(exc).lower()
    return (
        "does not exist" in lowered
        or "undefinedtable" in lowered
        or "undefined_table" in lowered
        or "no such table" in lowered
    )


def _fetch_read_model(
    view_name: str,
    *,
    where: str | None = None,
    params: dict[str, Any] | None = None,
    order_by: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Fetch and validate rows from a governed dashboard read-model view."""

    columns = ", ".join(VIEW_COLUMNS[view_name])
    query = f"SELECT {columns} FROM {view_name}"
    if where:
        query += f" WHERE {where}"
    if order_by:
        query += f" ORDER BY {order_by}"
    if limit is not None:
        query += f" LIMIT {limit}"

    try:
        df = _db.fetch_df(query, params or {})
    except SQLAlchemyError as exc:
        if _is_missing_read_model_error(exc):
            raise _read_model_missing_error(view_name) from None
        raise _query_failed_error(view_name) from None

    _validate_read_model_rows(view_name, df)
    return df


def _iso_or_none(value: Any) -> str | None:
    """Convert a scalar date/time value to a string when present."""

    converted = _to_json_value(value)
    return None if converted is None else str(converted)


def _sanitize_provider_message(value: Any) -> str:
    """Return a display-safe provider message for dashboard health rows."""

    if value is None or pd.isna(value):
        return ""
    message = str(value)
    lowered = message.lower()
    sensitive_tokens = (
        "select ",
        " from ",
        " join ",
        "postgresql://",
        "password",
        "secret",
        "traceback",
        "sqlalchemy",
        "dsn",
    )
    if any(token in lowered for token in sensitive_tokens):
        return "Details are hidden; check dashboard data-layer logs."
    return message


def _attach_empty_state(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Attach a governed empty-state payload to an empty DataFrame."""

    if df.empty:
        df.attrs["empty_state"] = _empty_state(kind)
    else:
        df.attrs["empty_state"] = None
    return df


def _blank_portfolio_summary() -> dict[str, Any]:
    """Return legacy-compatible zero KPI values with an explicit empty state."""

    return {
        "portfolio_value": 0.0,
        "daily_pnl": 0.0,
        "open_bets_count": 0,
        "total_exposure": 0.0,
        "win_rate": 0.0,
        "total_bets": 0,
        "settled_count": 0,
        "empty_state": _empty_state("no_portfolio_snapshots"),
    }


@st.cache_data(ttl=TTL_LIVE)
def get_portfolio_summary() -> dict[str, Any]:
    """Return portfolio KPI values from the governed portfolio read model."""

    df = _fetch_read_model(
        PORTFOLIO_VIEW,
        order_by="snapshot_hour_utc DESC",
        limit=1,
    )
    if df.empty:
        return _blank_portfolio_summary()

    row = df.iloc[0]
    settled_count = int(row["settled_bet_count"])
    open_count = int(row["open_bet_count"])
    return {
        "portfolio_value": float(row["portfolio_value_dollars"]),
        "daily_pnl": float(row["realized_profit_dollars"]),
        "open_bets_count": open_count,
        "total_exposure": float(row["open_risk_dollars"]),
        "win_rate": 0.0,
        "total_bets": settled_count + open_count,
        "settled_count": settled_count,
        "empty_state": None,
    }


@st.cache_data(ttl=TTL_LIVE)
def get_placed_bets(
    limit: int = 50,
    status: Optional[str] = None,
    sport: Optional[str] = None,
) -> pd.DataFrame:
    """Return recent governed bet-detail rows in the legacy placed-bets shape."""

    where_parts: list[str] = []
    params: dict[str, Any] = {}
    if status:
        where_parts.append("LOWER(status) = :status")
        params["status"] = status.lower()

    df = _fetch_read_model(
        BET_DETAIL_VIEW,
        where=" AND ".join(where_parts) if where_parts else None,
        params=params,
        order_by="created_at DESC",
        limit=limit,
    )
    mapped = pd.DataFrame(
        [
            {
                **_record_from_series(row),
                "placed_at": _iso_or_none(row["placed_time_utc"]),
                "sport": sport or "",
                "market": row["ticker"],
                "team": row["bet_on"],
                "stake": (
                    row["cost_dollars"] if row["cost_dollars"] is not None else 0.0
                ),
                "payout": (
                    row["payout_dollars"] if row["payout_dollars"] is not None else 0.0
                ),
            }
            for _, row in df.iterrows()
        ]
    )
    return _attach_empty_state(mapped, "no_bet_details")


@st.cache_data(ttl=TTL_STANDARD)
def get_bet_detail(bet_id: str) -> dict[str, Any]:
    """Return governed bet-detail data for the selected bet."""

    df = _fetch_read_model(
        BET_DETAIL_VIEW,
        where="bet_id = :bet_id",
        params={"bet_id": bet_id},
        limit=1,
    )
    if df.empty:
        raise DashboardEmptyState(
            _state(
                "bet_not_found",
                "Bet not found",
                "The selected bet is not available in the governed dashboard detail view.",
                "Return to recent activity and choose an available bet.",
                "info",
            )
        )

    row = _record_from_series(df.iloc[0])
    execution_link_df = _fetch_read_model(
        GOVERNED_RECOMMENDATION_EXECUTION_LINK_VIEW,
        where="recommendation_id = :recommendation_id OR placed_bet_id = :placed_bet_id",
        params={"recommendation_id": bet_id, "placed_bet_id": bet_id},
        order_by="observed_at DESC NULLS LAST, placed_bet_id ASC",
        limit=1,
    )
    execution_link = (
        _record_from_series(execution_link_df.iloc[0])
        if not execution_link_df.empty
        else {}
    )
    lookup_placed_bet_id = execution_link.get("placed_bet_id") or bet_id
    clv_evidence_df = _fetch_read_model(
        GOVERNED_CLV_EVIDENCE_VIEW,
        where="recommendation_id = :recommendation_id OR placed_bet_id = :placed_bet_id",
        params={
            "recommendation_id": bet_id,
            "placed_bet_id": lookup_placed_bet_id,
        },
        order_by="observed_at DESC NULLS LAST, placed_bet_id ASC",
        limit=1,
    )
    clv_evidence = (
        _record_from_series(clv_evidence_df.iloc[0])
        if not clv_evidence_df.empty
        else {}
    )
    bet = {
        **row,
        "placed_at": row["placed_time_utc"],
        "sport": execution_link.get("sport") or clv_evidence.get("sport") or "",
        "market": row["ticker"],
        "team": row["bet_on"],
        "stake": row["cost_dollars"] or 0.0,
        "payout": row["payout_dollars"] or 0.0,
    }
    home_team = str(row["home_team"])
    away_team = str(row["away_team"])
    return {
        "bet": bet,
        "execution_link": execution_link,
        "clv_evidence": clv_evidence,
        "odds": [],
        "elo_snapshot": {
            "team_a_rating": 0.0,
            "team_b_rating": 0.0,
            "team_a_name": home_team,
            "team_b_name": away_team,
            "rating_diff": 0.0,
            "home_advantage": 0.0,
            "effective_diff": 0.0,
        },
        "elo_history": [],
        "recent_form": {
            "team_a": {"team": home_team, "games": [], "record": "0-0"},
            "team_b": {"team": away_team, "games": [], "record": "0-0"},
        },
        "empty_state": None,
    }


@st.cache_data(ttl=TTL_STANDARD)
def get_current_elo_ratings(sport: str) -> pd.DataFrame:
    """Return active rankings for a sport from the governed ranking view."""

    df = _fetch_read_model(
        RANKINGS_VIEW,
        where="sport = :sport",
        params={"sport": sport.upper()},
        order_by="rank ASC",
    )
    mapped = pd.DataFrame(
        [
            {
                **_record_from_series(row),
                "team": row["entity_name"],
                "last_updated": _iso_or_none(row["valid_from"]),
                "trend_7d": 0.0,
                "trend_30d": 0.0,
            }
            for _, row in df.iterrows()
        ]
    )
    return _attach_empty_state(mapped, "no_rankings")


@st.cache_data(ttl=TTL_LIVE)
def get_live_markets() -> pd.DataFrame:
    """Return governed live market rows for the Live Markets page."""

    df = _fetch_read_model(
        LIVE_MARKETS_VIEW,
        order_by="commence_time ASC, market_external_id ASC",
        limit=250,
    )
    mapped = pd.DataFrame(
        [_record_from_series(row) for _, row in df.iterrows()],
        columns=LIVE_MARKET_COLUMNS,
    )
    return _attach_empty_state(mapped, "no_live_markets")


@st.cache_data(ttl=TTL_LIVE)
def get_tomorrow_tennis_predictions(
    reference_date: date | None = None,
) -> pd.DataFrame:
    """Return current-run governed TENNIS predictions for upcoming markets.

    ``bet_recommendations.recommendation_date`` is the DAG/run date, while the
    underlying Kalshi markets can settle on later dates. Use the run date here
    so today's tennis task output appears immediately on the dashboard.
    """
    base_date = reference_date or datetime.now(ZoneInfo("America/New_York")).date()
    df = _fetch_read_model(
        TENNIS_PREDICTIONS_VIEW,
        where="recommendation_date = :recommendation_date",
        params={"recommendation_date": base_date.isoformat()},
        order_by="edge DESC, expected_value DESC NULLS LAST, created_at DESC NULLS LAST",
        limit=100,
    )
    mapped = pd.DataFrame(
        [_record_from_series(row) for _, row in df.iterrows()],
        columns=TENNIS_PREDICTION_COLUMNS,
    )
    return _attach_empty_state(mapped, "no_tennis_predictions")


@st.cache_data(ttl=TTL_STANDARD)
def get_tennis_model_health(limit: int = 30) -> pd.DataFrame:
    """Return recent governed tennis model-health rows."""

    df = _fetch_read_model(
        TENNIS_MODEL_HEALTH_VIEW,
        where="data_source = :data_source AND betmgm_holdout_rows > 0",
        params={"data_source": "postgres_tennis_games"},
        order_by="run_date DESC, created_at DESC, model_version ASC",
        limit=limit,
    )
    mapped = pd.DataFrame(
        [_record_from_series(row) for _, row in df.iterrows()],
        columns=TENNIS_MODEL_HEALTH_COLUMNS,
    )
    return _attach_empty_state(mapped, "no_tennis_model_health")


@st.cache_data(ttl=TTL_STANDARD)
def get_mlb_model_health(limit: int = 30) -> pd.DataFrame:
    """Return recent governed MLB model-health rows."""

    df = _fetch_read_model(
        MLB_MODEL_HEALTH_VIEW,
        order_by="run_date DESC, model_version ASC",
        limit=limit,
    )
    mapped = pd.DataFrame(
        [_record_from_series(row) for _, row in df.iterrows()],
        columns=MLB_MODEL_HEALTH_COLUMNS,
    )
    return _attach_empty_state(mapped, "no_calibration_predictions")


@st.cache_data(ttl=TTL_STANDARD)
def get_sport_validation_states() -> pd.DataFrame:
    """Return sport-level governed validation states for operator consumers."""

    df = _fetch_read_model(
        SPORT_VALIDATION_VIEW,
        order_by="sport ASC",
    )
    return pd.DataFrame(
        [_record_from_series(row) for _, row in df.iterrows()],
        columns=SPORT_VALIDATION_COLUMNS,
    )


@st.cache_data(ttl=TTL_STANDARD)
def get_sport_validation_state(sport: str) -> dict[str, Any] | None:
    """Return the governed validation state for a selected sport."""

    normalized_sport = _normalize_dashboard_sport(sport)
    df = _fetch_read_model(
        SPORT_VALIDATION_VIEW,
        where="sport = :sport",
        params={"sport": normalized_sport},
        order_by="sport ASC",
        limit=1,
    )
    if df.empty:
        return None
    return _record_from_series(df.iloc[0])


@st.cache_data(ttl=TTL_STANDARD)
def get_governed_evidence_records(
    approval_only: bool = False, limit: int = 100
) -> pd.DataFrame:
    """Return governed recommendation evidence rows with optional approval filter."""

    where = None
    if approval_only:
        where = "descriptive_only_flag = FALSE AND excluded_from_approval_flag = FALSE"

    df = _fetch_read_model(
        GOVERNED_EVIDENCE_VIEW,
        where=where,
        order_by="observed_at DESC, recommendation_id ASC",
        limit=limit,
    )
    return pd.DataFrame(
        [_record_from_series(row) for _, row in df.iterrows()],
        columns=GOVERNED_EVIDENCE_COLUMNS,
    )


@st.cache_data(ttl=TTL_STANDARD)
def get_governed_recommendation_execution_links(limit: int = 100) -> pd.DataFrame:
    """Return governed recommendation-to-execution linkage rows."""

    df = _fetch_read_model(
        GOVERNED_RECOMMENDATION_EXECUTION_LINK_VIEW,
        order_by="observed_at DESC, placed_bet_id ASC",
        limit=limit,
    )
    return pd.DataFrame(
        [_record_from_series(row) for _, row in df.iterrows()],
        columns=GOVERNED_RECOMMENDATION_EXECUTION_LINK_COLUMNS,
    )


@st.cache_data(ttl=TTL_STANDARD)
def get_governed_clv_evidence_envelopes(limit: int = 100) -> pd.DataFrame:
    """Return governed CLV lineage rows for operator-facing consumers."""

    df = _fetch_read_model(
        GOVERNED_CLV_EVIDENCE_VIEW,
        order_by="observed_at DESC, placed_bet_id ASC",
        limit=limit,
    )
    return pd.DataFrame(
        [_record_from_series(row) for _, row in df.iterrows()],
        columns=GOVERNED_CLV_EVIDENCE_COLUMNS,
    )


@st.cache_data(ttl=TTL_STANDARD)
def get_governed_portfolio_risk_state() -> pd.DataFrame:
    """Return governed portfolio-risk rows with separated exposure semantics."""

    df = _fetch_read_model(
        GOVERNED_PORTFOLIO_RISK_VIEW,
        order_by="sport ASC",
    )
    return pd.DataFrame(
        [_record_from_series(row) for _, row in df.iterrows()],
        columns=GOVERNED_PORTFOLIO_RISK_COLUMNS,
    )


@st.cache_data(ttl=TTL_LIVE)
def get_today_games(sport: Optional[str] = None) -> pd.DataFrame:
    """Return live market rows mapped into the current games-table shape."""

    df = get_live_markets()
    mapped = pd.DataFrame(
        [
            {
                **_record_from_series(row),
                "game_id": row["market_external_id"],
                "sport": sport or "",
                "home_team": row["home_team_name"],
                "away_team": row["away_team_name"],
                "start_time": _iso_or_none(row["commence_time"]),
                "home_elo": 0.0,
                "away_elo": 0.0,
                "home_win_prob": None,
                "best_home_odds": row["price"],
                "best_away_odds": None,
                "best_home_bookmaker": row["bookmaker"],
                "best_away_bookmaker": "",
                "edge": row["edge"] if row["edge"] is not None else 0.0,
                "edge_side": row["outcome_name"],
                "confidence": row["confidence"] or "",
            }
            for _, row in df.iterrows()
        ]
    )
    return _attach_empty_state(mapped, "no_live_markets")


# ---------------------------------------------------------------------------
# Ensemble adapter cache (one per sport, long TTL — historical data is stable)
# ---------------------------------------------------------------------------

HOME_ADVANTAGE: dict[str, float] = {
    "NBA": 100.0,
    "NHL": 50.0,
    "MLB": 20.0,
    "NFL": 65.0,
    "EPL": 60.0,
    "LIGUE1": 60.0,
    "NCAAB": 100.0,
    "WNCAAB": 100.0,
    "TENNIS": 0.0,
    "UNRIVALED": 0.0,
    "CBA": 80.0,
}

ENSEMBLE_SPORTS = frozenset({"MLB", "EPL", "LIGUE1"})


@st.cache_data(ttl=TTL_LONG)
def _get_ensemble_adapter(sport: str):
    """Return a populated ensemble adapter for *sport*, or ``None``.

    Ensemble adapters load season-long historical data (team form, goal
    stats, pitcher data, bookmaker odds) on first call and are cached for
    ``TTL_LONG`` (1 hour).  Ratings are refreshed from the ``elo_ratings``
    table on every ``get_upcoming_games`` call, so probability outputs stay
    current even when the adapter is cached.
    """
    sport_upper = sport.upper()
    try:
        if sport_upper == "MLB":
            from plugins.elo.mlb_ensemble_adapter import MLBEnsembleAdapter  # type: ignore[import-untyped]

            adapter = MLBEnsembleAdapter()
            adapter.populate_from_db(_db)
            return adapter

        if sport_upper == "EPL":
            from plugins.elo.epl_ensemble_adapter import EPLEnsembleAdapter  # type: ignore[import-untyped]

            adapter = EPLEnsembleAdapter(auto_train=False)
            adapter.populate_from_db(_db)
            adapter.ensemble.ensure_trained()
            return adapter

        if sport_upper == "LIGUE1":
            from plugins.elo.ligue1_ensemble_adapter import Ligue1EnsembleAdapter  # type: ignore[import-untyped]

            adapter = Ligue1EnsembleAdapter()
            adapter.populate_from_db(_db)
            return adapter
    except Exception:
        pass
    return None


def _normalize_tennis_name(name: str) -> str:
    """Convert ``\"Jannik Sinner\"`` → ``\"Sinner J.\"`` (elo_ratings format)."""
    if not name:
        return ""
    stripped = name.strip()
    if stripped.endswith("."):
        return stripped  # already in "Last I." format
    parts = stripped.split()
    if len(parts) < 2:
        return stripped
    first = parts[0]
    last = " ".join(parts[1:])
    return f"{last} {first[0].upper()}."


def _match_team_rating(
    team_name: str,
    ratings_lookup: dict[str, float],
    sport: str,
) -> float | None:
    """Return the Elo rating for *team_name*, or ``None`` if not found.

    Tries a direct case-insensitive match first, then falls back to the
    sport-specific team-name mapper registered in ``elo_update_config``.
    """
    if not team_name:
        return None

    key = team_name.strip().lower()
    if key in ratings_lookup:
        return ratings_lookup[key]

    # Try the sport-specific team mapper (NBA / NHL use abbreviations in
    # elo_ratings.entity_name whereas unified_games carries full names).
    try:
        from plugins.elo.elo_update_config import get_sport_config  # type: ignore[import-untyped]

        config = get_sport_config(sport.lower())
        if config.team_mapper is not None:
            mapped = config.team_mapper(team_name)
            if mapped is not None:
                mapped_key = mapped.strip().lower()
                if mapped_key in ratings_lookup:
                    return ratings_lookup[mapped_key]
    except Exception:
        pass

    # Tennis: unified_games uses "Jannik Sinner", elo_ratings uses "Sinner J."
    if sport.upper() == "TENNIS":
        normalized = _normalize_tennis_name(team_name)
        if normalized.lower() in ratings_lookup:
            return ratings_lookup[normalized.lower()]

    return None


@st.cache_data(ttl=TTL_LIVE)
def get_upcoming_games(sport: str, hours: int = 48) -> pd.DataFrame:
    """Return upcoming games with Elo win probabilities for *sport*.

    Columns
    -------
    away_team, away_elo_prob, home_team, home_elo_prob, prob_diff,
    game_date (ET), game_time_et, commence_time_utc (for sorting).
    """
    sport_upper = sport.upper()
    home_adv = HOME_ADVANTAGE.get(sport_upper, 0.0)

    # -- upcoming games from unified_games -----------------------------------
    games_df = _db.fetch_df(
        """
        SELECT game_id, sport, game_date, commence_time,
               home_team_name, away_team_name, status
        FROM unified_games
        WHERE UPPER(sport) = :sport
          AND commence_time >= NOW()
          AND commence_time <= NOW() + (:hours || ' hours')::INTERVAL
        ORDER BY commence_time ASC
        """,
        {"sport": sport_upper, "hours": str(hours)},
    )

    if games_df.empty:
        empty = pd.DataFrame()
        return _attach_empty_state(empty, "no_upcoming_games")

    # -- current Elo ratings -------------------------------------------------
    ratings_df = _db.fetch_df(
        """
        SELECT entity_name, rating
        FROM elo_ratings
        WHERE UPPER(sport) = :sport
          AND entity_type = 'team'
          AND valid_to IS NULL
        """,
        {"sport": sport_upper},
    )
    ratings_lookup: dict[str, float] = {}
    for _, row in ratings_df.iterrows():
        name = str(row["entity_name"]).strip()
        ratings_lookup[name.lower()] = float(row["rating"])

    # -- ensemble adapter (MLB / EPL / Ligue 1) -----------------------------
    ensemble = (
        _get_ensemble_adapter(sport_upper) if sport_upper in ENSEMBLE_SPORTS else None
    )
    if ensemble is not None:
        # Refresh ratings into the adapter so predictions use current values.
        ensemble.ratings = dict(ratings_lookup)

    # -- timezone helpers ----------------------------------------------------
    UTC = ZoneInfo("UTC")
    ET = ZoneInfo("America/New_York")

    def _to_et(ts) -> tuple[str, str]:
        """Convert a db timestamp to ``(game_date_str, game_time_str)`` in ET."""
        if ts is None or pd.isna(ts):
            return ("", "")
        if isinstance(ts, datetime):
            dt_utc = ts.replace(tzinfo=UTC)
        else:
            dt_utc = pd.Timestamp(ts).tz_localize(UTC)
        dt_et = dt_utc.astimezone(ET)
        time_str = dt_et.strftime("%I:%M %p ET").lstrip("0")
        return (dt_et.strftime("%Y-%m-%d"), time_str)

    # -- build result rows ---------------------------------------------------
    rows: list[dict[str, Any]] = []
    for _, game in games_df.iterrows():
        home_team = str(game["home_team_name"] or "")
        away_team = str(game["away_team_name"] or "")

        home_rating = _match_team_rating(home_team, ratings_lookup, sport_upper)
        away_rating = _match_team_rating(away_team, ratings_lookup, sport_upper)

        # Elo win probability
        if ensemble is not None and home_team and away_team:
            try:
                home_prob = float(ensemble.predict(home_team, away_team))
            except Exception:
                home_prob = None
        elif home_rating is not None and away_rating is not None:
            adjusted_home = home_rating + home_adv
            home_prob = 1.0 / (1.0 + 10.0 ** ((away_rating - adjusted_home) / 400.0))
        else:
            home_prob = None

        away_prob = (1.0 - home_prob) if home_prob is not None else None
        prob_diff = (home_prob - away_prob) if home_prob is not None else None

        game_date_et, game_time_et = _to_et(game["commence_time"])

        rows.append(
            {
                "away_team": away_team,
                "away_elo_prob": away_prob,
                "home_team": home_team,
                "home_elo_prob": home_prob,
                "prob_diff": prob_diff,
                "game_date": game_date_et,
                "game_time_et": game_time_et,
                "commence_time_utc": game["commence_time"],
            }
        )

    result = pd.DataFrame(rows)
    return _attach_empty_state(result, "no_upcoming_games")


@st.cache_data(ttl=TTL_LIVE)
def get_bet_recommendations(sport: Optional[str] = None) -> pd.DataFrame:
    """Return governed recommendation/detail rows for the recommendations table."""

    df = _fetch_read_model(BET_DETAIL_VIEW, order_by="created_at DESC", limit=100)
    mapped = pd.DataFrame(
        [
            {
                **_record_from_series(row),
                "sport": sport or "",
                "game_id": row["ticker"],
                "side": row["bet_on"],
                "bookmaker": "",
            }
            for _, row in df.iterrows()
        ]
    )
    return _attach_empty_state(mapped, "no_bet_details")


@st.cache_data(ttl=TTL_LONG)
def get_calibration_data(sport: Optional[str] = None) -> dict[str, Any]:
    """Return governed calibration buckets in the current page shape."""

    sport_validation_state = get_sport_validation_state(sport) if sport else None
    df = _fetch_read_model(CALIBRATION_VIEW, order_by="bucket_start ASC")
    if df.empty:
        return {
            "bets": [],
            "buckets": [],
            "by_sport": [],
            "empty_state": _empty_state("no_calibration_predictions"),
            "sport_validation_state": sport_validation_state,
        }

    buckets = []
    total_predictions = 0
    total_settled = 0
    total_edge = 0.0
    edge_count = 0
    for _, row in df.iterrows():
        prediction_count = int(row["prediction_count"])
        total_predictions += prediction_count
        total_settled += int(row["settled_count"])
        if row["avg_edge"] is not None:
            total_edge += float(row["avg_edge"]) * prediction_count
            edge_count += prediction_count
        buckets.append(
            {
                "label": f"{float(row['bucket_start']):.0%}-{float(row['bucket_end']):.0%}",
                "bucket_start": float(row["bucket_start"]),
                "bucket_end": float(row["bucket_end"]),
                "predicted_min": float(row["bucket_start"]),
                "predicted_max": float(row["bucket_end"]),
                "count": prediction_count,
                "prediction_count": prediction_count,
                "avg_elo_prob": float(row["avg_elo_prob"]),
                "avg_market_prob": (
                    float(row["avg_market_prob"])
                    if row["avg_market_prob"] is not None
                    else None
                ),
                "observed_win_rate": (
                    float(row["observed_win_rate"])
                    if row["observed_win_rate"] is not None
                    else None
                ),
                "actual_win_rate": (
                    float(row["observed_win_rate"])
                    if row["observed_win_rate"] is not None
                    else None
                ),
                "avg_edge": (
                    float(row["avg_edge"]) if row["avg_edge"] is not None else None
                ),
                "avg_expected_value": (
                    float(row["avg_expected_value"])
                    if row["avg_expected_value"] is not None
                    else None
                ),
                "settled_count": int(row["settled_count"]),
                "unsettled_count": int(row["unsettled_count"]),
                "empty_state": (
                    "no_settled_calibration_outcomes"
                    if row["observed_win_rate"] is None
                    else None
                ),
            }
        )

    by_sport = [
        {
            "sport": sport or "ALL",
            "bet_count": total_predictions,
            "win_rate": 0.0,
            "avg_edge": round(total_edge / edge_count, 4) if edge_count else 0.0,
            "roi": 0.0,
        }
    ]
    return {
        "bets": [],
        "buckets": buckets,
        "by_sport": by_sport if total_predictions else [],
        "empty_state": (
            None if total_predictions else _empty_state("no_calibration_predictions")
        ),
        "sport_validation_state": sport_validation_state,
        "settled_empty_state": (
            _empty_state("no_settled_calibration_outcomes")
            if total_settled == 0
            else None
        ),
    }


@st.cache_data(ttl=TTL_STANDARD)
def get_elo_history(team: str, sport: str, days: int = 30) -> pd.DataFrame:
    """Return the current governed ranking point as legacy history data."""

    df = _fetch_read_model(
        RANKINGS_VIEW,
        where="sport = :sport AND entity_name = :team",
        params={"sport": sport.upper(), "team": team},
        order_by="valid_from ASC",
    )
    mapped = pd.DataFrame(
        [
            {
                "date": _iso_or_none(row["valid_from"]),
                "team": row["entity_name"],
                "rating": row["rating"],
            }
            for _, row in df.iterrows()
        ]
    )
    return _attach_empty_state(mapped, "no_rankings")


@st.cache_data(ttl=TTL_STANDARD)
def get_data_quality_report() -> dict[str, Any]:
    """Return dashboard health from the governed data-quality read model."""

    df = _fetch_read_model(DATA_QUALITY_VIEW, order_by="relation_type, relation_name")
    if df.empty:
        raise _contract_error(
            DATA_QUALITY_VIEW,
            "the data-quality read model returned zero rows",
        )

    score_by_status = {"pass": 100, "warn": 60, "fail": 0}
    sport_reports = []
    checks = []
    total_score = 0
    for _, row in df.iterrows():
        status = str(row["status"])
        score = score_by_status[status]
        total_score += score
        safe_message = _sanitize_provider_message(row["message"])
        issue = None if status == "pass" else safe_message
        checks.append(
            {
                "check_name": str(row["check_name"]),
                "relation_name": str(row["relation_name"]),
                "relation_type": str(row["relation_type"]),
                "status": status,
                "row_count": _to_json_value(row["row_count"]),
                "freshness_timestamp": _iso_or_none(row["freshness_timestamp"]),
                "max_allowed_lag_minutes": _to_json_value(
                    row["max_allowed_lag_minutes"]
                ),
                "actual_lag_minutes": _to_json_value(row["actual_lag_minutes"]),
                "message": safe_message,
                "checked_at_utc": _iso_or_none(row["checked_at_utc"]),
            }
        )
        sport_reports.append(
            {
                "sport": row["relation_name"],
                "health_score": score,
                "missing_games": 0,
                "stale_elo": 0,
                "odds_freshness_minutes": (
                    row["actual_lag_minutes"]
                    if row["actual_lag_minutes"] is not None
                    else "N/A"
                ),
                "last_game_date": _iso_or_none(row["freshness_timestamp"]) or "N/A",
                "last_dag_run": _iso_or_none(row["checked_at_utc"]) or "N/A",
                "issues": [issue] if issue else [],
                "check_name": row["check_name"],
                "relation_type": row["relation_type"],
                "row_count": row["row_count"],
            }
        )

    return {
        "overall_health": int(total_score // len(sport_reports)),
        "sports": sport_reports,
        "checks": checks,
        "empty_state": None,
    }


@st.cache_data(ttl=TTL_STANDARD)
def get_portfolio_snapshots(hours: int = 168) -> pd.DataFrame:
    """Return governed portfolio value points in the legacy chart shape."""

    df = _fetch_read_model(
        PORTFOLIO_VIEW,
        order_by="snapshot_hour_utc ASC",
        limit=hours,
    )
    mapped = pd.DataFrame(
        [
            {
                **_record_from_series(row),
                "timestamp": _iso_or_none(row["snapshot_hour_utc"]),
                "portfolio_value": row["portfolio_value_dollars"],
            }
            for _, row in df.iterrows()
        ]
    )
    return _attach_empty_state(mapped, "no_portfolio_snapshots")


def bust_cache() -> None:
    """Clear all dashboard data caches."""

    for cached_function in (
        get_portfolio_summary,
        get_placed_bets,
        get_bet_detail,
        get_current_elo_ratings,
        get_live_markets,
        get_tomorrow_tennis_predictions,
        get_tennis_model_health,
        get_mlb_model_health,
        get_today_games,
        get_upcoming_games,
        get_bet_recommendations,
        get_calibration_data,
        get_elo_history,
        get_data_quality_report,
        get_portfolio_snapshots,
        _get_ensemble_adapter,
    ):
        cached_function.clear()
