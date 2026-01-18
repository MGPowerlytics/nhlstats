#!/usr/bin/env python3
"""
Fetch Historical NHL Betting Odds

This script fetches historical betting odds from free sources:
1. Sportsbook Review (direct downloads - EASIEST)
2. Odds Portal (web scraping - MOST DATA)
3. Kaggle datasets (if available)

Run once to backfill historical odds data.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from pathlib import Path
import duckdb
from datetime import datetime

# ============================================================================
# 1. SPORTSBOOK REVIEW (Direct Downloads - RECOMMENDED)
# ============================================================================

def download_sbr_odds(output_dir='data/historical_odds'):
    """
    Download historical odds from Sportsbook Review.
    
    These are pre-compiled Excel files with clean data.
    Check: https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl/nhloddsarchives.htm
    """
    print("\n📥 Sportsbook Review Odds")
    print("=" * 60)
    print("⚠️  Manual download required:")
    print("   1. Visit: https://www.sportsbookreviewsonline.com/scoresoddsarchives/nhl/nhloddsarchives.htm")
    print("   2. Download Excel files for each season (2007-2024)")
    print("   3. Save to: data/historical_odds/")
    print("   4. Run this script to load into database")
    print()
    
    # Check if files exist
    odds_dir = Path(output_dir)
    odds_dir.mkdir(parents=True, exist_ok=True)
    
    excel_files = list(odds_dir.glob('*.xlsx')) + list(odds_dir.glob('*.xls'))
    
    if excel_files:
        print(f"✅ Found {len(excel_files)} odds files:")
        for f in excel_files:
            print(f"   - {f.name}")
        return excel_files
    else:
        print("❌ No odds files found in data/historical_odds/")
        return []


def load_sbr_excel(excel_path):
    """
    Load and parse Sportsbook Review Excel file.
    
    Expected columns: Date, Rot, VH, Team, Final, Open, Close, ML
    """
    df = pd.read_excel(excel_path)
    
    # Typical SBR format has pairs of rows (Visitor/Home)
    # Parse into one row per game
    games = []
    
    for i in range(0, len(df), 2):
        if i + 1 >= len(df):
            break
        
        visitor_row = df.iloc[i]
        home_row = df.iloc[i + 1]
        
        # Extract game data
        game = {
            'game_date': pd.to_datetime(visitor_row['Date']),
            'away_team': visitor_row['Team'],
            'home_team': home_row['Team'],
            'away_score': visitor_row.get('Final'),
            'home_score': home_row.get('Final'),
            'away_ml_open': visitor_row.get('Open'),
            'home_ml_open': home_row.get('Open'),
            'away_ml_close': visitor_row.get('Close'),
            'home_ml_close': home_row.get('Close'),
        }
        games.append(game)
    
    return pd.DataFrame(games)


# ============================================================================
# 2. ODDS PORTAL (Web Scraping - MOST COMPREHENSIVE)
# ============================================================================

def scrape_oddsportal_season(season='2023-2024', max_pages=50):
    """
    Scrape NHL odds from Odds Portal for a specific season.
    
    Args:
        season: Format '2023-2024'
        max_pages: Limit pages to avoid getting blocked
    
    Returns:
        DataFrame with game_date, teams, odds
    """
    print(f"\n🌐 Scraping Odds Portal: {season}")
    print("=" * 60)
    
    base_url = f"https://www.oddsportal.com/hockey/usa/nhl-{season}/results/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    all_games = []
    
    try:
        # Note: Odds Portal has changed to React-based site
        # This is a simplified example - actual implementation may need Selenium
        
        response = requests.get(base_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find game rows (structure varies, this is conceptual)
        game_rows = soup.find_all('div', class_='eventRow')
        
        for row in game_rows:
            try:
                # Extract data (actual selectors will differ)
                date_elem = row.find('span', class_='date')
                teams_elem = row.find('div', class_='name')
                odds_elems = row.find_all('span', class_='odds')
                
                if date_elem and teams_elem and len(odds_elems) >= 2:
                    game_data = {
                        'game_date': date_elem.text.strip(),
                        'teams': teams_elem.text.strip(),
                        'home_ml': odds_elems[0].text.strip(),
                        'away_ml': odds_elems[1].text.strip(),
                        'source': 'oddsportal'
                    }
                    all_games.append(game_data)
            except Exception as e:
                continue
        
        print(f"   Found {len(all_games)} games")
        
    except Exception as e:
        print(f"   ❌ Error scraping Odds Portal: {e}")
        print(f"   💡 Odds Portal requires Selenium for modern site")
        print(f"   💡 Consider using Sportsbook Review instead")
    
    return pd.DataFrame(all_games) if all_games else pd.DataFrame()


def scrape_with_selenium(season='2023-2024'):
    """
    Scrape Odds Portal using Selenium (for JavaScript-rendered sites).
    
    Requires: pip install selenium
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        print(f"\n🤖 Scraping Odds Portal with Selenium: {season}")
        print("=" * 60)
        
        url = f"https://www.oddsportal.com/hockey/usa/nhl-{season}/results/"
        
        # Set up headless browser
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        
        # Wait for page to load
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'eventRow')))
        
        # Scroll to load more games
        for _ in range(5):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        
        # Extract game data
        games = []
        game_rows = driver.find_elements(By.CLASS_NAME, 'eventRow')
        
        for row in game_rows:
            try:
                # Extract elements (selectors will vary)
                date = row.find_element(By.CLASS_NAME, 'date').text
                teams = row.find_element(By.CLASS_NAME, 'name').text
                odds = row.find_elements(By.CLASS_NAME, 'odds')
                
                games.append({
                    'game_date': date,
                    'teams': teams,
                    'odds': [o.text for o in odds]
                })
            except:
                continue
        
        driver.quit()
        
        print(f"   ✅ Scraped {len(games)} games")
        return pd.DataFrame(games)
        
    except ImportError:
        print("   ❌ Selenium not installed")
        print("   💡 Install with: pip install selenium")
        return pd.DataFrame()
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return pd.DataFrame()


# ============================================================================
# 3. SAVE TO DATABASE
# ============================================================================

def load_odds_to_database(df, db_path='data/nhlstats.duckdb'):
    """
    Load historical odds DataFrame into database.
    """
    if df.empty:
        print("⚠️  No data to load")
        return
    
    conn = duckdb.connect(db_path)
    
    # Create table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS historical_betting_lines (
            game_date DATE,
            home_team VARCHAR,
            away_team VARCHAR,
            home_ml_open DECIMAL,
            away_ml_open DECIMAL,
            home_ml_close DECIMAL,
            away_ml_close DECIMAL,
            home_score INTEGER,
            away_score INTEGER,
            home_implied_prob DECIMAL,
            away_implied_prob DECIMAL,
            source VARCHAR,
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (game_date, home_team, away_team)
        )
    """)
    
    # Calculate implied probabilities
    def ml_to_prob(ml):
        if pd.isna(ml):
            return None
        ml = float(ml)
        if ml < 0:
            return abs(ml) / (abs(ml) + 100)
        else:
            return 100 / (ml + 100)
    
    df['home_implied_prob'] = df['home_ml_close'].apply(ml_to_prob)
    df['away_implied_prob'] = df['away_ml_close'].apply(ml_to_prob)
    
    # Insert
    try:
        conn.execute("""
            INSERT INTO historical_betting_lines 
            SELECT * FROM df
            ON CONFLICT DO NOTHING
        """)
        
        count = conn.execute("SELECT COUNT(*) FROM historical_betting_lines").fetchone()[0]
        print(f"\n✅ Database now has {count:,} games with betting lines")
        
    except Exception as e:
        print(f"❌ Error loading to database: {e}")
    finally:
        conn.close()


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 80)
    print("🏒 NHL Historical Betting Odds Fetcher")
    print("=" * 80)
    
    # Option 1: Check for SBR files
    sbr_files = download_sbr_odds()
    
    if sbr_files:
        print("\n📊 Loading SBR Excel files...")
        all_data = []
        
        for excel_file in sbr_files:
            try:
                df = load_sbr_excel(excel_file)
                all_data.append(df)
                print(f"   ✅ Loaded {len(df)} games from {excel_file.name}")
            except Exception as e:
                print(f"   ❌ Error loading {excel_file.name}: {e}")
        
        if all_data:
            combined = pd.concat(all_data, ignore_index=True)
            combined['source'] = 'sportsbook_review'
            load_odds_to_database(combined)
    
    # Option 2: Scrape Odds Portal (if no SBR files)
    else:
        print("\n💡 No SBR files found. Attempting Odds Portal scrape...")
        print("   (Note: May require Selenium for modern site)")
        
        seasons = ['2023-2024', '2022-2023', '2021-2022']
        
        for season in seasons:
            df = scrape_oddsportal_season(season)
            if not df.empty:
                df['source'] = 'oddsportal'
                load_odds_to_database(df)
            
            time.sleep(3)  # Be polite
    
    print("\n" + "=" * 80)
    print("✅ Historical odds fetch complete!")
    print("=" * 80)
    print("\n📌 Next Steps:")
    print("   1. Join betting lines with your games table")
    print("   2. Add implied probability as model features")
    print("   3. Track line movement (opening vs closing)")
    print("   4. Compare model predictions to market odds\n")


if __name__ == "__main__":
    main()
