#!/usr/bin/env python3
"""
Load Historical Betting Odds from Sportsbook Review

Download Excel files manually from:
https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl/nhloddsarchives.htm

Save them to: data/historical_odds/

This script will parse and load them into DuckDB.
"""

import pandas as pd
from pathlib import Path
import duckdb
from datetime import datetime
import re

# Team abbreviation mapping (SBR format -> NHL format)
TEAM_MAPPING = {
    'Anaheim': 'ANA',
    'Arizona': 'ARI',
    'Boston': 'BOS',
    'Buffalo': 'BUF',
    'Calgary': 'CGY',
    'Carolina': 'CAR',
    'Chicago': 'CHI',
    'Colorado': 'COL',
    'Columbus': 'CBJ',
    'Dallas': 'DAL',
    'Detroit': 'DET',
    'Edmonton': 'EDM',
    'Florida': 'FLA',
    'Los Angeles': 'LAK',
    'Minnesota': 'MIN',
    'Montreal': 'MTL',
    'Nashville': 'NSH',
    'New Jersey': 'NJD',
    'NY Islanders': 'NYI',
    'NY Rangers': 'NYR',
    'Ottawa': 'OTT',
    'Philadelphia': 'PHI',
    'Pittsburgh': 'PIT',
    'San Jose': 'SJS',
    'Seattle': 'SEA',
    'St. Louis': 'STL',
    'Tampa Bay': 'TBL',
    'Toronto': 'TOR',
    'Vancouver': 'VAN',
    'Vegas': 'VGK',
    'Washington': 'WSH',
    'Winnipeg': 'WPG',
}


def parse_sbr_excel(excel_path):
    """
    Parse Sportsbook Review Excel file into game records.
    
    SBR format has paired rows (Visitor/Home) for each game.
    Columns typically: Date, Rot, VH, Team, 1st, 2nd, 3rd, Final, Open, Close, ML
    """
    print(f"📄 Parsing {excel_path.name}...")
    
    try:
        # Read Excel file
        df = pd.read_excel(excel_path)
        
        # Clean column names
        df.columns = df.columns.str.strip().str.lower()
        
        # Find the date column (might be 'date' or unnamed)
        date_col = 'date' if 'date' in df.columns else df.columns[0]
        
        games = []
        i = 0
        
        while i < len(df) - 1:
            visitor_row = df.iloc[i]
            home_row = df.iloc[i + 1]
            
            # Check if this is a valid game pair (both have same date)
            visitor_vh = str(visitor_row.get('vh', visitor_row.get('v/h', ''))).strip().upper()
            home_vh = str(home_row.get('vh', home_row.get('v/h', ''))).strip().upper()
            
            if visitor_vh == 'V' and home_vh == 'H':
                # Parse game data
                try:
                    game_date = pd.to_datetime(visitor_row[date_col])
                    
                    # Extract team names
                    visitor_team = str(visitor_row.get('team', '')).strip()
                    home_team = str(home_row.get('team', '')).strip()
                    
                    # Map to abbreviations
                    away_abbrev = TEAM_MAPPING.get(visitor_team, visitor_team)
                    home_abbrev = TEAM_MAPPING.get(home_team, home_team)
                    
                    # Extract scores
                    visitor_score = visitor_row.get('final', visitor_row.get('fin', None))
                    home_score = home_row.get('final', home_row.get('fin', None))
                    
                    # Extract odds (ML = moneyline)
                    # Open and Close columns
                    away_ml_open = visitor_row.get('open', None)
                    home_ml_open = home_row.get('open', None)
                    away_ml_close = visitor_row.get('close', None)
                    home_ml_close = home_row.get('close', None)
                    
                    # Sometimes ML is in separate column
                    if pd.isna(away_ml_close) and 'ml' in df.columns:
                        away_ml_close = visitor_row.get('ml', None)
                        home_ml_close = home_row.get('ml', None)
                    
                    game = {
                        'game_date': game_date.date(),
                        'away_team': away_abbrev,
                        'home_team': home_abbrev,
                        'away_score': int(visitor_score) if pd.notna(visitor_score) else None,
                        'home_score': int(home_score) if pd.notna(home_score) else None,
                        'away_ml_open': float(away_ml_open) if pd.notna(away_ml_open) else None,
                        'home_ml_open': float(home_ml_open) if pd.notna(home_ml_open) else None,
                        'away_ml_close': float(away_ml_close) if pd.notna(away_ml_close) else None,
                        'home_ml_close': float(home_ml_close) if pd.notna(home_ml_close) else None,
                        'source': 'sportsbook_review',
                    }
                    games.append(game)
                
                except Exception as e:
                    print(f"   ⚠️  Error parsing row {i}: {e}")
                
                i += 2  # Move to next game pair
            else:
                i += 1  # Skip this row
        
        print(f"   ✅ Parsed {len(games)} games")
        return games
    
    except Exception as e:
        print(f"   ❌ Error reading Excel: {e}")
        return []


def calculate_implied_probability(moneyline):
    """
    Convert American moneyline odds to implied probability.
    
    Examples:
        -200 -> 66.7% (favorite)
        +150 -> 40.0% (underdog)
    """
    if pd.isna(moneyline) or moneyline == 0:
        return None
    
    if moneyline < 0:
        # Favorite
        return abs(moneyline) / (abs(moneyline) + 100)
    else:
        # Underdog
        return 100 / (moneyline + 100)


def load_to_database(games, db_path='data/nhlstats.duckdb'):
    """
    Load parsed games with betting lines into DuckDB.
    """
    if not games:
        print("⚠️  No games to load")
        return
    
    conn = duckdb.connect(db_path)
    
    # Create table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS historical_betting_lines (
            game_date DATE NOT NULL,
            home_team VARCHAR NOT NULL,
            away_team VARCHAR NOT NULL,
            home_ml_open DECIMAL,
            away_ml_open DECIMAL,
            home_ml_close DECIMAL,
            away_ml_close DECIMAL,
            home_implied_prob_open DECIMAL,
            away_implied_prob_open DECIMAL,
            home_implied_prob_close DECIMAL,
            away_implied_prob_close DECIMAL,
            line_movement DECIMAL,
            home_score INTEGER,
            away_score INTEGER,
            source VARCHAR,
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (game_date, home_team, away_team)
        )
    """)
    
    # Calculate implied probabilities and line movement
    for game in games:
        game['home_implied_prob_open'] = calculate_implied_probability(game['home_ml_open'])
        game['away_implied_prob_open'] = calculate_implied_probability(game['away_ml_open'])
        game['home_implied_prob_close'] = calculate_implied_probability(game['home_ml_close'])
        game['away_implied_prob_close'] = calculate_implied_probability(game['away_ml_close'])
        
        # Line movement (opening to closing)
        if game['home_ml_open'] and game['home_ml_close']:
            game['line_movement'] = game['home_ml_close'] - game['home_ml_open']
        else:
            game['line_movement'] = None
    
    # Convert to DataFrame
    df = pd.DataFrame(games)
    
    # Insert (ON CONFLICT DO NOTHING to avoid duplicates)
    try:
        conn.execute("""
            INSERT INTO historical_betting_lines 
            SELECT 
                game_date,
                home_team,
                away_team,
                home_ml_open,
                away_ml_open,
                home_ml_close,
                away_ml_close,
                home_implied_prob_open,
                away_implied_prob_open,
                home_implied_prob_close,
                away_implied_prob_close,
                line_movement,
                home_score,
                away_score,
                source
            FROM df
            ON CONFLICT DO NOTHING
        """)
        
        total_count = conn.execute("SELECT COUNT(*) FROM historical_betting_lines").fetchone()[0]
        print(f"\n✅ Database now has {total_count:,} games with betting lines")
        
    except Exception as e:
        print(f"❌ Error loading to database: {e}")
    finally:
        conn.close()


def main():
    print("=" * 80)
    print("🏒 Load Historical NHL Betting Odds from Sportsbook Review")
    print("=" * 80)
    
    # Check for Excel files in data/historical_odds/
    odds_dir = Path('data/historical_odds')
    
    if not odds_dir.exists():
        print(f"\n❌ Directory not found: {odds_dir}")
        print("\n📥 Please download NHL odds Excel files from:")
        print("   https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl/nhloddsarchives.htm")
        print(f"\n   Save them to: {odds_dir}/")
        print("\n   Then run this script again.")
        return
    
    # Find Excel files
    excel_files = list(odds_dir.glob('*.xlsx')) + list(odds_dir.glob('*.xls'))
    
    if not excel_files:
        print(f"\n❌ No Excel files found in {odds_dir}")
        print("\n📥 Please download NHL odds Excel files and save to this directory")
        return
    
    print(f"\n📂 Found {len(excel_files)} Excel files:\n")
    for f in excel_files:
        print(f"   - {f.name}")
    
    # Parse all files
    all_games = []
    
    for excel_file in excel_files:
        games = parse_sbr_excel(excel_file)
        all_games.extend(games)
    
    print(f"\n📊 Total games parsed: {len(all_games):,}")
    
    if all_games:
        # Load to database
        print("\n💾 Loading to database...")
        load_to_database(all_games)
        
        # Show sample
        print("\n📋 Sample records:")
        df = pd.DataFrame(all_games[:5])
        print(df[['game_date', 'away_team', 'home_team', 'away_ml_close', 'home_ml_close']].to_string(index=False))
    
    print("\n" + "=" * 80)
    print("✅ Historical odds loading complete!")
    print("=" * 80)
    print("\n📌 Next Steps:")
    print("   1. Add betting line features to training dataset")
    print("   2. Retrain model with odds features")
    print("   3. Set up daily odds fetching in Airflow DAG\n")


if __name__ == "__main__":
    main()
