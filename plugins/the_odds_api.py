"""
The Odds API integration - aggregates odds from multiple sportsbooks.
Free tier: 500 requests/month, covers NBA, NHL, MLB, NFL, EPL and more.
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import os


class TheOddsAPI:
    """Interface to The Odds API for aggregated sports betting odds."""
    
    BASE_URL = "https://api.the-odds-api.com/v4"
    
    # Sport keys mapping
    SPORT_KEYS = {
        'nba': 'basketball_nba',
        'nhl': 'icehockey_nhl',
        'mlb': 'baseball_mlb',
        'nfl': 'americanfootball_nfl',
        'epl': 'soccer_epl',
        'ncaab': 'basketball_ncaab'
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize The Odds API client.
        
        Args:
            api_key: API key from the-odds-api.com (free tier: 500 req/month)
        """
        self.api_key = api_key or os.getenv('ODDS_API_KEY')
        
        if not self.api_key:
            print("⚠️  No Odds API key provided. Set ODDS_API_KEY environment variable.")
            print("   Get free key at: https://the-odds-api.com/")
        
        self.session = requests.Session()
    
    def fetch_markets(self, sport: str, markets: str = 'h2h', regions: str = 'us') -> List[Dict]:
        """
        Fetch betting odds for a sport.
        
        Args:
            sport: Sport key (nba, nhl, mlb, nfl, epl, ncaab)
            markets: Market types (h2h, spreads, totals)
            regions: Regions (us, uk, eu, au)
            
        Returns:
            List of games with odds from multiple bookmakers
        """
        sport_key = self.SPORT_KEYS.get(sport)
        if not sport_key:
            print(f"⚠️  Unknown sport: {sport}")
            return []
        
        print(f"📥 Fetching odds for {sport.upper()} from multiple bookmakers...")
        
        if not self.api_key:
            print("⚠️  No API key - skipping")
            return []
        
        try:
            url = f"{self.BASE_URL}/sports/{sport_key}/odds"
            params = {
                'apiKey': self.api_key,
                'regions': regions,
                'markets': markets,
                'oddsFormat': 'decimal',
                'dateFormat': 'iso'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            games = response.json()
            
            # Check remaining requests
            remaining = response.headers.get('x-requests-remaining')
            if remaining:
                print(f"📊 Requests remaining: {remaining}")
            
            # Parse into our standard format
            parsed_markets = []
            
            for game in games:
                parsed = self._parse_game(game, sport)
                if parsed:
                    parsed_markets.append(parsed)
            
            print(f"✓ Found {len(parsed_markets)} games with odds from {self._count_bookmakers(games)} bookmakers")
            return parsed_markets
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Error fetching odds: {e}")
            return []
    
    def _parse_game(self, game: Dict, sport: str) -> Optional[Dict]:
        """Parse game data into standard format."""
        try:
            home_team = game.get('home_team')
            away_team = game.get('away_team')
            commence_time = game.get('commence_time')
            
            # Extract odds from all bookmakers
            bookmakers = {}
            
            for bookmaker in game.get('bookmakers', []):
                bm_name = bookmaker.get('key')
                
                # Get h2h odds
                for market in bookmaker.get('markets', []):
                    if market.get('key') == 'h2h':
                        outcomes = market.get('outcomes', [])
                        
                        home_odds = None
                        away_odds = None
                        
                        for outcome in outcomes:
                            if outcome.get('name') == home_team:
                                home_odds = outcome.get('price')
                            elif outcome.get('name') == away_team:
                                away_odds = outcome.get('price')
                        
                        if home_odds and away_odds:
                            home_prob = 1 / home_odds
                            away_prob = 1 / away_odds
                            
                            bookmakers[bm_name] = {
                                'home_odds': home_odds,
                                'away_odds': away_odds,
                                'home_prob': home_prob,
                                'away_prob': away_prob,
                                'last_update': bookmaker.get('last_update')
                            }
            
            if not bookmakers:
                return None
            
            # Find best odds across all bookmakers
            best_home = max(bookmakers.items(), key=lambda x: x[1]['home_prob'])
            best_away = max(bookmakers.items(), key=lambda x: x[1]['away_prob'])
            
            return {
                'platform': 'odds_api',
                'sport': sport,
                'game_id': game.get('id'),
                'home_team': home_team,
                'away_team': away_team,
                'commence_time': commence_time,
                'bookmakers': bookmakers,
                'best_home_bookmaker': best_home[0],
                'best_home_odds': best_home[1]['home_odds'],
                'best_home_prob': best_home[1]['home_prob'],
                'best_away_bookmaker': best_away[0],
                'best_away_odds': best_away[1]['away_odds'],
                'best_away_prob': best_away[1]['away_prob'],
                'num_bookmakers': len(bookmakers)
            }
            
        except Exception as e:
            print(f"⚠️  Error parsing game: {e}")
            return None
    
    def _count_bookmakers(self, games: List[Dict]) -> int:
        """Count unique bookmakers."""
        bookmakers = set()
        for game in games:
            for bm in game.get('bookmakers', []):
                bookmakers.add(bm.get('key'))
        return len(bookmakers)
    
    def fetch_and_save_markets(self, sport: str, date_str: str) -> int:
        """Fetch markets and save to JSON file."""
        markets = self.fetch_markets(sport)
        
        if not markets:
            return 0
        
        # Save to file
        output_dir = Path(f'data/{sport}')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f'odds_api_markets_{date_str}.json'
        
        with open(output_file, 'w') as f:
            json.dump(markets, f, indent=2)
        
        print(f"💾 Saved {len(markets)} games to {output_file}")
        return len(markets)
    
    def get_available_sports(self) -> List[Dict]:
        """Get list of available sports."""
        if not self.api_key:
            return []
        
        try:
            url = f"{self.BASE_URL}/sports"
            params = {'apiKey': self.api_key}
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Error fetching sports: {e}")
            return []


def fetch_all_sports(date_str: str, api_key: Optional[str] = None):
    """Fetch odds for all sports."""
    api = TheOddsAPI(api_key)
    
    sports = ['nba', 'nhl', 'mlb', 'nfl', 'epl', 'ncaab']
    total = 0
    
    for sport in sports:
        count = api.fetch_and_save_markets(sport, date_str)
        total += count
    
    print(f"\n✓ Total games fetched: {total}")
    return total


if __name__ == '__main__':
    from datetime import date
    
    print("=" * 80)
    print("THE ODDS API TEST")
    print("=" * 80)
    print("\nThe Odds API aggregates odds from 40+ bookmakers including:")
    print("  • DraftKings, FanDuel, BetMGM (US)")
    print("  • Bet365, William Hill (International)")
    print("  • Pinnacle, Bovada, MyBookie")
    print("  • And many more...")
    print("\nFree tier: 500 requests/month")
    print("Get your API key at: https://the-odds-api.com/\n")
    print("Set environment variable: export ODDS_API_KEY='your-key-here'")
    print("=" * 80)
    
    api = TheOddsAPI()
    
    # Check if API key is set
    if api.api_key:
        today = date.today().strftime('%Y-%m-%d')
        
        # Test NBA
        print("\nTesting NBA odds...")
        markets = api.fetch_markets('nba')
        
        if markets:
            print(f"\n📊 Sample game with {markets[0]['num_bookmakers']} bookmakers:")
            sample = markets[0]
            print(f"  {sample['away_team']} @ {sample['home_team']}")
            print(f"  Best home odds: {sample['best_home_odds']:.2f} ({sample['best_home_bookmaker']})")
            print(f"  Best away odds: {sample['best_away_odds']:.2f} ({sample['best_away_bookmaker']})")
            
            # Show all bookmakers for this game
            print(f"\n  All bookmakers offering this game:")
            for bm_name, bm_data in sample['bookmakers'].items():
                print(f"    {bm_name}: Home {bm_data['home_odds']:.2f}, Away {bm_data['away_odds']:.2f}")
    else:
        print("\n⚠️  No API key found. Please set ODDS_API_KEY environment variable.")
        print("   Get a free key at: https://the-odds-api.com/")
