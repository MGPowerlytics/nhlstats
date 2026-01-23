import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))
from plugins.elo import NHLEloRating
from plugins.elo import NCAABEloRating
from plugins.elo import WNCAABEloRating
from db_manager import default_db

def analyze_nhl_sharp_value():
    print("\n🏒 Analyzing NHL Sharp Consensus Value (Unified Database)...")

    # 1. Load NHL historical lines from PostgreSQL
    query = """
        SELECT game_date, home_team, away_team,
               home_implied_prob_open as k_prob,
               home_implied_prob_close as sharp_prob
        FROM historical_betting_lines
        WHERE home_implied_prob_open IS NOT NULL AND home_implied_prob_close IS NOT NULL
    """
    lines_df = default_db.fetch_df(query)
    if lines_df.empty:
        print("❌ No NHL historical lines found in historical_betting_lines.")
        return

    # 2. Get results for these games from 'unified_games' table
    query = """
        SELECT game_date, home_team_id as home_team, away_team_id as away_team,
               CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
        FROM unified_games
        WHERE sport = 'NHL' AND home_score IS NOT NULL AND away_score IS NOT NULL
    """
    results_df = default_db.fetch_df(query)

    # Normalize dates and team names
    lines_df['game_date'] = pd.to_datetime(lines_df['game_date']).dt.date.astype(str)
    results_df['game_date'] = pd.to_datetime(results_df['game_date']).dt.date.astype(str)

    df = pd.merge(lines_df, results_df,
                  on=['game_date', 'home_team', 'away_team'])

    print(f"✓ Matched {len(df)} games with results and lines.")
    if df.empty:
        return

    # 3. Elo Simulation
    elo = NHLEloRating(k_factor=20, home_advantage=50)
    query = """
        SELECT game_date, home_team_id as home_team, away_team_id as away_team,
               CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
        FROM unified_games
        WHERE sport = 'NHL' AND home_score IS NOT NULL AND away_score IS NOT NULL
        ORDER BY game_date
    """
    all_games = default_db.fetch_df(query)

    elo_probs = {} # (date, home, away) -> prob
    for _, g in all_games.iterrows():
        d = str(pd.to_datetime(g['game_date']).date())
        # Predict BEFORE update
        prob = elo.predict(g['home_team'], g['away_team'])
        elo_probs[(d, g['home_team'], g['away_team'])] = prob
        # Update
        elo.update(g['home_team'], g['away_team'], g['home_win'])

    df['elo_prob'] = df.apply(lambda x: elo_probs.get((x['game_date'], x['home_team'], x['away_team']), 0.5), axis=1)

    # 4. Simulation
    threshold = 0.05

    strategies = [
        ("Base Elo vs Opening Line (Kalshi Proxy)", False),
        ("Elo vs Sharp (Closing Line)", "sharp_only"),
        ("Elo + Sharp Consensus (Confirmation)", True)
    ]

    print(f"\n📈 NHL Simulation Results (N={len(df)}):")
    print(f"{ 'Strategy':<45} | {'ROI':<8} | {'Win Rate':<8} | {'Bets'}")
    print("-" * 80)

    for name, use_sharp in strategies:
        temp_df = df.copy()

        # Bets on home
        temp_df['edge_home'] = temp_df['elo_prob'] - temp_df['k_prob']
        # Bets on away
        temp_df['edge_away'] = (1 - temp_df['elo_prob']) - (1 - temp_df['k_prob'])

        if use_sharp == "sharp_only":
            bets_h = temp_df[temp_df['elo_prob'] - temp_df['sharp_prob'] > threshold]
            bets_a = temp_df[(1-temp_df['elo_prob']) - (1-temp_df['sharp_prob']) > threshold]
        elif use_sharp == True:
            # Elo edge must exist AND Sharp must agree (Sharp prob > Kalshi prob)
            bets_h = temp_df[(temp_df['edge_home'] > threshold) & (temp_df['sharp_prob'] > temp_df['k_prob'] + 0.01)]
            bets_a = temp_df[(temp_df['edge_away'] > threshold) & ((1-temp_df['sharp_prob']) > (1-temp_df['k_prob']) + 0.01)]
        else:
            bets_h = temp_df[temp_df['edge_home'] > threshold]
            bets_a = temp_df[temp_df['edge_away'] > threshold]

        num_win = bets_h['home_win'].sum() + (len(bets_a) - bets_a['home_win'].sum())
        total = len(bets_h) + len(bets_a)

        if total == 0: continue

        # Payouts (using Opening Line as the bet price)
        profit = 0
        for _, b in bets_h.iterrows():
            if b['home_win'] == 1: profit += (1/b['k_prob'] - 1)
            else: profit -= 1
        for _, b in bets_a.iterrows():
            if b['home_win'] == 0: profit += (1/(1-b['k_prob']) - 1)
            else: profit -= 1

        roi = profit / total
        print(f"  {name:45} | {roi:7.2%} | {num_win/total:8.1%} | {total}")

def analyze_ncaab_recent_value():
    print("\n🏀 Analyzing Recent NCAAB/WNCAAB Sharp Performance...")

    # We use all placed bets to see if CLV (Closing Line Value) predicted profit
    query = """
        SELECT sport, bet_line_prob, closing_line_prob, profit_dollars
        FROM placed_bets
        WHERE sport IN ('NCAAB', 'WNCAAB') AND status = 'Settled'
    """
    df = default_db.fetch_df(query)
    if df.empty:
        print("❌ No settled basketball bets found in placed_bets.")
        return

    print(f"✓ Found {len(df)} settled basketball bets.")

    df['clv_edge'] = df['closing_line_prob'] - df['bet_line_prob']

    # Strategy: What if we only took bets with positive CLV?
    clv_bets = df[df['clv_edge'] > 0]

    actual_profit = df['profit_dollars'].sum()
    actual_roi = actual_profit / (len(df) * 2) # Assuming $2 bet

    print(f"\n📈 Basketball Results:")
    print(f"  Overall Actual ROI: {actual_roi:7.2%} ({len(df)} bets)")

    if not clv_bets.empty:
        clv_profit = clv_bets['profit_dollars'].sum()
        clv_roi = clv_profit / (len(clv_bets) * 2)
        print(f"  If only Positive CLV: {clv_roi:7.2%} ({len(clv_bets)} bets)")
    else:
        print("  No positive CLV bets found.")

if __name__ == "__main__":
    analyze_nhl_sharp_value()
    analyze_ncaab_recent_value()
