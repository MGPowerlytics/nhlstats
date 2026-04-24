#!/usr/bin/env python3
"""Test database connection with IP address."""

import sys
from pathlib import Path

# Add plugins directory to Python path
plugins_dir = Path(__file__).parent / "plugins"
if str(plugins_dir) not in sys.path:
    sys.path.insert(0, str(plugins_dir))

from db_manager import DBManager
from sqlalchemy import text
import os

def test_connection():
    """Test database connection with IP address."""
    print("Testing database connection with IP address...")

    try:
        # Override the host with IP address
        os.environ["POSTGRES_HOST"] = "172.20.0.2"

        db_manager = DBManager()
        print(f"✓ DBManager created: {db_manager}")
        print(f"✓ Connection string: {db_manager.connection_string}")

        # Test the connection
        with db_manager.engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            print(f"✓ Connection test successful: {row[0]}")

        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
