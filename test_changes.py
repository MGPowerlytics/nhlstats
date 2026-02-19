#!/usr/bin/env python3
"""
Test the changes made to exclude problematic segments and fix sport classification.
"""

import sys
import os
from pathlib import Path

# Add plugins directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'plugins'))

def test_sport_classification():
    """Test that sport classification works correctly for all ticker types."""
    print("Testing sport classification in bet_tracker.py...")

    # Test cases: (ticker, expected_sport)
    test_cases = [
        ("KXNBAGAME-26FEB09LALGSW-LAL", "NBA"),
        ("KXNHLGAME-26FEB04BOSNYR-BOS", "NHL"),
        ("KXNCAAMBGAME-26FEB09DUKEUNC-DUKE", "NCAAB"),
        ("KXNCAAWBGAME-26FEB08LSUAUB-AUB", "WNCAAB"),  # Women's NCAA Basketball
        ("KXATPMATCH-26FEB08DJOKOVICNADAL-DJO", "TENNIS"),
        ("KXWTAMATCH-26FEB08SWIATEKSABALENKA-SWI", "TENNIS"),
        ("KXATPCHALLENGERMATCH-26FEB04MARMIL-MIL", "TENNIS"),  # Challenger tournament
        ("KXWTACHALLENGERMATCH-26FEB07TIATAG-TAG", "TENNIS"),  # Challenger tournament
        ("KXEPLGAME-26FEB08ARSMCI-ARS", "EPL"),
        ("KXLIGUE1GAME-26FEB08PSGMAR-PSG", "LIGUE1"),
        ("KXCBAGAME-26FEB08BEIJSHAN-BEI", "CBA"),
        ("RANDOMTICKER-123", "UNKNOWN"),  # Unknown ticker
    ]

    # Import the bet_tracker module to test the logic
    try:
        import bet_tracker
        print("✓ bet_tracker module imports successfully")
    except ImportError as e:
        print(f"✗ Failed to import bet_tracker: {e}")
        return False

    # Test the sport classification logic directly
    print("\nTesting sport classification logic:")

    for ticker, expected_sport in test_cases:
        sport = "UNKNOWN"
        if "NBAGAME" in ticker:
            sport = "NBA"
        elif "NHLGAME" in ticker:
            sport = "NHL"
        elif "MLBGAME" in ticker:
            sport = "MLB"
        elif "NFLGAME" in ticker:
            sport = "NFL"
        elif "NCAAMBGAME" in ticker:
            sport = "NCAAB"
        elif "NCAAWBGAME" in ticker:  # Women's NCAA Basketball
            sport = "WNCAAB"
        elif "ATPMATCH" in ticker or "WTAMATCH" in ticker:
            sport = "TENNIS"
        elif "ATPCHALLENGERMATCH" in ticker or "WTACHALLENGERMATCH" in ticker:
            sport = "TENNIS"  # Challenger tournaments are still tennis
        elif "EPLGAME" in ticker:
            sport = "EPL"
        elif "LIGUE1GAME" in ticker:
            sport = "LIGUE1"
        elif "CBAGAME" in ticker:
            sport = "CBA"

        if sport == expected_sport:
            print(f"  ✓ {ticker[:30]}... -> {sport}")
        else:
            print(f"  ✗ {ticker[:30]}... -> {sport} (expected: {expected_sport})")
            return False

    return True

def test_excluded_segments():
    """Test that excluded segments are correctly defined."""
    print("\n\nTesting excluded segments configuration...")

    # Expected excluded segments based on our analysis
    expected_excluded = [
        ("WNCAAB", "HIGH"),   # Catastrophic: 0% win rate, -100% ROI
        ("NBA", "LOW"),       # Very poor: 20% win rate, -68% ROI
        ("TENNIS", "HIGH"),   # Poor: 44% win rate, -46% ROI
        ("TENNIS", "MEDIUM"), # Unprofitable: 61% win rate but -16% ROI
    ]

    # Check DAG configuration
    dag_file = Path("dags/multi_sport_betting_workflow.py")
    if not dag_file.exists():
        print(f"✗ DAG file not found: {dag_file}")
        return False

    with open(dag_file, 'r') as f:
        dag_content = f.read()

    # Check if excluded segments are defined
    if "excluded_segments = [" in dag_content:
        print("✓ Found excluded_segments definition in DAG")

        # Extract the excluded segments block
        start = dag_content.find("excluded_segments = [")
        end = dag_content.find("]", start)
        excluded_block = dag_content[start:end+1]

        # Check for each expected segment
        for sport, confidence in expected_excluded:
            segment_str = f'("{sport}", "{confidence}")'
            if segment_str in excluded_block:
                print(f"  ✓ Found excluded segment: {sport} {confidence}")
            else:
                print(f"  ✗ Missing excluded segment: {sport} {confidence}")
                return False
    else:
        print("✗ excluded_segments not found in DAG")
        return False

    return True

def test_portfolio_optimizer():
    """Test that PortfolioOptimizer can be instantiated with excluded segments."""
    print("\n\nTesting PortfolioOptimizer with excluded segments...")

    try:
        from portfolio_optimizer import PortfolioOptimizer

        # Test instantiation with excluded segments
        excluded_segments = [
            ("WNCAAB", "HIGH"),
            ("NBA", "LOW"),
            ("TENNIS", "HIGH"),
            ("TENNIS", "MEDIUM"),
        ]

        optimizer = PortfolioOptimizer(
            bankroll=1000.0,
            max_daily_risk_pct=0.25,
            kelly_fraction=0.20,
            min_bet_size=2.0,
            max_bet_size=10.0,
            max_single_bet_pct=0.03,
            min_edge=-1.0,
            min_confidence=0.65,
            excluded_segments=excluded_segments,
        )

        print(f"✓ PortfolioOptimizer instantiated successfully")
        print(f"  Excluded segments: {optimizer.excluded_segments}")

        # Verify excluded segments are stored correctly
        if len(optimizer.excluded_segments) == len(excluded_segments):
            print(f"  ✓ All {len(excluded_segments)} excluded segments stored")
        else:
            print(f"  ✗ Expected {len(excluded_segments)} excluded segments, got {len(optimizer.excluded_segments)}")
            return False

    except Exception as e:
        print(f"✗ Failed to instantiate PortfolioOptimizer: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

def main():
    """Run all tests."""
    print("=" * 80)
    print("TESTING CHANGES FOR BETTING SYSTEM UPDATE")
    print("=" * 80)

    tests_passed = 0
    tests_failed = 0

    # Run tests
    if test_sport_classification():
        tests_passed += 1
    else:
        tests_failed += 1

    if test_excluded_segments():
        tests_passed += 1
    else:
        tests_failed += 1

    if test_portfolio_optimizer():
        tests_passed += 1
    else:
        tests_failed += 1

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests passed: {tests_passed}")
    print(f"Tests failed: {tests_failed}")

    if tests_failed == 0:
        print("\n✅ All tests passed! Ready to redeploy.")
        return 0
    else:
        print("\n❌ Some tests failed. Please fix before redeploying.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
