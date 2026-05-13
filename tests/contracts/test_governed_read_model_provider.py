"""Provider contract tests for migrated governed approval read models."""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).parents[2] / "plugins"))

from plugins.db_manager import DBManager
from plugins.schema_migrations import (  # noqa: E402
    EXPECTED_GOVERNED_READ_MODEL_VIEWS,
    SchemaMigrationRunner,
)
from tests.contracts.fixtures.dashboard_seed_samples import (  # noqa: E402
    build_dashboard_source_seed_payload,
    seed_dashboard_source_rows,
)
from plugins.sport_validation import publish_all_sport_validation_states  # noqa: E402


SCHEMAS_DIR = Path(__file__).parent / "schemas"
NON_BASELINE_VIEWS = tuple(
    view
    for view in EXPECTED_GOVERNED_READ_MODEL_VIEWS
    if view != "sport_validation_state_v1"
)


class _ConnectionDB:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def execute(self, query: str, params: dict[str, Any] | None = None) -> Any:
        return self.connection.execute(text(query), params or {})


def _build_live_connection_string() -> str:
    user = os.getenv("POSTGRES_USER", "airflow")
    password = os.getenv("POSTGRES_PASSWORD", "airflow")
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "airflow")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"


def _postgres_available() -> bool:
    try:
        engine = create_engine(_build_live_connection_string())
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


_LIVE_POSTGRES_AVAILABLE = _postgres_available()
requires_live_postgres = pytest.mark.skipif(
    not _LIVE_POSTGRES_AVAILABLE,
    reason="Requires live PostgreSQL for migrated governed read-model provider checks.",
)
pytestmark = [pytest.mark.integration, requires_live_postgres]


@pytest.fixture(scope="module")
def governed_schemas() -> dict[str, dict[str, Any]]:
    return {
        view: json.loads(
            (SCHEMAS_DIR / f"{view}.schema.json").read_text(encoding="utf-8")
        )
        for view in EXPECTED_GOVERNED_READ_MODEL_VIEWS
    }


@pytest.fixture(scope="module")
def migrated_governed_db() -> Any:
    base_connection_string = _build_live_connection_string()
    schema_name = f"governed_provider_{uuid.uuid4().hex}"
    admin_engine = create_engine(base_connection_string)

    with admin_engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema_name}"))

    db = DBManager(connection_string=base_connection_string, schema=schema_name)
    try:
        runner = SchemaMigrationRunner(db)
        runner.apply()
        runner.assert_verified()
        yield db
    finally:
        db.engine.dispose()
        with admin_engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
        admin_engine.dispose()


@pytest.fixture()
def governed_conn(migrated_governed_db: Any) -> Any:
    with migrated_governed_db.engine.connect() as conn:
        transaction = conn.begin()
        try:
            yield conn
        finally:
            transaction.rollback()


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _fetch_rows(connection: Any, view_name: str) -> list[dict[str, Any]]:
    result = connection.execute(text(f"SELECT * FROM {view_name}"))
    return [
        {key: _json_ready(value) for key, value in row._mapping.items()}
        for row in result.fetchall()
    ]


def _fetch_columns(connection: Any, view_name: str) -> list[str]:
    result = connection.execute(text(f"SELECT * FROM {view_name} LIMIT 0"))
    return list(result.keys())


def _canonical_validation_projection() -> dict[str, dict[str, Any]]:
    return {
        state["sport"]: {
            "evidence_state": state["validation_status"],
            "contamination_flag": bool(state["approval_blockers"]["contamination"]),
            "contamination_reason": (
                ";".join(state["approval_blockers"]["contamination"])
                if state["approval_blockers"]["contamination"]
                else None
            ),
            "runtime_consumer": state["artifact_provenance"]["runtime_consumer"],
            "artifact_id": state["artifact_provenance"]["artifact_id"],
            "artifact_version": (
                state["artifact_provenance"]["artifact_version"]
                or "approval_evidence_unavailable"
            ),
            "artifact_available_flag": (
                state["artifact_provenance"]["artifact_id"] is not None
            ),
            "placed_bet_only_flag": state["cohort_provenance"]["placed_bet_only"],
            "synthetic_identity_flag": state["cohort_provenance"][
                "includes_synthetic_tickers"
            ],
            "backfill_flag": state["cohort_provenance"][
                "includes_backfilled_recommendations"
            ],
        }
        for state in publish_all_sport_validation_states()
    }


class TestGovernedReadModelProvider:
    @pytest.mark.parametrize("view_name", EXPECTED_GOVERNED_READ_MODEL_VIEWS)
    def test_migrated_view_columns_match_schema_exactly(
        self,
        governed_conn: Any,
        governed_schemas: dict[str, dict[str, Any]],
        view_name: str,
    ) -> None:
        assert _fetch_columns(governed_conn, view_name) == list(
            governed_schemas[view_name]["properties"]
        )

    @pytest.mark.parametrize("view_name", EXPECTED_GOVERNED_READ_MODEL_VIEWS)
    def test_seeded_views_return_contract_compliant_rows(
        self,
        governed_conn: Any,
        governed_schemas: dict[str, dict[str, Any]],
        view_name: str,
    ) -> None:
        seed_dashboard_source_rows(
            _ConnectionDB(governed_conn), build_dashboard_source_seed_payload()
        )

        rows = _fetch_rows(governed_conn, view_name)
        assert rows, f"{view_name} should return provider rows"

        validator = Draft202012Validator(governed_schemas[view_name])
        for row in rows:
            validator.validate(row)

    @pytest.mark.parametrize("view_name", NON_BASELINE_VIEWS)
    def test_empty_source_tables_return_zero_rows_for_nonbaseline_views(
        self, governed_conn: Any, view_name: str
    ) -> None:
        assert _fetch_rows(governed_conn, view_name) == []

    def test_validation_state_view_exists_without_runtime_source_rows(
        self, governed_conn: Any, governed_schemas: dict[str, dict[str, Any]]
    ) -> None:
        rows = _fetch_rows(governed_conn, "sport_validation_state_v1")
        assert rows

        validator = Draft202012Validator(governed_schemas["sport_validation_state_v1"])
        for row in rows:
            validator.validate(row)

    def test_validation_state_view_publishes_match_winner_for_soccer_sports(
        self, governed_conn: Any
    ) -> None:
        rows = _fetch_rows(governed_conn, "sport_validation_state_v1")
        market_type_by_sport = {row["sport"]: row["market_type"] for row in rows}

        assert market_type_by_sport["EPL"] == "match_winner"
        assert market_type_by_sport["LIGUE1"] == "match_winner"

    def test_validation_state_view_matches_canonical_publication_contamination_and_provenance(
        self, governed_conn: Any
    ) -> None:
        rows = _fetch_rows(governed_conn, "sport_validation_state_v1")
        rows_by_sport = {row["sport"]: row for row in rows}

        for sport, projection in _canonical_validation_projection().items():
            row = rows_by_sport[sport]
            for field, expected in projection.items():
                assert row[field] == expected

    def test_execution_link_view_uses_governed_market_linkage_not_bet_id_parity(
        self, governed_conn: Any
    ) -> None:
        seed_dashboard_source_rows(
            _ConnectionDB(governed_conn),
            build_dashboard_source_seed_payload(
                placed_bets__0__bet_id="DASHBOARD-SEED-NHL-ORDER-20260503-NYR-BOS-HOME"
            ),
        )

        rows = _fetch_rows(governed_conn, "governed_recommendation_execution_link_v1")
        linked_row = next(
            row
            for row in rows
            if row["placed_bet_id"] == "DASHBOARD-SEED-NHL-ORDER-20260503-NYR-BOS-HOME"
        )

        assert (
            linked_row["recommendation_id"]
            == "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME"
        )
        assert linked_row["linkage_status"] == "linked"
        assert (
            linked_row["linkage_basis"]
            == "market_ticker_selection_key_canonical_game_id"
        )
        assert linked_row["linked_market_ticker"] == "KXNHL-26MAY03NYRBOS-NYR"
        assert linked_row["linked_selection_key"] == "New York Rangers"
        assert linked_row["placed_bet_id"] != linked_row["recommendation_id"]

    def test_governed_views_surface_quote_lineage_placeholders(
        self, governed_conn: Any
    ) -> None:
        seed_dashboard_source_rows(
            _ConnectionDB(governed_conn), build_dashboard_source_seed_payload()
        )

        evidence_rows = _fetch_rows(governed_conn, "governed_evidence_record_v1")
        execution_rows = _fetch_rows(
            governed_conn, "governed_recommendation_execution_link_v1"
        )

        evidence_row = next(
            row
            for row in evidence_rows
            if row["recommendation_id"] == "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME"
        )
        execution_row = next(
            row
            for row in execution_rows
            if row["placed_bet_id"] == "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME"
        )

        assert evidence_row["quote_source_system"] == "bet_recommendation_payload"
        assert evidence_row["quote_bookmaker"] == "Kalshi"
        assert (
            evidence_row["quote_payload_ref"]
            == "DASHBOARD-SEED-NHL-20260503-NYR-BOS-KALSHI-HOME"
        )
        assert evidence_row["quote_lineage_status"] == "linked_market_quote"
        assert evidence_row["quote_price_cents"] == 54
        assert evidence_row["quote_price_role"] == "executable"
        assert evidence_row["quote_freshness_result"] == "fresh"
        assert evidence_row["quote_fallback_status"] == "direct_quote"
        assert execution_row["entry_quote_source_system"] == "kalshi_market_details"
        assert execution_row["entry_quote_bookmaker"] == "Kalshi"
        assert (
            execution_row["entry_quote_payload_ref"]
            == "DASHBOARD-SEED-NHL-20260503-NYR-BOS-KALSHI-HOME"
        )
        assert execution_row["entry_quote_lineage_status"] == "linked_market_quote"
        assert execution_row["entry_price_cents"] == 54
        assert execution_row["entry_quote_freshness_result"] == "fresh"
        assert execution_row["entry_quote_fallback_status"] == "direct_market_quote"

    def test_portfolio_risk_view_separates_resting_and_executed_unsettled_exposure(
        self, governed_conn: Any
    ) -> None:
        payload = build_dashboard_source_seed_payload(
            placed_bets__1__status="filled",
            placed_bets__1__cost_dollars=12.0,
            placed_bets__1__payout_dollars=19.5,
            placed_bets__1__settled_date=None,
        )
        payload["portfolio_value_snapshots"].append(
            {
                "snapshot_hour_utc": "2026-05-03T13:00:00",
                "balance_dollars": 1360.25,
                "portfolio_value_dollars": 1600.0,
                "cumulative_deposits_dollars": 1000.0,
                "created_at_utc": "2026-05-03T13:01:00",
            }
        )
        seed_dashboard_source_rows(_ConnectionDB(governed_conn), payload)

        rows = _fetch_rows(governed_conn, "governed_portfolio_risk_state_v1")
        nhl_row = next(row for row in rows if row["sport"] == "NHL")

        assert nhl_row["resting_order_exposure_amount"] == 10.0
        assert nhl_row["resting_order_count"] == 1
        assert nhl_row["executed_unsettled_exposure_amount"] == 12.0
        assert nhl_row["executed_unsettled_count"] == 1
        assert nhl_row["open_exposure_amount"] == 22.0
        assert nhl_row["exposure_state"] == "mixed_open_exposure"
        assert nhl_row["same_event_exposure_amount"] == 12.0
        assert nhl_row["same_side_exposure_amount"] == 12.0
        assert nhl_row["remaining_daily_risk_budget_dollars"] == 346.9375
        assert nhl_row["peak_portfolio_value_dollars"] == 1600.0
        assert nhl_row["current_portfolio_value_dollars"] == 1475.75
        assert nhl_row["drawdown_amount_dollars"] == 124.25
        assert nhl_row["drawdown_state"] == "drawdown_active"
        assert nhl_row["risk_of_ruin_state"] == "capital_available"
        assert nhl_row["portfolio_guardrail_state"] == "eligible"
        assert nhl_row["portfolio_guardrail_reason_code"] is None
        assert nhl_row["portfolio_guardrail_reason_detail"] is None
        assert nhl_row["existing_position_state"] == "mixed_open_exposure"
        assert nhl_row["rejection_reason_code"] == "missing_evidence"
        assert nhl_row["rejection_reason_detail"] == (
            "NHL remains blocked until governed approval evidence exists."
        )

    def test_portfolio_risk_view_blocks_when_latest_snapshot_enables_drawdown_guardrail(
        self, governed_conn: Any
    ) -> None:
        payload = build_dashboard_source_seed_payload(
            portfolio_value_snapshots__0__drawdown_gate_active=True,
            portfolio_value_snapshots__0__drawdown_gate_reason_code="drawdown_gate_blocked",
            portfolio_value_snapshots__0__drawdown_gate_reason_detail=(
                "Explicit governed drawdown regime is active for new approvals."
            ),
        )
        payload["portfolio_value_snapshots"].append(
            {
                "snapshot_hour_utc": "2026-05-03T13:00:00",
                "balance_dollars": 1360.25,
                "portfolio_value_dollars": 1600.0,
                "cumulative_deposits_dollars": 1000.0,
                "drawdown_gate_active": False,
                "drawdown_gate_reason_code": None,
                "drawdown_gate_reason_detail": None,
                "created_at_utc": "2026-05-03T13:01:00",
            }
        )
        seed_dashboard_source_rows(_ConnectionDB(governed_conn), payload)

        rows = _fetch_rows(governed_conn, "governed_portfolio_risk_state_v1")
        nhl_row = next(row for row in rows if row["sport"] == "NHL")

        assert nhl_row["drawdown_state"] == "drawdown_active"
        assert nhl_row["portfolio_guardrail_state"] == "blocked_drawdown"
        assert nhl_row["portfolio_guardrail_reason_code"] == "drawdown_gate_blocked"
        assert nhl_row["portfolio_guardrail_reason_detail"] == (
            "Explicit governed drawdown regime is active for new approvals."
        )
        assert nhl_row["rejection_reason_code"] == "drawdown_gate_blocked"
        assert nhl_row["rejection_reason_detail"] == (
            "Explicit governed drawdown regime is active for new approvals."
        )

    def test_clv_view_surfaces_selected_close_governance_fields(
        self, governed_conn: Any
    ) -> None:
        seed_dashboard_source_rows(
            _ConnectionDB(governed_conn), build_dashboard_source_seed_payload()
        )

        rows = _fetch_rows(governed_conn, "governed_clv_evidence_envelope_v1")
        clv_row = next(
            row
            for row in rows
            if row["placed_bet_id"] == "DASHBOARD-SEED-NHL-20260501-CAR-NJD-HOME"
        )

        assert clv_row["entry_price_role"] == "executable"
        assert clv_row["close_price_role"] == "close"
        assert clv_row["close_freshness_result"] == "fresh"
        assert clv_row["selected_close_rule"] == "latest_admissible_pregame_quote"
        assert clv_row["selected_close_provenance"] is not None
        assert clv_row["clv_evidence_tier"] == "partially_evidenced"
        assert (
            clv_row["recommendation_id"] == "DASHBOARD-SEED-NHL-20260501-CAR-NJD-HOME"
        )
        assert clv_row["entry_price_cents"] == 54
        assert clv_row["entry_freshness_result"] == "fresh"
        assert (
            clv_row["closing_quote_payload_ref"]
            == "DASHBOARD-SEED-NHL-20260501-CAR-NJD-SBR-HOME"
        )
        assert clv_row["close_fallback_status"] == "latest_admissible_pregame_quote"

    @pytest.mark.parametrize("sport", ("MLB", "TENNIS", "EPL", "LIGUE1"))
    def test_downstream_views_reuse_governed_validation_contamination_state(
        self, governed_conn: Any, sport: str
    ) -> None:
        seed_dashboard_source_rows(
            _ConnectionDB(governed_conn),
            build_dashboard_source_seed_payload(
                unified_games__0__sport=sport,
                bet_recommendations__0__sport=sport,
                placed_bets__0__sport=sport,
                placed_bets__1__sport=sport,
            ),
        )

        validation_row = next(
            row
            for row in _fetch_rows(governed_conn, "sport_validation_state_v1")
            if row["sport"] == sport
        )
        evidence_row = next(
            row
            for row in _fetch_rows(governed_conn, "governed_evidence_record_v1")
            if row["sport"] == sport
        )
        execution_row = next(
            row
            for row in _fetch_rows(
                governed_conn, "governed_recommendation_execution_link_v1"
            )
            if row["sport"] == sport
        )
        risk_row = next(
            row
            for row in _fetch_rows(governed_conn, "governed_portfolio_risk_state_v1")
            if row["sport"] == sport
        )

        for row in (evidence_row, execution_row, risk_row):
            assert row["evidence_state"] == validation_row["evidence_state"]
            assert row["governance_status"] == validation_row["governance_status"]
            assert (
                row["descriptive_only_flag"] == validation_row["descriptive_only_flag"]
            )
            assert row["contamination_flag"] == validation_row["contamination_flag"]
            assert row["contamination_reason"] == validation_row["contamination_reason"]
            assert (
                row["excluded_from_approval_flag"]
                == validation_row["excluded_from_approval_flag"]
            )
