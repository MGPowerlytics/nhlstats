#!/usr/bin/env python3
"""Test the fixes for EPL Elo and date_str conversion."""

import sys
sys.path.insert(0, '/mnt/data2/nhlstats')

from plugins.elo.epl_elo_rating import EPLEloRating
from plugins.utils import _clean_bet_recommendations_params

def test_epl_elo_fix():
    """Test that EPL Elo update works with the fix."""
    print("Testing EPL Elo fix...")

    elo = EPLEloRating()
    elo.set_rating("Arsenal", 1600)
    elo.set_rating("Chelsea", 1500)

    # Test update with home advantage
    try:
        result = elo.update("Arsenal", "Chelsea", True)
        print(f"✓ EPL Elo update succeeded: {result}")
        return True
    except Exception as e:
        print(f"✗ EPL Elo update failed: {e}")
        return False

def test_date_str_conversion():
    """Test that date_str is converted to recommendation_date."""
    print("\nTesting date_str conversion fix...")

    # Test params with date_str
    params = {
        "bet_id": "test_123",
        "sport": "nba",
        "home_team": "Lakers",
        "away_team": "Celtics",
        "date_str": "2026-03-06",
        "elo_prob": 0.7,
        "market_prob": 0.6,
        "edge": 0.1
    }

    cleaned = _clean_bet_recommendations_params(params)

    # Check that date_str was removed
    if "date_str" in cleaned:
        print(f"✗ date_str still in cleaned params: {list(cleaned.keys())}")
        return False

    # Check that recommendation_date was added
    if "recommendation_date" not in cleaned:
        print(f"✗ recommendation_date not in cleaned params: {list(cleaned.keys())}")
        return False

    if cleaned["recommendation_date"] != "2026-03-06":
        print(f"✗ recommendation_date has wrong value: {cleaned['recommendation_date']}")
        return False

    print(f"✓ date_str conversion succeeded")
    print(f"  Original keys: {list(params.keys())}")
    print(f"  Cleaned keys: {list(cleaned.keys())}")
    return True

def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing fixes for Airflow task failures")
    print("=" * 60)

    success = True

    # Test EPL Elo fix
    if not test_epl_elo_fix():
        success = False

    # Test date_str conversion fix
    if not test_date_str_conversion():
        success = False

    print("\n" + "=" * 60)
    if success:
        print("✓ All tests passed! Fixes should resolve Airflow task failures.")
    else:
        print("✗ Some tests failed. Further investigation needed.")

    return success

if __name__ == "__main__":
    main()
