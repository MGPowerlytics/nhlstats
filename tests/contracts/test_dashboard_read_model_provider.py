"""Provider contract tests for migrated dashboard PostgreSQL read models.

These tests validate the actual ``dashboard_*_v1`` views produced by the
governed migration chain. They intentionally seed source tables, then query
the migrated views so stale source-column references and schema drift fail at
the provider boundary instead of being hidden by dashboard mocks.
"""

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
    EXPECTED_DASHBOARD_SOURCE_TABLES,
    EXPECTED_DASHBOARD_VIEWS,
    SchemaMigrationRunner,
)
from tests.contracts.fixtures.dashboard_seed_samples import (  # noqa: E402
    build_dashboard_source_seed_payload,
    seed_dashboard_source_rows,
)


SCHEMAS_DIR = Path(__file__).parent / "schemas"
EMPTY_STATE_VIEWS = tuple(
    view for view in EXPECTED_DASHBOARD_VIEWS if view != "dashboard_data_quality_v1"
)


class _ConnectionDB:
    """DBManager-compatible wrapper that keeps fixture writes transactional."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def execute(self, query: str, params: dict[str, Any] | None = None) -> Any:
        """Execute a SQL statement on the existing test transaction."""

        return self.connection.execute(text(query), params or {})


def _build_live_connection_string() -> str:
    """Build the direct PostgreSQL connection string used by provider tests."""

    user = os.getenv("POSTGRES_USER", "airflow")
    password = os.getenv("POSTGRES_PASSWORD", "airflow")
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "airflow")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"


def _postgres_available() -> bool:
    """Return True when a live PostgreSQL database is reachable."""

    try:
        engine = create_engine(_build_live_connection_string())
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


_LIVE_POSTGRES_AVAILABLE = _postgres_available()
if not _LIVE_POSTGRES_AVAILABLE and os.environ.get("DASHBOARD_REQUIRE_LIVE_POSTGRES"):
    raise RuntimeError(
        "DASHBOARD_REQUIRE_LIVE_POSTGRES=1 but the configured PostgreSQL test "
        "database is unavailable; provider tests must fail instead of skipping."
    )

requires_live_postgres = pytest.mark.skipif(
    not _LIVE_POSTGRES_AVAILABLE,
    reason=(
        "Requires live PostgreSQL; provider tests query migrated dashboard views "
        "and are skipped when the repository integration database is unavailable."
    ),
)
pytestmark = [pytest.mark.integration, requires_live_postgres]


@pytest.fixture(scope="module")
def dashboard_schemas() -> dict[str, dict[str, Any]]:
    """Load canonical dashboard row schemas."""

    return {
        view: json.loads(
            (SCHEMAS_DIR / f"{view}.schema.json").read_text(encoding="utf-8")
        )
        for view in EXPECTED_DASHBOARD_VIEWS
    }


@pytest.fixture(scope="module")
def migrated_dashboard_db() -> Any:
    """Apply the governed migration chain in an isolated PostgreSQL schema."""

    base_connection_string = _build_live_connection_string()
    schema_name = f"dashboard_provider_{uuid.uuid4().hex}"
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
def dashboard_conn(migrated_dashboard_db: Any) -> Any:
    """Provide a transaction-scoped connection in the migrated test schema."""

    with migrated_dashboard_db.engine.connect() as conn:
        transaction = conn.begin()
        try:
            yield conn
        finally:
            transaction.rollback()


def _json_ready(value: Any) -> Any:
    """Convert database scalar values to JSON Schema-compatible values."""

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _row_to_payload(row: Any) -> dict[str, Any]:
    """Convert a SQLAlchemy row to a JSON-compatible dictionary."""

    return {key: _json_ready(value) for key, value in row._mapping.items()}


def _fetch_view_rows(connection: Any, view_name: str) -> list[dict[str, Any]]:
    """Fetch all rows from a migrated dashboard read-model view."""

    result = connection.execute(text(f"SELECT * FROM {view_name}"))
    return [_row_to_payload(row) for row in result.fetchall()]


def _fetch_view_columns(connection: Any, view_name: str) -> list[str]:
    """Return migrated provider columns in view order."""

    result = connection.execute(text(f"SELECT * FROM {view_name} LIMIT 0"))
    return list(result.keys())


def _validate_rows(rows: list[dict[str, Any]], schema: dict[str, Any]) -> None:
    """Validate actual provider rows against a canonical JSON Schema."""

    validator = Draft202012Validator(schema)
    for row in rows:
        validator.validate(row)


class TestDashboardReadModelProvider:
    """Provider tests for the actual migrated dashboard read-model views."""

    @pytest.mark.parametrize("view_name", EXPECTED_DASHBOARD_VIEWS)
    def test_migrated_view_columns_match_canonical_schema_exactly(
        self,
        dashboard_conn: Any,
        dashboard_schemas: dict[str, dict[str, Any]],
        view_name: str,
    ) -> None:
        """Views fail on extra columns, missing columns, or stale aliases."""

        assert _fetch_view_columns(dashboard_conn, view_name) == list(
            dashboard_schemas[view_name]["properties"]
        )

    def test_migration_governance_verifies_dashboard_views_and_sources(
        self, migrated_dashboard_db: Any
    ) -> None:
        """Missing dashboard views or source relations fail governance."""

        runner = SchemaMigrationRunner(migrated_dashboard_db)
        status = runner.verify()
        assert status["missing_tables"] == []
        assert status["missing_views"] == []
        assert status["wrong_relation_types"] == []

        relation_names = {
            relation["name"]: relation["expected_type"]
            for relation in status["expected_relations"]
        }
        for table_name in EXPECTED_DASHBOARD_SOURCE_TABLES:
            assert relation_names[table_name] == "table"
        for view_name in EXPECTED_DASHBOARD_VIEWS:
            assert relation_names[view_name] == "view"

    @pytest.mark.parametrize("view_name", EXPECTED_DASHBOARD_VIEWS)
    def test_seeded_migrated_views_return_contract_compliant_rows(
        self,
        dashboard_conn: Any,
        dashboard_schemas: dict[str, dict[str, Any]],
        view_name: str,
    ) -> None:
        """Seed source tables and validate each actual provider view row."""

        seed_dashboard_source_rows(
            _ConnectionDB(dashboard_conn), build_dashboard_source_seed_payload()
        )

        rows = _fetch_view_rows(dashboard_conn, view_name)
        assert rows, f"{view_name} should return seeded provider rows"
        _validate_rows(rows, dashboard_schemas[view_name])

    @pytest.mark.parametrize("view_name", EMPTY_STATE_VIEWS)
    def test_empty_source_tables_return_zero_rows_for_page_views(
        self, dashboard_conn: Any, view_name: str
    ) -> None:
        """Page read models expose true zero-row empty states without mock rows."""

        rows = _fetch_view_rows(dashboard_conn, view_name)
        assert rows == []

    def test_empty_source_tables_keep_data_quality_contract_compliant(
        self,
        dashboard_conn: Any,
        dashboard_schemas: dict[str, dict[str, Any]],
    ) -> None:
        """Data-quality view reports empty sources instead of becoming empty."""

        rows = _fetch_view_rows(dashboard_conn, "dashboard_data_quality_v1")
        assert rows
        _validate_rows(rows, dashboard_schemas["dashboard_data_quality_v1"])

        source_checks = [
            row
            for row in rows
            if row["relation_name"] in EXPECTED_DASHBOARD_SOURCE_TABLES
        ]
        assert source_checks
        assert {row["status"] for row in source_checks} == {"warn"}
        assert {row["row_count"] for row in source_checks} == {0}

    @pytest.mark.parametrize("view_name", EXPECTED_DASHBOARD_VIEWS)
    def test_selecting_migrated_view_detects_stale_source_references(
        self, dashboard_conn: Any, view_name: str
    ) -> None:
        """A direct provider query fails if a migrated view references stale sources."""

        dashboard_conn.execute(text(f"SELECT COUNT(*) FROM {view_name}")).scalar_one()
