import sys
import os
import logging

# Configure logging to stdout
logging.basicConfig(level=logging.INFO)

# Add plugins to path
sys.path.append(os.getcwd())

try:
    from plugins.kalshi_markets import fetch_nba_markets, save_to_db
    print("✓ Imported fetch_nba_markets")
except ImportError as e:
    print(f"✗ Failed to import: {e}")
    sys.exit(1)

def test_fetch():
    print("Fetching NBA markets...")
    markets = fetch_nba_markets()
    print(f"Fetched {len(markets)} markets")

    if markets:
        print("Sample market:", markets[0])
        # Try saving to DB explicitly to see if it works
        try:
            from plugins.db_manager import default_db
            print("Saving to DB...")
            count = save_to_db("nba", markets, default_db)
            print(f"Saved {count} odds records")
        except Exception as e:
            print(f"Error saving to DB: {e}")

if __name__ == "__main__":
    test_fetch()
