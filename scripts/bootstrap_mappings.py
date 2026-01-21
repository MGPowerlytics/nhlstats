import sys
import os
from pathlib import Path
import pandas as pd
import re

# Add plugins directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))
from db_manager import default_db
from naming_resolver import NamingResolver


def bootstrap_mappings():
    print("🛠️  Performing Deep Mapping Bootstrap...")

    # 1. NHL (Abbrevs to Full)
    nhl_teams = {
        'ANA': 'Anaheim Ducks', 'BOS': 'Boston Bruins', 'BUF': 'Buffalo Sabres',
        'CAR': 'Carolina Hurricanes', 'CBJ': 'Columbus Blue Jackets', 'CGY': 'Calgary Flames',
        'CHI': 'Chicago Blackhawks', 'COL': 'Colorado Avalanche', 'DAL': 'Dallas Stars',
        'DET': 'Detroit Red Wings', 'EDM': 'Edmonton Oilers', 'FLA': 'Florida Panthers',
        'LAK': 'Los Angeles Kings', 'MIN': 'Minnesota Wild', 'MTL': 'Montreal Canadiens',
        'NSH': 'Nashville Predators', 'NJD': 'New Jersey Devils', 'NYI': 'New York Islanders',
        'NYR': 'New York Rangers', 'OTT': 'Ottawa Senators', 'PHI': 'Philadelphia Flyers',
        'PIT': 'Pittsburgh Penguins', 'SJS': 'San Jose Sharks', 'SEA': 'Seattle Kraken',
        'STL': 'St. Louis Blues', 'TBL': 'Tampa Bay Lightning', 'TOR': 'Toronto Maple Leafs',
        'VAN': 'Vancouver Canucks', 'VGK': 'Vegas Golden Knights', 'WSH': 'Washington Capitals',
        'WPG': 'Winnipeg Jets', 'ARI': 'Arizona Coyotes', 'UTA': 'Utah Hockey Club'
    }
    for abbrev, full in nhl_teams.items():
        NamingResolver.add_mapping('NHL', 'kalshi', abbrev, full)
        NamingResolver.add_mapping('NHL', 'the_odds_api', full, full)
        NamingResolver.add_mapping('NHL', 'elo', abbrev, full)

    # 2. Tennis (ATP/WTA) - Deeper Matching
    # Map Elo "Lastname I." -> Canonical Full Name
    # Map Kalshi/Sharp "Full Name" -> Canonical Full Name
    for tour in ['atp', 'wta']:
        try:
            df = pd.read_csv(f'data/{tour}_current_elo_ratings.csv')
            for elo_name in df['team']:
                # Example: "Alcaraz C."
                parts = elo_name.split()
                last_name = parts[0].strip(',')

                # We assume the Elo name IS the canonical name for now
                canonical = elo_name
                NamingResolver.add_mapping('TENNIS', 'elo', elo_name, canonical)
                NamingResolver.add_mapping('TENNIS', 'kalshi', last_name, canonical)
                NamingResolver.add_mapping('TENNIS', 'the_odds_api', last_name, canonical)

                # Also try to resolve from existing Unified Games to find "Full Names"
                # This helps bridge "Carlos Alcaraz" -> "Alcaraz C."
        except:
            continue

    # 3. Soccer (Common Aliases)
    soccer_teams = {
        'EPL': {
            'Man City': ['Manchester City'],
            'Man United': ['Manchester United'],
            'Tottenham': ['Spurs', 'Tottenham Hotspur'],
            'Nott\'m Forest': ['Nottingham Forest'],
            'Leicester': ['Leicester City']
        },
        'LIGUE1': {
            'Paris SG': ['PSG', 'Paris Saint Germain'],
            'Marseille': ['Olympique Marseille', 'Marseille'],
            'Lyon': ['Olympique Lyon', 'Lyon'],
            'St Etienne': ['Saint-Etienne']
        }
    }
    for sport, teams in soccer_teams.items():
        for canon, variants in teams.items():
            NamingResolver.add_mapping(sport, 'elo', canon, canon)
            NamingResolver.add_mapping(sport, 'the_odds_api', canon, canon)
            NamingResolver.add_mapping(sport, 'kalshi', canon, canon)
            for v in variants:
                NamingResolver.add_mapping(sport, 'the_odds_api', v, canon)
                NamingResolver.add_mapping(sport, 'kalshi', v, canon)

    print("✅ Deep Bootstrap Complete.")

if __name__ == "__main__":
    bootstrap_mappings()
