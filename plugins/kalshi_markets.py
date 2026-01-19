#!/usr/bin/env python3
"""
Fetch Kalshi markets for NHL/NBA games using official SDK.
"""

from kalshi_python import Configuration, ApiClient, MarketsApi
import json
from datetime import datetime
from pathlib import Path
import requests


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
    
    def search_markets(self, query, limit=200):
        """Search for markets by title"""
        try:
            response = self.markets_api.get_markets(
                limit=limit,
                status='open'
            )
            
            data = response.to_dict()
            
            # Filter markets by query
            if 'markets' in data and query:
                data['markets'] = [m for m in data['markets'] 
                                   if query.upper() in m.get('title', '').upper()]
            return data
        except Exception as e:
            print(f"✗ Failed to search markets: {e}")
            return None


def load_kalshi_credentials():
    """Load Kalshi API credentials from kalshkey file"""
    key_file = Path("kalshkey")
    
    if not key_file.exists():
        key_file = Path("/opt/airflow/kalshkey")
    
    if not key_file.exists():
        raise FileNotFoundError("kalshkey file not found")
    
    content = key_file.read_text()
    
    # Extract API key ID
    api_key_id = None
    for line in content.split('\n'):
        if 'API key id:' in line:
            api_key_id = line.split(':', 1)[1].strip()
            break
    
    # Extract private key
    private_key_lines = []
    in_key = False
    for line in content.split('\n'):
        if '-----BEGIN RSA PRIVATE KEY-----' in line:
            in_key = True
        if in_key:
            private_key_lines.append(line)
        if '-----END RSA PRIVATE KEY-----' in line:
            break
    
    private_key = '\n'.join(private_key_lines)
    
    return api_key_id, private_key


def fetch_nba_markets(date_str=None):
    """Fetch Kalshi markets for NBA games on a specific date.
    
    Args:
        date_str: Date string in YYYY-MM-DD format (defaults to today)
    
    Returns:
        List of market dictionaries
    """
    try:
        import requests
        
        # Load credentials  
        api_key_id, private_key = load_kalshi_credentials()
        
        # Make authenticated request using requests library
        # The kalshi_python SDK handles auth internally, so we use its session
        api = KalshiAPI(api_key_id, private_key)
        
        # Call via the SDK's markets_api but catch the enum error
        try:
            # Try SDK first
            result = api.get_markets(series_ticker='KXNBAGAME', limit=200)
            if result and 'markets' in result:
                markets = result['markets']
                active_markets = [m for m in markets if m.get('status') in ['active', 'initialized']]
                print(f"✓ Found {len(active_markets)} NBA markets")
                return active_markets
        except:
            # Fall back to basic auth request
            url = 'https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXNBAGAME&limit=200'
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                markets = data.get('markets', [])
                active_markets = [m for m in markets if m.get('status') in ['active', 'initialized']]
                print(f"✓ Found {len(active_markets)} NBA markets")
                return active_markets
        
        print("⚠️ No NBA markets found")
        return []
        
    except Exception as e:
        print(f"⚠️ Error fetching NBA markets: {e}")
        return []



def fetch_epl_markets(date_str=None):
    """Fetch Kalshi markets for EPL games."""
    try:
        # Load credentials
        api_key_id, private_key = load_kalshi_credentials()
        
        # Make authenticated request
        api = KalshiAPI(api_key_id, private_key)
        
        # Try SDK first
        try:
            result = api.get_markets(series_ticker='KXEPLGAME', limit=200)
            if result and 'markets' in result:
                markets = result['markets']
                active_markets = [m for m in markets if m.get('status') in ['active', 'initialized', 'open']]
                print(f"✓ Found {len(active_markets)} EPL markets")
                return active_markets
        except Exception as e:
            print(f"Error fetching EPL markets: {e}")
            return []
            
        return []
    except Exception as e:
        print(f"Failed to fetch EPL markets: {e}")
        return []


def fetch_nhl_markets(date_str=None):
    """Fetch Kalshi markets for NHL games on a specific date.
    
    Args:
        date_str: Date string in YYYY-MM-DD format (defaults to today)
    
    Returns:
        List of market dictionaries
    """
    try:
        import requests
        
        # Load credentials
        api_key_id, private_key = load_kalshi_credentials()
        
        # Make authenticated request
        api = KalshiAPI(api_key_id, private_key)
        
        # Try SDK first
        try:
            result = api.get_markets(series_ticker='KXNHLGAME', limit=200)
            if result and 'markets' in result:
                markets = result['markets']
                active_markets = [m for m in markets if m.get('status') in ['active', 'initialized']]
                print(f"✓ Found {len(active_markets)} NHL markets")
                return active_markets
        except:
            # Fall back to basic request
            url = 'https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXNHLGAME&limit=200'
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                markets = data.get('markets', [])
                active_markets = [m for m in markets if m.get('status') in ['active', 'initialized']]
                print(f"✓ Found {len(active_markets)} NHL markets")
                return active_markets
        
        print("⚠️ No NHL markets found")
        return []
        
    except Exception as e:
        print(f"⚠️ Error fetching NHL markets: {e}")
        return []


def fetch_mlb_markets(date_str=None):
    """Fetch Kalshi markets for MLB games on a specific date.
    
    Args:
        date_str: Date string in YYYY-MM-DD format (defaults to today)
    
    Returns:
        List of market dictionaries
    """
    try:
        import requests
        
        # Load credentials
        api_key_id, private_key = load_kalshi_credentials()
        
        # Make authenticated request
        api = KalshiAPI(api_key_id, private_key)
        
        # Try SDK first
        try:
            result = api.get_markets(series_ticker='KXMLBGAME', limit=200)
            if result and 'markets' in result:
                markets = result['markets']
                active_markets = [m for m in markets if m.get('status') in ['active', 'initialized']]
                print(f"✓ Found {len(active_markets)} MLB markets")
                return active_markets
        except:
            # Fall back to basic request
            url = 'https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXMLBGAME&limit=200'
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                markets = data.get('markets', [])
                active_markets = [m for m in markets if m.get('status') in ['active', 'initialized']]
                print(f"✓ Found {len(active_markets)} MLB markets")
                return active_markets
        
        print("⚠️ No MLB markets found")
        return []
        
    except Exception as e:
        print(f"⚠️ Error fetching MLB markets: {e}")
        return []


def fetch_nfl_markets(date_str=None):
    """Fetch Kalshi markets for NFL games on a specific date.
    
    Args:
        date_str: Date string in YYYY-MM-DD format (defaults to today)
    
    Returns:
        List of market dictionaries
    """
    try:
        import requests
        
        # Load credentials
        api_key_id, private_key = load_kalshi_credentials()
        
        # Make authenticated request
        api = KalshiAPI(api_key_id, private_key)
        
        # Try SDK first
        try:
            result = api.get_markets(series_ticker='KXNFLGAME', limit=200)
            if result and 'markets' in result:
                markets = result['markets']
                active_markets = [m for m in markets if m.get('status') in ['active', 'initialized']]
                print(f"✓ Found {len(active_markets)} NFL markets")
                return active_markets
        except:
            # Fall back to basic request
            url = 'https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXNFLGAME&limit=200'
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                markets = data.get('markets', [])
                active_markets = [m for m in markets if m.get('status') in ['active', 'initialized']]
                print(f"✓ Found {len(active_markets)} NFL markets")
                return active_markets
        
        print("⚠️ No NFL markets found")
        return []
        
    except Exception as e:
        print(f"⚠️ Error fetching NFL markets: {e}")
        return []

def fetch_ncaab_markets(date_str=None):
    """Fetch Kalshi markets for NCAAB games."""
    try:
        # Load credentials
        api_key_id, private_key = load_kalshi_credentials()
        
        # Make authenticated request
        api = KalshiAPI(api_key_id, private_key)
        
        # Call via SDK
        try:
            print("  Searching for KXNCAAMBGAME...")
            result = api.get_markets(series_ticker='KXNCAAMBGAME', limit=200)
            if result and 'markets' in result:
                markets = result['markets']
                active_markets = [m for m in markets if m.get('status') in ['active', 'initialized']]
                print(f"✓ Found {len(active_markets)} NCAAB markets")
                return active_markets
        except Exception as e:
            print(f"  SDK fetch failed: {e}")
            
        print("⚠️ No NCAAB markets found")
        return []
        
    except Exception as e:
        print(f"⚠️ Error fetching NCAAB markets: {e}")
        return []

def fetch_tennis_markets(date_str=None):
    """
    Fetch Tennis markets from Kalshi.
    
    Uses KXATPMATCH (ATP) and KXWTAMATCH (WTA) series tickers.
    """
    try:
        # Load credentials
        api_key_id, private_key = load_kalshi_credentials()
        
        # Make authenticated request
        api = KalshiAPI(api_key_id, private_key)
        
        # Tennis series on Kalshi
        tennis_series = ['KXATPMATCH', 'KXWTAMATCH']
        
        all_markets = []
        for series in tennis_series:
            try:
                response = api.get_markets(series_ticker=series, status='open')
                if response and 'markets' in response:
                    markets = response['markets']
                    print(f"  ✓ Found {len(markets)} {series} markets")
                    all_markets.extend(markets)
            except Exception as e:
                print(f"  ⚠️  Error fetching {series}: {e}")
                continue
        
        print(f"  ✓ Total: {len(all_markets)} tennis markets")
        return all_markets
            
    except Exception as e:
        print(f"❌ Error fetching Tennis markets: {e}")
        return []

def main():
    print("🎲 Kalshi Markets Fetcher (SDK version)")
    print("=" * 80)
    
    # Load credentials
    try:
        api_key_id, private_key = load_kalshi_credentials()
        print(f"✓ Loaded API credentials (Key ID: {api_key_id[:8]}...)")
    except Exception as e:
        print(f"✗ Failed to load credentials: {e}")
        return
    
    # Create API client
    api = KalshiAPI(api_key_id, private_key)
    
    print("\n📊 Searching for NBA markets...")
    nba_markets = fetch_nba_markets()
    
    if nba_markets:
        print(f"\n🏀 Found {len(nba_markets)} NBA markets:\n")
        for i, market in enumerate(nba_markets[:10], 1):
            print(f"{i:2}. [{market.get('ticker', 'N/A')[:30]}]")
            print(f"    {market.get('title', 'N/A')[:80]}")
            yes_ask = market.get('yes_ask', 0)
            if yes_ask:
                print(f"    YES: ${yes_ask/100:.2f} / NO: ${market.get('no_ask', 0)/100:.2f}")
            print()
    
    print("\n📊 Searching for NHL markets...")
    nhl_markets = fetch_nhl_markets()
    
    if nhl_markets:
        print(f"\n🏒 Found {len(nhl_markets)} NHL markets:\n")
        for i, market in enumerate(nhl_markets[:10], 1):
            print(f"{i:2}. [{market.get('ticker', 'N/A')[:30]}]")
            print(f"    {market.get('title', 'N/A')[:80]}")
            yes_ask = market.get('yes_ask', 0)
            if yes_ask:
                print(f"    YES: ${yes_ask/100:.2f} / NO: ${market.get('no_ask', 0)/100:.2f}")
            print()


if __name__ == "__main__":
    main()


def fetch_ligue1_markets(date_str=None):
    """Fetch Kalshi markets for Ligue 1 games."""
    try:
        # Load credentials
        api_key_id, private_key = load_kalshi_credentials()
        
        # Make authenticated request
        api = KalshiAPI(api_key_id, private_key)
        
        # Try SDK first
        try:
            # Note: Actual series ticker may vary - check Kalshi docs
            # Common formats: KXLIGUE1GAME, KXFRENCHLEAGUE, etc.
            result = api.get_markets(series_ticker='KXLIGUE1GAME', limit=200)
            if result and 'markets' in result:
                markets = result['markets']
                active_markets = [m for m in markets if m.get('status') in ['active', 'initialized', 'open']]
                print(f"✓ Found {len(active_markets)} Ligue 1 markets")
                return active_markets
        except Exception as e:
            print(f"⚠️  Error fetching Ligue 1 markets: {e}")
            # Try alternative ticker formats
            for ticker in ['KXFRENCHLEAGUE', 'KXFRENCHFOOTBALL', 'KXLIGUE1']:
                try:
                    result = api.get_markets(series_ticker=ticker, limit=200)
                    if result and 'markets' in result:
                        markets = result['markets']
                        active_markets = [m for m in markets if m.get('status') in ['active', 'initialized', 'open']]
                        if active_markets:
                            print(f"✓ Found {len(active_markets)} Ligue 1 markets using {ticker}")
                            return active_markets
                except:
                    continue
            return []
            
        return []
    except Exception as e:
        print(f"❌ Failed to fetch Ligue 1 markets: {e}")
        return []
