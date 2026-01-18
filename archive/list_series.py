import json
from pathlib import Path
from kalshi_python import Configuration, ApiClient, SeriesApi

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
    series_api = SeriesApi(client)
    
    try:
        print("SeriesApi methods:")
        methods = [m for m in dir(series_api) if not m.startswith('_')]
        print(methods)
        
        if 'get_series' in methods:
             print("\nCalling get_series()...")
             res = series_api.get_series()
             if hasattr(res, 'series'):
                 print(f"Found {len(res.series)} series")
                 for s in res.series:
                     content = (str(s.ticker) + str(s.title)).upper()
                     if 'NCAA' in content or 'COLLEGE' in content or 'BASKET' in content:
                         print(f"MATCH: {s.ticker} - {s.title}")
             else:
                 print("Result:", res)
                 
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
