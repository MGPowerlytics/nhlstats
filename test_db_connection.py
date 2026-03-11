#!/usr/bin/env python3
"""Test database connection."""

import os
import sys
from sqlalchemy import create_engine, text

# Add plugins directory to path
plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
if plugins_dir not in sys.path:
    sys.path.insert(0, plugins_dir)

try:
    from db_manager import DBManager
    print("✓ DBManager imported successfully")

    # Test 1: Create DBManager instance
    db_manager = DBManager()
    print(f"✓ DBManager created: {db_manager}")
    print(f"✓ Connection string: {db_manager.connection_string}")

    # Test 2: Test connection
    with db_manager.engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print(f"✓ Connection test successful: {result.scalar()}")

    # Test 3: Test NHLDatabaseLoader
    from db_loader import NHLDatabaseLoader
    loader = NHLDatabaseLoader(db=db_manager)
    print(f"✓ NHLDatabaseLoader created: {loader}")

    print("\n✅ All database tests passed!")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
