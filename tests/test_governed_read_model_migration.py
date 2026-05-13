"""Regression tests for governed approval read-model migration assets."""

from __future__ import annotations

from pathlib import Path

from plugins.schema_migrations import EXPECTED_GOVERNED_READ_MODEL_VIEWS


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "stats_schema"
    / "V014__create_governed_approval_read_models.sql"
)
PRICING_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "stats_schema"
    / "V015__harden_pricing_clv_governance.sql"
)
EXECUTION_LINEAGE_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "stats_schema"
    / "V016__persist_execution_lineage_governance.sql"
)
PORTFOLIO_RISK_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "stats_schema"
    / "V017__harden_portfolio_risk_read_model.sql"
)
EXPLICIT_DRAWDOWN_GUARDRAIL_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "stats_schema"
    / "V018__add_explicit_drawdown_guardrail.sql"
)


def test_governed_read_models_are_registered_as_governed_views() -> None:
    expected = {
        "governed_evidence_record_v1",
        "governed_recommendation_execution_link_v1",
        "governed_clv_evidence_envelope_v1",
        "sport_validation_state_v1",
        "governed_portfolio_risk_state_v1",
    }
    assert expected.issubset(set(EXPECTED_GOVERNED_READ_MODEL_VIEWS))


def test_v014_migration_exists_and_preserves_dashboard_v1_boundary() -> None:
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    assert (
        "preserve existing dashboard_*_v1 contracts unchanged this cycle"
        in migration_sql.lower()
    )
    assert "instead of mutating dashboard_*_v1 semantics in place" in migration_sql


def test_v014_migration_creates_expected_governed_read_models() -> None:
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    for view_name in EXPECTED_GOVERNED_READ_MODEL_VIEWS:
        assert f"CREATE VIEW {view_name} AS" in migration_sql


def test_v014_migration_keeps_soccer_market_type_semantics_aligned() -> None:
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    assert migration_sql.count("IN ('TENNIS', 'EPL', 'LIGUE1')") == 5


def test_v014_migration_uses_governed_validation_publication_as_shared_source() -> None:
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    assert (
        "'governed_validation_publication'::VARCHAR AS source_relation" in migration_sql
    )
    assert (
        "'tests/contracts/fixtures/sport_validation_samples.py;plugins/sport_validation.py'::VARCHAR"
        in migration_sql
    )
    assert (
        "(baseline.contamination_reason IS NOT NULL) AS contamination_flag"
        in migration_sql
    )


def test_v014_migration_propagates_validation_contamination_into_downstream_views() -> (
    None
):
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    assert (
        migration_sql.count(
            "validation.contamination_flag AS validation_contamination_flag"
        )
        == 3
    )
    assert (
        migration_sql.count(
            "COALESCE(validation.contamination_flag, FALSE) AS contamination_flag"
        )
        == 1
    )
    assert (
        "CONCAT(br.validation_contamination_reason, ';', br.local_contamination_reason)"
        in migration_sql
    )
    assert (
        "CONCAT(pb.validation_contamination_reason, ';', pb.local_contamination_reason)"
        in migration_sql
    )


def test_v014_migration_avoids_ambiguous_governed_evidence_context_columns() -> None:
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "NULLIF(to_jsonb(br)->>'canonical_game_id', '')" in migration_sql
    assert "mc.canonical_game_id" in migration_sql
    assert "NULLIF(to_jsonb(br)->>'quote_loaded_at', '')::TIMESTAMP" in migration_sql
    assert "NULLIF(to_jsonb(br)->>'quote_bookmaker', '')" in migration_sql
    assert "NULLIF(to_jsonb(br)->>'quote_payload_ref', '')" in migration_sql
    assert "COALESCE(" in migration_sql
    assert "AS resolved_canonical_game_id" in migration_sql
    assert "mc.quote_bookmaker AS linked_quote_bookmaker" in migration_sql
    assert "mc.quote_observed_at AS linked_quote_observed_at" in migration_sql
    assert "mc.quote_loaded_at AS linked_quote_loaded_at" in migration_sql
    assert "mc.quote_payload_ref AS linked_quote_payload_ref" in migration_sql


def test_v015_migration_exists_and_hardens_clv_governance_contract() -> None:
    migration_sql = PRICING_MIGRATION_PATH.read_text(encoding="utf-8")

    assert "DROP VIEW IF EXISTS governed_clv_evidence_envelope_v1;" in migration_sql
    assert "selected_close_provenance" in migration_sql
    assert "close_freshness_result" in migration_sql
    assert "clv_evidence_tier" in migration_sql
    assert "binary_result_placeholder" in migration_sql


def test_v016_migration_persists_execution_and_close_lineage() -> None:
    migration_sql = EXECUTION_LINEAGE_MIGRATION_PATH.read_text(encoding="utf-8")

    assert "entry_quote_fallback_status" in migration_sql
    assert "entry_quote_freshness_result" in migration_sql
    assert "close_quote_payload_ref" in migration_sql
    assert "selected_close_provenance" in migration_sql
    assert "recommendation_linkage_basis" in migration_sql
    assert "resolved_canonical_game_id" in migration_sql
    assert "computed_close_freshness_result" in migration_sql


def test_v017_migration_keeps_below_peak_drawdown_reporting_only_without_explicit_regime() -> (
    None
):
    migration_sql = PORTFOLIO_RISK_MIGRATION_PATH.read_text(encoding="utf-8")

    assert (
        "WHEN COALESCE(latest_snapshot.portfolio_value_dollars, 0.0) < COALESCE(peak_snapshot.peak_portfolio_value_dollars, 0.0)"
        in migration_sql
    )
    assert "THEN 'drawdown_active'" in migration_sql
    assert (
        "Current portfolio value remains below the governed high-water mark."
        not in migration_sql
    )
    assert "NULLIF(to_jsonb(pb)->>'canonical_game_id', '')" in migration_sql
    assert "NULLIF(to_jsonb(pb)->>'outcome_name', '')" in migration_sql


def test_v018_migration_adds_explicit_snapshot_driven_drawdown_guardrail() -> None:
    migration_sql = EXPLICIT_DRAWDOWN_GUARDRAIL_MIGRATION_PATH.read_text(
        encoding="utf-8"
    )

    assert (
        "ADD COLUMN IF NOT EXISTS drawdown_gate_active BOOLEAN DEFAULT FALSE"
        in migration_sql
    )
    assert "ADD COLUMN IF NOT EXISTS drawdown_gate_reason_code VARCHAR" in migration_sql
    assert (
        "ADD COLUMN IF NOT EXISTS drawdown_gate_reason_detail VARCHAR" in migration_sql
    )
    assert "THEN 'blocked_drawdown'" in migration_sql
    assert "'drawdown_gate_blocked'" in migration_sql
    assert "COALESCE(latest_snapshot.drawdown_gate_active, FALSE)" in migration_sql
    assert (
        "Explicit governed drawdown regime is active for new approvals."
        in migration_sql
    )
