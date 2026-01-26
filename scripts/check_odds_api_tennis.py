#!/usr/bin/env python3
import os
import requests
from pathlib import Path


def get_api_key():
    # Try environment variable first
    api_key = os.getenv("ODDS_API_KEY")
    if api_key:
        return api_key

    # Try file
    key_file = Path("data/odds_api_key")
    if not key_file.exists():
        key_file = Path("odds_api_key")

    if key_file.exists():
        return key_file.read_text().strip()
    return None


def list_tennis_sports():
    api_key = get_api_key()
    if not api_key:
        print("❌ No Odds API key found")
        return

    url = "https://api.the-odds-api.com/v4/sports"
    params = {"apiKey": api_key}

    response = requests.get(url, params=params)
    if response.status_code == 200:
        sports = response.json()
        tennis_sports = [s for s in sports if "tennis" in s["key"].lower()]
        print(f"Found {len(tennis_sports)} tennis sports:")
        for s in tennis_sports:
            print(f"  {s['key']}: {s['title']} ({s['group']})")
    else:
        print(f"Error: {response.status_code} - {response.text}")


if __name__ == "__main__":
    list_tennis_sports()
