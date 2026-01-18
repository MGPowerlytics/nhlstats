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
        guesses = ['KXNCAAB', 'KXNCAABGAME', 'KXCOLLEGE', 'KXNCAA', 'NCAAB', 'KXCBKGAME']
        
        for g in guesses:
            try:
                print(f"Testing series_ticker={g}...")
                res = markets_api.get_markets(series_ticker=g, limit=5)
                if res.markets:
                    print(f"✓ SUCCESS! Found {len(res.markets)} markets for {g}")
                    print(f"Sample: {res.markets[0].ticker} - {res.markets[0].title}")
                else:
                    print(f"No markets for {g}")
            except Exception as e:
                print(f"Error checking {g}: {e}")

    except Exception as e:
        print(f"Fatal Error: {e}")

if __name__ == "__main__":
    main()
