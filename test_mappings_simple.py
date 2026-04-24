#!/usr/bin/env python3
"""Simple test for team name mappings."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'plugins'))

# Import after path is set
from naming_resolver import NamingResolver, NamingContext

def test_mappings():
    """Test current mappings."""
    resolver = NamingResolver()

    print("Testing team name mappings...")
    print("=" * 60)

    # Test some known mappings
    test_cases = [
        # NHL (should work)
        ("nhl", "kalshi", "ANA", "ANA"),
        ("nhl", "kalshi", "BOS", "BOS"),

        # MLB (check if our fix worked)
        ("mlb", "kalshi", "LAD", "Los Angeles Dodgers"),
        ("mlb", "kalshi", "TEX", "Texas Rangers"),

        # EPL (likely broken)
        ("epl", "kalshi", "WHU", "West Ham United"),
        ("epl", "kalshi", "LFC", "Liverpool"),

        # NBA (check cross-sport issue)
        ("nba", "kalshi", "ATL", "Atlanta Hawks"),
        ("nba", "kalshi", "MIA", "Miami Heat"),
    ]

    for sport, source, input_name, expected in test_cases:
        context = NamingContext(sport=sport, source=source, name=input_name)
        result = resolver.resolve(context)

        status = "✓" if result == expected else "✗"
        print(f"{status} {sport.upper():4} {source:8} {input_name:15} → {result:25} (expected: {expected})")

    print("\n" + "=" * 60)
    print("Checking cross-sport contamination...")

    # Check if NBA abbreviations map to MLB teams (bad!)
    cross_sport_tests = [
        ("nba", "kalshi", "ATL", "Atlanta Braves"),  # MLB team!
        ("nba", "kalshi", "MIA", "Miami Marlins"),   # MLB team!
        ("nba", "kalshi", "CLE", "Cleveland Guardians"),  # MLB team!
    ]

    for sport, source, input_name, wrong_mapping in cross_sport_tests:
        context = NamingContext(sport=sport, source=source, name=input_name)
        result = resolver.resolve(context)

        if result == wrong_mapping:
            print(f"⚠️  CROSS-SPORT CONTAMINATION: {sport.upper()} {input_name} → {result} (should be NBA team!)")
        else:
            print(f"✓ {sport.upper():4} {input_name:15} → {result:25}")

if __name__ == "__main__":
    test_mappings()
