"""
Multi-platform arbitrage finder.
Compares Kalshi predictions with aggregated sportsbook odds from The Odds API.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
import sys

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent))

from the_odds_api import TheOddsAPI
from kalshi_markets import fetch_nba_markets, fetch_nhl_markets, fetch_mlb_markets, fetch_nfl_markets


class ArbitrageFinder:
    """Find arbitrage and value betting opportunities across platforms."""
    
    def __init__(self, odds_api_key: str = None):
        self.odds_api = TheOddsAPI(odds_api_key)
        self.elo_predictions = {}
    
    def load_elo_predictions(self, sport: str) -> Dict:
        """Load current Elo ratings and predictions."""
        elo_file = Path(f'data/{sport}_current_elo_ratings.csv')
        
        if not elo_file.exists():
            print(f"⚠️  No Elo ratings found for {sport}")
            return {}
        
        ratings = {}
        with open(elo_file, 'r') as f:
            next(f)  # Skip header
            for line in f:
                team, rating = line.strip().split(',')
                ratings[team] = float(rating)
        
        return ratings
    
    def calculate_win_probability(self, home_rating: float, away_rating: float, home_advantage: float = 100) -> float:
        """Calculate win probability from Elo ratings."""
        rating_diff = (home_rating + home_advantage) - away_rating
        return 1 / (1 + 10 ** (-rating_diff / 400))
    
    def normalize_team_name(self, team: str) -> str:
        """Normalize team names for matching."""
        # Remove common words and standardize
        team = team.lower().strip()
        replacements = {
            'boston celtics': 'celtics',
            'miami heat': 'heat',
            'la lakers': 'lakers',
            'los angeles lakers': 'lakers',
            'golden state warriors': 'warriors',
            'philadelphia 76ers': '76ers',
            # Add more mappings as needed
        }
        
        for full, short in replacements.items():
            if full in team:
                return short
        
        # Return last word (usually team name)
        words = team.split()
        return words[-1] if words else team
    
    def find_opportunities(self, sport: str, date_str: str) -> List[Dict]:
        """
        Find arbitrage and value betting opportunities.
        
        Returns:
            List of opportunities with type, platform, edge, etc.
        """
        print(f"\n{'='*80}")
        print(f"FINDING OPPORTUNITIES FOR {sport.upper()}")
        print(f"{'='*80}\n")
        
        opportunities = []
        
        # 1. Load Elo predictions
        print("📊 Loading Elo predictions...")
        elo_ratings = self.load_elo_predictions(sport)
        
        if not elo_ratings:
            print(f"⚠️  No Elo ratings available for {sport}")
            return []
        
        print(f"✓ Loaded Elo ratings for {len(elo_ratings)} teams")
        
        # 2. Fetch Kalshi markets
        print("\n💰 Fetching Kalshi markets...")
        kalshi_markets = self._fetch_kalshi_for_sport(sport, date_str)
        print(f"✓ Found {len(kalshi_markets)} Kalshi markets")
        
        # 3. Fetch aggregated sportsbook odds
        print("\n🎲 Fetching sportsbook odds from The Odds API...")
        sportsbook_odds = self.odds_api.fetch_markets(sport)
        print(f"✓ Found {len(sportsbook_odds)} games with sportsbook odds")
        
        # 4. Compare and find opportunities
        print(f"\n🔍 Analyzing {len(sportsbook_odds)} games...")
        
        for game in sportsbook_odds:
            home_team = game['home_team']
            away_team = game['away_team']
            
            # Match with Elo ratings
            home_elo = self._find_team_rating(home_team, elo_ratings)
            away_elo = self._find_team_rating(away_team, elo_ratings)
            
            if not home_elo or not away_elo:
                continue
            
            # Calculate Elo prediction
            home_advantage = 100 if sport == 'nba' else 50
            elo_prob = self.calculate_win_probability(home_elo, away_elo, home_advantage)
            
            # Compare with best available odds
            best_home_prob = game['best_home_prob']
            best_away_prob = game['best_away_prob']
            
            # Check for value bets (Elo says better odds than market)
            home_edge = elo_prob - best_home_prob
            away_edge = (1 - elo_prob) - best_away_prob
            
            # Value bet thresholds
            VALUE_THRESHOLD = 0.05  # 5% edge
            
            if home_edge > VALUE_THRESHOLD:
                opportunities.append({
                    'type': 'value_bet',
                    'sport': sport,
                    'home_team': home_team,
                    'away_team': away_team,
                    'side': 'home',
                    'platform': game['best_home_bookmaker'],
                    'elo_prob': elo_prob,
                    'market_prob': best_home_prob,
                    'edge': home_edge,
                    'odds': game['best_home_odds'],
                    'num_bookmakers': game['num_bookmakers'],
                    'commence_time': game['commence_time']
                })
            
            if away_edge > VALUE_THRESHOLD:
                opportunities.append({
                    'type': 'value_bet',
                    'sport': sport,
                    'home_team': home_team,
                    'away_team': away_team,
                    'side': 'away',
                    'platform': game['best_away_bookmaker'],
                    'elo_prob': 1 - elo_prob,
                    'market_prob': best_away_prob,
                    'edge': away_edge,
                    'odds': game['best_away_odds'],
                    'num_bookmakers': game['num_bookmakers'],
                    'commence_time': game['commence_time']
                })
            
            # Check for arbitrage (can bet both sides profitably)
            total_prob = best_home_prob + best_away_prob
            if total_prob < 1.0:
                profit_margin = 1.0 - total_prob
                
                opportunities.append({
                    'type': 'arbitrage',
                    'sport': sport,
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_platform': game['best_home_bookmaker'],
                    'away_platform': game['best_away_bookmaker'],
                    'home_odds': game['best_home_odds'],
                    'away_odds': game['best_away_odds'],
                    'home_prob': best_home_prob,
                    'away_prob': best_away_prob,
                    'profit_margin': profit_margin,
                    'risk_free': True,
                    'commence_time': game['commence_time']
                })
            
            # Compare with Kalshi if available
            kalshi_match = self._find_kalshi_match(home_team, away_team, kalshi_markets)
            if kalshi_match:
                kalshi_prob = kalshi_match.get('yes_ask', 50) / 100.0
                
                # Kalshi vs best sportsbook
                kalshi_edge = elo_prob - kalshi_prob
                best_sportsbook_edge = elo_prob - best_home_prob
                
                # Cross-platform arbitrage
                if kalshi_prob < best_home_prob:
                    # Kalshi offers better price
                    opportunities.append({
                        'type': 'cross_platform',
                        'sport': sport,
                        'home_team': home_team,
                        'away_team': away_team,
                        'side': 'home',
                        'platform': 'kalshi',
                        'alternative_platform': game['best_home_bookmaker'],
                        'kalshi_prob': kalshi_prob,
                        'sportsbook_prob': best_home_prob,
                        'edge': best_home_prob - kalshi_prob,
                        'elo_prob': elo_prob,
                        'commence_time': game['commence_time']
                    })
        
        print(f"\n✓ Found {len(opportunities)} opportunities")
        
        # Sort by edge/profit margin
        opportunities.sort(key=lambda x: x.get('edge', x.get('profit_margin', 0)), reverse=True)
        
        return opportunities
    
    def _fetch_kalshi_for_sport(self, sport: str, date_str: str) -> List[Dict]:
        """Fetch Kalshi markets for a sport."""
        fetch_funcs = {
            'nba': fetch_nba_markets,
            'nhl': fetch_nhl_markets,
            'mlb': fetch_mlb_markets,
            'nfl': fetch_nfl_markets
        }
        
        fetch_func = fetch_funcs.get(sport)
        if not fetch_func:
            return []
        
        try:
            return fetch_func(date_str)
        except Exception as e:
            print(f"⚠️  Error fetching Kalshi markets: {e}")
            return []
    
    def _find_team_rating(self, team: str, ratings: Dict) -> float:
        """Find team rating by fuzzy matching."""
        team_norm = self.normalize_team_name(team)
        
        # Exact match
        if team in ratings:
            return ratings[team]
        
        # Fuzzy match
        for rating_team, rating in ratings.items():
            if team_norm in rating_team.lower() or rating_team.lower() in team_norm:
                return rating
        
        return None
    
    def _find_kalshi_match(self, home_team: str, away_team: str, kalshi_markets: List[Dict]) -> Dict:
        """Find matching Kalshi market."""
        # This needs proper team name matching logic
        # For now, return None
        return None
    
    def print_opportunities(self, opportunities: List[Dict]):
        """Print opportunities in a nice format."""
        if not opportunities:
            print("\n❌ No opportunities found")
            return
        
        print(f"\n{'='*80}")
        print(f"FOUND {len(opportunities)} OPPORTUNITIES")
        print(f"{'='*80}\n")
        
        # Group by type
        by_type = {}
        for opp in opportunities:
            opp_type = opp['type']
            if opp_type not in by_type:
                by_type[opp_type] = []
            by_type[opp_type].append(opp)
        
        # Print arbitrage opportunities
        if 'arbitrage' in by_type:
            print(f"\n🎯 ARBITRAGE OPPORTUNITIES ({len(by_type['arbitrage'])})")
            print("-" * 80)
            for opp in by_type['arbitrage'][:10]:
                print(f"\n{opp['away_team']} @ {opp['home_team']}")
                print(f"  💰 RISK-FREE PROFIT: {opp['profit_margin']:.2%}")
                print(f"  Bet Home on {opp['home_platform']}: {opp['home_odds']:.2f}")
                print(f"  Bet Away on {opp['away_platform']}: {opp['away_odds']:.2f}")
        
        # Print value bets
        if 'value_bet' in by_type:
            print(f"\n📈 VALUE BETS ({len(by_type['value_bet'])})")
            print("-" * 80)
            for opp in by_type['value_bet'][:20]:
                side_team = opp['home_team'] if opp['side'] == 'home' else opp['away_team']
                print(f"\n{opp['away_team']} @ {opp['home_team']}")
                print(f"  Bet {opp['side'].upper()}: {side_team}")
                print(f"  Platform: {opp['platform']}")
                print(f"  Edge: {opp['edge']:.1%} (Elo: {opp['elo_prob']:.1%}, Market: {opp['market_prob']:.1%})")
                print(f"  Odds: {opp['odds']:.2f}")
        
        # Print cross-platform opportunities
        if 'cross_platform' in by_type:
            print(f"\n🔄 CROSS-PLATFORM OPPORTUNITIES ({len(by_type['cross_platform'])})")
            print("-" * 80)
            for opp in by_type['cross_platform'][:10]:
                print(f"\n{opp['away_team']} @ {opp['home_team']}")
                print(f"  Kalshi: {opp['kalshi_prob']:.1%}")
                print(f"  {opp['alternative_platform']}: {opp['sportsbook_prob']:.1%}")
                print(f"  Price difference: {opp['edge']:.1%}")
    
    def save_opportunities(self, opportunities: List[Dict], date_str: str):
        """Save opportunities to file."""
        output_file = Path(f'data/arbitrage_opportunities_{date_str}.json')
        
        with open(output_file, 'w') as f:
            json.dump(opportunities, f, indent=2)
        
        print(f"\n💾 Saved {len(opportunities)} opportunities to {output_file}")


if __name__ == '__main__':
    import os
    from datetime import date
    
    today = date.today().strftime('%Y-%m-%d')
    
    # Check for API key
    api_key = os.getenv('ODDS_API_KEY')
    
    if not api_key:
        print("=" * 80)
        print("⚠️  ERROR: ODDS_API_KEY environment variable not set")
        print("=" * 80)
        print("\nTo use this tool:")
        print("1. Get a free API key at: https://the-odds-api.com/")
        print("2. Set environment variable: export ODDS_API_KEY='your-key-here'")
        print("3. Run this script again")
        print("\nFree tier: 500 requests/month (plenty for daily analysis)")
        print("=" * 80)
        sys.exit(1)
    
    finder = ArbitrageFinder(api_key)
    
    # Find opportunities for each sport
    all_opportunities = []
    
    for sport in ['nba', 'nhl']:  # Start with nba and nhl
        opportunities = finder.find_opportunities(sport, today)
        all_opportunities.extend(opportunities)
        finder.print_opportunities(opportunities)
    
    # Save all opportunities
    if all_opportunities:
        finder.save_opportunities(all_opportunities, today)
        
        print(f"\n{'='*80}")
        print(f"SUMMARY: {len(all_opportunities)} total opportunities found")
        print(f"{'='*80}")
