"""
Utility functions for the Multi-Sport Betting System.

This module contains shared utility functions to eliminate code duplication
and promote the DRY (Don't Repeat Yourself) principle across the codebase.
"""

from typing import Dict, TypeVar, Any, List, Optional, Callable, Tuple

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
    _validate_upsert_input(params)

    # NUCLEAR FIX: Always remove date_str from params for any table
    # No table in our schema has a date_str column - bet_recommendations has recommendation_date
    if "date_str" in params:
        print(
            f"🚨 NUCLEAR FIX in upsert_record: Removing 'date_str' from params for table '{table_name}'"
        )
        print(f"🚨 Params keys before removing date_str: {list(params.keys())}")

        # For bet_recommendations table, rename date_str to recommendation_date if needed
        if table_name == "bet_recommendations":
            if "recommendation_date" not in params:
                params["recommendation_date"] = params["date_str"]
                print(
                    f"🚨 Renamed date_str to recommendation_date for bet_recommendations table. Value: {params['date_str']}"
                )
            else:
                print(
                    f"🚨 recommendation_date already exists in params: {params['recommendation_date']}"
                )

        # Remove date_str
        del params["date_str"]
        print(f"🚨 Params keys after removing date_str: {list(params.keys())}")

    # NUCLEAR FIX: Also use pop with default to ensure date_str is really gone
    params.pop("date_str", None)

    # Handle table-specific parameter cleaning
    params, all_columns = _prepare_upsert_parameters(table_name, params)

    # Generate placeholders for SQL
    placeholders = [f":{col}" for col in all_columns]

    update_columns = _determine_update_columns(
        all_columns, conflict_columns, update_columns
    )
    update_clause = _build_update_clause(update_columns)

    sql = _build_upsert_sql(
        table_name, all_columns, placeholders, conflict_columns, update_clause
    )

    db.execute(sql, params)


def _prepare_upsert_parameters(
    table_name: str, params: Dict[str, Any]
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Prepare parameters for upsert operation with table-specific cleaning.

    Args:
        table_name: Name of the table
        params: Dictionary of column names to values

    Returns:
        Tuple of (cleaned_params, column_names)
    """
    # Special handling for bet_recommendations table
    if table_name == "bet_recommendations":
        params = _clean_bet_recommendations_params(params)

    all_columns = list(params.keys())

    # Final safety check for bet_recommendations table
    if table_name == "bet_recommendations":
        all_columns = _apply_bet_recommendations_final_checks(params, all_columns)

    return params, all_columns


def _clean_bet_recommendations_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Clean parameters specifically for bet_recommendations table.

    Handles date_str to recommendation_date conversion and ensures
    all date_str variations are removed.
    """
    _log_bet_recommendations_debug_info(
        "before cleaning", "bet_recommendations", params
    )

    # 1. Convert date_str to recommendation_date if present
    params = _convert_date_str_to_recommendation_date(params)

    # 2. Ensure recommendation_date exists (fallback from bet_id or default)
    params = _ensure_recommendation_date_present(params)

    # 3. Remove any variation of date_str - MORE AGGRESSIVE
    params = _remove_all_date_str_variations(params)

    # 4. EXTRA SAFETY: Remove date_str no matter what (in case it was added back)
    if "date_str" in params:
        # Log a warning since this shouldn't happen
        import logging

        logging.warning(
            f"CRITICAL: date_str still in params after cleaning! Removing. Params keys: {list(params.keys())}"
        )
        del params["date_str"]

    # 5. Final safety: use pop with default
    params.pop("date_str", None)

    _log_bet_recommendations_debug_info("after cleaning", "bet_recommendations", params)
    _ensure_date_str_removed(params)

    return params


def _convert_date_str_to_recommendation_date(params: Dict[str, Any]) -> Dict[str, Any]:
    """Convert date_str to recommendation_date if date_str exists."""
    if "date_str" in params:
        if "recommendation_date" not in params:
            params["recommendation_date"] = params["date_str"]
        # Remove date_str
        del params["date_str"]
    return params


def _ensure_recommendation_date_present(params: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure recommendation_date exists with fallback logic."""
    if "recommendation_date" not in params:
        # Try to extract date from bet_id as fallback
        if "bet_id" in params:
            # bet_id format: nba_2024-01-01_Home_Away_...
            parts = params["bet_id"].split("_")
            if len(parts) >= 2:
                # Try to parse date from second part
                date_part = parts[1]
                if len(date_part) == 10 and date_part[4] == "-" and date_part[7] == "-":
                    params["recommendation_date"] = date_part
                    print(
                        f"⚠️  WARNING: Extracted recommendation_date from bet_id: {date_part}"
                    )
        # If still not present, use today's date as last resort
        if "recommendation_date" not in params:
            from datetime import datetime

            params["recommendation_date"] = datetime.now().strftime("%Y-%m-%d")
            print("🚨 CRITICAL: Using today's date as recommendation_date fallback")
    return params


def _remove_all_date_str_variations(params: Dict[str, Any]) -> Dict[str, Any]:
    """Remove any key containing 'date_str' (case-insensitive)."""
    keys_to_remove = [key for key in params.keys() if "date_str" in key.lower()]
    for key in keys_to_remove:
        print(f"⚠️  Removing date_str variation: '{key}'")
        del params[key]
    return params


def _apply_bet_recommendations_final_checks(
    params: Dict[str, Any], all_columns: List[str]
) -> List[str]:
    """Apply final safety checks for bet_recommendations table."""
    all_columns = _remove_date_str_from_columns(all_columns)
    _debug_log_bet_recommendations("bet_recommendations", all_columns)

    # ULTRA DEFENSIVE: Also check and clean params one more time
    # This is a nuclear option to ensure date_str is never in the final output
    if "date_str" in params:
        print(
            "🚨 ULTRA DEFENSIVE: date_str STILL in params after all cleaning! Removing..."
        )
        del params["date_str"]
        # Also remove from all_columns if it somehow got back in
        all_columns = [col for col in all_columns if col != "date_str"]

    return all_columns


def _log_bet_recommendations_debug_info(
    stage: str, table_name: str, params: Dict[str, Any]
) -> None:
    """Log debug information for bet_recommendations table operations."""
    if table_name != "bet_recommendations":
        return

    print(
        f"🔍 DEBUG upsert_record: Table: {table_name}, Params {stage}: {list(params.keys())}"
    )
    if "date_str" in params:
        print(
            f"🔍 DEBUG upsert_record: Found 'date_str' in params with value: {params.get('date_str')}"
        )


def _ensure_date_str_removed(params: Dict[str, Any]) -> None:
    """Ensure date_str is removed from parameters after cleaning."""
    if "date_str" in params:
        print("🚨 ERROR upsert_record: 'date_str' STILL in params after cleaning!")
        # Emergency fix: remove date_str if it somehow still exists
        del params["date_str"]


def _remove_date_str_from_columns(all_columns: List[str]) -> List[str]:
    """Remove date_str from column list if present."""
    # Remove any column that contains "date_str" case-insensitively
    original_len = len(all_columns)
    filtered_columns = [col for col in all_columns if "date_str" not in col.lower()]

    if len(filtered_columns) < original_len:
        removed = set(all_columns) - set(filtered_columns)
        print(
            f"🚨 CRITICAL: Removed columns containing 'date_str' from all_columns: {removed}"
        )

    return filtered_columns


def _validate_upsert_input(params: Dict[str, Any]) -> None:
    """Validate input parameters for upsert operation."""
    if not params:
        raise ValueError("params cannot be empty")

    # Try to extract date from bet_id or use a default
    bet_id = params.get("bet_id", "")
    date_match = _extract_date_from_bet_id(bet_id)

    if date_match:
        params["recommendation_date"] = date_match
        print(f"⚠️  Extracted date from bet_id: {params['recommendation_date']}")
    else:
        params["recommendation_date"] = "1900-01-01"
        print(f"⚠️  Using default date: {params['recommendation_date']}")


def _extract_date_from_bet_id(bet_id: str) -> Optional[str]:
    """Extract date from bet_id format: nba_2026-03-06_..."""
    import re

    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", bet_id)
    return date_match.group(1) if date_match else None


def _debug_log_bet_recommendations(table_name: str, all_columns: List[str]) -> None:
    """Log debug information for bet_recommendations table operations."""
    if table_name == "bet_recommendations":
        print(
            f"🔍 DEBUG _debug_log_bet_recommendations: Building SQL for {table_name} with columns: {all_columns}"
        )
        if "date_str" in all_columns:
            print(
                "🚨 ERROR _debug_log_bet_recommendations: date_str is in all_columns! This should never happen!"
            )
            print(
                f"🚨 ERROR _debug_log_bet_recommendations: Full column list: {all_columns}"
            )


def _determine_update_columns(
    all_columns: List[str],
    conflict_columns: List[str],
    update_columns: Optional[List[str]],
) -> List[str]:
    """
    Determine which columns should be updated on conflict.

    If update_columns is None, update all columns except conflict columns.
    Returns empty list if no columns should be updated.
    """
    if update_columns is None:
        # Update all columns except conflict columns
        return [col for col in all_columns if col not in conflict_columns]
    return update_columns


def _build_update_clause(update_columns: List[str]) -> str:
    """
    Build the UPDATE clause for UPSERT operation.

    Returns "NOTHING" if no columns should be updated.
    """
    if not update_columns:
        # If no columns to update, use DO NOTHING
        return "NOTHING"

    update_set = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_columns])
    return f"UPDATE SET {update_set}"


def _build_upsert_sql(
    table_name: str,
    all_columns: List[str],
    placeholders: List[str],
    conflict_columns: List[str],
    update_clause: str,
) -> str:
    """Build the complete UPSERT SQL statement."""
    # Apply table-specific transformations if needed
    if table_name == "bet_recommendations":
        all_columns, placeholders = _transform_bet_recommendations_columns(
            all_columns, placeholders
        )
        update_clause = _clean_update_clause_for_bet_recommendations(update_clause)

    return f"""
        INSERT INTO {table_name}
        ({", ".join(all_columns)})
        VALUES ({", ".join(placeholders)})
        ON CONFLICT ({", ".join(conflict_columns)}) DO
        {update_clause}
    """


def _transform_bet_recommendations_columns(
    columns: List[str], placeholders: List[str]
) -> Tuple[List[str], List[str]]:
    """
    Transform columns and placeholders for bet_recommendations table.

    Removes any date_str columns and ensures recommendation_date is present.
    """
    filtered_columns = []
    filtered_placeholders = []
    has_recommendation_date = False

    for col, placeholder in zip(columns, placeholders):
        if "date_str" in col.lower():
            # Skip date_str columns
            continue
        filtered_columns.append(col)
        filtered_placeholders.append(placeholder)
        if col == "recommendation_date":
            has_recommendation_date = True

    # Ensure recommendation_date is present
    if not has_recommendation_date:
        filtered_columns.append("recommendation_date")
        filtered_placeholders.append(":recommendation_date")

    return filtered_columns, filtered_placeholders


def _clean_update_clause_for_bet_recommendations(update_clause: str) -> str:
    """Clean update clause for bet_recommendations table by replacing date_str."""
    if "date_str" in update_clause.lower():
        update_clause = update_clause.replace("date_str", "recommendation_date")
        update_clause = update_clause.replace("DATE_STR", "recommendation_date")
    return update_clause


def create_entity_upserter(
    table_name: str,
    conflict_column: str,
    update_columns: List[str],
) -> Callable:
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
