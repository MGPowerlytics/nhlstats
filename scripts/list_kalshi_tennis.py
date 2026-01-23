#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))
from kalshi_markets import load_kalshi_credentials
import requests

def list_all_series():
    api_key_id, private_key = load_kalshi_credentials()

    tennis_series = [
        'KXATPMATCH', 'KXWTAMATCH',
        'KXATPCHALLENGERMATCH', 'KXWTACHALLENGERMATCH',
        'KXCHALLENGERMATCH',
        'KXEXHIBITIONMEN', 'KXEXHIBITIONWOMEN',
        'KXDAVISCUPMATCH', 'KXUNITEDCUPMATCH',
        'KXATPDOUBLES', 'KXWTADOUBLES'
    ]

    total_found = 0
    for series in tennis_series:
        url = f"https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker={series}&status=open&limit=100"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            markets = data.get('markets', [])
            if markets:
                print(f"\nSeries {series} found {len(markets)} active markets:")
                total_found += len(markets)
                for m in markets[:5]:
                    print(f"  {m.get('ticker')} - {m.get('title')}")
        else:
            print(f"Error {series}: {response.status_code}")

    print(f"\nTotal active tennis markets found: {total_found}")

if __name__ == "__main__":
    list_all_series()
