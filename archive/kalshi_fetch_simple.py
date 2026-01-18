#!/usr/bin/env python3
"""Fetch Kalshi markets"""

from kalshi_python import Configuration, ApiClient, MarketsApi
from pathlib import Path
import json
from datetime import datetime

# JSON encoder for datetime
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Load credentials
key_file = Path("kalshkey")
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

print("🎲 Kalshi Markets Fetcher")
print("=" * 80)
print(f"✓ Loaded API credentials (Key ID: {api_key_id[:8]}...)")

# Configure API client
config = Configuration(host="https://api.elections.kalshi.com/trade-api/v2")
config.api_key['api_key_id'] = api_key_id
config.api_key['private_key'] = private_key

# Create client
api_client = ApiClient(configuration=config)
markets_api = MarketsApi(api_client)

print("✓ Created Kalshi client")
print("\n📊 Fetching markets...")

try:
    # Get markets
    response = markets_api.get_markets(
        limit=200,
        status="open"
    )
    
    markets = response.to_dict().get('markets', [])
    
    if markets:
        print(f"✓ Found {len(markets)} open markets total\n")
        
        # Filter for sports/NHL
        nhl_markets = [m for m in markets if 'NHL' in m.get('title', '').upper()]
        sports_markets = [m for m in markets if any(sport in m.get('title', '').upper() 
                                                     for sport in ['NHL', 'NBA', 'NFL', 'MLB', 'HOCKEY', 'BASKETBALL', 'FOOTBALL', 'BASEBALL'])]
        
        if nhl_markets:
            print(f"🏒 Found {len(nhl_markets)} NHL markets:\n")
            
            for i, market in enumerate(nhl_markets[:20], 1):
                print(f"{i:2}. [{market.get('ticker')}] {market.get('title')}")
                if market.get('subtitle'):
                    print(f"    {market.get('subtitle')}")
                print(f"    Status: {market.get('status')}")
                yes_ask = market.get('yes_ask')
                if yes_ask:
                    print(f"    YES Ask: ${yes_ask/100:.2f} | Bid: ${market.get('yes_bid', 0)/100:.2f}")
                    print(f"    NO  Ask: ${market.get('no_ask', 0)/100:.2f} | Bid: ${market.get('no_bid', 0)/100:.2f}")
                print()
                
        elif sports_markets:
            print(f"⚽ Found {len(sports_markets)} sports markets (no NHL currently):\n")
            
            for i, market in enumerate(sports_markets[:15], 1):
                title = market.get('title', '')[:80]
                print(f"{i:2}. [{market.get('ticker')[:30]}...] {title}")
                print(f"    Status: {market.get('status')}")
                yes_ask = market.get('yes_ask')
                if yes_ask:
                    print(f"    YES: ${yes_ask/100:.2f} / NO: ${market.get('no_ask', 0)/100:.2f}")
        else:
            print("⚠ No sports markets found")
        
        # Save to file
        output_file = Path("data/kalshi_markets.json")
        output_file.parent.mkdir(exist_ok=True)
        
        markets_to_save = nhl_markets if nhl_markets else sports_markets if sports_markets else markets[:20]
        
        markets_data = {
            'timestamp': datetime.now().isoformat(),
            'total_count': len(markets),
            'nhl_count': len(nhl_markets),
            'sports_count': len(sports_markets),
            'markets': markets_to_save
        }
        
        with open(output_file, 'w') as f:
            json.dump(markets_data, f, indent=2, cls=DateTimeEncoder)
        print(f"\n💾 Saved {len(markets_to_save)} markets to {output_file}")
        
    else:
        print("✗ No markets returned")
        
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
