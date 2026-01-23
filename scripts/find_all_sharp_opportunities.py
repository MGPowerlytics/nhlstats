#!/usr/bin/env python3
import sys
import os
import re
from pathlib import Path
import pandas as pd
from datetime import datetime

# Add plugins directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))
from kalshi_markets import fetch_tennis_markets, fetch_nhl_markets, fetch_ligue1_markets
from plugins.elo import TennisEloRating
from plugins.elo import NHLEloRating
from plugins.elo import Ligue1EloRating
from the_odds_api import TheOddsAPI
from odds_comparator import OddsComparator
from naming_resolver import NamingResolver

def find_volume_opportunities():
    print("🚀 Finding ALL Current Volume-Optimized Sharp Opportunities...")
    print("🎯 Sports: TENNIS, NHL, LIGUE 1")
    print("📊 Strategy: DB-Backed Naming Resolution + Sharp Confirmation")
    print("-" * 120)

    # 1. Setup
    api_key_file = Path('data/odds_api_key')
    if not api_key_file.exists(): api_key_file = Path('odds_api_key')
    api_key = api_key_file.read_text().strip() if api_key_file.exists() else os.getenv('ODDS_API_KEY')

    odds_api = TheOddsAPI(api_key=api_key)
    comparator = OddsComparator()

    # 2. Process
    configs = {
        'tennis': {'fetch': fetch_tennis_markets, 'system': TennisEloRating(), 'threshold': 0.60},
        'nhl': {'fetch': fetch_nhl_markets, 'system': NHLEloRating(), 'threshold': 0.66},
        'ligue1': {'fetch': fetch_ligue1_markets, 'system': Ligue1EloRating(), 'threshold': 0.45}
    }

    all_opps = []

    for sport, cfg in configs.items():
        print(f"\nScanning {sport.upper()}...")

        # Refresh Data
        cfg['fetch']()
        if sport == 'tennis':
            odds_api.SPORT_KEYS['atp'] = 'tennis_atp_aus_open_singles'
            odds_api.SPORT_KEYS['wta'] = 'tennis_wta_aus_open_singles'
            odds_api.fetch_and_save_markets('atp', 'today')
            odds_api.fetch_and_save_markets('wta', 'today')
        else:
            odds_api.fetch_and_save_markets(sport, 'today')

        # Load Elo
        if sport == 'tennis':
            atp_df = pd.read_csv('data/atp_current_elo_ratings.csv')
            wta_df = pd.read_csv('data/wta_current_elo_ratings.csv')
            elo_data = {"ATP": dict(zip(atp_df['team'], atp_df['rating'])),
                       "WTA": dict(zip(wta_df['team'], wta_df['rating']))}
            cfg['system'].atp_ratings = elo_data['ATP']
            cfg['system'].wta_ratings = elo_data['WTA']
        else:
            df = pd.read_csv(f'data/{sport}_current_elo_ratings.csv')
            elo_data = dict(zip(df['team'], df['rating']))
            cfg['system'].ratings = elo_data

        # Find opportunities (using new DB-backed resolver inside comparator)
        opps = comparator.find_opportunities(
            sport=sport,
            elo_ratings=elo_data,
            elo_system=cfg['system'],
            threshold=cfg['threshold'],
            min_edge=0.02, # VOLUME FOCUS
            use_sharp_confirmation=True
        )
        all_opps.extend(opps)

    # 3. Output
    print("\n" + "="*120)
    print(f"{ 'SPORT':<8} | { 'MATCHUP':<40} | { 'BET ON':<15} | { 'KALSHI':<7} | { 'ELO':<7} | {'EDGE'} | {'SHARP'}")
    print("-" * 120)

    if not all_opps:
        print("No opportunities found meeting criteria.")
    else:
        for o in sorted(all_opps, key=lambda x: x['edge'], reverse=True):
            sharp_status = "✅ Confirmed" if o.get('sharp_confirmed') else "Elo Only"
            print(f"{o['sport'].upper():<8} | {o['away_team'][:18]} @ {o['home_team'][:18]:<19} | {o['bet_on'][:15]:<15} | {o['market_prob']:6.1%} | {o['elo_prob']:6.1%} | {o['edge']:+.1%} | {sharp_status}")

    print("="*120)
    print(f"Total Confirmed Opportunities: {len(all_opps)}")

if __name__ == "__main__":
    find_volume_opportunities()
