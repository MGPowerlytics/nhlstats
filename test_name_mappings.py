#!/usr/bin/env python3
"""Test script for team name mapping fixes."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'plugins'))

from naming_resolver import NamingResolver

def test_current_mappings():
    """Test current mappings to identify gaps."""
    resolver = NamingResolver()

    print("=" * 80)
    print("TEAM NAME MAPPING TEST - CURRENT STATE")
    print("=" * 80)

    # Test cases from actual bet files
    test_cases = [
        # EPL (most broken)
        ("epl", "kalshi", "WHU"),
        ("epl", "kalshi", "WOL"),
        ("epl", "kalshi", "LFC"),
        ("epl", "kalshi", "FUL"),
        ("epl", "kalshi", "Arsenal"),
        ("epl", "kalshi", "Bournemouth"),

        # NBA (cross-sport contamination)
        ("nba", "kalshi", "ATL"),
        ("nba", "kalshi", "MIA"),
        ("nba", "kalshi", "CLE"),
        ("nba", "kalshi", "LAL"),
        ("nba", "kalshi", "GSW"),

        # MLB (should work after our fix)
        ("mlb", "kalshi", "LAD"),
        ("mlb", "kalshi", "TEX"),
        ("mlb", "kalshi", "HOU"),
        ("mlb", "kalshi", "SEA"),
        ("mlb", "kalshi", "Los Angeles Dodgers"),
        ("mlb", "kalshi", "Texas Rangers"),

        # NHL (should work)
        ("nhl", "kalshi", "ANA"),
        ("nhl", "kalshi", "BOS"),
        ("nhl", "kalshi", "CHI"),
        ("nhl", "kalshi", "DET"),
    ]

    results = []
    for sport, source, name in test_cases:
        try:
            context = NamingContext(sport=sport, source=source, name=name)
            resolved = resolver.resolve(context)
            status = "✓" if resolved != name and resolved != "Unknown" else "✗"
            if resolved == name:
                note = "NO MAPPING"
            elif resolved == "Unknown":
                note = "UNKNOWN"
            else:
                note = "MAPPED"
        except Exception as e:
            resolved = f"ERROR: {e}"
            status = "✗"
            note = "ERROR"

        results.append({
            'sport': sport,
            'source': source,
            'input': name,
            'output': resolved,
            'status': status,
            'note': note
        })

    # Print results by sport
    for sport in ['epl', 'nba', 'mlb', 'nhl']:
        sport_results = [r for r in results if r['sport'] == sport]
        print(f"\n{sport.upper()} MAPPINGS:")
        print("-" * 60)
        for r in sport_results:
            print(f"  {r['status']} {r['input']:25} → {r['output']:30} ({r['note']})")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY:")
    total = len(results)
    working = sum(1 for r in results if r['status'] == '✓')
    broken = sum(1 for r in results if r['status'] == '✗')

    print(f"Total tests: {total}")
    print(f"Working mappings: {working} ({working/total*100:.1f}%)")
    print(f"Broken mappings: {broken} ({broken/total*100:.1f}%)")

    # Sport-specific breakdown
    print("\nBy sport:")
    for sport in ['epl', 'nba', 'mlb', 'nhl']:
        sport_results = [r for r in results if r['sport'] == sport]
        sport_working = sum(1 for r in sport_results if r['status'] == '✓')
        sport_total = len(sport_results)
        print(f"  {sport.upper():4}: {sport_working}/{sport_total} ({sport_working/sport_total*100:.1f}%)")

    print("=" * 80)

if __name__ == "__main__":
    test_current_mappings()
