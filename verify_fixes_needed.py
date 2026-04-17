#!/usr/bin/env python3
"""Verify what name mappings need to be fixed."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'plugins'))

from naming_resolver import NamingResolver, NamingContext
import csv

def get_elo_team_names(sport):
    """Get team names from Elo ratings CSV."""
    csv_path = f"data/{sport}_current_elo_ratings.csv"
    teams = []
    if os.path.exists(csv_path):
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                teams.append(row['team'])
    return teams

def get_bet_team_names(sport):
    """Get team names from latest bet file."""
    import json
    import glob

    pattern = f"data/{sport}/bets_*.json"
    bet_files = sorted(glob.glob(pattern))
    if not bet_files:
        return []

    latest = bet_files[-1]
    with open(latest, 'r') as f:
        bets = json.load(f)

    teams = set()
    for bet in bets:
        teams.add(bet.get('home_team', ''))
        teams.add(bet.get('away_team', ''))

    return sorted(list(teams))

def analyze_sport(sport, resolver):
    """Analyze mapping gaps for a sport."""
    print(f"\n{sport.upper()} ANALYSIS:")
    print("-" * 60)

    # Get Elo team names (full names)
    elo_teams = get_elo_team_names(sport)
    print(f"Elo CSV teams ({len(elo_teams)}): {', '.join(elo_teams[:5])}...")

    # Get bet team names (abbreviations/mixed)
    bet_teams = get_bet_team_names(sport)
    print(f"Bet file teams ({len(bet_teams)}): {', '.join(bet_teams[:5])}...")

    # Check mappings
    print("\nMapping check:")
    missing_mappings = []
    working_mappings = []

    for bet_team in bet_teams[:10]:  # Check first 10
        context = NamingContext(sport=sport, source="kalshi", name=bet_team)
        result = resolver.resolve(context)

        if result == bet_team:
            # No mapping
            missing_mappings.append(bet_team)
            print(f"  ✗ {bet_team:20} → NO MAPPING")
        elif result in elo_teams:
            # Good mapping to Elo team
            working_mappings.append((bet_team, result))
            print(f"  ✓ {bet_team:20} → {result}")
        else:
            # Mapped but not to Elo team (cross-sport?)
            print(f"  ⚠️  {bet_team:20} → {result} (not in Elo CSV)")

    return missing_mappings, working_mappings

def main():
    print("TEAM NAME MAPPING ANALYSIS")
    print("=" * 60)

    resolver = NamingResolver()

    sports = ['epl', 'nba', 'mlb', 'nhl']
    all_missing = {}

    for sport in sports:
        missing, working = analyze_sport(sport, resolver)
        all_missing[sport] = missing

    print("\n" + "=" * 60)
    print("SUMMARY OF FIXES NEEDED:")

    for sport, missing in all_missing.items():
        if missing:
            print(f"\n{sport.upper()} needs {len(missing)} mappings:")
            for team in missing:
                print(f"  ('{sport}', 'kalshi', '{team.lower()}'): 'TODO',")
        else:
            print(f"\n{sport.upper()}: All mappings working ✓")

    print("\n" + "=" * 60)
    print("CROSS-SPORT CONTAMINATION CHECK:")

    # Check NBA for MLB contamination
    nba_context = NamingContext(sport="nba", source="kalshi", name="ATL")
    nba_result = resolver.resolve(nba_context)
    mlb_context = NamingContext(sport="mlb", source="kalshi", name="ATL")
    mlb_result = resolver.resolve(mlb_context)

    if nba_result == mlb_result:
        print(f"⚠️  NBA ATL maps to {nba_result} (same as MLB!)")
    else:
        print(f"✓ NBA ATL → {nba_result}, MLB ATL → {mlb_result}")

if __name__ == "__main__":
    main()
