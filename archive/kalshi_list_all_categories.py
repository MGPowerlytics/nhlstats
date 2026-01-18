#!/usr/bin/env python3
"""List all available categories and series on Kalshi"""

from kalshi_python import Configuration, ApiClient, EventsApi, SeriesApi
from pathlib import Path

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

print("🔍 Kalshi Categories & Events Explorer")
print("=" * 80)

# Configure API
config = Configuration(host="https://api.elections.kalshi.com/trade-api/v2")
config.api_key['api_key_id'] = api_key_id
config.api_key['private_key'] = private_key

api_client = ApiClient(configuration=config)
events_api = EventsApi(api_client)
series_api = SeriesApi(api_client)

print("\n📊 Fetching all series...")
try:
    response = series_api.get_series()
    all_series = response.to_dict().get('series', [])
    
    print(f"✓ Found {len(all_series)} series\n")
    
    # Group by category/prefix
    categories = {}
    for series in all_series:
        ticker = series.get('ticker', '')
        title = series.get('title', '')
        
        # Extract prefix (usually indicates category)
        prefix = ticker.split('-')[0] if '-' in ticker else ticker[:10]
        
        if prefix not in categories:
            categories[prefix] = []
        categories[prefix].append({'ticker': ticker, 'title': title})
    
    print(f"📁 Categories found: {len(categories)}\n")
    
    for category, series_list in sorted(categories.items()):
        print(f"\n{category}: {len(series_list)} series")
        for series in series_list[:5]:
            print(f"  - {series['ticker']}: {series['title'][:60]}")
        if len(series_list) > 5:
            print(f"  ... and {len(series_list) - 5} more")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n\n📊 Fetching events with 'hockey' or 'nhl' category...")
try:
    # Try different category values
    for category in ['SPORTS', 'HOCKEY', 'NHL', 'sports', 'hockey', 'nhl']:
        try:
            print(f"\nTrying category='{category}'...")
            response = events_api.get_events(category=category, limit=50)
            events = response.to_dict().get('events', [])
            
            if events:
                print(f"  ✓ Found {len(events)} events!")
                for i, event in enumerate(events[:10], 1):
                    print(f"    {i}. {event.get('ticker', 'N/A')}: {event.get('title', 'N/A')[:60]}")
            else:
                print(f"  No events found")
        except Exception as e:
            print(f"  Error: {str(e)[:100]}")
            
except Exception as e:
    print(f"Error: {e}")
    
print("\n\n📊 Getting ALL events (no filter)...")
try:
    response = events_api.get_events(limit=200, status='open')
    events = response.to_dict().get('events', [])
    
    print(f"✓ Found {len(events)} open events\n")
    
    # Look for hockey/nhl
    hockey_events = [e for e in events if any(kw in str(e).upper() for kw in ['HOCKEY', 'NHL', 'BRUINS', 'RANGERS'])]
    
    if hockey_events:
        print(f"🏒 Found {len(hockey_events)} hockey events!")
        for event in hockey_events[:10]:
            print(f"  - {event.get('ticker')}: {event.get('title')}")
    else:
        print("⚠️ No hockey events found")
        print("\nSample event tickers:")
        for e in events[:20]:
            print(f"  - {e.get('ticker', 'N/A')}: {e.get('title', 'N/A')[:60]}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
