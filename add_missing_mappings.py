#!/usr/bin/env python3
"""Add missing team name mappings to naming_resolver.py."""

import re

# EPL mappings (abbreviation → full name from Elo CSV)
epl_mappings = {
    # From bet abbreviations to Elo CSV names
    "WHU": "West Ham",
    "WOL": "Wolves",
    "LFC": "Liverpool",
    "FUL": "Fulham",
    "MCI": "Man City",
    "MUN": "Man United",
    "CHE": "Chelsea",
    "CFC": "Chelsea",  # Alternative
    "TOT": "Tottenham",
    "ARS": "Arsenal",
    "AVL": "Aston Villa",
    "NEW": "Newcastle",
    "BHA": "Brighton",  # Note: Bet uses BRI, Elo uses Brighton
    "BRI": "Brighton",
    "CRY": "Crystal Palace",
    "BRE": "Brentford",
    "EVE": "Everton",
    "LEE": "Leeds",
    "LEI": "Leicester",
    "SOU": "Southampton",
    "BOU": "Bournemouth",
    "NFO": "Nott'm Forest",
    "SUN": "Sunderland",
    # Full names that should pass through
    "Arsenal": "Arsenal",
    "Bournemouth": "Bournemouth",
    "Brighton and Hove Albion": "Brighton",
    "Burnley": "Burnley",
    "Chelsea": "Chelsea",
    "Leeds United": "Leeds",
    "Manchester City": "Man City",
    "Manchester United": "Man United",
    "Sunderland": "Sunderland",
    "Tottenham Hotspur": "Tottenham",
}

# NBA mappings to prevent cross-sport contamination
nba_mappings = {
    "ATL": "Atlanta Hawks",
    "MIA": "Miami Heat",
    "CLE": "Cleveland Cavaliers",
    "LAL": "Los Angeles Lakers",
    "GSW": "Golden State Warriors",
    "BOS": "Boston Celtics",
    "CHI": "Chicago Bulls",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "HOU": "Houston Rockets",
    "LAC": "Los Angeles Clippers",
    "MEM": "Memphis Grizzlies",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
}

def add_mappings_to_file():
    """Add mappings to naming_resolver.py."""
    with open('plugins/naming_resolver.py', 'r') as f:
        content = f.read()

    # Find where to insert (after existing mappings, before resolve method)
    # Look for the last mapping entry
    lines = content.split('\n')

    # Find the line with the last mapping
    last_mapping_line = -1
    for i, line in enumerate(lines):
        if '("ncaab"' in line or '("nhl"' in line or '("mlb"' in line or '("nba"' in line or '("epl"' in line:
            last_mapping_line = i

    if last_mapping_line == -1:
        print("Could not find where to insert mappings")
        return

    # Build new mapping lines
    new_mappings = []

    # Add EPL mappings
    for abbrev, full_name in epl_mappings.items():
        new_mappings.append(f'        ("epl", "kalshi", "{abbrev.lower()}"): "{full_name}",')

    # Add NBA mappings
    for abbrev, full_name in nba_mappings.items():
        new_mappings.append(f'        ("nba", "kalshi", "{abbrev.lower()}"): "{full_name}",')

    # Insert after the last mapping line
    insertion_point = last_mapping_line + 1
    lines = lines[:insertion_point] + new_mappings + lines[insertion_point:]

    # Write back
    with open('plugins/naming_resolver.py', 'w') as f:
        f.write('\n'.join(lines))

    print(f"Added {len(epl_mappings)} EPL mappings and {len(nba_mappings)} NBA mappings")
    print("Mappings added successfully!")

def test_mappings():
    """Test that the mappings work."""
    import sys
    sys.path.insert(0, 'plugins')

    from naming_resolver import NamingResolver, NamingContext

    resolver = NamingResolver()

    print("\nTesting EPL mappings:")
    test_cases = [
        ("WHU", "West Ham"),
        ("LFC", "Liverpool"),
        ("MCI", "Man City"),
        ("Arsenal", "Arsenal"),  # Should pass through
    ]

    for abbrev, expected in test_cases:
        context = NamingContext(sport="epl", source="kalshi", name=abbrev)
        result = resolver.resolve(context)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {abbrev} → {result} (expected: {expected})")

    print("\nTesting NBA mappings (no cross-sport contamination):")
    nba_test_cases = [
        ("ATL", "Atlanta Hawks"),  # NOT Atlanta Braves
        ("MIA", "Miami Heat"),     # NOT Miami Marlins
        ("CLE", "Cleveland Cavaliers"),  # NOT Cleveland Guardians
    ]

    for abbrev, expected in nba_test_cases:
        context = NamingContext(sport="nba", source="kalshi", name=abbrev)
        result = resolver.resolve(context)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {abbrev} → {result} (expected: {expected})")

        # Also check MLB to ensure it still works
        mlb_context = NamingContext(sport="mlb", source="kalshi", name=abbrev)
        mlb_result = resolver.resolve(mlb_context)
        if abbrev == "ATL" and mlb_result == "Atlanta Braves":
            print(f"    ✓ MLB {abbrev} → {mlb_result} (correct)")

if __name__ == "__main__":
    print("Adding missing team name mappings...")
    add_mappings_to_file()
    test_mappings()
