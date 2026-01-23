#!/usr/bin/env python3
"""
Fetch Kalshi markets for NHL/NBA games using official SDK.
"""

from kalshi_python import Configuration, ApiClient, MarketsApi
import json
from datetime import datetime, timezone
from pathlib import Path
import requests
import re
from typing import Dict, List, Optional
from db_manager import DBManager, default_db

class KalshiAPI:
    """Kalshi API client using official SDK"""

    def __init__(self, api_key_id, private_key_pem):
        self.api_key_id = api_key_id
        self.private_key_pem = private_key_pem

        # Configure API client
        config = Configuration(host="https://api.elections.kalshi.com/trade-api/v2")
        config.api_key['api_key_id'] = api_key_id
        config.api_key['private_key'] = private_key_pem

        # Create client
        self.api_client = ApiClient(configuration=config)
        self.markets_api = MarketsApi(self.api_client)

    def get_markets(self, event_ticker=None, series_ticker=None, status='open', limit=100):
        """Get markets from Kalshi"""
        try:
            response = self.markets_api.get_markets(
                event_ticker=event_ticker,
                series_ticker=series_ticker,
                status=status,
                limit=limit
            )
            return response.to_dict()
        except Exception as e:
            print(f"✗ Failed to get markets: {e}")
            return None

def _generate_game_id(sport, game_date, home_team, away_team):
    """
    Generates a consistent and unique game_id.
    Format: SPORT_YYYYMMDD_HOME_AWAY (cleaned)
    """
    date_str = game_date.replace('-', '')
    home_slug = "".join(filter(str.isalnum, home_team)).upper()
    away_slug = "".join(filter(str.isalnum, away_team)).upper()
    return f"{sport.upper()}_{date_str}_{home_slug}_{away_slug}"

def save_to_db(sport: str, markets: list, db_manager: DBManager = default_db):
    """
    Save Kalshi markets to the unified_games and game_odds tables in PostgreSQL.
    """
    if not markets:
        return 0

    from naming_resolver import NamingResolver

    odds_count = 0
    print(f"💾 Saving {len(markets)} {sport.upper()} Kalshi markets to PostgreSQL...")

    for market in markets:
        ticker = market.get('ticker', '')
        title = market.get('title', '')

        home_team = None
        away_team = None
        game_date = None

        # Standard Kalshi Ticker Parsing
        # Attempt 1: SERIES-YYMMDD-AWAYHOME-OUTCOME (Old format)
        parts = ticker.split('-')
        parsed = False

        if len(parts) >= 3:
            # Try numeric date format first (Old)
            try:
                date_part = parts[1]
                # Check if it's purely numeric and length 6 (YYMMDD)
                if len(date_part) == 6 and date_part.isdigit():
                    year = 2000 + int(date_part[0:2])
                    month = int(date_part[2:4])
                    day = int(date_part[4:6])
                    game_date = f"{year}-{month:02d}-{day:02d}"

                    teams_part = parts[2]
                    if len(teams_part) == 6:
                        away_team = teams_part[0:3]
                        home_team = teams_part[3:6]
                        parsed = True
            except:
                pass

        # Attempt 2: SERIES-YYMMMDDTEAMS-OUTCOME (New format: 26JAN24LALDAL)
        if not parsed and len(parts) >= 2:
            try:
                # The middle part contains everything: Date + Teams
                middle = parts[1]
                # Regex for YYMMMDDTEAMS (e.g. 26JAN24LALDAL)
                # 2 digits Year, 3 letters Month, 2 digits Day, remaining is Teams
                match_new = re.match(r"^(\d{2})([A-Z]{3})(\d{2})([A-Z]+)$", middle)
                if match_new:
                    y_str, m_str, d_str, teams_str = match_new.groups()

                    # Parse date
                    dt = datetime.strptime(f"{y_str}{m_str}{d_str}", "%y%b%d")
                    game_date = dt.strftime("%Y-%m-%d")

                    # Teams: Assuming 3-char codes usually, so 6 chars total?
                    # Or split in half?
                    # NBA/NCAAB usually 3 chars.
                    if len(teams_str) == 6:
                        away_team = teams_str[0:3]
                        home_team = teams_str[3:6]
                        parsed = True
                    elif " vs " in title: # Fallback to title if ticker teams are ambiguous
                        pass
            except Exception as e:
                # print(f"Failed new format parse: {e}")
                pass

        # Fallback for Tennis or others where Title is key
        if not home_team or not away_team or not game_date:
            if sport.lower() == 'tennis':
                match = re.search(r"win the (.*?) vs (.*?) (?:match|:)", title)
                if not match: match = re.search(r"win the (.*?) vs (.*?) match", title)

                if match:
                    home_team = match.group(1).strip()
                    away_team = match.group(2).strip()
                    if away_team.endswith(' match'): away_team = away_team[:-6].strip()

                    close_time = market.get('close_time')
                    if close_time:
                        if isinstance(close_time, str):
                            game_date = close_time.split('T')[0]
                        else:
                            game_date = close_time.strftime('%Y-%m-%d')

        if not home_team or not away_team or not game_date:
            continue

        # Resolve canonical names
        canon_home = NamingResolver.resolve(sport, 'kalshi', home_team) or home_team
        canon_away = NamingResolver.resolve(sport, 'kalshi', away_team) or away_team

        game_id = _generate_game_id(sport, game_date, canon_home, canon_away)

        # 1. Upsert into unified_games
        db_manager.execute("""
            INSERT INTO unified_games (
                game_id, sport, game_date, home_team_id, home_team_name,
                away_team_id, away_team_name, status
            ) VALUES (:game_id, :sport, :game_date, :home_id, :home_name,
                     :away_id, :away_name, :status)
            ON CONFLICT (game_id) DO UPDATE SET
                status = EXCLUDED.status
        """, {
            'game_id': game_id, 'sport': sport.upper(), 'game_date': game_date,
            'home_id': home_team, 'home_name': canon_home,
            'away_id': away_team, 'away_name': canon_away,
            'status': 'Scheduled'
        })

        # 2. Upsert into game_odds for Kalshi
        outcome_side = parts[-1] if len(parts) > 1 else None
        yes_price_cents = market.get('yes_ask', 0)

        if yes_price_cents > 0 and outcome_side:
            decimal_odds = 100.0 / yes_price_cents

            def get_last_name_code(name):
                parts = name.split()
                return parts[-1][:3].upper() if parts else name[:3].upper()

            h_code = get_last_name_code(home_team)
            a_code = get_last_name_code(away_team)

            if outcome_side == h_code:
                outcome_name = 'home'
            elif outcome_side == a_code:
                outcome_name = 'away'
            else:
                outcome_name = 'home' if outcome_side == home_team else 'away'

            odds_id = f"{game_id}_kalshi_{outcome_name}"
            db_manager.execute("""
                INSERT INTO game_odds (
                    odds_id, game_id, bookmaker, market_name, outcome_name, price, is_pregame, external_id
                ) VALUES (:odds_id, :game_id, 'Kalshi', 'moneyline', :outcome_name, :price, True, :ticker)
                ON CONFLICT (odds_id) DO UPDATE SET
                    price = EXCLUDED.price,
                    external_id = EXCLUDED.external_id
            """, {
                'odds_id': odds_id, 'game_id': game_id,
                'outcome_name': outcome_name, 'price': decimal_odds,
                'ticker': ticker
            })
            odds_count += 1
    return odds_count

def load_kalshi_credentials():
    """Load Kalshi credentials from standard files."""
    key_file = Path('kalshkey')
    if not key_file.exists(): key_file = Path('/opt/airflow/kalshkey')

    if not key_file.exists():
        raise FileNotFoundError(f"Kalshi credentials file not found")

    content = key_file.read_text()

    # 1. Extract API Key ID
    api_key_id = None
    for line in content.split('\n'):
        if "API key id:" in line:
            api_key_id = line.split(': ')[1].strip()
            break

    # 2. Extract Private Key
    private_key = None
    if "-----BEGIN RSA PRIVATE KEY-----" in content:
        # Key is embedded in the kalshkey file
        lines = content.split('\n')
        in_key = False
        key_lines = []
        for line in lines:
            if "-----BEGIN RSA PRIVATE KEY-----" in line:
                in_key = True
            if in_key:
                key_lines.append(line)
            if "-----END RSA PRIVATE KEY-----" in line:
                break
        private_key = '\n'.join(key_lines)
    else:
        # Look for external .pem file
        pem_file = Path('kalshi_private_key.pem')
        if not pem_file.exists(): pem_file = Path('/opt/airflow/kalshi_private_key.pem')
        if not pem_file.exists(): pem_file = Path(__file__).parent.parent / 'kalshi_private_key.pem'

        if pem_file.exists():
            private_key = pem_file.read_text()

    if not api_key_id or not private_key:
        raise ValueError("Could not find both API Key ID and Private Key in credentials")

    return api_key_id, private_key

def fetch_nba_markets(date_str=None):
    api_key_id, private_key = load_kalshi_credentials()
    api = KalshiAPI(api_key_id, private_key)
    result = api.get_markets(series_ticker='KXNBAGAME', limit=200)
    if result and 'markets' in result:
        markets = [m for m in result['markets'] if m.get('status') in ['active', 'initialized', 'open']]
        save_to_db('nba', markets)
        return markets
    return []

def fetch_nhl_markets(date_str=None):
    api_key_id, private_key = load_kalshi_credentials()
    api = KalshiAPI(api_key_id, private_key)
    result = api.get_markets(series_ticker='KXNHLGAME', limit=200)
    if result and 'markets' in result:
        markets = [m for m in result['markets'] if m.get('status') in ['active', 'initialized', 'open']]
        save_to_db('nhl', markets)
        return markets
    return []

def fetch_epl_markets(date_str=None):
    api_key_id, private_key = load_kalshi_credentials()
    api = KalshiAPI(api_key_id, private_key)
    result = api.get_markets(series_ticker='KXEPLGAME', limit=200)
    if result and 'markets' in result:
        markets = [m for m in result['markets'] if m.get('status') in ['active', 'initialized', 'open']]
        save_to_db('epl', markets)
        return markets
    return []

def fetch_ligue1_markets(date_str=None):
    api_key_id, private_key = load_kalshi_credentials()
    api = KalshiAPI(api_key_id, private_key)
    result = api.get_markets(series_ticker='KXLIGUE1GAME', limit=200)
    if result and 'markets' in result:
        markets = [m for m in result['markets'] if m.get('status') in ['active', 'initialized', 'open']]
        save_to_db('ligue1', markets)
        return markets
    return []

def fetch_tennis_markets(date_str=None):
    api_key_id, private_key = load_kalshi_credentials()
    api = KalshiAPI(api_key_id, private_key)
    all_markets = []
    for series in ['KXATPMATCH', 'KXWTAMATCH', 'KXATPCHALLENGERMATCH', 'KXWTACHALLENGERMATCH']:
        res = api.get_markets(series_ticker=series, limit=200)
        if res and 'markets' in res:
            all_markets.extend([m for m in res['markets'] if m.get('status') in ['active', 'initialized', 'open']])
    save_to_db('tennis', all_markets)
    return all_markets

def fetch_ncaab_markets(date_str=None):
    api_key_id, private_key = load_kalshi_credentials()
    api = KalshiAPI(api_key_id, private_key)
    result = api.get_markets(series_ticker='KXNCAAMBGAME', limit=1000)
    if result and 'markets' in result:
        markets = [m for m in result['markets'] if m.get('status') in ['active', 'initialized', 'open']]
        save_to_db('ncaab', markets)
        return markets
    return []

def fetch_wncaab_markets(date_str=None):
    api_key_id, private_key = load_kalshi_credentials()
    api = KalshiAPI(api_key_id, private_key)
    result = api.get_markets(series_ticker='KXNCAAWBGAME', limit=1000)
    if result and 'markets' in result:
        markets = [m for m in result['markets'] if m.get('status') in ['active', 'initialized', 'open']]
        save_to_db('wncaab', markets)
        return markets
    return []

def fetch_mlb_markets(date_str=None):
    api_key_id, private_key = load_kalshi_credentials()
    api = KalshiAPI(api_key_id, private_key)
    result = api.get_markets(series_ticker='KXMLBGAME', limit=200)
    if result and 'markets' in result:
        markets = [m for m in result['markets'] if m.get('status') in ['active', 'initialized', 'open']]
        save_to_db('mlb', markets)
        return markets
    return []

def fetch_nfl_markets(date_str=None):
    api_key_id, private_key = load_kalshi_credentials()
    api = KalshiAPI(api_key_id, private_key)
    result = api.get_markets(series_ticker='KXNFLGAME', limit=200)
    if result and 'markets' in result:
        markets = [m for m in result['markets'] if m.get('status') in ['active', 'initialized', 'open']]
        save_to_db('nfl', markets)
        return markets
    return []
