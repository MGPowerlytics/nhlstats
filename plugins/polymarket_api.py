"""
Polymarket API integration for prediction market odds comparison.
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path


class PolymarketAPI:
    """Interface to Polymarket prediction markets API."""
    
    BASE_URL = "https://gamma-api.polymarket.com"
    CLOB_URL = "https://clob.polymarket.com"
    
    def __init__(self):
        """Initialize Polymarket API client (read-only, no auth needed)."""
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
    
    def fetch_markets(self, sport: str = None) -> List[Dict]:
        """
        Fetch active markets from Polymarket.
        
        Args:
            sport: Optional sport filter (nba, nhl, mlb, nfl, epl)
            
        Returns:
            List of market dictionaries
        """
        print(f"📥 Fetching Polymarket markets...")
        
        try:
            # Get all active markets
            url = f"{self.BASE_URL}/markets"
            params = {
                'closed': False,
                'active': True,
                'limit': 100
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Filter for sports markets
            sports_markets = []
            
            for market in data:
                parsed = self._parse_market(market, sport)
                if parsed:
                    sports_markets.append(parsed)
            
            print(f"✓ Found {len(sports_markets)} Polymarket sports markets")
            return sports_markets
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Error fetching Polymarket markets: {e}")
            return []
    
    def _parse_market(self, market: Dict, sport_filter: Optional[str] = None) -> Optional[Dict]:
        """Parse Polymarket market into standard format."""
        try:
            question = market.get('question', '').lower()
            description = market.get('description', '').lower()
            
            # Detect sport
            sport = None
            if any(keyword in question or keyword in description for keyword in ['nba', 'basketball']):
                sport = 'nba'
            elif any(keyword in question or keyword in description for keyword in ['nhl', 'hockey']):
                sport = 'nhl'
            elif any(keyword in question or keyword in description for keyword in ['mlb', 'baseball']):
                sport = 'mlb'
            elif any(keyword in question or keyword in description for keyword in ['nfl', 'football']):
                sport = 'nfl'
            elif any(keyword in question or keyword in description for keyword in ['premier league', 'epl']):
                sport = 'epl'
            
            # Apply filter
            if sport_filter and sport != sport_filter:
                return None
            
            if not sport:
                return None
            
            # Try to extract teams
            # Format: "Will [Team A] beat [Team B]?" or "[Team A] vs [Team B] winner?"
            home_team = None
            away_team = None
            
            if ' vs ' in question or ' v ' in question:
                separator = ' vs ' if ' vs ' in question else ' v '
                parts = question.split(separator)
                if len(parts) == 2:
                    away_team = parts[0].strip()
                    home_team = parts[1].split('winner')[0].strip() if 'winner' in parts[1] else parts[1].strip()
            elif ' beat ' in question:
                # "Will Team A beat Team B?"
                parts = question.split(' beat ')
                if len(parts) == 2:
                    away_team = parts[0].replace('will', '').strip()
                    home_team = parts[1].rstrip('?').strip()
            
            # Get odds from outcomes
            outcomes = market.get('outcomes', [])
            yes_prob = None
            
            if outcomes and len(outcomes) >= 2:
                # Polymarket returns prices as strings like "0.52"
                yes_price = outcomes[0].get('price')
                if yes_price:
                    yes_prob = float(yes_price)
            
            return {
                'platform': 'polymarket',
                'market_id': market.get('id'),
                'sport': sport,
                'question': market.get('question'),
                'home_team': home_team,
                'away_team': away_team,
                'yes_prob': yes_prob,
                'no_prob': 1 - yes_prob if yes_prob else None,
                'volume': market.get('volume'),
                'liquidity': market.get('liquidity'),
                'end_date': market.get('endDate'),
                'raw_data': market
            }
            
        except Exception as e:
            print(f"⚠️  Error parsing Polymarket market: {e}")
            return None
    
    def fetch_and_save_markets(self, sport: str, date_str: str) -> int:
        """Fetch markets and save to JSON file."""
        markets = self.fetch_markets(sport)
        
        if not markets:
            return 0
        
        # Save to file
        output_dir = Path(f'data/{sport}')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f'polymarket_markets_{date_str}.json'
        
        with open(output_file, 'w') as f:
            json.dump(markets, f, indent=2)
        
        print(f"💾 Saved {len(markets)} markets to {output_file}")
        return len(markets)


def fetch_all_sports(date_str: str):
    """Fetch Polymarket markets for all sports."""
    api = PolymarketAPI()
    
    sports = ['nba', 'nhl', 'mlb', 'nfl', 'epl']
    total = 0
    
    for sport in sports:
        count = api.fetch_and_save_markets(sport, date_str)
        total += count
    
    print(f"\n✓ Total Polymarket markets fetched: {total}")
    return total


if __name__ == '__main__':
    from datetime import date
    today = date.today().strftime('%Y-%m-%d')
    
    print("Testing Polymarket API integration...")
    api = PolymarketAPI()
    
    # Test fetching markets
    markets = api.fetch_markets()
    
    if markets:
        print(f"\n📊 Found {len(markets)} sports markets")
        print(f"\nSample market:")
        print(json.dumps(markets[0], indent=2))
