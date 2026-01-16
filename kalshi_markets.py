#!/usr/bin/env python3
"""
Fetch Kalshi markets for NHL games and compare with model predictions.
"""

import requests
import json
import time
import hmac
import hashlib
import base64
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode


class KalshiAPI:
    """Kalshi API client with API key authentication"""
    
    def __init__(self, api_key_id, private_key_pem):
        self.api_key_id = api_key_id
        self.private_key_pem = private_key_pem
        self.base_url = "https://api.elections.kalshi.com/trade-api/v2"
        self.token = None
        self.token_expiry = 0
    
    def _sign_request(self, method, path, body=""):
        """Create signature for API request"""
        timestamp = str(int(time.time() * 1000))
        
        # Create message to sign
        message = f"{timestamp}{method}{path}{body}"
        
        # Sign with private key
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend
        
        # Load private key
        private_key = serialization.load_pem_private_key(
            self.private_key_pem.encode(),
            password=None,
            backend=default_backend()
        )
        
        # Sign message
        signature = private_key.sign(
            message.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        
        # Base64 encode signature
        signature_b64 = base64.b64encode(signature).decode()
        
        return timestamp, signature_b64
    
    def _get_headers(self, method, path, body=""):
        """Get headers for authenticated request"""
        timestamp, signature = self._sign_request(method, path, body)
        
        return {
            "Content-Type": "application/json",
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp
        }
    
    def login(self):
        """Login to get access token"""
        path = "/login"
        headers = self._get_headers("POST", path)
        
        response = requests.post(
            f"{self.base_url}{path}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("token")
            # Token typically expires in 1 hour
            self.token_expiry = time.time() + 3600
            print("✓ Logged in to Kalshi")
            return True
        else:
            print(f"✗ Login failed: {response.status_code} {response.text}")
            return False
    
    def _ensure_logged_in(self):
        """Ensure we have a valid token"""
        if not self.token or time.time() >= self.token_expiry:
            return self.login()
        return True
    
    def get_markets(self, event_ticker=None, series_ticker=None, status=None, limit=100):
        """
        Get markets from Kalshi
        
        Args:
            event_ticker: Filter by event ticker (e.g., 'NHL')
            series_ticker: Filter by series ticker
            status: Filter by status ('open', 'closed', 'settled')
            limit: Max number of markets to return
        """
        if not self._ensure_logged_in():
            return None
        
        path = "/markets"
        params = {}
        
        if event_ticker:
            params['event_ticker'] = event_ticker
        if series_ticker:
            params['series_ticker'] = series_ticker
        if status:
            params['status'] = status
        if limit:
            params['limit'] = limit
        
        if params:
            path += f"?{urlencode(params)}"
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(f"{self.base_url}{path}", headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"✗ Failed to get markets: {response.status_code} {response.text}")
            return None
    
    def search_markets(self, query, limit=100):
        """Search markets by text query"""
        if not self._ensure_logged_in():
            return None
        
        path = f"/markets?search_query={query}&limit={limit}"
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(f"{self.base_url}{path}", headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"✗ Search failed: {response.status_code} {response.text}")
            return None


def load_kalshi_credentials():
    """Load Kalshi API credentials from kalshkey file"""
    key_file = Path("kalshkey")
    
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


def main():
    print("🎲 Kalshi Markets Fetcher")
    print("=" * 80)
    
    # Load credentials
    try:
        api_key_id, private_key = load_kalshi_credentials()
        print(f"✓ Loaded API credentials (Key ID: {api_key_id[:8]}...)")
    except Exception as e:
        print(f"✗ Failed to load credentials: {e}")
        return
    
    # Install cryptography if needed
    try:
        import cryptography
    except ImportError:
        print("\n⚠ Installing cryptography package...")
        import subprocess
        subprocess.check_call(["pip", "install", "-q", "cryptography"])
        print("✓ Installed cryptography")
    
    # Create API client
    api = KalshiAPI(api_key_id, private_key)
    
    # Login
    if not api.login():
        print("✗ Failed to login")
        return
    
    print("\n📊 Searching for NHL markets...")
    
    # Search for NHL markets
    result = api.search_markets("NHL", limit=50)
    
    if result and 'markets' in result:
        markets = result['markets']
        print(f"\n✓ Found {len(markets)} NHL markets\n")
        
        for i, market in enumerate(markets[:20], 1):  # Show first 20
            ticker = market.get('ticker', 'N/A')
            title = market.get('title', 'N/A')
            subtitle = market.get('subtitle', '')
            status = market.get('status', 'N/A')
            yes_price = market.get('yes_bid', 0) / 100 if market.get('yes_bid') else None
            no_price = market.get('no_bid', 0) / 100 if market.get('no_bid') else None
            
            print(f"{i:2}. [{ticker}] {title}")
            if subtitle:
                print(f"    {subtitle}")
            print(f"    Status: {status}")
            if yes_price:
                print(f"    YES: ${yes_price:.2f} / NO: ${no_price:.2f}")
            print()
        
        if len(markets) > 20:
            print(f"... and {len(markets) - 20} more markets")
        
        # Save to file
        output_file = Path("data/kalshi_nhl_markets.json")
        output_file.parent.mkdir(exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n💾 Saved all markets to {output_file}")
        
    else:
        print("✗ No markets found")
        
        # Try getting all open markets
        print("\n📊 Fetching all open markets...")
        result = api.get_markets(status='open', limit=100)
        
        if result and 'markets' in result:
            markets = result['markets']
            print(f"✓ Found {len(markets)} open markets total")
            
            # Look for sports-related
            sports_markets = [m for m in markets if any(sport in m.get('title', '').upper() 
                                                        for sport in ['NHL', 'NBA', 'NFL', 'MLB'])]
            
            if sports_markets:
                print(f"✓ Found {len(sports_markets)} sports markets\n")
                
                for i, market in enumerate(sports_markets[:10], 1):
                    ticker = market.get('ticker', 'N/A')
                    title = market.get('title', 'N/A')
                    status = market.get('status', 'N/A')
                    print(f"{i:2}. [{ticker}] {title} ({status})")


if __name__ == "__main__":
    main()
