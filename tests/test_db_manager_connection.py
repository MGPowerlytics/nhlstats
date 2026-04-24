"""
Tests for DBManager connection configuration.
Ensures database host defaults to 'postgres' for Docker environments.

NOTE: These tests verify PostgreSQL configuration behavior and must be run
outside the pytest session that mocks DBManager to use SQLite.
"""

import pytest
from unittest.mock import patch, MagicMock
import os
from plugins.db_manager import DBManager

# Skip entire module when conftest mocks DBManager to SQLite
pytestmark = pytest.mark.skipif(
    os.environ.get("POSTGRES_HOST") != "postgres",
    reason="DBManager connection tests require unmocked PostgreSQL environment",
)


class TestDBManagerConnection:
    """Test DBManager database connection configuration."""

    def test_postgres_host_defaults_to_postgres_service_name(self):
        """POSTGRES_HOST should default to 'postgres' for Docker environments."""
        # Arrange - Clear any existing POSTGRES_HOST env var
        with patch.dict(os.environ, {}, clear=True):
            # Act - Create DBManager without specifying connection string
            db = DBManager()

            # Assert - Connection string should use 'postgres' as host
            assert "postgres" in db.connection_string.lower()
            assert "localhost" not in db.connection_string
            assert "@postgres:" in db.connection_string

    def test_postgres_host_respects_environment_variable(self):
        """POSTGRES_HOST from environment should be used in connection string."""
        # Arrange
        with patch.dict(os.environ, {"POSTGRES_HOST": "my-custom-host"}):
            # Act
            db = DBManager()

            # Assert
            assert "@my-custom-host:" in db.connection_string

    def test_localhost_only_used_when_explicitly_set(self):
        """Localhost should only be used when explicitly set via env var."""
        # Arrange
        with patch.dict(os.environ, {"POSTGRES_HOST": "localhost"}):
            # Act
            db = DBManager()

            # Assert
            assert "@localhost:" in db.connection_string

    def test_connection_string_includes_all_components(self):
        """Connection string should include protocol, user, pass, host, port, db."""
        # Arrange
        test_env = {
            "POSTGRES_USER": "testuser",
            "POSTGRES_PASSWORD": "testpass",
            "POSTGRES_HOST": "testhost",
            "POSTGRES_PORT": "5433",
            "POSTGRES_DB": "testdb",
        }

        with patch.dict(os.environ, test_env, clear=True):
            # Act
            db = DBManager()

            # Assert
            assert "postgresql+psycopg2://" in db.connection_string
            assert "testuser:testpass" in db.connection_string
            assert "@testhost:5433" in db.connection_string
            assert "/testdb" in db.connection_string

    @patch("plugins.db_manager.create_engine")
    def test_custom_connection_string_overrides_env_vars(self, mock_create_engine):
        """Custom connection string should override environment variables."""
        # Arrange
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        custom_conn = "postgresql://user:pass@customhost:9999/customdb"

        with patch.dict(os.environ, {"POSTGRES_HOST": "ignored"}):
            # Act
            db = DBManager(connection_string=custom_conn)

            # Assert
            assert db.connection_string == custom_conn
            assert "customhost" in db.connection_string
            assert "ignored" not in db.connection_string
