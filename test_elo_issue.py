#!/usr/bin/env python3
"""Test script to reproduce the EPL Elo issue."""

import sys
sys.path.insert(0, '/mnt/data2/nhlstats')

from plugins.elo.epl_elo_rating import EPLEloRating

def test_elo():
    """Test EPL Elo rating system."""
    print("Testing EPL Elo rating system...")

    # Create instance
    elo = EPLEloRating()
    print(f"Created EPLEloRating instance: {elo}")
    print(f"Type: {type(elo)}")
    print(f"MRO: {type(elo).__mro__}")

    # Check if _apply_home_advantage exists
    print(f"\nChecking _apply_home_advantage method:")
    print(f"  hasattr: {hasattr(elo, '_apply_home_advantage')}")

    # Try to access it
    try:
        method = elo._apply_home_advantage
        print(f"  Method exists: {method}")
    except AttributeError as e:
        print(f"  AttributeError: {e}")

    # Check config
    print(f"\nChecking config:")
    print(f"  hasattr config: {hasattr(elo, 'config')}")
    if hasattr(elo, 'config'):
        print(f"  config value: {elo.config}")
        if elo.config:
            print(f"  config.home_advantage: {elo.config.home_advantage}")

    # Try to call update with simple values
    print(f"\nTrying to call update method...")
    try:
        # Set some initial ratings
        elo.set_rating("Team A", 1500)
        elo.set_rating("Team B", 1500)

        # Try to update
        result = elo.update("Team A", "Team B", True)
        print(f"  Update succeeded: {result}")
    except Exception as e:
        print(f"  Exception during update: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_elo()
