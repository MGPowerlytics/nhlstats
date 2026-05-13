"""Regression tests for governed tennis model-health schema assets."""

from __future__ import annotations

from pathlib import Path

from plugins.schema_migrations import EXPECTED_DASHBOARD_VIEWS, EXPECTED_STATS_TABLES


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "stats_schema"
    / "V013__add_tennis_model_evaluation_dashboard_view.sql"
)


def test_tennis_model_health_table_is_governed_relation() -> None:
    """Schema verification must include the tennis model-evaluation table."""
    assert "tennis_model_evaluations" in EXPECTED_STATS_TABLES


def test_v013_migration_creates_tennis_model_health_assets() -> None:
    """The checked-in migration owns both the source table and dashboard view."""
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS tennis_model_evaluations" in migration_sql
    assert "CREATE VIEW dashboard_tennis_model_health_v1 AS" in migration_sql


def test_tennis_model_health_view_is_governed_dashboard_view() -> None:
    """Dashboard governance includes the tennis model-health read model."""
    assert "dashboard_tennis_model_health_v1" in EXPECTED_DASHBOARD_VIEWS
