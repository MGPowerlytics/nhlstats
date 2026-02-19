import json
import glob
import os

files = glob.glob("data/*/bets_2026-02-02.json")
print(f"Found {len(files)} bet files.")

total_bets = 0
for f in files:
    try:
        with open(f, 'r') as fp:
            data = json.load(fp)
            if not isinstance(data, list):
                print(f"{f}: Not a list")
                continue

            # Count positive Kelly bets
            positive_bets = [b for b in data if b.get('kelly_fraction', 0) > 0]
            print(f"{f}: {len(positive_bets)} bets > 0 Kelly (Total: {len(data)})")
            total_bets += len(positive_bets)
    except Exception as e:
        print(f"{f}: Error reading - {e}")

print(f"Total positive bets identified: {total_bets}")
