#!/usr/bin/env python3
"""Search for all hockey/NHL markets on Kalshi"""

from kalshi_python import Configuration, ApiClient, MarketsApi, EventsApi, SeriesApi
from pathlib import Path
import json
from datetime import datetime

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Load credentials
key_file = Path("kalshkey")
content = key_file.read_text()

api_key_id = None
for line in content.split('\n'):
    if 'API key id:' in line:
        api_key_id = line.split(':', 1)[1].strip()
        break

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

print("🏒 Kalshi Hockey Markets Finder")
print("=" * 80)

# Configure API
config = Configuration(host="https://api.elections.kalshi.com/trade-api/v2")
config.api_key['api_key_id'] = api_key_id
config.api_key['private_key'] = private_key

api_client = ApiClient(configuration=config)
markets_api = MarketsApi(api_client)
events_api = EventsApi(api_client)
series_api = SeriesApi(api_client)

print("\n📊 Strategy 1: Searching for series with 'hockey'...")
try:
    series_response = series_api.get_series(limit=500)
    all_series = series_response.to_dict().get('series', [])
    
    hockey_series = [s for s in all_series if 'HOCKEY' in s.get('ticker', '').upper() or 
                                               'NHL' in s.get('ticker', '').upper() or
                                               'HOCKEY' in s.get('title', '').upper() or
                                               'NHL' in s.get('title', '').upper()]
    
    if hockey_series:
        print(f"✓ Found {len(hockey_series)} hockey series!")
        for i, series in enumerate(hockey_series[:10], 1):
            print(f"  {i}. [{series.get('ticker')}] {series.get('title')}")
    else:
        print("  No hockey series found in ticker/title")
        print(f"  Total series: {len(all_series)}")
        print("\n  Sample series tickers:")
        for s in all_series[:20]:
            print(f"    - {s.get('ticker')}")
except Exception as e:
    print(f"  Error: {e}")

print("\n📊 Strategy 2: Fetching ALL open markets (no limit)...")
try:
    all_markets = []
    cursor = None
    page = 1
    
    while page <= 10:  # Fetch up to 10 pages
        if cursor:
            response = markets_api.get_markets(limit=200, status="open", cursor=cursor)
        else:
            response = markets_api.get_markets(limit=200, status="open")
        
        data = response.to_dict()
        markets = data.get('markets', [])
        all_markets.extend(markets)
        
        print(f"  Page {page}: {len(markets)} markets")
        
        cursor = data.get('cursor')
        if not cursor or len(markets) == 0:
            break
        page += 1
    
    print(f"\n✓ Total markets fetched: {len(all_markets)}")
    
    # Search for hockey/NHL in various fields
    hockey_keywords = ['HOCKEY', 'NHL', 'BRUINS', 'RANGERS', 'MAPLE LEAFS', 'CANADIENS', 
                       'PENGUINS', 'CAPITALS', 'LIGHTNING', 'OILERS', 'AVALANCHE']
    
    hockey_markets = []
    for market in all_markets:
        market_str = json.dumps(market, default=str).upper()
        if any(keyword in market_str for keyword in hockey_keywords):
            hockey_markets.append(market)
    
    if hockey_markets:
        print(f"\n🏒 Found {len(hockey_markets)} hockey markets!\n")
        
        for i, market in enumerate(hockey_markets[:20], 1):
            ticker = market.get('ticker', 'N/A')
            title = market.get('title', 'N/A')
            subtitle = market.get('subtitle', '')
            status = market.get('status', 'N/A')
            yes_ask = market.get('yes_ask')
            yes_bid = market.get('yes_bid')
            
            print(f"{i:2}. [{ticker[:50]}]")
            print(f"    {title[:100]}")
            if subtitle:
                print(f"    {subtitle[:100]}")
            print(f"    Status: {status}")
            if yes_ask:
                print(f"    YES Ask: ${yes_ask/100:.2f} | Bid: ${yes_bid/100:.2f}")
            print()
        
        # Save to file
        output_file = Path("data/kalshi_hockey_markets.json")
        markets_data = {
            'timestamp': datetime.now().isoformat(),
            'total_markets': len(all_markets),
            'hockey_markets_count': len(hockey_markets),
            'markets': hockey_markets
        }
        
        with open(output_file, 'w') as f:
            json.dump(markets_data, f, indent=2, cls=DateTimeEncoder)
        print(f"💾 Saved {len(hockey_markets)} hockey markets to {output_file}")
        
    else:
        print("\n⚠️ No hockey markets found")
        print("\nSample market tickers:")
        for m in all_markets[:30]:
            print(f"  - {m.get('ticker', 'N/A')[:60]}")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
