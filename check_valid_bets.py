import json
import glob
import os

files = glob.glob("data/*/bets_2026-02-02.json")

# Configuration from code
min_confidence = 0.68
excluded_segments = [
    ("nhl", "MEDIUM"),
    ("tennis", "LOW")
]

print("Scanning for valid bets...")
valid_bets_count = 0

for f in files:
    sport = f.split('/')[1]
    try:
        with open(f, 'r') as fp:
            data = json.load(fp)
            if not isinstance(data, list):
                continue

            for bet in data:
                # 1. Check Kelly > 0
                if bet.get('kelly_fraction', 0) <= 0:
                    continue

                # 2. Check min_confidence (elo_prob)
                if bet.get('elo_prob', 0) < min_confidence:
                    continue

                # 3. Check excluded segments
                confidence_str = bet.get('confidence', 'UNKNOWN')
                is_excluded = False
                for ex_sport, ex_conf in excluded_segments:
                    if sport == ex_sport and confidence_str == ex_conf:
                        is_excluded = True
                        break

                if is_excluded:
                    continue

                print(f"✅ VALID BET FOUND: {sport} - {bet.get('home_team')} vs {bet.get('away_team')}")
                print(f"   Elo: {bet.get('elo_prob')}, Kelly: {bet.get('kelly_fraction')}, Conf: {confidence_str}")
                valid_bets_count += 1

    except Exception as e:
        print(f"Error reading {f}: {e}")

print(f"Total valid bets: {valid_bets_count}")
