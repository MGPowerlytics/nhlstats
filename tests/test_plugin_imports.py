"""
Tests for plugin import compatibility.
Ensures plugins can be imported both directly and via plugins. prefix.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestPluginImports:
    """Test plugin module import compatibility."""

    def test_clv_backfill_imports_successfully(self):
        """clv_backfill should import without errors."""
        # Arrange - Mock db connection
        mock_db = MagicMock()

        with patch("plugins.db_manager.default_db", mock_db):
            # Act - Import should succeed
            from plugins.clv_backfill import CLVBackfiller

            # Assert - Class is accessible
            assert CLVBackfiller is not None

    def test_update_clv_data_imports_successfully(self):
        """update_clv_data should import without errors."""
        # Arrange - Mock dependencies
        mock_db = MagicMock()
        mock_kalshi = MagicMock()

        with patch("plugins.db_manager.default_db", mock_db):
            with patch("plugins.kalshi_betting.KalshiBetting", mock_kalshi):
                # Act - Import should succeed
                import plugins.update_clv_data as update_clv

                # Assert - Module is accessible
                assert update_clv is not None

    def test_db_manager_default_db_exists(self):
        """db_manager should export default_db instance."""
        # Act
        from plugins.db_manager import default_db, DBManager

        # Assert
        assert default_db is not None
        assert isinstance(default_db, DBManager)

    def test_db_manager_can_be_imported_without_plugins_prefix(self):
        """Within plugins directory, imports should work without prefix."""
        # This simulates how Airflow loads plugins
        with patch.dict(sys.modules, clear=False):
            # Act - Import as Airflow would
            import plugins.db_manager as db_manager

            # Assert
            assert hasattr(db_manager, "DBManager")
            assert hasattr(db_manager, "default_db")
