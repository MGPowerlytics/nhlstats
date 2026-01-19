"""
NHL Betting Backtest using Odds API Historical Data
Tests Elo predictions against real market odds to evaluate profitability.
"""

import json
import duckdb
import requests
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

class NHLEloRating:
    """Optimized Elo with recency weighting"""
    def __init__(self, k_factor=10, home_advantage=50, recency_weight=0.2):
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.recency_weight = recency_weight
        self.ratings = defaultdict(lambda: 1500)
        self.last_game_date = {}
        
    def expected_score(self, rating_a, rating_b):
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
        
    def predict(self, home_team, away_team):
        home_rating = self.ratings[home_team] + self.home_advantage
        away_rating = self.ratings[away_team]
        return self.expected_score(home_rating, away_rating)
        
    def update(self, home_team, away_team, home_won, game_date=None):
        home_rating = self.ratings[home_team]
        away_rating = self.ratings[away_team]
        
        home_expected = self.expected_score(
            home_rating + self.home_advantage, 
            away_rating
        )
        
        k_factor = self.k_factor
        if self.recency_weight > 0 and game_date:
            for team in [home_team, away_team]:
                if team in self.last_game_date:
                    days_since = (game_date - self.last_game_date[team]).days
                    if days_since > 5:
                        k_factor *= (1 + self.recency_weight * min(days_since / 7, 1.0))
        
        home_actual = 1.0 if home_won else 0.0
        home_change = k_factor * (home_actual - home_expected)
        away_change = k_factor * ((1-home_actual) - (1-home_expected))
        
        self.ratings[home_team] += home_change
        self.ratings[away_team] += away_change
        
        if game_date:
            self.last_game_date[home_team] = game_date
            self.last_game_date[away_team] = game_date
            
    def apply_season_reversion(self, factor=0.45):
        for team in self.ratings:
            self.ratings[team] = self.ratings[team] * (1-factor) + 1500 * factor


def load_historical_odds(odds_file):
    """Load historical odds from OddsPortal format"""
    print(f"📂 Loading historical odds from {odds_file}...")
    
    with open(odds_file, 'r') as f:
        data = json.load(f)
    
    odds_by_game = {}
    
    for event in data:
        try:
            # Parse date
            match_date_str = event.get('match_date', '')
            if match_date_str:
                match_date = datetime.strptime(match_date_str, '%Y-%m-%d %H:%M:%S %Z').date()
            else:
                continue
            
            home_team = event.get('home_team', '')
            away_team = event.get('away_team', '')
            
            # Get average odds from bookmakers
            home_away_markets = event.get('home_away_market', [])
            if not home_away_markets:
                continue
            
            # Average the odds from multiple bookmakers
            home_odds_list = []
            away_odds_list = []
            
            for market in home_away_markets:
                if market.get('period') == 'FullTime':
                    try:
                        home_decimal = float(market.get('1', 0))
                        away_decimal = float(market.get('2', 0))
                        if home_decimal > 0 and away_decimal > 0:
                            home_odds_list.append(home_decimal)
                            away_odds_list.append(away_decimal)
                    except:
                        continue
            
            if home_odds_list and away_odds_list:
                avg_home_decimal = np.mean(home_odds_list)
                avg_away_decimal = np.mean(away_odds_list)
                
                # Convert decimal odds to probability
                home_prob = 1 / avg_home_decimal if avg_home_decimal > 0 else 0
                away_prob = 1 / avg_away_decimal if avg_away_decimal > 0 else 0
                
                # Normalize probabilities (remove vig)
                total_prob = home_prob + away_prob
                if total_prob > 0:
                    home_prob = home_prob / total_prob
                    away_prob = away_prob / total_prob
                
                game_key = (match_date, home_team, away_team)
                odds_by_game[game_key] = {
                    'home_decimal': avg_home_decimal,
                    'away_decimal': avg_away_decimal,
                    'home_prob': home_prob,
                    'away_prob': away_prob,
                    'num_bookmakers': len(home_odds_list)
                }
        except Exception as e:
            continue
    
    print(f"✓ Loaded odds for {len(odds_by_game)} games")
    return odds_by_game


def american_to_prob(american_odds):
    """Convert American odds to implied probability"""
    if american_odds > 0:
        return 100 / (american_odds + 100)
    else:
        return -american_odds / (-american_odds + 100)


def prob_to_american(prob):
    """Convert probability to American odds"""
    if prob >= 0.5:
        return -100 * prob / (1 - prob)
    else:
        return 100 * (1 - prob) / prob


def calculate_kelly_bet(elo_prob, odds_prob, edge, bankroll, kelly_fraction=0.25):
    """Calculate Kelly criterion bet size"""
    if edge <= 0:
        return 0
    
    # Kelly formula: f = (bp - q) / b
    # where b = net odds, p = win prob, q = 1-p
    
    # Convert to decimal odds
    if odds_prob > 0:
        decimal_odds = 1 / odds_prob
        b = decimal_odds - 1
        p = elo_prob
        q = 1 - p
        
        f = (b * p - q) / b
        
        # Apply Kelly fraction for safety
        f = f * kelly_fraction
        
        # Cap at 5% of bankroll
        f = min(f, 0.05)
        f = max(f, 0)
        
        return bankroll * f
    
    return 0


def backtest_betting_strategy(
    start_season='2025',
    elo_threshold=0.62,
    min_edge=0.05,
    max_bet=5.0,
    use_kelly=False
):
    """Backtest NHL betting strategy"""
    
    print("=" * 80)
    print("NHL BETTING BACKTEST")
    print("=" * 80)
    print(f"\nStrategy Parameters:")
    print(f"  Elo Threshold: {elo_threshold:.1%}")
    print(f"  Min Edge: {min_edge:.1%}")
    print(f"  Max Bet: ${max_bet:.2f}")
    print(f"  Kelly Criterion: {use_kelly}")
    print()
    
    # Load historical odds
    odds_file = Path('data/historical_odds/nhl_2023_2024.json')
    if not odds_file.exists():
        print(f"❌ Odds file not found: {odds_file}")
        return
    
    odds_data = load_historical_odds(odds_file)
    
    # Load games from database
    conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)
    
    exhibition_teams = ('CAN', 'USA', 'ATL', 'MET', 'CEN', 'PAC', 
                       'SWE', 'FIN', 'EIS', 'MUN', 'SCB', 'KLS', 
                       'KNG', 'MKN', 'HGS', 'MAT', 'MCD')
    
    games = conn.execute("""
        WITH ranked_games AS (
            SELECT game_date, home_team_abbrev, home_team_name, 
                   away_team_abbrev, away_team_name,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_won,
                   season,
                   ROW_NUMBER() OVER (
                       PARTITION BY game_date, home_team_abbrev, away_team_abbrev 
                       ORDER BY game_id
                   ) as rn
            FROM games 
            WHERE game_state IN ('OFF', 'FINAL')
              AND home_team_abbrev NOT IN ?
              AND away_team_abbrev NOT IN ?
        )
        SELECT game_date, home_team_abbrev, home_team_name, 
               away_team_abbrev, away_team_name, home_won, season
        FROM ranked_games
        WHERE rn = 1
        ORDER BY game_date, home_team_abbrev
    """, [exhibition_teams, exhibition_teams]).fetchall()
    conn.close()
    
    print(f"📊 Loaded {len(games)} games from database")
    
    # Initialize tracking
    elo = NHLEloRating(k_factor=10, home_advantage=50, recency_weight=0.2)
    
    bets = []
    bankroll = 100.0
    initial_bankroll = bankroll
    
    last_season = None
    backtest_started = False
    
    for game in games:
        game_date, home_abbrev, home_name, away_abbrev, away_name, home_won, season = game
        
        if isinstance(game_date, str):
            game_date = datetime.strptime(game_date, '%Y-%m-%d').date()
        
        # Apply season reversion
        if last_season and season != last_season:
            elo.apply_season_reversion(0.45)
        last_season = season
        
        # Start backtest at target season
        if str(season) >= start_season:
            backtest_started = True
        
        # Make prediction
        elo_prob = elo.predict(home_abbrev, away_abbrev)
        
        # Check if we have odds for this game
        game_key = (game_date, home_name, away_name)
        
        if backtest_started and game_key in odds_data:
            odds = odds_data[game_key]
            market_prob = odds['home_prob']
            edge = elo_prob - market_prob
            
            # Check if we would bet on this game
            if elo_prob >= elo_threshold and edge >= min_edge:
                # Calculate bet size
                if use_kelly:
                    bet_size = calculate_kelly_bet(elo_prob, market_prob, edge, bankroll)
                    bet_size = min(bet_size, max_bet)
                else:
                    bet_size = max_bet
                
                if bet_size > 0.10:  # Minimum $0.10 bet
                    # Calculate payout using decimal odds
                    home_decimal_odds = odds['home_decimal']
                    if home_won:
                        profit = bet_size * (home_decimal_odds - 1)
                    else:
                        profit = -bet_size
                    
                    bankroll += profit
                    
                    bets.append({
                        'date': game_date,
                        'home': home_abbrev,
                        'away': away_abbrev,
                        'elo_prob': elo_prob,
                        'market_prob': market_prob,
                        'edge': edge,
                        'bet_size': bet_size,
                        'odds': home_decimal_odds,
                        'won': home_won,
                        'profit': profit,
                        'bankroll': bankroll
                    })
        
        # Update Elo with actual result
        elo.update(home_abbrev, away_abbrev, home_won, game_date)
    
    # Calculate results
    print("\n" + "=" * 80)
    print("BACKTEST RESULTS")
    print("=" * 80)
    
    if not bets:
        print("\n❌ No bets placed - check parameters or odds data coverage")
        return
    
    total_bets = len(bets)
    winning_bets = sum(1 for b in bets if b['won'])
    losing_bets = total_bets - winning_bets
    
    total_wagered = sum(b['bet_size'] for b in bets)
    total_profit = sum(b['profit'] for b in bets)
    
    win_rate = winning_bets / total_bets if total_bets > 0 else 0
    roi = (total_profit / total_wagered * 100) if total_wagered > 0 else 0
    
    avg_edge = np.mean([b['edge'] for b in bets])
    avg_elo_prob = np.mean([b['elo_prob'] for b in bets])
    avg_market_prob = np.mean([b['market_prob'] for b in bets])
    
    print(f"\n📊 BETTING STATISTICS")
    print(f"  Total Bets: {total_bets}")
    print(f"  Winning Bets: {winning_bets} ({win_rate:.1%})")
    print(f"  Losing Bets: {losing_bets}")
    print()
    print(f"💰 FINANCIAL RESULTS")
    print(f"  Initial Bankroll: ${initial_bankroll:.2f}")
    print(f"  Final Bankroll: ${bankroll:.2f}")
    print(f"  Total Wagered: ${total_wagered:.2f}")
    print(f"  Total Profit: ${total_profit:+.2f}")
    print(f"  ROI: {roi:+.1f}%")
    print()
    print(f"📈 PREDICTION QUALITY")
    print(f"  Avg Elo Probability: {avg_elo_prob:.1%}")
    print(f"  Avg Market Probability: {avg_market_prob:.1%}")
    print(f"  Avg Edge: {avg_edge:+.1%}")
    
    # Show recent bets
    print("\n" + "=" * 80)
    print("RECENT BETS (Last 10)")
    print("=" * 80)
    print(f"\n{'Date':<12} {'Teams':<20} {'Elo%':>6} {'Mkt%':>6} {'Edge':>7} {'Bet':>6} {'Result':>8}")
    print("-" * 80)
    
    for bet in bets[-10:]:
        result = f"+${bet['profit']:.2f}" if bet['won'] else f"-${bet['bet_size']:.2f}"
        matchup = f"{bet['home']} vs {bet['away']}"
        print(f"{bet['date']} {matchup:<20} {bet['elo_prob']:>5.1%} {bet['market_prob']:>5.1%} "
              f"{bet['edge']:>+6.1%} ${bet['bet_size']:>5.2f} {result:>8}")
    
    # Performance by edge bucket
    print("\n" + "=" * 80)
    print("PERFORMANCE BY EDGE BUCKET")
    print("=" * 80)
    
    edge_buckets = {
        '5-10%': (0.05, 0.10),
        '10-15%': (0.10, 0.15),
        '15-20%': (0.15, 0.20),
        '>20%': (0.20, 1.0)
    }
    
    print(f"\n{'Edge Range':<12} {'Bets':>6} {'Win%':>7} {'Profit':>10} {'ROI':>8}")
    print("-" * 80)
    
    for label, (min_edge, max_edge) in edge_buckets.items():
        bucket_bets = [b for b in bets if min_edge <= b['edge'] < max_edge]
        if bucket_bets:
            bucket_wins = sum(1 for b in bucket_bets if b['won'])
            bucket_win_rate = bucket_wins / len(bucket_bets)
            bucket_profit = sum(b['profit'] for b in bucket_bets)
            bucket_wagered = sum(b['bet_size'] for b in bucket_bets)
            bucket_roi = (bucket_profit / bucket_wagered * 100) if bucket_wagered > 0 else 0
            
            print(f"{label:<12} {len(bucket_bets):>6} {bucket_win_rate:>6.1%} "
                  f"${bucket_profit:>+9.2f} {bucket_roi:>+7.1f}%")
    
    return {
        'total_bets': total_bets,
        'win_rate': win_rate,
        'total_profit': total_profit,
        'roi': roi,
        'final_bankroll': bankroll,
        'bets': bets
    }


if __name__ == '__main__':
    import sys
    
    # Parse command line args
    threshold = float(sys.argv[1]) if len(sys.argv) > 1 else 0.62
    min_edge = float(sys.argv[2]) if len(sys.argv) > 2 else 0.05
    
    backtest_betting_strategy(
        start_season='2023',
        elo_threshold=threshold,
        min_edge=min_edge,
        max_bet=5.0,
        use_kelly=False
    )
