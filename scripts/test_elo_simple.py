#!/usr/bin/env python3
"""
Simple test for Elo update logic.
"""

import sys
import os

# Mimic DAG's path setup
sys.path.insert(0, "plugins")

# Test the exact imports the DAG uses
try:
    from db_manager import default_db

    print("✅ db_manager import successful")

    # Test query
    test_query = "SELECT COUNT(*) as count FROM unified_games WHERE sport = 'NHL'"
    result = default_db.fetch_df(test_query)
    print(f"✅ Database query successful: {result.iloc[0]['count']} NHL games")

    # Test Elo import (as done in DAG)
    from elo import get_elo_class

    print("✅ elo import successful")

    # Test getting classes
    nhl_class = get_elo_class("nhl")
    print(f"✅ NHL Elo class: {nhl_class}")

    nba_class = get_elo_class("nba")
    print(f"✅ NBA Elo class: {nba_class}")

    print("\n✅ All imports successful!")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
