#!/usr/bin/env python3
"""
Ligue1 Betting Backtest

Tests Elo-based betting strategies for French Ligue 1 using simulated odds.
"""

import sys
sys.path.insert(0, 'plugins')

from plugins.elo import Ligue1EloRating
import duckdb
import pandas as pd

def backtest_ligue1_betting(elo_threshold=0.45, min_edge=0.05):
    """
    Backtest Ligue1 betting strategy.

    Since we don't have historical Ligue1 odds, we'll simulate based on:
    - Soccer typically has ~27% vig
    - Favorites average around 1.80 odds (56% implied)
    - Underdogs average around 4.0 odds (25% implied)

    Args:
        elo_threshold: Min Elo probability to consider bet
        min_edge: Min edge over market required
    """
    print(f"\n{'='*80}")
    print(f"🇫🇷 LIGUE1 BETTING BACKTEST")
    print(f"{'='*80}")
    print(f"Strategy: {elo_threshold:.0%} Elo threshold, {min_edge:.0%} min edge")
    print(f"{'='*80}\n")

    # Load games
    conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)
    query = """
        SELECT game_date, season, home_team, away_team, home_score, away_score, result
        FROM ligue1_games
        WHERE season >= 2023  -- Focus on recent seasons for backtest
        ORDER BY game_date
    """
    games_df = conn.execute(query).fetchdf()
    conn.close()

    print(f"📊 Loaded {len(games_df)} games (2023-2026 seasons)")

    # Initialize Elo
    elo = Ligue1EloRating(k_factor=20, home_advantage=60)

    # Track bets
    bets = []

    for _, game in games_df.iterrows():
        # Get Elo prediction (home win probability, ignoring draws)
        home_prob = elo.predict(game['home_team'], game['away_team'])
        away_prob = 1 - home_prob

        # Simulate market odds with typical soccer vig (27%)
        # True probability → implied probability with vig → decimal odds
        # For simplicity, we'll use: market_prob = elo_prob * 0.95 (5% less confident than Elo)
        market_home_prob = home_prob * 0.95
        market_away_prob = away_prob * 0.95

        # Add vig (proportional to probability)
        total_market = market_home_prob + market_away_prob
        market_home_prob = market_home_prob / total_market * 1.27
        market_away_prob = market_away_prob / total_market * 1.27

        # Convert to decimal odds
        home_odds = 1 / market_home_prob if market_home_prob > 0 else 999
        away_odds = 1 / market_away_prob if market_away_prob > 0 else 999

        # Check betting opportunities
        home_edge = home_prob - market_home_prob
        away_edge = away_prob - market_away_prob

        # Actual outcome
        home_won = game['result'] == 'H'
        away_won = game['result'] == 'A'
        was_draw = game['result'] == 'D'

        # Bet on home team?
        if home_prob > elo_threshold and home_edge > min_edge:
            payout = home_odds if home_won else 0
            profit = payout - 1

            bets.append({
                'date': game['game_date'],
                'home': game['home_team'],
                'away': game['away_team'],
                'bet_on': 'home',
                'elo_prob': home_prob,
                'market_prob': market_home_prob,
                'edge': home_edge,
                'odds': home_odds,
                'won': home_won,
                'draw': was_draw,
                'profit': profit
            })

        # Bet on away team?
        elif away_prob > elo_threshold and away_edge > min_edge:
            payout = away_odds if away_won else 0
            profit = payout - 1

            bets.append({
                'date': game['game_date'],
                'home': game['home_team'],
                'away': game['away_team'],
                'bet_on': 'away',
                'elo_prob': away_prob,
                'market_prob': market_away_prob,
                'edge': away_edge,
                'odds': away_odds,
                'won': away_won,
                'draw': was_draw,
                'profit': profit
            })

        # Update Elo
        elo.update(game['home_team'], game['away_team'], game['result'])

    # Analyze results
    if not bets:
        print("❌ No bets placed with these parameters")
        return

    bets_df = pd.DataFrame(bets)

    total_bets = len(bets_df)
    wins = bets_df['won'].sum()
    draws = bets_df['draw'].sum()
    losses = total_bets - wins - draws
    win_rate = wins / total_bets

    total_profit = bets_df['profit'].sum()
    roi = total_profit / total_bets * 100

    avg_odds = bets_df['odds'].mean()
    avg_edge = bets_df['edge'].mean()

    print(f"\n📈 BACKTEST RESULTS:")
    print(f"{'='*80}")
    print(f"Total Bets:      {total_bets}")
    print(f"Wins:            {wins} ({win_rate:.1%})")
    print(f"Draws:           {draws} ({draws/total_bets:.1%})")
    print(f"Losses:          {losses} ({losses/total_bets:.1%})")
    print(f"")
    print(f"Total Profit:    ${total_profit:.2f} on ${total_bets} wagered")
    print(f"ROI:             {roi:+.1f}%")
    print(f"")
    print(f"Avg Odds:        {avg_odds:.2f}")
    print(f"Avg Edge:        {avg_edge:.1%}")
    print(f"Avg Elo Prob:    {bets_df['elo_prob'].mean():.1%}")

    # By edge bucket
    print(f"\n📊 BY EDGE BUCKET:")
    print(f"{'='*80}")

    edge_buckets = [
        (0.05, 0.10, '5-10%'),
        (0.10, 0.15, '10-15%'),
        (0.15, 0.20, '15-20%'),
        (0.20, 1.00, '20%+')
    ]

    for min_e, max_e, label in edge_buckets:
        bucket = bets_df[(bets_df['edge'] >= min_e) & (bets_df['edge'] < max_e)]
        if len(bucket) == 0:
            continue

        b_wins = bucket['won'].sum()
        b_draws = bucket['draw'].sum()
        b_total = len(bucket)
        b_profit = bucket['profit'].sum()
        b_roi = b_profit / b_total * 100

        print(f"{label:10s}: {b_total:3d} bets, {b_wins:3d} wins ({b_wins/b_total:5.1%}), "
              f"{b_draws:3d} draws ({b_draws/b_total:5.1%}), ROI: {b_roi:+6.1f}%")

    # Top 10 bets
    print(f"\n🎯 TOP 10 BETS BY EDGE:")
    print(f"{'='*80}")
    top_bets = bets_df.nlargest(10, 'edge')
    for _, bet in top_bets.iterrows():
        result = "✅ WIN" if bet['won'] else "⚽ DRAW" if bet['draw'] else "❌ LOSS"
        print(f"{bet['date'].strftime('%Y-%m-%d')} | {bet['away']:15s} @ {bet['home']:15s}")
        print(f"  Bet: {bet['bet_on']:4s} @ {bet['odds']:.2f} | Edge: {bet['edge']:.1%} | {result}")

    print(f"\n{'='*80}")

    return bets_df

if __name__ == '__main__':
    import sys

    # Parse arguments
    threshold = float(sys.argv[1]) if len(sys.argv) > 1 else 0.45
    min_edge = float(sys.argv[2]) if len(sys.argv) > 2 else 0.05

    # Run backtest
    results = backtest_ligue1_betting(elo_threshold=threshold, min_edge=min_edge)

    # Try different thresholds
    print(f"\n\n{'='*80}")
    print(f"TESTING MULTIPLE STRATEGIES")
    print(f"{'='*80}\n")

    strategies = [
        (0.40, 0.05),
        (0.40, 0.10),
        (0.45, 0.05),
        (0.45, 0.10),
        (0.50, 0.05),
        (0.50, 0.10),
    ]

    summary = []
    for thresh, edge in strategies:
        bets_df = backtest_ligue1_betting(elo_threshold=thresh, min_edge=edge)
        if bets_df is not None and len(bets_df) > 0:
            summary.append({
                'threshold': f'{thresh:.0%}',
                'min_edge': f'{edge:.0%}',
                'bets': len(bets_df),
                'win_rate': f'{bets_df["won"].sum()/len(bets_df):.1%}',
                'roi': f'{bets_df["profit"].sum()/len(bets_df)*100:+.1f}%'
            })

    if summary:
        print(f"\n📊 STRATEGY COMPARISON:")
        print(f"{'='*80}")
        summary_df = pd.DataFrame(summary)
        print(summary_df.to_string(index=False))
