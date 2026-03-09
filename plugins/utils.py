"""
Utility functions for the Multi-Sport Betting System.

This module contains shared utility functions to eliminate code duplication
and promote the DRY (Don't Repeat Yourself) principle across the codebase.
"""

from typing import Dict, TypeVar, Any, List, Optional
try:
    from .db_manager import DBManager
except ImportError:
    from plugins.db_manager import DBManager

K = TypeVar("K")  # Key type
V = TypeVar("V")  # Value type


def store_value(dictionary: Dict[K, V], key: K, value: V) -> None:
    """
    Store a value in a dictionary with the given key.

    This utility function eliminates duplication of the pattern:
        dictionary[key] = value

    Args:
        dictionary: The dictionary to store the value in
        key: The key to use for storage
        value: The value to store

    Returns:
        None
    """
    dictionary[key] = value


def get_nested_value(data_dict: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """
    Get a nested value from a dictionary with safe access.

    This utility function eliminates duplication of the pattern of
    safely accessing nested dictionary keys that might not exist.

    Args:
        data_dict: The dictionary to get the value from
        *keys: One or more keys to traverse (e.g., "homeTeam", "id")
        default: Default value to return if any key in the chain is not found

    Returns:
        The value at the nested location, or default if any key is missing

    Example:
        # Gets data["homeTeam"]["id"] or returns None if either key is missing
        team_id = get_nested_value(data, "homeTeam", "id")
    """
    current = data_dict
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def upsert_record(
    db: DBManager,
    table_name: str,
    params: Dict[str, Any],
    conflict_columns: List[str],
    update_columns: Optional[List[str]] = None,
) -> None:
    """
    Execute an UPSERT (INSERT ... ON CONFLICT ... DO UPDATE) operation.

    This utility function eliminates duplication of the UPSERT pattern
    used across multiple database operations in the system.

    Args:
        db: Database manager instance
        table_name: Name of the table to upsert into
        params: Dictionary of column names to values for insertion
        conflict_columns: List of column names that define the conflict constraint
        update_columns: Optional list of columns to update on conflict.
                       If None, all columns except conflict columns will be updated.

    Returns:
        None

    Example:
        upsert_record(
            db=self.db,
            table_name="bet_recommendations",
            params={"bet_id": "123", "sport": "NBA", "elo_prob": 0.65},
            conflict_columns=["bet_id"],
            update_columns=["elo_prob"]
        )
    """
    if not params:
        raise ValueError("params cannot be empty")

    # Build column lists
    all_columns = list(params.keys())
    placeholders = [f":{col}" for col in all_columns]

    # Build UPDATE clause
    if update_columns is None:
        # Update all columns except conflict columns
        update_columns = [col for col in all_columns if col not in conflict_columns]

    if not update_columns:
        # If no columns to update, use DO NOTHING
        update_clause = "NOTHING"
    else:
        update_set = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_columns])
        update_clause = f"UPDATE SET {update_set}"

    # Build SQL
    sql = f"""
        INSERT INTO {table_name}
        ({", ".join(all_columns)})
        VALUES ({", ".join(placeholders)})
        ON CONFLICT ({", ".join(conflict_columns)}) DO
        {update_clause}
    """

    # Execute
    db.execute(sql, params)


def create_entity_upserter(
    table_name: str,
    conflict_column: str,
    update_columns: List[str],
) -> callable:
    """
    Create a reusable upsert function for a specific entity type.

    This factory function eliminates duplication of entity-specific upsert
    wrapper functions that follow the pattern of defining update columns
    and calling upsert_record.

    Args:
        table_name: Name of the database table
        conflict_column: Primary key or unique constraint column for conflict resolution
        update_columns: List of columns to update on conflict

    Returns:
        A function that takes (db, params) and performs the upsert

    Example:
        upsert_bet = create_entity_upserter(
            table_name="bet_recommendations",
            conflict_column="bet_id",
            update_columns=["elo_prob", "market_prob", "edge"]
        )
        upsert_bet(db, params)
    """

    def upsert_entity(db: DBManager, params: Dict[str, Any]) -> None:
        """Upsert entity into the specified table."""
        upsert_record(
            db=db,
            table_name=table_name,
            params=params,
            conflict_columns=[conflict_column],
            update_columns=update_columns,
        )

    return upsert_entity


class DictStoreMixin:
    """Mixin class that provides dictionary storage methods.

    This mixin eliminates duplication of simple setter methods
    that follow the pattern of calling store_value on a dictionary attribute.
    """

    def store_in_dict(self, attr_name: str, key: str, value: Any) -> None:
        """Store a value in the specified dictionary attribute.

        This is the generic implementation used by domain-specific methods
        like add_stat() and set_rating() to eliminate code duplication
        while maintaining domain-specific naming and type hints.

        Args:
            attr_name: Name of the dictionary attribute (e.g., "stats", "ratings")
            key: Key to store the value under
            value: Value to store
        """
        dictionary = getattr(self, attr_name)
        store_value(dictionary, key, value)
