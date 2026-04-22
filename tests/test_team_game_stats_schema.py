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
    assert status["expected_versions"] == ["V001", "V002", "V003"]
    assert status["missing_versions"] == []
    assert status["checksum_mismatches"] == []
    assert status["missing_tables"] == []


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
