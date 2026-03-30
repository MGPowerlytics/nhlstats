import sys
import os
import time
sys.path.append(os.getcwd())
try:
    from kalshi_python import Configuration, ApiClient, MarketsApi
except ImportError:
    print("kalshi_python not installed")
    sys.exit(1)

from plugins.kalshi_markets import load_kalshi_credentials

def test_host(host_url):
    print(f"\nTesting host: {host_url}")
    try:
        api_key_id, private_key = load_kalshi_credentials()
        config = Configuration(host=host_url)
        config.api_key["api_key_id"] = api_key_id
        config.api_key["private_key"] = private_key

        client = ApiClient(configuration=config)
        markets_api = MarketsApi(client)

        # Try to fetch NBA markets
        print("  Fetching NBA markets...")
        response = markets_api.get_markets(series_ticker="KXNBAGAME", limit=5)
        markets = response.to_dict().get("markets", [])
        print(f"  Found {len(markets)} markets")

        if markets:
            ticker = markets[0]["ticker"]
            print(f"  Testing orderbook for {ticker}...")
            # Try get_market_orderbook
            try:
                ob = markets_api.get_market_orderbook(ticker=ticker)
                print(f"  Orderbook raw: {ob}")
                print(f"  Orderbook dict: {ob.to_dict()}")
            except Exception as e:
                print(f"  Orderbook failed: {e}")

    except Exception as e:
        print(f"  Host failed: {e}")

hosts = [
    "https://api.elections.kalshi.com/trade-api/v2",
    "https://trading-api.kalshi.com/trade-api/v2",
    "https://api.kalshi.com/trade-api/v2"
]

for h in hosts:
    test_host(h)
    time.sleep(1)
