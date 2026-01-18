#!/usr/bin/env python3
"""
Fetch Daily NHL Betting Odds (Free Sources)

Scrapes current day's betting odds from free sources:
1. OddsShark.com (no API key required)
2. TheScore.com (public odds data)
3. The Odds API (free tier backup)

Called by Airflow DAG daily at 9am.
"""

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, date
import duckdb
from pathlib import Path
import time


def scrape_oddsshark():
    """
    Scrape NHL odds from OddsShark.com
    
    Free, no API key required, reliable.
    """
    print("🦈 Scraping OddsShark.com...")
    
    url = "https://www.oddsshark.com/nhl/odds"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        games = []
        
        # Find game rows (structure may vary)
        game_rows = soup.find_all('div', class_='op-matchup-wrapper')
        
        for row in game_rows:
            try:
                # Extract teams
                teams = row.find_all('div', class_='op-matchup-team')
                if len(teams) < 2:
                    continue
                
                away_team = teams[0].find('span', class_='op-team-name').text.strip()
                home_team = teams[1].find('span', class_='op-team-name').text.strip()
                
                # Extract moneylines
                odds = row.find_all('div', class_='op-item-moneyline')
                if len(odds) < 2:
                    continue
                
                away_ml = odds[0].text.strip()
                home_ml = odds[1].text.strip()
                
                # Extract game time
                game_time = row.find('div', class_='op-matchup-time')
                game_time_str = game_time.text.strip() if game_time else None
                
                games.append({
                    'away_team': away_team,
                    'home_team': home_team,
                    'away_ml': away_ml,
                    'home_ml': home_ml,
                    'game_time': game_time_str,
                    'source': 'oddsshark'
                })
                
            except Exception as e:
                continue
        
        print(f"   ✅ Found {len(games)} games")
        return games
        
    except Exception as e:
        print(f"   ❌ Error scraping OddsShark: {e}")
        return []


def scrape_thescore():
    """
    Scrape NHL odds from TheScore.com
    
    Alternative free source, good mobile API.
    """
    print("📱 Fetching from TheScore.com...")
    
    # TheScore has a public API for their mobile app
    url = "https://api.thescore.com/nhl/events"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)',
    }
    
    params = {
        'date': date.today().isoformat()
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        games = []
        
        for event in data:
            try:
                away_team = event['away_team']['display_name']
                home_team = event['home_team']['display_name']
                
                # Extract betting lines if available
                betting = event.get('betting', {})
                odds = betting.get('odds', {})
                
                away_ml = odds.get('away_ml')
                home_ml = odds.get('home_ml')
                
                games.append({
                    'away_team': away_team,
                    'home_team': home_team,
                    'away_ml': away_ml,
                    'home_ml': home_ml,
                    'game_time': event.get('game_date'),
                    'source': 'thescore'
                })
                
            except Exception as e:
                continue
        
        print(f"   ✅ Found {len(games)} games")
        return games
        
    except Exception as e:
        print(f"   ❌ Error fetching TheScore: {e}")
        return []


def fetch_odds_api_free(api_key=None):
    """
    Fetch from The Odds API (free tier: 500 requests/month)
    
    Sign up: https://the-odds-api.com/
    """
    import os
    
    if api_key is None:
        api_key = os.environ.get('ODDS_API_KEY')
    
    if not api_key:
        print("⚠️  ODDS_API_KEY not set, skipping...")
        return []
    
    print("🔑 Fetching from The Odds API...")
    
    url = "https://api.the-odds-api.com/v4/sports/icehockey_nhl/odds/"
    
    params = {
        'apiKey': api_key,
        'regions': 'us',
        'markets': 'h2h',  # Moneyline only
        'oddsFormat': 'american'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        games = []
        
        for game in data:
            home_team = game['home_team']
            away_team = game['away_team']
            
            # Get first bookmaker's odds (or average)
            if game.get('bookmakers'):
                bookmaker = game['bookmakers'][0]
                markets = bookmaker.get('markets', [])
                
                if markets:
                    outcomes = markets[0].get('outcomes', [])
                    
                    home_ml = next((o['price'] for o in outcomes if o['name'] == home_team), None)
                    away_ml = next((o['price'] for o in outcomes if o['name'] == away_team), None)
                    
                    games.append({
                        'away_team': away_team,
                        'home_team': home_team,
                        'away_ml': away_ml,
                        'home_ml': home_ml,
                        'game_time': game['commence_time'],
                        'source': 'odds_api'
                    })
        
        print(f"   ✅ Found {len(games)} games")
        
        # Show remaining quota
        remaining = response.headers.get('x-requests-remaining')
        if remaining:
            print(f"   📊 API quota remaining: {remaining}/500")
        
        return games
        
    except Exception as e:
        print(f"   ❌ Error fetching Odds API: {e}")
        return []


def normalize_team_name(team_name):
    """
    Normalize team names to match our database abbreviations.
    """
    mapping = {
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
    
    # Try to find team name in mapping
    for key, value in mapping.items():
        if key in team_name:
            return value
    
    return team_name  # Return as-is if not found


def parse_moneyline(ml_str):
    """
    Parse moneyline string to float.
    
    Examples: '+150', '-200', 'EV' (even)
    """
    if not ml_str or ml_str == 'EV':
        return 100.0  # Even money
    
    try:
        return float(str(ml_str).replace('+', ''))
    except:
        return None


def calculate_implied_probability(moneyline):
    """Convert American moneyline to implied probability."""
    if not moneyline:
        return None
    
    if moneyline < 0:
        return abs(moneyline) / (abs(moneyline) + 100)
    else:
        return 100 / (moneyline + 100)


def save_to_database(games, db_path='data/nhlstats.duckdb'):
    """
    Save daily odds to database.
    """
    if not games:
        print("⚠️  No games to save")
        return
    
    conn = duckdb.connect(db_path)
    
    # Create table for daily odds
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_betting_lines (
            fetch_date DATE NOT NULL,
            game_date DATE,
            home_team VARCHAR NOT NULL,
            away_team VARCHAR NOT NULL,
            home_ml DECIMAL,
            away_ml DECIMAL,
            home_implied_prob DECIMAL,
            away_implied_prob DECIMAL,
            source VARCHAR,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (fetch_date, home_team, away_team, source)
        )
    """)
    
    # Process games
    records = []
    for game in games:
        # Normalize team names
        away_abbrev = normalize_team_name(game['away_team'])
        home_abbrev = normalize_team_name(game['home_team'])
        
        # Parse moneylines
        away_ml = parse_moneyline(game['away_ml'])
        home_ml = parse_moneyline(game['home_ml'])
        
        record = {
            'fetch_date': date.today(),
            'game_date': date.today(),  # Assume today's games
            'home_team': home_abbrev,
            'away_team': away_abbrev,
            'home_ml': home_ml,
            'away_ml': away_ml,
            'home_implied_prob': calculate_implied_probability(home_ml),
            'away_implied_prob': calculate_implied_probability(away_ml),
            'source': game['source'],
        }
        records.append(record)
    
    # Insert
    try:
        import pandas as pd
        df = pd.DataFrame(records)
        
        conn.execute("""
            INSERT INTO daily_betting_lines 
            SELECT * FROM df
            ON CONFLICT DO UPDATE SET
                home_ml = EXCLUDED.home_ml,
                away_ml = EXCLUDED.away_ml,
                home_implied_prob = EXCLUDED.home_implied_prob,
                away_implied_prob = EXCLUDED.away_implied_prob,
                fetched_at = CURRENT_TIMESTAMP
        """)
        
        print(f"\n✅ Saved {len(records)} betting lines to database")
        
    except Exception as e:
        print(f"❌ Error saving to database: {e}")
    finally:
        conn.close()


def fetch_and_save_odds(target_date=None):
    """
    Fetch and save daily odds for a specific date (for Airflow integration).
    
    Args:
        target_date: Optional date string (YYYY-MM-DD). Defaults to today.
        
    Returns:
        Number of games with odds fetched
    """
    if target_date:
        print(f"🏒 Fetching NHL odds for {target_date}")
    else:
        print(f"🏒 Fetching NHL odds for today")
    
    all_games = []
    
    # Try multiple sources (fallback if one fails)
    oddsshark_games = scrape_oddsshark()
    all_games.extend(oddsshark_games)
    
    time.sleep(2)
    
    if not all_games:
        thescore_games = scrape_thescore()
        all_games.extend(thescore_games)
        time.sleep(2)
    
    if not all_games:
        odds_api_games = fetch_odds_api_free()
        all_games.extend(odds_api_games)
    
    if all_games:
        print(f"📊 Fetched {len(all_games)} games with odds")
        save_to_database(all_games)
        return len(all_games)
    else:
        print("❌ No odds fetched from any source")
        return 0


def main():
    """
    Main function to fetch daily odds from multiple sources.
    """
    print("=" * 80)
    print("🏒 NHL Daily Betting Odds Fetcher")
    print(f"📅 {date.today().strftime('%A, %B %d, %Y')}")
    print("=" * 80)
    
    all_games = []
    
    # Try multiple sources (fallback if one fails)
    
    # 1. OddsShark (most reliable)
    oddsshark_games = scrape_oddsshark()
    all_games.extend(oddsshark_games)
    
    time.sleep(2)  # Be polite
    
    # 2. TheScore
    if not all_games:  # Only try if OddsShark failed
        thescore_games = scrape_thescore()
        all_games.extend(thescore_games)
        time.sleep(2)
    
    # 3. The Odds API (backup, uses quota)
    if not all_games:  # Only if others failed
        odds_api_games = fetch_odds_api_free()
        all_games.extend(odds_api_games)
    
    # Display results
    if all_games:
        print(f"\n📊 Fetched {len(all_games)} games with odds:\n")
        for game in all_games:
            print(f"   {game['away_team']:>3} @ {game['home_team']:<3}  "
                  f"ML: {game['away_ml']:>6} / {game['home_ml']:<6}  "
                  f"({game['source']})")
        
        # Save to database
        print("\n💾 Saving to database...")
        save_to_database(all_games)
    else:
        print("\n❌ No odds fetched. All sources failed.")
        return 1
    
    print("\n" + "=" * 80)
    print("✅ Daily odds fetch complete!")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
