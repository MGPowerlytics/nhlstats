#!/usr/bin/env python3
import sys
import os
import json
import re
from pathlib import Path
import pandas as pd
from datetime import datetime

# Add plugins directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))
from kalshi_markets import fetch_epl_markets, fetch_ligue1_markets
from the_odds_api import TheOddsAPI

def normalize_name(name):
    if not name: return ""
    name = name.lower()
    return re.sub(r'[^a-z0-9]', '', name)

def find_current_value(sport_name):
    print(f"\n🔍 Finding current {sport_name.upper()} Value vs Sharp Odds...")

    # 1. Fetch Kalshi Markets
    fetch_funcs = {
        'epl': fetch_epl_markets,
        'ligue1': fetch_ligue1_markets
    }

    kalshi_markets = fetch_funcs[sport_name]()
    if not kalshi_markets:
        print(f"❌ No Kalshi {sport_name} markets found.")
        return

    # 2. Fetch External Odds
    api_key_file = Path('data/odds_api_key')
    if not api_key_file.exists(): api_key_file = Path('odds_api_key')
    api_key = api_key_file.read_text().strip() if api_key_file.exists() else os.getenv('ODDS_API_KEY')

    odds_api = TheOddsAPI(api_key=api_key)

    # Map to Odds API keys
    api_sport_map = {
        'epl': 'soccer_epl',
        'ligue1': 'soccer_france_ligue_one'
    }

    ext_odds = odds_api.fetch_markets(sport_name)

    print(f"\n📊 Comparing {len(kalshi_markets)} Kalshi markets vs {len(ext_odds)} external games...")
    print("-" * 100)
    print(f"{ 'MATCHUP':<40} | {'OUTCOME':<7} | {'KALSHI':<7} | {'SHARP':<7} | {'EDGE'}")
    print("-" * 100)

    found = 0
    for km in kalshi_markets:
        ticker = km.get('ticker', '')
        # Yes price
        k_prob = km.get('yes_ask', 0) / 100.0
        if k_prob <= 0: continue

        # Tickers for soccer are like KXEPLGAME-2026JAN20-CRY-TOT-DRAW or KXEPLGAME-2026JAN20-CRY-TOT-CRY
        parts = ticker.split('-')
        if len(parts) < 5: continue

        t1_code = parts[-3]
        t2_code = parts[-2]
        outcome_code = parts[-1]

        # Find match
        match = None
        for em in ext_odds:
            em_h = normalize_name(em['home_team'])
            em_a = normalize_name(em['away_team'])

            # Simple matching: check if codes are in names or known mappings
            # (In a real system we'd use a robust mapping table)
            if (t1_code.lower() in em_h or t1_code.lower() in em_a) and \
               (t2_code.lower() in em_h or t2_code.lower() in em_a):
                match = em
                break

        if match:
            # Determine which outcome we are betting on
            side = None
            if outcome_code == 'DRAW':
                side = 'draw'
            elif normalize_name(outcome_code) in normalize_name(match['home_team']):
                side = 'home'
            else:
                side = 'away'

            # Get sharp prob
            pin = match['bookmakers'].get('pinnacle') or match['bookmakers'].get('betmgm') or list(match['bookmakers'].values())[0]

            sharp_prob = pin.get(f'{side}_prob')
            if sharp_prob:
                edge = sharp_prob - k_prob
                if edge > 0.02:
                    found += 1
                    match_str = f"{match['away_team']} @ {match['home_team']}"
                    print(f"{match_str[:40]:<40} | {outcome_code:<7} | {k_prob:6.1%} | {sharp_prob:6.1%} | {edge:+.1%}")

    if found == 0:
        print("No significant discrepancies found currently.")

if __name__ == "__main__":
    find_current_value('epl')
    find_current_value('ligue1')
