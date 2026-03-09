"""SQL Parameters Mixin for dataclasses.

Provides reusable to_sql_params() method to eliminate duplicate code
when converting dataclass instances to SQL parameter dictionaries.
"""

from typing import Dict, Any
from dataclasses import fields


class SqlParamsMixin:
    """Mixin class that provides to_sql_params() method for dataclasses.

    This eliminates duplicate code for converting dataclass instances to
    SQL parameter dictionaries. Subclasses can override _get_field_mapping()
    to customize field name mappings.
    """

    def to_sql_params(self) -> Dict[str, Any]:
        """Convert dataclass to dictionary suitable for SQL parameters.

        Returns:
            Dictionary mapping field names to values. Includes all fields
            even if None - database can handle NULL values.

        Note:
            Subclasses can override _get_field_mapping() to provide custom
            field name mappings.
        """
        field_mapping = self._get_field_mapping()
        params = {}

        for field_obj in fields(self):
            field_name = field_obj.name
            # Use mapped name if available, otherwise use original field name
            sql_field_name = field_mapping.get(field_name, field_name)
            params[sql_field_name] = getattr(self, field_name)

        return params

    def _get_field_mapping(self) -> Dict[str, str]:
        """Get field name mappings for SQL parameters.

        Returns:
            Dictionary mapping dataclass field names to SQL column names.
            Default implementation returns empty dict (no mappings).

        Note:
            Subclasses should override this method if they need to map
            dataclass field names to different SQL column names.
        """
        return {}
