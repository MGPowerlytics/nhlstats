"""
Wrapper script to use OddsHarvester for scraping NHL betting odds.
Handles both historical and upcoming matches.
"""

import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime, timedelta
import duckdb


def scrape_historical_nhl_odds(seasons=['2021-2022', '2022-2023', '2023-2024', '2024-2025']):
    """
    Scrape historical NHL odds from OddsPortal using OddsHarvester.
    
    Args:
        seasons: List of NHL seasons to scrape (e.g., ['2021-2022', '2022-2023'])
    """
    print("=" * 80)
    print("🏒 Scraping Historical NHL Odds from OddsPortal")
    print("=" * 80)
    
    oddsharvester_dir = Path(__file__).parent / "oddsharvester"
    
    for season in seasons:
        print(f"\n📅 Scraping season: {season}")
        
        # Output file for this season
        output_file = f"data/historical_odds/nhl_{season.replace('-', '_')}_oddsportal.json"
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Run OddsHarvester command
        cmd = [
            sys.executable,
            "src/main.py",
            "scrape_historic",
            "--sport", "ice-hockey",
            "--leagues", "usa-nhl",
            "--season", season,
            "--markets", "home_away",  # Moneyline equivalent for NHL
            "--storage", "local",
            "--file_path", output_file,
            "--format", "json",
            "--headless", "True",
            "--odds_format", "Money Line Odds"  # Get American odds
        ]
        
        print(f"   Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(oddsharvester_dir),  # Run from oddsharvester directory
                capture_output=True,
                text=True,
                timeout=1800  # 30 minute timeout
            )
            
            if result.returncode == 0:
                print(f"   ✅ Successfully scraped {season}")
                
                # Check file size
                if Path(output_file).exists():
                    size = Path(output_file).stat().st_size
                    print(f"   📦 Data file size: {size:,} bytes")
            else:
                print(f"   ❌ Failed to scrape {season}")
                print(f"   Error: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            print(f"   ⏱️  Timeout scraping {season} (>30 min)")
        except Exception as e:
            print(f"   ❌ Error scraping {season}: {e}")
    
    print("\n" + "=" * 80)
    print("✅ Historical scraping complete!")
    print("=" * 80)


def scrape_upcoming_nhl_odds(date=None):
    """
    Scrape upcoming NHL odds from OddsPortal using OddsHarvester.
    
    Args:
        date: Date to scrape (YYYY-MM-DD format). Defaults to today.
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    print("=" * 80)
    print(f"🏒 Scraping Upcoming NHL Odds for {date}")
    print("=" * 80)
    
    oddsharvester_dir = Path(__file__).parent / "oddsharvester"
    
    # Convert date format (YYYY-MM-DD -> YYYYMMDD)
    date_formatted = date.replace("-", "")
    
    # Output file
    output_file = f"data/daily_odds/nhl_{date}_oddsportal.json"
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    # Run OddsHarvester command
    cmd = [
        sys.executable,
        "src/main.py",
        "scrape_upcoming",
        "--sport", "ice-hockey",
        "--date", date_formatted,
        "--markets", "home_away",  # Moneyline equivalent
        "--storage", "local",
        "--file_path", output_file,
        "--format", "json",
        "--headless", "True",
        "--odds_format", "Money Line Odds"  # Get American odds
    ]
    
    print(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(oddsharvester_dir),  # Run from oddsharvester directory
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        if result.returncode == 0:
            print(f"✅ Successfully scraped upcoming games for {date}")
            
            # Check file size
            if Path(output_file).exists():
                size = Path(output_file).stat().st_size
                print(f"📦 Data file size: {size:,} bytes")
                
                # Load and parse the data
                load_oddsportal_to_duckdb(output_file, is_historical=False)
        else:
            print(f"❌ Failed to scrape upcoming games")
            print(f"Error: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        print(f"⏱️  Timeout scraping upcoming games (>10 min)")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 80)


def load_oddsportal_to_duckdb(json_file, is_historical=True):
    """
    Load OddsPortal JSON data into DuckDB.
    
    Args:
        json_file: Path to JSON file from OddsHarvester
        is_historical: If True, load into historical_betting_lines table
    """
    print(f"\n💾 Loading data from {json_file} into DuckDB...")
    
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    if not data:
        print("⚠️  No data in file")
        return
    
    conn = duckdb.connect('data/nhlstats.duckdb')
    
    table_name = "historical_betting_lines" if is_historical else "daily_betting_lines"
    
    records = []
    for match in data:
        try:
            # Parse date
            game_date = datetime.strptime(match.get('start_time', ''), '%Y-%m-%dT%H:%M:%S%z').date()
            
            # Extract teams
            home_team = match.get('home_team', '')
            away_team = match.get('away_team', '')
            
            # Extract odds (OddsHarvester stores them in the markets dict)
            markets = match.get('markets', {})
            home_away_market = markets.get('home_away', {})
            
            # Get home and away odds
            home_odds = None
            away_odds = None
            
            # OddsPortal structure varies, try to extract odds
            if isinstance(home_away_market, dict):
                bookmakers = home_away_market.get('bookmakers', [])
                if bookmakers:
                    # Average the odds from all bookmakers
                    home_odds_list = [b.get('home_odds') for b in bookmakers if b.get('home_odds')]
                    away_odds_list = [b.get('away_odds') for b in bookmakers if b.get('away_odds')]
                    
                    if home_odds_list:
                        home_odds = sum(home_odds_list) / len(home_odds_list)
                    if away_odds_list:
                        away_odds = sum(away_odds_list) / len(away_odds_list)
            
            # Calculate implied probabilities
            home_prob = None
            away_prob = None
            
            if home_odds:
                if home_odds < 0:
                    home_prob = abs(home_odds) / (abs(home_odds) + 100)
                else:
                    home_prob = 100 / (home_odds + 100)
            
            if away_odds:
                if away_odds < 0:
                    away_prob = abs(away_odds) / (abs(away_odds) + 100)
                else:
                    away_prob = 100 / (away_odds + 100)
            
            records.append({
                'game_date': game_date,
                'home_team': home_team,
                'away_team': away_team,
                'home_ml_open': home_odds,  # OddsPortal doesn't distinguish open/close
                'home_ml_close': home_odds,
                'away_ml_open': away_odds,
                'away_ml_close': away_odds,
                'home_implied_prob_open': home_prob,
                'home_implied_prob_close': home_prob,
                'away_implied_prob_open': away_prob,
                'away_implied_prob_close': away_prob,
                'line_movement': 0.0,
                'source': 'OddsPortal',
                'fetched_at': datetime.now()
            })
            
        except Exception as e:
            print(f"   ⚠️  Error parsing match: {e}")
            continue
    
    if records:
        # Insert into database
        conn.execute(f"""
            INSERT INTO {table_name}
            SELECT * FROM records
            ON CONFLICT DO UPDATE SET
                home_ml_close = EXCLUDED.home_ml_close,
                away_ml_close = EXCLUDED.away_ml_close,
                home_implied_prob_close = EXCLUDED.home_implied_prob_close,
                away_implied_prob_close = EXCLUDED.away_implied_prob_close,
                fetched_at = CURRENT_TIMESTAMP
        """)
        
        print(f"   ✅ Loaded {len(records)} games into {table_name}")
    else:
        print("   ⚠️  No valid records to load")
    
    conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape NHL odds using OddsHarvester")
    parser.add_argument("--mode", choices=["historical", "upcoming", "both"], default="both",
                        help="Scraping mode")
    parser.add_argument("--date", help="Date for upcoming odds (YYYY-MM-DD)")
    parser.add_argument("--seasons", nargs="+", 
                        default=['2021-2022', '2022-2023', '2023-2024', '2024-2025'],
                        help="Seasons to scrape for historical data")
    
    args = parser.parse_args()
    
    if args.mode in ["historical", "both"]:
        scrape_historical_nhl_odds(args.seasons)
    
    if args.mode in ["upcoming", "both"]:
        scrape_upcoming_nhl_odds(args.date)
