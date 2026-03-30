import logging
import sys
import os
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try imports
try:
    from kalshi_python import Configuration, ApiClient, MarketsApi
    try:
        from kalshi_python import MarketDataApi
        print("MarketDataApi exists!")
    except ImportError:
        print("MarketDataApi does NOT exist.")
except ImportError:
    print("kalshi_python not installed")
    sys.exit(1)

def load_credentials():
    # Hardcoded path logic from plugins/kalshi_markets.py
    paths = [Path("kalshkey"), Path("/opt/airflow/kalshkey")]
    key_file = next((p for p in paths if p.exists()), None)
    if not key_file:
        raise FileNotFoundError("kalshkey not found")

    content = key_file.read_text(encoding="utf-8")

    # Extract ID
    api_key_id = None
    for line in content.splitlines():
        if "API key id:" in line:
            api_key_id = line.split(": ")[1].strip()
            break

    # Extract Key
    private_key = None
    if "-----BEGIN RSA PRIVATE KEY-----" in content:
        lines = content.splitlines()
        key_lines = []
        in_key = False
        for line in lines:
            if "-----BEGIN RSA PRIVATE KEY-----" in line:
                in_key = True
            if in_key:
                key_lines.append(line)
            if "-----END RSA PRIVATE KEY-----" in line:
                break
        private_key = "\n".join(key_lines)
    else:
        # Check pem files
        pem_paths = [Path("kalshi_private_key.pem"), Path("/mnt/data2/nhlstats/kalshi_private_key.pem")]
        pem_file = next((p for p in pem_paths if p.exists()), None)
        if pem_file:
            private_key = pem_file.read_text(encoding="utf-8")

    return api_key_id, private_key

def inspect():
    try:
        api_key_id, private_key = load_credentials()
        print(f"Loaded credentials. Key ID: {api_key_id}")

        config = Configuration(host="https://api.elections.kalshi.com/trade-api/v2")
        config.api_key["api_key_id"] = api_key_id
        config.api_key["private_key"] = private_key

        client = ApiClient(configuration=config)
        api = MarketsApi(client)

        ticker = "KXNBAGAME-26MAR23MILLAC-MIL"
        print(f"\n--- Inspecting {ticker} ---")

        # Get Market
        try:
            resp = api.get_market(ticker)
            print("Get Market Response:")
            d = resp.to_dict()
            import pprint
            pprint.pprint(d)
        except Exception as e:
            print(f"Get Market Failed: {e}")

        # Get Orderbook
        try:
            resp = api.get_market_orderbook(ticker)
            print("\nGet Orderbook Response:")
            d = resp.to_dict()
            import pprint
            pprint.pprint(d)
        except Exception as e:
            print(f"Get Orderbook Failed: {e}")

        # Get Markets List
        try:
            print(f"\n--- Inspecting Markets List (Series: KXNBAGAME) ---")
            resp = api.get_markets(series_ticker="KXNBAGAME", limit=5)
            d = resp.to_dict()
            if 'markets' in d and d['markets']:
                print("First market in list:")
                import pprint
                pprint.pprint(d['markets'][0])
            else:
                print("No markets found in list")
        except Exception as e:
            print(f"Get Markets List Failed: {e}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect()
