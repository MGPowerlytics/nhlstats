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

import subprocess
import sys
from pathlib import Path
from typing import Generator

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
    """Return an initialised DatabaseSchemaManager connected to the live DB.

    Bypasses the conftest SQLite mock by constructing a direct PostgreSQL
    connection string so the fixture always targets the real Postgres instance.
    """
    import os

    from database_schema_manager import DatabaseSchemaManager
    from sqlalchemy import create_engine
    from db_manager import DBManager

    user = os.getenv("POSTGRES_USER", "airflow")
    password = os.getenv("POSTGRES_PASSWORD", "airflow")
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "airflow")
    conn_str = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"

    db = DBManager.__new__(DBManager)
    db.connection_string = conn_str
    db.engine = create_engine(conn_str)
    mgr = DatabaseSchemaManager(db)
    mgr._schema_initialized = False
    mgr.initialize_schema()
    return mgr


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
    """After initialize_schema(), all stats tables appear in information_schema."""
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
