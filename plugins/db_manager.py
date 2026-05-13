"""
Unified Database Manager for the multi-sport betting system.
Exclusively uses PostgreSQL for all data storage.
"""

import os
import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, text
from typing import Optional, Any, Dict
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Global registry for engines to prevent connection exhaustion
_ENGINE_REGISTRY: Dict[str, sqlalchemy.engine.Engine] = {}


class DBManager:
    """
    Unified interface for PostgreSQL operations.
    """

    def __init__(
        self, connection_string: Optional[str] = None, schema: Optional[str] = None
    ):
        """
        Initialize the DBManager for PostgreSQL.

        Args:
            connection_string: SQLAlchemy connection string. If None, defaults to env vars.
            schema: Optional PostgreSQL schema to use.
        """
        if connection_string:
            self.connection_string = connection_string
        else:
            # Default credentials from docker-compose
            user = os.getenv("POSTGRES_USER", "airflow")
            password = os.getenv("POSTGRES_PASSWORD", "airflow")
            host = os.getenv(
                "POSTGRES_HOST", "postgres"
            )  # Default to 'postgres' service name for Docker
            port = os.getenv("POSTGRES_PORT", "5432")
            db = os.getenv("POSTGRES_DB", "airflow")
            self.connection_string = (
                f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
            )

        schema = schema or os.getenv("POSTGRES_SCHEMA")
        if schema:
            # Append search_path to connection string
            separator = "&" if "?" in self.connection_string else "?"
            self.connection_string += f"{separator}options=-csearch_path%3D{schema}"

        # Use global registry to share engines/pools across instances
        if self.connection_string not in _ENGINE_REGISTRY:
            # Use a conservative pool size for the shared engine
            _ENGINE_REGISTRY[self.connection_string] = create_engine(
                self.connection_string,
                pool_size=10,
                max_overflow=20,
                pool_timeout=30,
                pool_recycle=1800,
            )

        self.engine = _ENGINE_REGISTRY[self.connection_string]

    def get_engine(self):
        """Returns the SQLAlchemy engine."""
        return self.engine

    def execute(self, query: str, params: Optional[Dict[str, Any]] = None):
        """
        Execute a SQL query on PostgreSQL.
        """
        with self.engine.begin() as conn:
            try:
                result = conn.execute(text(query), params or {})
                return result
            except Exception as e:
                logger.error(
                    f"Error executing query: {query}\nParams: {params}\nError: {e}"
                )
                raise

    def fetch_df(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Execute a query and return the result as a Pandas DataFrame.

        Note:
            We deliberately avoid ``pandas.read_sql`` here because pandas 3.x
            no longer recognises SQLAlchemy 1.4 ``Connection`` objects (Airflow
            pins ``sqlalchemy<2.0``) and falls back to the DBAPI code path,
            which raises ``TypeError: Query must be a string unless using
            sqlalchemy``. Executing through SQLAlchemy directly and constructing
            the DataFrame from the result keeps this function compatible with
            both the SQLA 1.4 / pandas 3.x and SQLA 2.x stacks.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"fetch_df requires a SQL string, got {type(query).__name__}"
            )
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                rows = result.fetchall()
                columns = list(result.keys())
                return pd.DataFrame(rows, columns=columns)
        except Exception as e:
            logger.error(
                f"Error fetching DataFrame: {query}\nParams: {params}\nError: {e}"
            )
            raise

    def fetch_scalar(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute a query and return the first column of the first row, or None.

        Args:
            query: SQL query string. Must return at least one column.
            params: Optional dict of bound parameters.

        Returns:
            The scalar value from the first row/first column, or None if no rows.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"fetch_scalar requires a SQL string, got {type(query).__name__}"
            )
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                row = result.fetchone()
                if row is None:
                    return None
                return row[0]
        except Exception as e:
            logger.error(
                f"Error fetching scalar: {query}\nParams: {params}\nError: {e}"
            )
            raise

    def insert_df(
        self,
        df: pd.DataFrame,
        table_name: str,
        if_exists: str = "append",
        index: bool = False,
    ):
        """
        Insert a DataFrame into a table.
        """
        try:
            df.to_sql(
                table_name,
                self.engine,
                if_exists=if_exists,
                index=index,
                method="multi",
            )
            logger.info(f"Inserted {len(df)} rows into {table_name}")
        except Exception as e:
            logger.error(f"Error inserting DataFrame into {table_name}: {e}")
            raise

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in PostgreSQL."""
        inspector = sqlalchemy.inspect(self.engine)
        return inspector.has_table(table_name)

    def close(self):
        """Dispose of the engine."""
        self.engine.dispose()


# Default instance for easy import
# Use this for general operations
default_db = DBManager()
