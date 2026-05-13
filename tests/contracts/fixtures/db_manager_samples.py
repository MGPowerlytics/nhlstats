"""Deterministic DBManager contract fixtures for consumer contract tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


def build_db_fetch_df_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical fetch_df result payload.

    Represents the dict-form of a query result with columns and rows,
    as consumed by downstream components that expect this shape.
    """
    return deepcopy(_BASE_FETCH_DF_PAYLOAD)


def build_db_fetch_scalar_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical fetch_scalar result payload."""
    return deepcopy(_BASE_FETCH_SCALAR_PAYLOAD)


def build_db_execution_payload() -> Dict[str, Any]:
    """Return a fresh deep copy of the canonical execute result payload."""
    return deepcopy(_BASE_EXECUTION_PAYLOAD)


def build_db_manager_config() -> Dict[str, Any]:
    """Return a dict of canonical DBManager connection configuration.

    This is used by contract tests to verify configuration shape without
    actually connecting to a database.
    """
    return deepcopy(_BASE_DB_MANAGER_CONFIG)


_BASE_FETCH_DF_PAYLOAD: Dict[str, Any] = {
    "columns": ["game_id", "home_team", "away_team", "home_score", "away_score"],
    "rows": [
        [1001, "New York Yankees", "Boston Red Sox", 5, 3],
        [1002, "Los Angeles Dodgers", "San Francisco Giants", 2, 1],
        [1003, "Chicago Cubs", "St. Louis Cardinals", 4, 4],
    ],
}

_BASE_FETCH_SCALAR_PAYLOAD: Dict[str, Any] = {
    "value": 42,
}

_BASE_EXECUTION_PAYLOAD: Dict[str, Any] = {
    "rowcount": 1,
    "success": True,
}

_BASE_DB_MANAGER_CONFIG: Dict[str, Any] = {
    "connection_string": "postgresql+psycopg2://user:pass@localhost:5432/db",
    "schema": "public",
}
