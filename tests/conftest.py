import pytest
import os
import sqlalchemy
from sqlalchemy import create_engine, text, event
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path
import re

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))

# Use file-based SQLite for interactions or in-memory
# Using file ensures new connections see the same data
TEST_DB_FILE = "test_nhlstats.db"
TEST_DB_URL = f"sqlite:///{TEST_DB_FILE}"

# Global engine for all tests
_TEST_ENGINE = create_engine(TEST_DB_URL)

def regexp(expr, item):
    if item is None:
        return False
    try:
        reg = re.compile(expr, re.IGNORECASE)
        return reg.search(str(item)) is not None
    except Exception:
        return False

@event.listens_for(_TEST_ENGINE, "connect")
def sqlite_connect(dbapi_connection, connection_record):
    dbapi_connection.create_function("REGEXP", 2, regexp)

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Ensure the test db is clean."""
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)
    yield
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)

@pytest.fixture(autouse=True)
def clean_test_schema():
    """Clean the test schema before EACH test to ensure isolation."""
    # SQLite doesn't have schemas, so simply drop all tables
    with _TEST_ENGINE.connect() as conn:
        # Enable foreign keys
        conn.execute(text("PRAGMA foreign_keys = ON"))

        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = [row[0] for row in result if row[0] not in ['sqlite_sequence']]

        if tables:
            # Drop views first just in case
            conn.execute(text("PRAGMA foreign_keys = OFF"))
            for table in tables:
                conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
            conn.execute(text("PRAGMA foreign_keys = ON"))
            conn.commit()
    yield

@pytest.fixture(scope="session", autouse=True)
def mock_db_manager_to_test_engine():
    """Surgically redirect DBManager to the test engine."""
    from db_manager import DBManager, default_db

    # Patch the class init for any new instances
    def mocked_init(self, connection_string=None, schema=None):
        self.connection_string = str(_TEST_ENGINE.url)
        self.engine = _TEST_ENGINE

    # Patch the global default_db instance
    default_db.engine = _TEST_ENGINE
    default_db.connection_string = str(_TEST_ENGINE.url)

    # Also patch plugins.db_manager.default_db
    # We force import it to ensure it's loaded and patched
    try:
        import plugins.db_manager
        plugins.db_manager.default_db.engine = _TEST_ENGINE
        plugins.db_manager.default_db.connection_string = str(_TEST_ENGINE.url)

        # Also patch the class in plugins.db_manager
        with patch.object(plugins.db_manager.DBManager, '__init__', mocked_init):
            with patch.object(DBManager, '__init__', mocked_init):
                yield
            return

    except ImportError:
        pass

    with patch.object(DBManager, '__init__', mocked_init):
        # Also patch plugins.db_manager.DBManager if available checking sys.modules
        if 'plugins.db_manager' in sys.modules:
             with patch.object(sys.modules['plugins.db_manager'].DBManager, '__init__', mocked_init):
                 yield
        else:
            yield

def translate_sql(sql):
    """Translate Postgres/DuckDB SQL to SQLite for tests."""
    sql_upper = sql.strip().upper()
    sql_normalized = " ".join(sql_upper.split())

    # CASE 0: SERIAL PRIMARY KEY -> INTEGER PRIMARY KEY AUTOINCREMENT
    if "SERIAL PRIMARY KEY" in sql_upper:
        sql = re.sub(r"SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT", sql, flags=re.IGNORECASE)

    # CASE 0a: DOUBLE PRECISION -> REAL
    if "DOUBLE PRECISION" in sql_upper:
        sql = re.sub(r"DOUBLE PRECISION", "REAL", sql, flags=re.IGNORECASE)

    # CASE 1: pg_tables
    if "FROM PG_TABLES" in sql_normalized:
        return "SELECT name as tablename FROM sqlite_master WHERE type='table'"

    # CASE 2: information_schema.columns
    # Pattern: SELECT ... FROM information_schema.columns WHERE table_name = 'X'
    if "FROM INFORMATION_SCHEMA.COLUMNS" in sql_normalized:
        # Extract table name
        match = re.search(r"table_name\s*=\s*'(\w+)'", sql, re.IGNORECASE)
        if match:
            table_name = match.group(1)
            # Use SQLite pragma table valued function
            return f"SELECT name as column_name, type as data_type FROM pragma_table_info('{table_name}')"

    # CASE 3: information_schema.table_constraints
    # Pattern: SELECT constraint_name FROM information_schema.table_constraints WHERE table_name = 'X' AND constraint_type = 'PRIMARY KEY'
    if "FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS" in sql_normalized:
         match = re.search(r"table_name\s*=\s*'(\w+)'", sql, re.IGNORECASE)
         if match:
             table_name = match.group(1)
             if "PRIMARY KEY" in sql_normalized:
                 return f"SELECT 'pk_' || '{table_name}' as constraint_name FROM pragma_table_info('{table_name}') WHERE pk > 0 LIMIT 1"
             elif "FOREIGN KEY" in sql_normalized:
                 return f"SELECT 'fk_' || '{table_name}' as constraint_name FROM pragma_foreign_key_list('{table_name}') LIMIT 1"

    # CASE 3b: information_schema.tables (Added)
    if "FROM INFORMATION_SCHEMA.TABLES" in sql_normalized:
        return "SELECT name as table_name FROM sqlite_master WHERE type='table'"

    # CASE 0: Type Casts (::numeric, ::text)
    # Remove ::type suffix
    sql = re.sub(r"::[a-zA-Z0-9_]+", "", sql)

    # CASE 0b: Regex operator ~
    if " ~ " in sql:
        sql = sql.replace(" ~ ", " REGEXP ")
    if " ~* " in sql:
        sql = sql.replace(" ~* ", " REGEXP ")

    # CASE 0c: ARRAY_AGG -> GROUP_CONCAT
    if "ARRAY_AGG" in sql_upper:
        # Simplistic replacement: remove ORDER BY inside array_agg if present
        # Pattern: ARRAY_AGG( [DISTINCT] col [ORDER BY col] )
        # We want: GROUP_CONCAT( [DISTINCT] col )

        def replace_agg(match):
            content = match.group(1)
            # Remove ORDER BY ...
            content = re.sub(r"ORDER BY.*", "", content, flags=re.IGNORECASE).strip()
            return f"GROUP_CONCAT({content})"

        sql = re.sub(r"ARRAY_AGG\((.*?)\)", replace_agg, sql, flags=re.IGNORECASE)

    # CASE 4: Interval syntax
    # Pattern: NOW() - INTERVAL 'X days'
    # SQLite: datetime('now', '-X days')
    if "INTERVAL" in sql_upper:
        # Replace: now() - interval '2 days'  ->  datetime('now', '-2 days')
        # Regex for generic interval subtraction from now()
        # This is tricky without a full parser, but let's try common patterns
        # Note: tests usually use current_date - interval or similar

        # Pattern: - INTERVAL '7 days'
        sql = re.sub(r"-\s*INTERVAL\s*'(\d+)\s*days'", r", '-\1 days')", sql, flags=re.IGNORECASE)
        # Now we need to prepend datetime( if it was strictly now(), but wait.
        # usually checks are: column > NOW() - INTERVAL '2 days'
        # SQLite: column > datetime('now', '-2 days')

        # Let's naive replace NOW() with datetime('now'
        sql = re.sub(r"NOW\(\)\s*,", r"datetime('now',", sql, flags=re.IGNORECASE)

        # If the replace didn't work (because of no NOW()), let's try:
        # column >= current_date - INTERVAL '1 day' -> column >= date('now', '-1 day')
        match_interval = re.search(r"-\s*INTERVAL\s*'(\d+)\s*days'", sql, re.IGNORECASE)
        if match_interval and "datetime('now'" not in sql:
             days = match_interval.group(1)
             if "CURRENT_DATE" in sql_upper:
                 sql = re.sub(r"CURRENT_DATE\s*-\s*INTERVAL\s*'(\d+)\s*days'", f"date('now', '-\1 days')", sql, flags=re.IGNORECASE)
             else:
                 # CAUTION: This is a hack
                 sql = re.sub(r"-\s*INTERVAL\s*'(\d+)\s*days'", f", '-\1 days')", sql, flags=re.IGNORECASE)
                 # Expecting previous part to be wrapped in date function? No.
                 # Maybe explicitly replace specific queries found in logs
                 pass

    # CASE 5: Generic translations
    if sql_upper == "SHOW TABLES":
        return "SELECT name FROM sqlite_master WHERE type='table'"

    if sql_upper.startswith("DESCRIBE "):
        table = sql.split()[1].strip('"').strip("'").lower()
        return f"PRAGMA table_info({table})"

    # CASE 5a: ALTER TABLE ADD CONSTRAINT ... PRIMARY KEY - SQLite doesn't support this
    if "ADD CONSTRAINT" in sql_upper and "PRIMARY KEY" in sql_upper:
        return "SELECT 1"  # No-op, SQLite doesn't support adding PK to existing table

    # CASE 5b: ALTER TABLE ADD COLUMN IF NOT EXISTS - SQLite doesn't support IF NOT EXISTS
    if "ADD COLUMN IF NOT EXISTS" in sql_upper:
        sql = re.sub(r"ADD COLUMN IF NOT EXISTS", "ADD COLUMN", sql, flags=re.IGNORECASE)
        # Wrap in try/catch approach - just return no-op if column exists
        return "SELECT 1"  # Simplify - let table creation handle columns

    if "INSERT OR REPLACE" in sql_upper and "INTO" not in sql_upper:
        sql = sql.replace("INSERT OR REPLACE", "INSERT OR REPLACE INTO")

    if sql_upper.startswith("CREATE TABLE ") and "IF NOT EXISTS" not in sql_upper:
        sql = sql.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS")

    if sql_upper.startswith("DROP TABLE ") and "IF EXISTS" not in sql_upper:
        sql = sql.replace("DROP TABLE", "DROP TABLE IF EXISTS")

    if " CASCADE" in sql_upper:
        sql = sql.replace(" CASCADE", "")

    if "TEST_NHLSTATS." in sql_upper:
        sql = sql.replace("test_nhlstats.", "").replace("TEST_NHLSTATS.", "")

    if sql_upper.startswith("INSERT INTO ") and "ON CONFLICT" not in sql_upper:
        if "GAMES" in sql_upper:
            sql = sql.rstrip(';').rstrip() + " ON CONFLICT (game_id) DO NOTHING"
        elif "TEAMS" in sql_upper:
            sql = sql.rstrip(';').rstrip() + " ON CONFLICT (team_id) DO NOTHING"
        elif "PLACED_BETS" in sql_upper:
            sql = sql.rstrip(';').rstrip() + " ON CONFLICT (bet_id) DO NOTHING"
        elif "BET_RECOMMENDATIONS" in sql_upper:
            sql = sql.rstrip(';').rstrip() + " ON CONFLICT (bet_id) DO NOTHING"

    return sql

@pytest.fixture(autouse=True)
def patch_sqlalchemy_execute_for_duckdb_compat():
    """Intercept SQL strings in tests and translate for SQLite."""
    from sqlalchemy.engine.base import Connection
    from sqlalchemy.sql.elements import TextClause

    original_execute = Connection.execute
    def mocked_execute(self, statement, parameters=None, **kwargs):
        # Unwrap TextClause to string if possible, translate, then re-wrap
        sql_text = None
        if isinstance(statement, str):
            sql_text = statement
        elif isinstance(statement, TextClause):
            sql_text = str(statement)

        if sql_text:
            translated_sql = translate_sql(sql_text)
            if translated_sql != sql_text:
                statement = text(translated_sql)

        return original_execute(self, statement, parameters, **kwargs)
    with patch.object(Connection, 'execute', mocked_execute):
        yield

@pytest.fixture(autouse=True)
def silence_duckdb():
    """Mock duckdb.connect to redirect to our SQLite test engine."""
    with patch('duckdb.connect') as mock:
        class DuckDBBridge:
            def __init__(self, engine):
                self.engine = engine
                self._conn = None
            @property
            def conn(self):
                if not self._conn:
                    self._conn = self.engine.connect()
                return self._conn
            def execute(self, sql, params=None):
                sql = translate_sql(sql)
                try:
                    res = self.conn.execute(text(sql), params or {})
                    self.conn.commit()
                    return res
                except Exception as e:
                    # Log error?
                    raise e
            def fetchall(self): return []
            def fetchdf(self): return []
            def close(self):
                if self._conn: self._conn.close(); self._conn = None
            def __getattr__(self, name): return getattr(self.conn, name)
        mock.return_value = DuckDBBridge(_TEST_ENGINE)
        yield mock
