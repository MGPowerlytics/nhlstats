#!/usr/bin/env python3
"""
Load OddsHarvester JSON data into DuckDB historical_betting_lines table.
"""
import json
import duckdb
from datetime import datetime
from pathlib import Path
import re


# Team name mapping from OddsPortal to NHL abbreviations
TEAM_MAPPING = {
    # Full names to abbreviations
    'Anaheim Ducks': 'ANA',
    'Arizona Coyotes': 'ARI',
    'Boston Bruins': 'BOS',
    'Buffalo Sabres': 'BUF',
    'Calgary Flames': 'CGY',
    'Carolina Hurricanes': 'CAR',
    'Chicago Blackhawks': 'CHI',
    'Colorado Avalanche': 'COL',
    'Columbus Blue Jackets': 'CBJ',
    'Dallas Stars': 'DAL',
    'Detroit Red Wings': 'DET',
    'Edmonton Oilers': 'EDM',
    'Florida Panthers': 'FLA',
    'Los Angeles Kings': 'LAK',
    'Minnesota Wild': 'MIN',
    'Montreal Canadiens': 'MTL',
    'Nashville Predators': 'NSH',
    'New Jersey Devils': 'NJD',
    'New York Islanders': 'NYI',
    'New York Rangers': 'NYR',
    'Ottawa Senators': 'OTT',
    'Philadelphia Flyers': 'PHI',
    'Pittsburgh Penguins': 'PIT',
    'San Jose Sharks': 'SJS',
    'Seattle Kraken': 'SEA',
    'St. Louis Blues': 'STL',
    'Tampa Bay Lightning': 'TBL',
    'Toronto Maple Leafs': 'TOR',
    'Vancouver Canucks': 'VAN',
    'Vegas Golden Knights': 'VGK',
    'Washington Capitals': 'WSH',
    'Winnipeg Jets': 'WPG',
    # Short names without location
    'Ducks': 'ANA',
    'Coyotes': 'ARI',
    'Bruins': 'BOS',
    'Sabres': 'BUF',
    'Flames': 'CGY',
    'Hurricanes': 'CAR',
    'Blackhawks': 'CHI',
    'Avalanche': 'COL',
    'Blue Jackets': 'CBJ',
    'Stars': 'DAL',
    'Red Wings': 'DET',
    'Oilers': 'EDM',
    'Panthers': 'FLA',
    'Kings': 'LAK',
    'Wild': 'MIN',
    'Canadiens': 'MTL',
    'Predators': 'NSH',
    'Devils': 'NJD',
    'Islanders': 'NYI',
    'Rangers': 'NYR',
    'Senators': 'OTT',
    'Flyers': 'PHI',
    'Penguins': 'PIT',
    'Sharks': 'SJS',
    'Kraken': 'SEA',
    'Blues': 'STL',
    'Lightning': 'TBL',
    'Maple Leafs': 'TOR',
    'Canucks': 'VAN',
    'Golden Knights': 'VGK',
    'Capitals': 'WSH',
    'Jets': 'WPG',
}


def normalize_team_name(team_name):
    """Normalize team name to NHL abbreviation."""
    # Try direct mapping first
    if team_name in TEAM_MAPPING:
        return TEAM_MAPPING[team_name]
    
    # Try removing location prefix
    parts = team_name.split()
    if len(parts) > 1:
        # Try just the team name (e.g., "Boston Bruins" -> "Bruins")
        team_only = ' '.join(parts[1:])
        if team_only in TEAM_MAPPING:
            return TEAM_MAPPING[team_only]
    
    # If no mapping found, return original
    print(f"⚠️  No mapping for team: {team_name}")
    return team_name


def decimal_to_probability(decimal_odds):
    """Convert decimal odds to implied probability."""
    if decimal_odds is None or decimal_odds <= 0:
        return None
    
    # Decimal odds to probability: 1 / decimal_odds
    return 1.0 / decimal_odds


def decimal_to_american(decimal_odds):
    """Convert decimal odds to American moneyline."""
    if decimal_odds is None or decimal_odds <= 0:
        return None
    
    if decimal_odds >= 2.0:
        # Underdog: (decimal - 1) * 100
        return (decimal_odds - 1) * 100
    else:
        # Favorite: -100 / (decimal - 1)
        return -100 / (decimal_odds - 1)


def parse_decimal_odds(odds_str):
    """Parse decimal odds string (e.g., '1.50', '2.55') to float."""
    if not odds_str or odds_str == '-':
        return None
    
    try:
        return float(odds_str)
    except ValueError:
        return None


def load_oddsportal_json(json_file, db_path='data/nhlstats.duckdb'):
    """Load OddsHarvester JSON data into DuckDB."""
    print(f"\n{'='*80}")
    print(f"Loading OddsHarvester data from: {json_file}")
    print(f"{'='*80}\n")
    
    # Read JSON file
    with open(json_file, 'r') as f:
        matches = json.load(f)
    
    print(f"✅ Loaded {len(matches)} matches from JSON")
    
    # Connect to DuckDB
    conn = duckdb.connect(db_path)
    
    # Parse and insert records
    records = []
    skipped = 0
    
    for match in matches:
        try:
            # Extract basic info
            match_date_str = match.get('match_date', match.get('match_time', ''))
            if not match_date_str:
                skipped += 1
                continue
            
            # Parse date - handle various formats
            try:
                if 'T' in match_date_str or ' UTC' in match_date_str:
                    # ISO format with timezone
                    match_date_str = match_date_str.replace(' UTC', '')
                    match_date = datetime.fromisoformat(match_date_str.replace('Z', '+00:00')).date()
                else:
                    # Try other formats
                    match_date = datetime.strptime(match_date_str, '%d %b %Y').date()
            except:
                print(f"⚠️  Could not parse date: {match_date_str}")
                skipped += 1
                continue
            
            # Extract teams
            home_team_raw = match.get('home_team', '')
            away_team_raw = match.get('away_team', '')
            
            if not home_team_raw or not away_team_raw:
                skipped += 1
                continue
            
            home_team = normalize_team_name(home_team_raw)
            away_team = normalize_team_name(away_team_raw)
            
            # Extract odds from home_away_market (OddsHarvester format)
            home_away_market = match.get('home_away_market', [])
            
            if not home_away_market or not isinstance(home_away_market, list):
                skipped += 1
                continue
            
            # Get odds from bookmakers - use first and last for open/close
            # Filter for FullTime period only
            fulltime_odds = [b for b in home_away_market if b.get('period') == 'FullTime']
            
            if not fulltime_odds:
                skipped += 1
                continue
            
            # Use first bookmaker as opening odds
            first_book = fulltime_odds[0]
            home_odds_dec = parse_decimal_odds(first_book.get('1'))
            away_odds_dec = parse_decimal_odds(first_book.get('2'))
            
            if home_odds_dec is None or away_odds_dec is None:
                skipped += 1
                continue
            
            # Convert decimal to American moneyline
            home_odds = decimal_to_american(home_odds_dec)
            away_odds = decimal_to_american(away_odds_dec)
            
            # Use last bookmaker as closing odds (or same if only one)
            if len(fulltime_odds) > 1:
                last_book = fulltime_odds[-1]
                home_close_dec = parse_decimal_odds(last_book.get('1'))
                away_close_dec = parse_decimal_odds(last_book.get('2'))
                
                if home_close_dec and away_close_dec:
                    home_close = decimal_to_american(home_close_dec)
                    away_close = decimal_to_american(away_close_dec)
                else:
                    home_close = home_odds
                    away_close = away_odds
            else:
                home_close = home_odds
                away_close = away_odds
            
            # Calculate implied probabilities from decimal odds
            home_prob_open = decimal_to_probability(home_odds_dec)
            away_prob_open = decimal_to_probability(away_odds_dec)
            
            if len(fulltime_odds) > 1:
                home_prob_close = decimal_to_probability(home_close_dec)
                away_prob_close = decimal_to_probability(away_close_dec)
            else:
                home_prob_close = home_prob_open
                away_prob_close = away_prob_open
            
            # Calculate line movement (positive = moved in home team's favor)
            if home_prob_close and home_prob_open:
                line_movement = home_prob_close - home_prob_open
            else:
                line_movement = 0.0
            
            records.append({
                'game_date': match_date,
                'home_team': home_team,
                'away_team': away_team,
                'home_ml_open': home_odds,
                'home_ml_close': home_close,
                'away_ml_open': away_odds,
                'away_ml_close': away_close,
                'home_implied_prob_open': home_prob_open,
                'home_implied_prob_close': home_prob_close,
                'away_implied_prob_open': away_prob_open,
                'away_implied_prob_close': away_prob_close,
                'line_movement': line_movement,
                'source': 'OddsPortal',
                'fetched_at': datetime.now()
            })
            
        except Exception as e:
            print(f"⚠️  Error parsing match: {e}")
            skipped += 1
            continue
    
    print(f"✅ Parsed {len(records)} valid records")
    print(f"⚠️  Skipped {skipped} matches (missing data or parse errors)")
    
    if not records:
        print("❌ No records to insert!")
        return
    
    # Insert into DuckDB
    print(f"\n💾 Inserting into DuckDB...")
    
    # Delete existing records from same source and date range
    dates = [r['game_date'] for r in records]
    min_date = min(dates)
    max_date = max(dates)
    
    delete_result = conn.execute("""
        DELETE FROM historical_betting_lines 
        WHERE source = 'OddsPortal' 
        AND game_date BETWEEN ? AND ?
    """, [min_date, max_date])
    
    deleted_count = delete_result.fetchone()[0] if delete_result else 0
    print(f"🗑️  Deleted {deleted_count} existing OddsPortal records from {min_date} to {max_date}")
    
    # Insert new records
    conn.executemany("""
        INSERT INTO historical_betting_lines VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [(
        r['game_date'],
        r['home_team'],
        r['away_team'],
        r['home_ml_open'],
        r['home_ml_close'],
        r['away_ml_open'],
        r['away_ml_close'],
        r['home_implied_prob_open'],
        r['home_implied_prob_close'],
        r['away_implied_prob_open'],
        r['away_implied_prob_close'],
        r['line_movement'],
        r['source'],
        r['fetched_at']
    ) for r in records])
    
    print(f"✅ Inserted {len(records)} records into historical_betting_lines")
    
    # Show summary stats
    stats = conn.execute("""
        SELECT 
            COUNT(*) as total_records,
            MIN(game_date) as earliest_game,
            MAX(game_date) as latest_game,
            COUNT(DISTINCT home_team) as unique_teams,
            AVG(home_implied_prob_close) as avg_home_prob
        FROM historical_betting_lines
        WHERE source = 'OddsPortal'
    """).fetchone()
    
    print(f"\n📊 Database Summary (OddsPortal):")
    print(f"   Total Records: {stats[0]}")
    print(f"   Date Range: {stats[1]} to {stats[2]}")
    print(f"   Unique Teams: {stats[3]}")
    print(f"   Avg Home Win Prob: {stats[4]:.1%}")
    
    conn.close()
    print(f"\n{'='*80}")
    print(f"✅ Successfully loaded OddsHarvester data!")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python load_odds_harvester_data.py <json_file> [db_path]")
        print("\nExample:")
        print("  python load_odds_harvester_data.py data/historical_odds/nhl_2023_2024.json")
        sys.exit(1)
    
    json_file = sys.argv[1]
    db_path = sys.argv[2] if len(sys.argv) > 2 else 'data/nhlstats.duckdb'
    
    if not Path(json_file).exists():
        print(f"❌ File not found: {json_file}")
        sys.exit(1)
    
    load_oddsportal_json(json_file, db_path)
