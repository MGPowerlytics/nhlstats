from kalshi_python import Configuration, ApiClient, MarketsApi

def main():
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

    config = Configuration(host="https://api.elections.kalshi.com/trade-api/v2")
    config.api_key['api_key_id'] = key_id
    config.api_key['private_key'] = private_key
    client = ApiClient(configuration=config)
    markets_api = MarketsApi(client)

    try:
        # Search for markets containing 'NCAA' or 'COLLEGE'
        print("Searching for NCAAB markets...")
        response = markets_api.get_markets(limit=1000, status='open')
        
        found = False
        prefixes = set()
        
        for m in response.markets:
            if 'NCAA' in m.title.upper() or 'COLLEGE' in m.title.upper() or 'NCAA' in m.ticker or 'BASKETBALL' in m.ticker:
                 if 'NBA' not in m.ticker:
                    print(f"Found: {m.ticker} - {m.title} (Series: {m.series_ticker})")
                    prefixes.add(m.series_ticker)
                    found = True
        
        if found:
            print("\nPotential Series Tickers:")
            for p in prefixes:
                print(p)
        else:
            print("No NCAAB markets found.")

    except Exception as e:
        print(e)

if __name__ == "__main__":
    main()
