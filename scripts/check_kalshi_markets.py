import sys
import os
import logging

# Add plugins to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../plugins')))

from kalshi_markets import fetch_nba_markets, fetch_ncaab_markets, fetch_wncaab_markets

logging.basicConfig(level=logging.INFO)

print("Checking Kalshi Markets...")

try:
    print("\n--- NBA ---")
    nba = fetch_nba_markets()
    print(f"Found {len(nba)} NBA markets.")
    for m in nba[:3]:
        print(f"  {m['ticker']}: {m['title']}")

    print("\n--- NCAAB ---")
    ncaab = fetch_ncaab_markets()
    print(f"Found {len(ncaab)} NCAAB markets.")
    for m in ncaab[:3]:
        print(f"  {m['ticker']}: {m['title']}")

    print("\n--- WNCAAB ---")
    wncaab = fetch_wncaab_markets()
    print(f"Found {len(wncaab)} WNCAAB markets.")
    for m in wncaab[:3]:
        print(f"  {m['ticker']}: {m['title']}")

except Exception as e:
    print(f"Error: {e}")
