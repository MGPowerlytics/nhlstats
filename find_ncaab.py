import json
from pathlib import Path
from kalshi_python import Configuration, ApiClient, MarketsApi

def load_kalshi_creds():
    with open('kalshkey', 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    key_id = lines[0].split(': ')[1].strip()
    
    # Extract private key
    private_key_lines = []
    in_key = False
    for line in lines:
        if 'BEGIN RSA PRIVATE KEY' in line:
            in_key = True
        if in_key:
            private_key_lines.append(line)
        if 'END RSA PRIVATE KEY' in line:
            break
            
    private_key = '\n'.join(private_key_lines)
    return key_id, private_key

def main():
    key_id, private_key = load_kalshi_creds()
    
    config = Configuration(host="https://api.elections.kalshi.com/trade-api/v2")
    config.api_key['api_key_id'] = key_id
    config.api_key['private_key'] = private_key
    
    client = ApiClient(configuration=config)
    markets_api = MarketsApi(client)
    
    print("Searching for NCAAB markets...")
    try:
        # Search widely
        response = markets_api.get_markets(limit=1000, status='open')
        for m in response.markets:
            t = m.ticker.upper()
            st = (m.series_ticker or "").upper()
            title = m.title.upper()
            
            if "NCAA" in t or "COLLEGE" in t or "BASKETBALL" in title:
                # Exclude NBA
                if "NBA" in t: continue
                
                print(f"Found: {m.ticker} (Series: {m.series_ticker}) - {m.title}")
                
    except Exception as e:
        print(e)

if __name__ == "__main__":
    main()
