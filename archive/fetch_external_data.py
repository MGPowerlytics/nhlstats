#!/usr/bin/env python3
"""
Fetch External Data (Morning-of-Game)

This script fetches external data sources that are available the morning of the game:
1. Starting goalies (DailyFaceoff, NHL API)
2. Betting lines (The Odds API, sportsbooks)
3. Injury reports (NHL official injury report)

Run this script in the morning (9-11am) before making predictions.
"""

import requests
import json
from datetime import datetime, date
from pathlib import Path
import duckdb

# ============================================================================
# 1. STARTING GOALIES
# ============================================================================

def fetch_nhl_api_probable_goalies(game_date=None):
    """
    Fetch probable starting goalies from NHL API.
    
    Args:
        game_date: YYYY-MM-DD string, defaults to today
    
    Returns:
        List of dicts with game_id, home_goalie_id, away_goalie_id
    """
    if game_date is None:
        game_date = date.today().isoformat()
    
    url = f"https://api-web.nhle.com/v1/schedule/{game_date}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        goalies = []
        for game_week in data.get('gameWeek', []):
            for game in game_week.get('games', []):
                goalie_info = {
                    'game_id': game['id'],
                    'game_date': game_date,
                    'home_team': game['homeTeam']['abbrev'],
                    'away_team': game['awayTeam']['abbrev'],
                    'home_goalie_id': game.get('homeTeam', {}).get('probableGoalie', {}).get('id'),
                    'home_goalie_name': game.get('homeTeam', {}).get('probableGoalie', {}).get('name', {}).get('default'),
                    'away_goalie_id': game.get('awayTeam', {}).get('probableGoalie', {}).get('id'),
                    'away_goalie_name': game.get('awayTeam', {}).get('probableGoalie', {}).get('name', {}).get('default'),
                    'source': 'nhl_api',
                    'fetched_at': datetime.now().isoformat()
                }
                goalies.append(goalie_info)
        
        return goalies
    
    except Exception as e:
        print(f"Error fetching NHL API goalies: {e}")
        return []


def scrape_dailyfaceoff_goalies():
    """
    Scrape confirmed starting goalies from DailyFaceoff.com.
    
    This is more reliable than NHL API but requires web scraping.
    DailyFaceoff updates with morning skate confirmations.
    
    Returns:
        List of dicts with team, goalie_name, status (confirmed/probable)
    """
    # TODO: Implement web scraping
    # URL: https://www.dailyfaceoff.com/starting-goalies/
    # 
    # Sample HTML structure:
    # <div class="starting-goalies">
    #   <div class="goalie-card">
    #     <span class="team">TOR</span>
    #     <span class="goalie-name">Joseph Woll</span>
    #     <span class="status confirmed">Confirmed</span>
    #   </div>
    # </div>
    
    print("⚠️  DailyFaceoff scraper not implemented yet")
    print("   Manual check: https://www.dailyfaceoff.com/starting-goalies/")
    return []


# ============================================================================
# 2. BETTING LINES
# ============================================================================

def fetch_odds_api_lines(api_key=None):
    """
    Fetch betting lines from The Odds API.
    
    Free tier: 500 requests/month
    Sign up: https://the-odds-api.com/
    
    Args:
        api_key: Your Odds API key (set in environment or pass directly)
    
    Returns:
        List of dicts with moneyline, puck line, totals for each game
    """
    if api_key is None:
        api_key = os.environ.get('ODDS_API_KEY')
    
    if not api_key:
        print("⚠️  ODDS_API_KEY not set. Get free API key at https://the-odds-api.com/")
        return []
    
    url = "https://api.the-odds-api.com/v4/sports/icehockey_nhl/odds/"
    params = {
        'apiKey': api_key,
        'regions': 'us',  # US sportsbooks
        'markets': 'h2h,spreads,totals',  # Moneyline, puck line, over/under
        'oddsFormat': 'american'  # -110, +150, etc.
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        lines = []
        for game in data:
            # Extract consensus lines (average across books)
            home_team = game['home_team']
            away_team = game['away_team']
            
            # Find moneyline (h2h market)
            moneylines = [b for b in game.get('bookmakers', []) for m in b.get('markets', []) if m['key'] == 'h2h']
            
            if moneylines:
                # Take first book's lines (or average across multiple)
                outcomes = moneylines[0].get('outcomes', [])
                home_ml = next((o['price'] for o in outcomes if o['name'] == home_team), None)
                away_ml = next((o['price'] for o in outcomes if o['name'] == away_team), None)
                
                lines.append({
                    'game_id': game['id'],
                    'commence_time': game['commence_time'],
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_moneyline': home_ml,
                    'away_moneyline': away_ml,
                    'home_implied_prob': moneyline_to_probability(home_ml) if home_ml else None,
                    'away_implied_prob': moneyline_to_probability(away_ml) if away_ml else None,
                    'source': 'odds_api',
                    'fetched_at': datetime.now().isoformat()
                })
        
        return lines
    
    except Exception as e:
        print(f"Error fetching betting lines: {e}")
        return []


def moneyline_to_probability(moneyline):
    """
    Convert American moneyline odds to implied probability.
    
    Examples:
        -200 (favorite) -> 66.7% probability
        +150 (underdog) -> 40.0% probability
    """
    if moneyline < 0:
        # Favorite
        return abs(moneyline) / (abs(moneyline) + 100)
    else:
        # Underdog
        return 100 / (moneyline + 100)


# ============================================================================
# 3. INJURIES
# ============================================================================

def scrape_nhl_injury_report():
    """
    Scrape official NHL injury report.
    
    URL: https://www.nhl.com/info/injury-report
    
    Returns:
        List of dicts with team, player_name, position, status (Out/Day-to-Day/IR)
    """
    # TODO: Implement web scraping
    # 
    # Sample structure:
    # [
    #   {
    #     'team': 'TOR',
    #     'player_name': 'Auston Matthews',
    #     'position': 'C',
    #     'status': 'Day-to-Day',
    #     'injury': 'Upper Body'
    #   }
    # ]
    
    print("⚠️  NHL injury scraper not implemented yet")
    print("   Manual check: https://www.nhl.com/info/injury-report")
    return []


# ============================================================================
# 4. SAVE TO DATABASE
# ============================================================================

def save_external_data_to_db(goalies, lines, injuries, db_path='data/nhlstats.duckdb'):
    """
    Save fetched external data to database for use in predictions.
    """
    conn = duckdb.connect(db_path)
    
    # Create tables if they don't exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS confirmed_goalies (
            game_id VARCHAR,
            game_date DATE,
            home_team VARCHAR,
            away_team VARCHAR,
            home_goalie_id INTEGER,
            home_goalie_name VARCHAR,
            away_goalie_id INTEGER,
            away_goalie_name VARCHAR,
            source VARCHAR,
            fetched_at TIMESTAMP,
            PRIMARY KEY (game_id, source)
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS betting_lines (
            game_id VARCHAR,
            commence_time TIMESTAMP,
            home_team VARCHAR,
            away_team VARCHAR,
            home_moneyline DECIMAL,
            away_moneyline DECIMAL,
            home_implied_prob DECIMAL,
            away_implied_prob DECIMAL,
            source VARCHAR,
            fetched_at TIMESTAMP,
            PRIMARY KEY (game_id, fetched_at)
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS injury_reports (
            report_date DATE,
            team VARCHAR,
            player_name VARCHAR,
            position VARCHAR,
            status VARCHAR,
            injury VARCHAR,
            fetched_at TIMESTAMP,
            PRIMARY KEY (report_date, team, player_name)
        )
    """)
    
    # Insert goalies
    if goalies:
        conn.executemany("""
            INSERT OR REPLACE INTO confirmed_goalies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [(g['game_id'], g['game_date'], g['home_team'], g['away_team'],
               g.get('home_goalie_id'), g.get('home_goalie_name'),
               g.get('away_goalie_id'), g.get('away_goalie_name'),
               g['source'], g['fetched_at']) for g in goalies])
        print(f"✅ Saved {len(goalies)} goalie records")
    
    # Insert betting lines
    if lines:
        conn.executemany("""
            INSERT OR REPLACE INTO betting_lines VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [(l['game_id'], l['commence_time'], l['home_team'], l['away_team'],
               l.get('home_moneyline'), l.get('away_moneyline'),
               l.get('home_implied_prob'), l.get('away_implied_prob'),
               l['source'], l['fetched_at']) for l in lines])
        print(f"✅ Saved {len(lines)} betting line records")
    
    # Insert injuries
    if injuries:
        conn.executemany("""
            INSERT OR REPLACE INTO injury_reports VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [(i['report_date'], i['team'], i['player_name'], i['position'],
               i['status'], i.get('injury'), i['fetched_at']) for i in injuries])
        print(f"✅ Saved {len(injuries)} injury records")
    
    conn.close()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import os
    
    print("=" * 80)
    print("🏒 NHL External Data Fetcher")
    print("=" * 80)
    
    # Get today's date or specific date
    target_date = date.today().isoformat()
    print(f"\n📅 Fetching data for: {target_date}")
    
    # 1. Fetch Starting Goalies
    print("\n🥅 Fetching starting goalies...")
    goalies = fetch_nhl_api_probable_goalies(target_date)
    if goalies:
        for g in goalies:
            print(f"   {g['home_team']} vs {g['away_team']}")
            print(f"     Home: {g.get('home_goalie_name', 'TBD')}")
            print(f"     Away: {g.get('away_goalie_name', 'TBD')}")
    else:
        print("   No games found or API error")
    
    # 2. Scrape DailyFaceoff (more reliable)
    print("\n🌐 Checking DailyFaceoff for confirmations...")
    df_goalies = scrape_dailyfaceoff_goalies()
    
    # 3. Fetch Betting Lines
    print("\n💰 Fetching betting lines...")
    lines = fetch_odds_api_lines()
    if lines:
        for l in lines:
            print(f"   {l['away_team']} @ {l['home_team']}")
            print(f"     ML: {l['away_moneyline']:+d} / {l['home_moneyline']:+d}")
            print(f"     Implied: {l['away_implied_prob']:.1%} / {l['home_implied_prob']:.1%}")
    
    # 4. Scrape Injuries
    print("\n🏥 Fetching injury reports...")
    injuries = scrape_nhl_injury_report()
    
    # 5. Save to database
    print("\n💾 Saving to database...")
    save_external_data_to_db(goalies, lines, injuries)
    
    print("\n" + "=" * 80)
    print("✅ External data fetch complete!")
    print("=" * 80)
    print("\nNext steps:")
    print("  1. Review confirmed goalies in database")
    print("  2. Run prediction model with external data")
    print("  3. Compare model predictions to betting lines")
    print("  4. Identify edge opportunities\n")
