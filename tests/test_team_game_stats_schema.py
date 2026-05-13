"""
Tests for team_game_stats schema definitions.

Validates that:
- database_schema_manager declares team_game_stats with correct PK/FK
- All per-sport extension tables exist with correct PK/FK
- tennis_player_match_stats and bet_reconciliation_audit are declared
- No stats module imports db_loader (legacy dependency)

Marked with @pytest.mark.integration for tests that require a live PostgreSQL
connection. These are skipped automatically when the DB is unavailable.
"""

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup — ensure plugins/ is on the path for direct test invocation
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXTENSION_TABLES = [
    "nba_team_game_stats_ext",
    "nhl_team_game_stats_ext",
    "mlb_team_game_stats_ext",
    "nfl_team_game_stats_ext",
    "soccer_team_game_stats_ext",
    "ncaab_team_game_stats_ext",
    "wncaab_team_game_stats_ext",
]

ALL_STATS_TABLES = [
    "team_game_stats",
    *EXTENSION_TABLES,
    "tennis_player_match_stats",
    "bet_reconciliation_audit",
]

GOVERNED_LEGACY_TABLES = [
    "games",
    "teams",
    "mlb_games",
    "nfl_games",
    "epl_games",
    "ligue1_games",
    "tennis_games",
    "ncaab_games",
    "wncaab_games",
    "unrivaled_games",
    "cba_games",
    "game_odds",
    "diagnostic_results",
    "placed_bets",
]


def _db_available() -> bool:
    """Return True if a PostgreSQL connection can be established."""
    try:
        from db_manager import DBManager

        db = DBManager()
        with db.engine.connect() as conn:
            from sqlalchemy import text

            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _build_live_connection_string() -> str:
    """Build the direct PostgreSQL connection string used by live-db tests."""
    import os

    user = os.getenv("POSTGRES_USER", "airflow")
    password = os.getenv("POSTGRES_PASSWORD", "airflow")
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "airflow")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"


requires_live_db = pytest.mark.skipif(
    not _db_available(),
    reason="Requires live PostgreSQL connection (pytest.mark.integration)",
)
pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def schema_manager():
    """Return a migration runner connected to the live PostgreSQL instance."""
    from sqlalchemy import create_engine
    from db_manager import DBManager
    from plugins.schema_migrations import SchemaMigrationRunner

    conn_str = _build_live_connection_string()

    db = DBManager.__new__(DBManager)
    db.connection_string = conn_str
    db.engine = create_engine(conn_str)
    runner = SchemaMigrationRunner(db)
    runner.apply()
    return runner


@pytest.fixture()
def db_conn(schema_manager):
    """Provide a connection with automatic transaction rollback after each test.

    The rollback ensures stats tables are clean between tests without
    dropping and recreating them.
    """
    from sqlalchemy import text

    engine = schema_manager.db.engine
    with engine.connect() as conn:
        trans = conn.begin_nested()  # SAVEPOINT for rollback isolation
        try:
            yield conn, text
        finally:
            trans.rollback()


# ---------------------------------------------------------------------------
# Task 5a — DatabaseSchemaManager imports and initialises without error
# ---------------------------------------------------------------------------


def test_schema_manager_import() -> None:
    """DatabaseSchemaManager and DBManager import cleanly."""
    from database_schema_manager import DatabaseSchemaManager  # noqa: F401
    from db_manager import DBManager  # noqa: F401


def test_stats_table_definitions_present() -> None:
    """_get_stats_table_definitions returns DDL for all expected tables."""
    from database_schema_manager import DatabaseSchemaManager
    from db_manager import DBManager

    # Use a dummy (non-connecting) manager just to inspect DDL text
    db = DBManager.__new__(DBManager)
    db.engine = None  # type: ignore[assignment]
    mgr = DatabaseSchemaManager.__new__(DatabaseSchemaManager)
    mgr.db = db
    mgr._schema_initialized = False

    ddl_list = mgr._get_stats_table_definitions()
    combined = "\n".join(ddl_list).lower()

    for table in ALL_STATS_TABLES:
        assert table in combined, f"Missing DDL for table: {table}"


def test_team_game_stats_has_primary_key() -> None:
    """team_game_stats DDL declares composite PK (game_id, team)."""
    from database_schema_manager import DatabaseSchemaManager
    from db_manager import DBManager

    db = DBManager.__new__(DBManager)
    db.engine = None  # type: ignore[assignment]
    mgr = DatabaseSchemaManager.__new__(DatabaseSchemaManager)
    mgr.db = db
    mgr._schema_initialized = False

    ddl_list = mgr._get_stats_table_definitions()
    tgs_ddl = next(
        (
            d
            for d in ddl_list
            if "team_game_stats" in d and "ext" not in d and "CREATE TABLE" in d
        ),
        None,
    )
    assert tgs_ddl is not None, "team_game_stats CREATE TABLE not found"
    ddl_lower = tgs_ddl.lower()
    assert "primary key" in ddl_lower
    assert "game_id" in ddl_lower
    assert "team" in ddl_lower
    assert "foreign key" in ddl_lower
    assert "unified_games" in ddl_lower


def test_extension_tables_have_composite_fk() -> None:
    """Each extension table DDL contains a FK back to team_game_stats."""
    from database_schema_manager import DatabaseSchemaManager
    from db_manager import DBManager

    db = DBManager.__new__(DBManager)
    db.engine = None  # type: ignore[assignment]
    mgr = DatabaseSchemaManager.__new__(DatabaseSchemaManager)
    mgr.db = db
    mgr._schema_initialized = False

    ddl_list = mgr._get_stats_table_definitions()

    for ext_table in EXTENSION_TABLES:
        ext_ddl = next(
            (d for d in ddl_list if ext_table in d and "CREATE TABLE" in d),
            None,
        )
        assert ext_ddl is not None, f"CREATE TABLE not found for {ext_table}"
        ddl_lower = ext_ddl.lower()
        assert "primary key" in ddl_lower, f"{ext_table}: missing PRIMARY KEY"
        assert "foreign key" in ddl_lower, f"{ext_table}: missing FOREIGN KEY"
        assert (
            "team_game_stats" in ddl_lower
        ), f"{ext_table}: FK does not reference team_game_stats"


def test_tennis_player_match_stats_ddl() -> None:
    """tennis_player_match_stats DDL has PK (game_id, player_name) and FK to unified_games."""
    from database_schema_manager import DatabaseSchemaManager
    from db_manager import DBManager

    db = DBManager.__new__(DBManager)
    db.engine = None  # type: ignore[assignment]
    mgr = DatabaseSchemaManager.__new__(DatabaseSchemaManager)
    mgr.db = db
    mgr._schema_initialized = False

    ddl_list = mgr._get_stats_table_definitions()
    tpms_ddl = next(
        (
            d
            for d in ddl_list
            if "tennis_player_match_stats" in d and "CREATE TABLE" in d
        ),
        None,
    )
    assert tpms_ddl is not None, "tennis_player_match_stats CREATE TABLE not found"
    ddl_lower = tpms_ddl.lower()
    assert "player_name" in ddl_lower
    assert "primary key" in ddl_lower
    assert "foreign key" in ddl_lower
    assert "unified_games" in ddl_lower


def test_bet_reconciliation_audit_ddl() -> None:
    """bet_reconciliation_audit DDL has SERIAL PK and required audit columns."""
    from database_schema_manager import DatabaseSchemaManager
    from db_manager import DBManager

    db = DBManager.__new__(DBManager)
    db.engine = None  # type: ignore[assignment]
    mgr = DatabaseSchemaManager.__new__(DatabaseSchemaManager)
    mgr.db = db
    mgr._schema_initialized = False

    ddl_list = mgr._get_stats_table_definitions()
    bra_ddl = next(
        (
            d
            for d in ddl_list
            if "bet_reconciliation_audit" in d and "CREATE TABLE" in d
        ),
        None,
    )
    assert bra_ddl is not None, "bet_reconciliation_audit CREATE TABLE not found"
    ddl_lower = bra_ddl.lower()
    for col in ("audit_id", "bet_id", "field_changed", "source", "reconciled_at"):
        assert col in ddl_lower, f"bet_reconciliation_audit: missing column '{col}'"
    assert "serial" in ddl_lower, "audit_id should be SERIAL"


def test_governed_chain_contains_legacy_schema_tables() -> None:
    """Checked-in migrations own the legacy production tables and placed_bets."""
    from db_manager import DBManager
    from plugins.schema_migrations import SchemaMigrationRunner

    db = DBManager.__new__(DBManager)
    db.engine = None  # type: ignore[assignment]
    runner = SchemaMigrationRunner(db)

    combined_sql = "\n".join(
        migration.sql.lower() for migration in runner.discover_migrations()
    )

    for table in GOVERNED_LEGACY_TABLES:
        assert table in combined_sql, f"Missing governed migration for table: {table}"


def test_initialize_schema_uses_governed_chain_for_postgres(monkeypatch) -> None:
    """PostgreSQL initialization must flow through apply+verify, not helper DDL."""
    import database_schema_manager as schema_module

    calls: list[str] = []

    class RunnerStub:
        def __init__(self, db) -> None:
            assert db is fake_db
            calls.append("init")

        def apply(self):
            calls.append("apply")
            return []

        def assert_verified(self):
            calls.append("verify")
            return {}

    class FakeDB:
        class Engine:
            class Dialect:
                name = "postgresql"

            dialect = Dialect()

        engine = Engine()

        def execute(self, _sql: str) -> None:
            raise AssertionError("PostgreSQL schema init should not execute helper DDL")

    fake_db = FakeDB()
    monkeypatch.setattr(schema_module, "SchemaMigrationRunner", RunnerStub)

    mgr = schema_module.DatabaseSchemaManager(fake_db)
    mgr.initialize_schema()

    assert calls == ["init", "apply", "verify"]
    assert mgr.is_schema_initialized() is True


def test_initialize_schema_keeps_local_compatibility_for_sqlite(monkeypatch) -> None:
    """Non-PostgreSQL test/local paths may still materialize compatibility DDL."""
    from database_schema_manager import DatabaseSchemaManager

    executed: list[str] = []

    class FakeDB:
        class Engine:
            class Dialect:
                name = "sqlite"

            dialect = Dialect()

        engine = Engine()

        def execute(self, sql: str) -> None:
            executed.append(sql)

    mgr = DatabaseSchemaManager(FakeDB())
    monkeypatch.setattr(
        mgr,
        "_get_table_definitions",
        lambda: [
            "CREATE TABLE alpha (id INTEGER PRIMARY KEY)",
            "CREATE TABLE beta (id INTEGER PRIMARY KEY)",
        ],
    )

    mgr.initialize_schema()

    assert executed == [
        "CREATE TABLE alpha (id INTEGER PRIMARY KEY)",
        "CREATE TABLE beta (id INTEGER PRIMARY KEY)",
    ]
    assert mgr.is_schema_initialized() is True


def test_governed_chain_defines_dashboard_read_model_views() -> None:
    """Checked-in migrations define all dashboard read-model views and columns."""
    from db_manager import DBManager
    from plugins.schema_migrations import (
        EXPECTED_DASHBOARD_VIEWS,
        SchemaMigrationRunner,
    )

    db = DBManager.__new__(DBManager)
    db.engine = None  # type: ignore[assignment]
    runner = SchemaMigrationRunner(db)

    combined_sql = "\n".join(
        migration.sql.lower() for migration in runner.discover_migrations()
    )

    for dashboard_view in EXPECTED_DASHBOARD_VIEWS:
        assert f"create view {dashboard_view}" in combined_sql

    expected_columns = {
        "dashboard_portfolio_v1": (
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
        ),
        "dashboard_live_markets_v1": (
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
        ),
        "dashboard_rankings_v1": (
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
        ),
        "dashboard_calibration_v1": (
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
        ),
        "dashboard_data_quality_v1": (
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
        ),
        "dashboard_bet_detail_v1": (
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
        ),
        "dashboard_tennis_predictions_v1": (
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
        ),
        "dashboard_tennis_model_health_v1": (
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
        ),
    }
    for columns in expected_columns.values():
        for column in columns:
            assert column in combined_sql

    stale_source_references = (
        "portfolio_value AS",
        "portfolio_value,",
        "placed_at",
        "stake",
    )
    for stale_reference in stale_source_references:
        assert stale_reference.lower() not in combined_sql


def test_migration_runner_fresh_apply_records_ledger(tmp_path: Path) -> None:
    """A fresh migration apply creates tables and ledger rows."""
    from sqlalchemy import create_engine, text
    from db_manager import DBManager
    from plugins.schema_migrations import SchemaMigrationRunner

    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    (migration_dir / "V001__create_alpha.sql").write_text(
        "CREATE TABLE IF NOT EXISTS alpha (id INTEGER PRIMARY KEY, value TEXT);",
        encoding="utf-8",
    )
    (migration_dir / "V002__create_beta.sql").write_text(
        "CREATE TABLE IF NOT EXISTS beta (id INTEGER PRIMARY KEY, alpha_id INTEGER);",
        encoding="utf-8",
    )

    db_file = tmp_path / "migration_runner.sqlite"
    db = DBManager.__new__(DBManager)
    db.connection_string = f"sqlite:///{db_file}"
    db.engine = create_engine(db.connection_string)

    runner = SchemaMigrationRunner(
        db=db,
        migrations_dir=migration_dir,
        expected_tables=("schema_migrations", "alpha", "beta"),
    )

    applied = runner.apply()
    status = runner.verify()

    assert [migration.version for migration in applied] == ["V001", "V002"]
    assert status["missing_versions"] == []
    assert status["missing_tables"] == []

    with db.engine.connect() as conn:
        rows = conn.execute(
            text("SELECT version FROM schema_migrations ORDER BY version")
        ).fetchall()
    assert [row[0] for row in rows] == ["V001", "V002"]


def test_migration_runner_preserves_semicolons_inside_string_literals(
    tmp_path: Path,
) -> None:
    """Governed migration execution must not split quoted PostgreSQL literals."""
    from sqlalchemy import create_engine, text
    from db_manager import DBManager
    from plugins.schema_migrations import SchemaMigrationRunner

    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    (migration_dir / "V001__seed_literal_with_semicolon.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS alpha (
            id INTEGER PRIMARY KEY,
            contamination_reason TEXT NOT NULL
        );
        INSERT INTO alpha (id, contamination_reason)
        VALUES (
            1,
            'binary_result_clv_contamination;synthetic_ticker_contamination'
        );
        """,
        encoding="utf-8",
    )

    db_file = tmp_path / "migration_literal.sqlite"
    db = DBManager.__new__(DBManager)
    db.connection_string = f"sqlite:///{db_file}"
    db.engine = create_engine(db.connection_string)

    runner = SchemaMigrationRunner(
        db=db,
        migrations_dir=migration_dir,
        expected_tables=("schema_migrations", "alpha"),
    )

    applied = runner.apply()

    assert [migration.version for migration in applied] == ["V001"]
    with db.engine.connect() as conn:
        stored_reason = conn.execute(
            text("SELECT contamination_reason FROM alpha WHERE id = 1")
        ).scalar()
    assert (
        stored_reason
        == "binary_result_clv_contamination;synthetic_ticker_contamination"
    )


def test_migration_governance_registers_dashboard_relations() -> None:
    """Dashboard source tables and read-model views are first-class relations."""
    from plugins.schema_migrations import (
        EXPECTED_DASHBOARD_SOURCE_TABLES,
        EXPECTED_DASHBOARD_VIEWS,
        EXPECTED_STATS_RELATIONS,
        EXPECTED_STATS_TABLES,
    )

    expected_relations = {
        relation.name: relation.relation_type for relation in EXPECTED_STATS_RELATIONS
    }

    assert "elo_ratings" in EXPECTED_STATS_TABLES
    assert "bet_recommendations" in EXPECTED_DASHBOARD_SOURCE_TABLES
    assert "portfolio_value_snapshots" in EXPECTED_DASHBOARD_SOURCE_TABLES
    assert "tennis_model_evaluations" in EXPECTED_DASHBOARD_SOURCE_TABLES
    assert expected_relations["bet_recommendations"] == "table"
    assert expected_relations["portfolio_value_snapshots"] == "table"
    assert expected_relations["tennis_model_evaluations"] == "table"

    for dashboard_view in (
        "dashboard_portfolio_v1",
        "dashboard_live_markets_v1",
        "dashboard_rankings_v1",
        "dashboard_calibration_v1",
        "dashboard_data_quality_v1",
        "dashboard_bet_detail_v1",
        "dashboard_tennis_predictions_v1",
        "dashboard_tennis_model_health_v1",
    ):
        assert dashboard_view in EXPECTED_DASHBOARD_VIEWS
        assert expected_relations[dashboard_view] == "view"


def test_migration_verify_passes_for_dashboard_tables_and_views(tmp_path: Path) -> None:
    """Governance verification accepts present tables and views with correct types."""
    from sqlalchemy import create_engine
    from db_manager import DBManager
    from plugins.schema_migrations import SchemaMigrationRunner

    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    (migration_dir / "V001__create_dashboard_relations.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS bet_recommendations (bet_id TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS portfolio_value_snapshots (
            snapshot_hour_utc TIMESTAMP PRIMARY KEY
        );
        CREATE VIEW dashboard_portfolio_v1 AS
            SELECT snapshot_hour_utc FROM portfolio_value_snapshots;
        """,
        encoding="utf-8",
    )

    db_file = tmp_path / "dashboard_relations.sqlite"
    db = DBManager.__new__(DBManager)
    db.connection_string = f"sqlite:///{db_file}"
    db.engine = create_engine(db.connection_string)

    runner = SchemaMigrationRunner(
        db=db,
        migrations_dir=migration_dir,
        expected_tables=(
            "schema_migrations",
            "bet_recommendations",
            "portfolio_value_snapshots",
        ),
        expected_views=("dashboard_portfolio_v1",),
    )

    runner.apply()
    status = runner.verify()

    assert status["missing_tables"] == []
    assert status["missing_views"] == []
    assert status["wrong_relation_types"] == []


def test_migration_verify_fails_for_missing_dashboard_source_table(
    tmp_path: Path,
) -> None:
    """Missing governed dashboard-critical source tables fail loudly."""
    from sqlalchemy import create_engine
    from db_manager import DBManager
    from plugins.schema_migrations import SchemaMigrationRunner

    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    (migration_dir / "V001__create_partial_dashboard_sources.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS portfolio_value_snapshots (
            snapshot_hour_utc TIMESTAMP PRIMARY KEY
        );
        """,
        encoding="utf-8",
    )

    db_file = tmp_path / "missing_dashboard_source.sqlite"
    db = DBManager.__new__(DBManager)
    db.connection_string = f"sqlite:///{db_file}"
    db.engine = create_engine(db.connection_string)

    runner = SchemaMigrationRunner(
        db=db,
        migrations_dir=migration_dir,
        expected_tables=(
            "schema_migrations",
            "bet_recommendations",
            "portfolio_value_snapshots",
        ),
        expected_views=(),
    )

    runner.apply()
    status = runner.verify()

    assert status["missing_tables"] == ["bet_recommendations"]
    with pytest.raises(RuntimeError, match="Missing tables: bet_recommendations"):
        runner.assert_verified()


def test_migration_verify_fails_for_missing_dashboard_view(tmp_path: Path) -> None:
    """Missing governed dashboard read-model views fail loudly."""
    from sqlalchemy import create_engine
    from db_manager import DBManager
    from plugins.schema_migrations import SchemaMigrationRunner

    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    (migration_dir / "V001__create_dashboard_sources.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS bet_recommendations (bet_id TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS portfolio_value_snapshots (
            snapshot_hour_utc TIMESTAMP PRIMARY KEY
        );
        """,
        encoding="utf-8",
    )

    db_file = tmp_path / "missing_dashboard_view.sqlite"
    db = DBManager.__new__(DBManager)
    db.connection_string = f"sqlite:///{db_file}"
    db.engine = create_engine(db.connection_string)

    runner = SchemaMigrationRunner(
        db=db,
        migrations_dir=migration_dir,
        expected_tables=(
            "schema_migrations",
            "bet_recommendations",
            "portfolio_value_snapshots",
        ),
        expected_views=("dashboard_portfolio_v1",),
    )

    runner.apply()
    status = runner.verify()

    assert status["missing_views"] == ["dashboard_portfolio_v1"]
    with pytest.raises(RuntimeError, match="Missing views: dashboard_portfolio_v1"):
        runner.assert_verified()


def test_migration_verify_fails_for_wrong_dashboard_relation_type(
    tmp_path: Path,
) -> None:
    """A dashboard view name backed by a table is a governance failure."""
    from sqlalchemy import create_engine
    from db_manager import DBManager
    from plugins.schema_migrations import SchemaMigrationRunner

    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    (migration_dir / "V001__create_wrong_dashboard_relation_type.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS dashboard_portfolio_v1 (
            snapshot_hour_utc TIMESTAMP PRIMARY KEY
        );
        """,
        encoding="utf-8",
    )

    db_file = tmp_path / "wrong_dashboard_relation_type.sqlite"
    db = DBManager.__new__(DBManager)
    db.connection_string = f"sqlite:///{db_file}"
    db.engine = create_engine(db.connection_string)

    runner = SchemaMigrationRunner(
        db=db,
        migrations_dir=migration_dir,
        expected_tables=("schema_migrations",),
        expected_views=("dashboard_portfolio_v1",),
    )

    runner.apply()
    status = runner.verify()

    assert status["wrong_relation_types"] == [
        {
            "name": "dashboard_portfolio_v1",
            "expected_type": "view",
            "actual_type": "table",
        }
    ]
    with pytest.raises(
        RuntimeError,
        match="dashboard_portfolio_v1 expected view but found table",
    ):
        runner.assert_verified()


def test_migration_runner_rerun_is_idempotent(tmp_path: Path) -> None:
    """Re-running the same migration chain should not duplicate ledger rows."""
    from sqlalchemy import create_engine, text
    from db_manager import DBManager
    from plugins.schema_migrations import SchemaMigrationRunner

    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    (migration_dir / "V001__create_alpha.sql").write_text(
        "CREATE TABLE IF NOT EXISTS alpha (id INTEGER PRIMARY KEY, value TEXT);",
        encoding="utf-8",
    )

    db_file = tmp_path / "migration_runner.sqlite"
    db = DBManager.__new__(DBManager)
    db.connection_string = f"sqlite:///{db_file}"
    db.engine = create_engine(db.connection_string)

    runner = SchemaMigrationRunner(
        db=db,
        migrations_dir=migration_dir,
        expected_tables=("schema_migrations", "alpha"),
    )

    first_apply = runner.apply()
    second_apply = runner.apply()

    assert [migration.version for migration in first_apply] == ["V001"]
    assert second_apply == []

    with db.engine.connect() as conn:
        ledger_count = conn.execute(
            text("SELECT COUNT(*) FROM schema_migrations")
        ).scalar()
    assert ledger_count == 1


def test_migration_runner_allows_known_legacy_checksum_alias(tmp_path: Path) -> None:
    """Known historical checksum drift should not block later governed versions."""
    from sqlalchemy import create_engine, text
    from db_manager import DBManager
    from plugins.schema_migrations import (
        LEDGER_BOOTSTRAP_SQL,
        LEGACY_CHECKSUMS_BY_VERSION,
        SchemaMigrationRunner,
    )

    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    (migration_dir / "V008__create_alpha.sql").write_text(
        "CREATE TABLE IF NOT EXISTS alpha (id INTEGER PRIMARY KEY, value TEXT);",
        encoding="utf-8",
    )
    (migration_dir / "V009__create_beta.sql").write_text(
        "CREATE TABLE IF NOT EXISTS beta (id INTEGER PRIMARY KEY, alpha_id INTEGER);",
        encoding="utf-8",
    )

    db_file = tmp_path / "migration_runner.sqlite"
    db = DBManager.__new__(DBManager)
    db.connection_string = f"sqlite:///{db_file}"
    db.engine = create_engine(db.connection_string)

    with db.engine.begin() as conn:
        conn.execute(text(LEDGER_BOOTSTRAP_SQL))
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alpha (id INTEGER PRIMARY KEY, value TEXT);"
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO schema_migrations (version, name, checksum)
                VALUES (:version, :name, :checksum)
                """
            ),
            {
                "version": "V008",
                "name": "create alpha",
                "checksum": next(iter(LEGACY_CHECKSUMS_BY_VERSION["V008"])),
            },
        )

    runner = SchemaMigrationRunner(
        db=db,
        migrations_dir=migration_dir,
        expected_tables=("schema_migrations", "alpha", "beta"),
    )

    applied = runner.apply()
    status = runner.verify()

    assert [migration.version for migration in applied] == ["V009"]
    assert status["checksum_mismatches"] == []
    assert status["missing_versions"] == []
    assert status["missing_tables"] == []


def test_migration_runner_rejects_unknown_checksum_mismatch(tmp_path: Path) -> None:
    """Unexpected checksum drift must still fail closed."""
    from sqlalchemy import create_engine, text
    from db_manager import DBManager
    from plugins.schema_migrations import LEDGER_BOOTSTRAP_SQL, SchemaMigrationRunner

    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    (migration_dir / "V001__create_alpha.sql").write_text(
        "CREATE TABLE IF NOT EXISTS alpha (id INTEGER PRIMARY KEY, value TEXT);",
        encoding="utf-8",
    )

    db_file = tmp_path / "migration_runner.sqlite"
    db = DBManager.__new__(DBManager)
    db.connection_string = f"sqlite:///{db_file}"
    db.engine = create_engine(db.connection_string)

    with db.engine.begin() as conn:
        conn.execute(text(LEDGER_BOOTSTRAP_SQL))
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alpha (id INTEGER PRIMARY KEY, value TEXT);"
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO schema_migrations (version, name, checksum)
                VALUES (:version, :name, :checksum)
                """
            ),
            {
                "version": "V001",
                "name": "create alpha",
                "checksum": "not-a-real-checksum",
            },
        )

    runner = SchemaMigrationRunner(
        db=db,
        migrations_dir=migration_dir,
        expected_tables=("schema_migrations", "alpha"),
    )

    with pytest.raises(RuntimeError, match="Checksum mismatch for V001"):
        runner.apply()


# ---------------------------------------------------------------------------
# Task 5d — No db_loader import in plugins/stats/
# ---------------------------------------------------------------------------


def test_no_db_loader_import_in_stats_package() -> None:
    """plugins/stats/ must not import db_loader (legacy dependency guardrail)."""
    stats_dir = Path(__file__).parent.parent / "plugins" / "stats"
    if not stats_dir.exists():
        pytest.skip("plugins/stats/ not yet created — skipping guardrail check")

    python_files = list(stats_dir.rglob("*.py"))
    offending: list[str] = []
    for pyfile in python_files:
        source = pyfile.read_text(errors="replace")
        if "db_loader" in source:
            offending.append(str(pyfile.relative_to(Path(__file__).parent.parent)))

    assert not offending, (
        "The following files in plugins/stats/ import db_loader (forbidden):\n"
        + "\n".join(f"  {f}" for f in offending)
    )


# ---------------------------------------------------------------------------
# Task 5b/5c — Live DB: tables exist with correct constraints
# ---------------------------------------------------------------------------


@requires_live_db
def test_tables_exist_in_information_schema(schema_manager) -> None:
    """After applying the migration chain, all stats tables exist in public."""
    from sqlalchemy import text

    with schema_manager.db.engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        )
        existing = {row[0] for row in result}

    for table in ALL_STATS_TABLES:
        assert table in existing, f"Table '{table}' not found in information_schema"


@requires_live_db
def test_schema_migrations_ledger_matches_checked_in_chain(schema_manager) -> None:
    """The live ledger records every checked-in stats migration version."""
    status = schema_manager.verify()
    assert status["expected_versions"] == [
        migration.version for migration in schema_manager.discover_migrations()
    ]
    assert status["missing_versions"] == []
    assert status["checksum_mismatches"] == []
    assert status["missing_tables"] == []
    assert status["missing_views"] == []


@requires_live_db
def test_team_game_stats_primary_key_in_db(schema_manager) -> None:
    """team_game_stats has composite PK (game_id, team) in the live DB."""
    from sqlalchemy import text

    with schema_manager.db.engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema   = kcu.table_schema
                WHERE tc.table_name       = 'team_game_stats'
                  AND tc.constraint_type  = 'PRIMARY KEY'
                  AND tc.table_schema     = 'public'
                """
            )
        )
        pk_cols = {row[0] for row in result}

    assert "game_id" in pk_cols, "team_game_stats PK missing game_id"
    assert "team" in pk_cols, "team_game_stats PK missing team"


@requires_live_db
def test_team_game_stats_foreign_key_in_db(schema_manager) -> None:
    """team_game_stats.game_id has a FK to unified_games."""
    from sqlalchemy import text

    with schema_manager.db.engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT ccu.table_name AS referenced_table
                FROM information_schema.table_constraints tc
                JOIN information_schema.referential_constraints rc
                    ON tc.constraint_name = rc.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                    ON rc.unique_constraint_name = ccu.constraint_name
                WHERE tc.table_name      = 'team_game_stats'
                  AND tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema    = 'public'
                """
            )
        )
        referenced = {row[0] for row in result}

    assert (
        "unified_games" in referenced
    ), "team_game_stats does not have a FK referencing unified_games"


@requires_live_db
def test_extension_tables_exist_and_have_fk_in_db(schema_manager) -> None:
    """Each extension table exists and has a FK to team_game_stats in the live DB."""
    from sqlalchemy import text

    with schema_manager.db.engine.connect() as conn:
        for ext_table in EXTENSION_TABLES:
            # Check table existence
            result = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name=:tbl"
                ),
                {"tbl": ext_table},
            )
            count = result.scalar()
            assert count == 1, f"Extension table '{ext_table}' not found in DB"

            # Check FK to team_game_stats
            result = conn.execute(
                text(
                    """
                    SELECT ccu.table_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.referential_constraints rc
                        ON tc.constraint_name = rc.constraint_name
                    JOIN information_schema.constraint_column_usage ccu
                        ON rc.unique_constraint_name = ccu.constraint_name
                    WHERE tc.table_name      = :tbl
                      AND tc.constraint_type = 'FOREIGN KEY'
                      AND tc.table_schema    = 'public'
                    """
                ),
                {"tbl": ext_table},
            )
            referenced = {row[0] for row in result}
            assert (
                "team_game_stats" in referenced
            ), f"{ext_table} does not have a FK referencing team_game_stats"


@requires_live_db
def test_audit_table_indexes_in_db(schema_manager) -> None:
    """bet_reconciliation_audit has indexes on bet_id and reconciled_at."""
    from sqlalchemy import text

    with schema_manager.db.engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT indexname FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename  = 'bet_reconciliation_audit'
                """
            )
        )
        index_names = {row[0] for row in result}

    assert "idx_bra_bet_id" in index_names, "Missing index idx_bra_bet_id"
    assert "idx_bra_reconciled_at" in index_names, "Missing index idx_bra_reconciled_at"
