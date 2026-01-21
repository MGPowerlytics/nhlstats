import pytest
import os
import sqlalchemy
from sqlalchemy import create_engine, text
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))

TEST_DB_URL = "postgresql+psycopg2://airflow:airflow@localhost:5432/airflow"
TEST_SCHEMA = "test_nhlstats"

# Global engine for all tests to use a shared pool
_TEST_ENGINE = create_engine(
    TEST_DB_URL,
    pool_size=20,
    max_overflow=30,
    connect_args={"options": f"-csearch_path={TEST_SCHEMA}"}
)

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Ensure the test schema exists."""
    admin_engine = create_engine(TEST_DB_URL)
    with admin_engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {TEST_SCHEMA}"))
        conn.commit()
    yield

@pytest.fixture(autouse=True)
def clean_test_schema():
    """Clean the test schema before EACH test to ensure isolation."""
    with _TEST_ENGINE.connect() as conn:
        # Get all tables in test_schema and drop them
        result = conn.execute(text(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{TEST_SCHEMA}'"))
        tables = [row[0] for row in result]
        if tables:
            for table in tables:
                conn.execute(text(f"DROP TABLE IF EXISTS {TEST_SCHEMA}.{table} CASCADE"))
            conn.commit()
    yield

@pytest.fixture(autouse=True)
def mock_db_manager_to_test_engine():
    """Surgically redirect DBManager to the test engine."""
    from db_manager import DBManager
    def mocked_init(self, connection_string=None, schema=None):
        self.connection_string = str(_TEST_ENGINE.url)
        self.engine = _TEST_ENGINE
    with patch.object(DBManager, '__init__', mocked_init):
        yield

def translate_sql(sql):
    """Translate DuckDB-isms to Postgres for tests."""
    sql_upper = sql.strip().upper()
    if sql_upper == "SHOW TABLES":
        return f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{TEST_SCHEMA}'"
    if sql_upper.startswith("DESCRIBE "):
        table = sql.split()[1].strip('"').strip("'").lower()
        return f"SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = '{TEST_SCHEMA}' AND table_name = '{table}'"
    if "INSERT OR REPLACE" in sql_upper:
        sql = sql.replace("INSERT OR REPLACE", "INSERT")
    if sql_upper.startswith("CREATE TABLE ") and "IF NOT EXISTS" not in sql_upper:
        sql = sql.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS")
    if sql_upper.startswith("DROP TABLE ") and "IF EXISTS" not in sql_upper:
        sql = sql.replace("DROP TABLE", "DROP TABLE IF EXISTS")
    # For tests that don't specify ON CONFLICT, add a default DO NOTHING to prevent UniqueViolation
    if sql_upper.startswith("INSERT INTO ") and "ON CONFLICT" not in sql_upper:
        # We try to detect the primary key based on the table name
        if "GAMES" in sql_upper:
            sql = sql.rstrip(';').rstrip() + " ON CONFLICT (game_id) DO NOTHING"
        elif "TEAMS" in sql_upper:
            sql = sql.rstrip(';').rstrip() + " ON CONFLICT (team_id) DO NOTHING"
        elif "PLACED_BETS" in sql_upper:
            sql = sql.rstrip(';').rstrip() + " ON CONFLICT (bet_id) DO NOTHING"
        elif "BET_RECOMMENDATIONS" in sql_upper:
            sql = sql.rstrip(';').rstrip() + " ON CONFLICT (bet_id) DO NOTHING"
        else:
            # Fallback for other tables - might fail if no PK exists but usually safe in these tests
            pass
    return sql

@pytest.fixture(autouse=True)
def patch_sqlalchemy_execute_for_duckdb_compat():
    """Intercept SQL strings in tests and translate DuckDB-isms to Postgres."""
    from sqlalchemy.engine.base import Connection
    original_execute = Connection.execute
    def mocked_execute(self, statement, parameters=None, **kwargs):
        if isinstance(statement, str):
            statement = text(translate_sql(statement))
        return original_execute(self, statement, parameters, **kwargs)
    with patch.object(Connection, 'execute', mocked_execute):
        yield

@pytest.fixture(autouse=True)
def silence_duckdb():
    """Mock duckdb.connect to redirect to our Postgres test engine."""
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
                res = self.conn.execute(text(sql), params or {})
                self.conn.commit()
                return res
            def fetchall(self): return []
            def close(self):
                if self._conn: self._conn.close(); self._conn = None
            def __getattr__(self, name): return getattr(self.conn, name)
        mock.return_value = DuckDBBridge(_TEST_ENGINE)
        yield mock
