"""Regression tests for governed MLB predictive-modeling schema assets."""

from __future__ import annotations

from pathlib import Path

from plugins.schema_migrations import EXPECTED_STATS_TABLES


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "stats_schema"
    / "V010__add_mlb_predictive_modeling_tables.sql"
)

EXPECTED_MLB_PREDICTIVE_TABLES = (
    "mlb_player_game_batting_stats",
    "mlb_player_game_pitching_stats",
    "mlb_pitch_level_features",
    "mlb_player_rolling_features",
    "mlb_environment_features",
    "mlb_travel_features",
    "mlb_matchup_features",
    "mlb_market_signals",
    "mlb_model_predictions",
    "mlb_prop_predictions",
)

EXPECTED_MLB_ODDS_TABLES = ("mlb_odds_snapshots",)


def test_mlb_predictive_tables_are_in_governed_expected_relations() -> None:
    """Schema verification must include the new MLB predictive-modeling tables."""
    for table_name in EXPECTED_MLB_PREDICTIVE_TABLES:
        assert table_name in EXPECTED_STATS_TABLES
    for table_name in EXPECTED_MLB_ODDS_TABLES:
        assert table_name in EXPECTED_STATS_TABLES


def test_v010_migration_creates_all_mlb_predictive_tables() -> None:
    """The V010 migration is the single checked-in DDL owner for these tables."""
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    for table_name in EXPECTED_MLB_PREDICTIVE_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in migration_sql


def test_v011_migration_creates_dashboard_mlb_model_health_view() -> None:
    """MLB model-health dashboard view is governed by a checked-in migration."""
    migration_sql = (
        MIGRATION_PATH.parent / "V011__create_dashboard_mlb_model_health_view.sql"
    ).read_text(encoding="utf-8")

    assert "CREATE VIEW dashboard_mlb_model_health_v1 AS" in migration_sql


def test_v012_migration_creates_mlb_odds_snapshots() -> None:
    """MLB odds snapshot history is governed by a checked-in migration."""
    migration_sql = (
        MIGRATION_PATH.parent / "V012__create_mlb_odds_snapshots.sql"
    ).read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS mlb_odds_snapshots" in migration_sql
    assert "UNIQUE (" in migration_sql
    assert "snapshot_type VARCHAR NOT NULL" in migration_sql
