"""
Unified Database Manager for the multi-sport betting system.
Abstracts database connections (Postgres, DuckDB) and operations to provide flexibility.
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
        """
        try:
            with self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
                return df
        except Exception as e:
            logger.error(
                f"Error fetching DataFrame: {query}\nParams: {params}\nError: {e}"
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
