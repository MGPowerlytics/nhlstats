import json
from datetime import datetime
from kalshi_python import Configuration, ApiClient, MarketsApi

def load_kalshi_creds():
    with open('kalshkey', 'r') as f:
        content = f.read()
    lines = content.split('\n')
    key_id = lines[0].split(': ')[1].strip()
    private_key_lines = []
    in_key = False
    for line in lines:
        if 'BEGIN RSA PRIVATE KEY' in line: in_key = True
        if in_key: private_key_lines.append(line)
        if 'END RSA PRIVATE KEY' in line: break
    private_key = '\n'.join(private_key_lines)
    return key_id, private_key

def main():
    key_id, private_key = load_kalshi_creds()
    config = Configuration(host="https://api.elections.kalshi.com/trade-api/v2")
    config.api_key['api_key_id'] = key_id
    config.api_key['private_key'] = private_key
    client = ApiClient(configuration=config)
    markets_api = MarketsApi(client)
    
    candidates = ['KXNCAABGAME', 'KXNCAAMBGAME']
    
    for ticker in candidates:
        print(f"Checking {ticker}...")
        try:
            # Check for active markets first
            res = markets_api.get_markets(series_ticker=ticker, status='open', limit=10)
            if res.markets:
                print(f"  OPEN markets found: {len(res.markets)}")
                print(f"  Example: {res.markets[0].title} ({res.markets[0].ticker})")
            else:
                print(f"  No OPEN markets.")
                
            # Check for history (closed markets)
            res = markets_api.get_markets(series_ticker=ticker, limit=10)
            if res.markets:
                print(f"  Total recent markets (open+closed): {len(res.markets)}")
                if not res.markets and res.markets:
                     print(f"  Example: {res.markets[0].title}")
            else:
                print(f"  No markets history found.")
                
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    main()
