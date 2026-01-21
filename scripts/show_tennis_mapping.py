#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))
from kalshi_markets import fetch_tennis_markets
import re

def get_last_name_code(full_name):
    if not full_name: return ""
    # Handle "First Last" or "Last"
    parts = full_name.strip().split()
    last_name = parts[-1] if parts else full_name
    return last_name[:3].upper()

def show_athlete_mapping():
    print("🎾 Fetching all open Tennis markets from Kalshi...")
    markets = fetch_tennis_markets()

    mapping = {}

    for m in markets:
        title = m.get('title', '')
        ticker = m.get('ticker', '')

        # Regex to find "Player A vs Player B"
        match = re.search(r"win the (.*?) vs (.*?) (?:match|:)", title)
        if not match:
            match = re.search(r"win the (.*?) vs (.*?) match", title)

        if match:
            p1 = match.group(1).strip()
            p2 = match.group(2).strip()
            if p2.endswith(' match'):
                p2 = p2[:-6].strip()

            # The part after the last hyphen is the outcome (winner) code
            ticker_parts = ticker.split('-')
            outcome_code = ticker_parts[-1] if len(ticker_parts) > 1 else ""

            p1_code = get_last_name_code(p1)
            p2_code = get_last_name_code(p2)

            # Match the outcome code to the correct athlete
            winner = None
            if outcome_code == p1_code:
                winner = p1
            elif outcome_code == p2_code:
                winner = p2

            if winner:
                if winner not in mapping: mapping[winner] = []
                mapping[winner].append(ticker)

    print("\n" + "="*100)
    print(f"{ 'ATHLETE':<30} | {'CORRECT KALSHI TICKER'}")
    print("-" * 100)

    # Sort by athlete name
    for athlete in sorted(mapping.keys()):
        for ticker in mapping[athlete]:
            print(f"{athlete:<30} | {ticker}")
    print("="*100)
    print(f"Total Athletes with Matches: {len(mapping)}")

if __name__ == "__main__":
    show_athlete_mapping()
