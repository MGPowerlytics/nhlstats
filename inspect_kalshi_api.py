import sys
import os
import logging
from pprint import pprint

# Add plugins to path
sys.path.append(os.getcwd())

# Need to set up logging to see debug output if any
logging.basicConfig(level=logging.INFO)

try:
    from plugins.kalshi_markets import KalshiMarkets
except ImportError:
    print("Error importing KalshiMarkets. Make sure plugins/ is in PYTHONPATH.")
    sys.exit(1)

def inspect():
    try:
        print("Initializing KalshiMarkets...")
        kalshi = KalshiMarkets()

        print("\n--- MarketsApi Attributes ---")
        # List attributes to see available methods
        attrs = [m for m in dir(kalshi.markets_api) if not m.startswith("_")]
        pprint(attrs)

        # Pick a ticker from previous logs that is for TODAY
        # KXNBAGAME-26MAR23MILLAC-MIL
        ticker = "KXNBAGAME-26MAR23MILLAC-MIL"

        print(f"\n--- Get Market: {ticker} ---")
        try:
            market_resp = kalshi.markets_api.get_market(ticker=ticker)
            print(f"Response Type: {type(market_resp)}")
            # The response object likely has a 'market' attribute or is a wrapper
            if hasattr(market_resp, 'market'):
                 print("Has .market attribute")
                 pprint(market_resp.market.to_dict())
            else:
                 print("No .market attribute, calling to_dict()")
                 pprint(market_resp.to_dict())
        except Exception as e:
            print(f"Error fetching market: {e}")

        print(f"\n--- Get Orderbook: {ticker} ---")
        try:
            ob_resp = kalshi.markets_api.get_market_orderbook(ticker=ticker)
            print(f"Response Type: {type(ob_resp)}")
            if hasattr(ob_resp, 'order_book'):
                 print("Has .order_book attribute")
                 pprint(ob_resp.order_book.to_dict())
            else:
                 print("No .order_book attribute, calling to_dict()")
                 pprint(ob_resp.to_dict())

        except Exception as e:
            print(f"Error fetching orderbook: {e}")

    except Exception as e:
        print(f"Initialization failed: {e}")

if __name__ == "__main__":
    inspect()
