#!/usr/bin/env python3
"""Test the load_data_to_db function."""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add plugins directory to Python path
plugins_dir = Path(__file__).parent / "plugins"
if str(plugins_dir) not in sys.path:
    sys.path.insert(0, str(plugins_dir))

# Mock the context
context = {"ds": "2026-03-10"}

# Import the function from the DAG
sys.path.insert(0, str(Path(__file__).parent / "dags"))
from multi_sport_betting_workflow import load_data_to_db

def test_nba_load():
    """Test loading NBA data."""
    print("Testing NBA load_data_to_db...")
    try:
        load_data_to_db("nba", **context)
        print("✓ NBA load successful")
        return True
    except Exception as e:
        print(f"❌ NBA load failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_nba_load()
    sys.exit(0 if success else 1)
