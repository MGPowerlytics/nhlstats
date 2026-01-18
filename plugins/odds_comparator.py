"""
Multi-platform odds comparison and arbitrage analysis.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import duckdb


class OddsComparator:
    """Compare odds across multiple platforms and identify arbitrage opportunities."""
    
    def __init__(self):
        self.platforms = ['kalshi', 'cloudbet', 'polymarket']
    
    def load_markets(self, sport: str, date_str: str, platform: str) -> List[Dict]:
        """Load markets from JSON file for a platform."""
        
        # Different platforms have different filename patterns
        filename_map = {
            'kalshi': f'markets_{date_str}.json',
            'cloudbet': f'cloudbet_markets_{date_str}.json',
            'polymarket': f'polymarket_markets_{date_str}.json'
        }
        
        market_file = Path(f'data/{sport}/{filename_map[platform]}')
        
        if not market_file.exists():
            return []
        
        with open(market_file, 'r') as f:
            return json.load(f)
    
    def normalize_team_name(self, team: str) -> str:
        """Normalize team names for matching across platforms."""
        # Remove common suffixes and normalize
        team = team.lower().strip()
        
        # Remove location prefixes for matching
        replacements = {
            'boston celtics': 'celtics',
            'miami heat': 'heat',
            'los angeles lakers': 'lakers',
            'golden state warriors': 'warriors',
            # Add more as needed
        }
        
        return replacements.get(team, team)
    
    def match_markets(self, sport: str, date_str: str) -> List[Dict]:
        """
        Match markets across platforms for the same game.
        
        Returns:
            List of matched markets with odds from all available platforms
        """
        print(f"🔍 Matching {sport} markets across platforms...")
        
        # Load markets from all platforms
        all_markets = {}
        for platform in self.platforms:
            markets = self.load_markets(sport, date_str, platform)
            all_markets[platform] = markets
            print(f"  {platform}: {len(markets)} markets")
        
        # Match markets by teams
        matched = []
        
        kalshi_markets = all_markets.get('kalshi', [])
        
        for kalshi_market in kalshi_markets:
            # Extract teams from Kalshi market
            if 'title' in kalshi_market:
                # Parse Kalshi title format
                title = kalshi_market.get('title', '')
                
                # Try to extract home/away teams
                # Kalshi format varies by sport
                home_team = None
                away_team = None
                
                # This needs sport-specific parsing logic
                # For now, skip complex parsing
                
            match_entry = {
                'sport': sport,
                'date': date_str,
                'home_team': kalshi_market.get('home_team'),
                'away_team': kalshi_market.get('away_team'),
                'platforms': {
                    'kalshi': {
                        'market_id': kalshi_market.get('ticker'),
                        'home_prob': kalshi_market.get('yes_ask', 0) / 100.0,
                        'away_prob': 1 - (kalshi_market.get('yes_ask', 0) / 100.0)
                    }
                }
            }
            
            # Try to match with Cloudbet
            for cb_market in all_markets.get('cloudbet', []):
                if self._teams_match(match_entry.get('home_team'), cb_market.get('home_team')) and \
                   self._teams_match(match_entry.get('away_team'), cb_market.get('away_team')):
                    match_entry['platforms']['cloudbet'] = {
                        'market_id': cb_market.get('event_id'),
                        'home_prob': cb_market.get('home_prob'),
                        'away_prob': cb_market.get('away_prob'),
                        'home_odds': cb_market.get('home_odds'),
                        'away_odds': cb_market.get('away_odds')
                    }
                    break
            
            # Try to match with Polymarket
            for pm_market in all_markets.get('polymarket', []):
                if self._teams_match(match_entry.get('home_team'), pm_market.get('home_team')) and \
                   self._teams_match(match_entry.get('away_team'), pm_market.get('away_team')):
                    match_entry['platforms']['polymarket'] = {
                        'market_id': pm_market.get('market_id'),
                        'yes_prob': pm_market.get('yes_prob'),
                        'volume': pm_market.get('volume')
                    }
                    break
            
            if len(match_entry['platforms']) > 1:
                matched.append(match_entry)
        
        print(f"✓ Matched {len(matched)} markets across platforms")
        return matched
    
    def _teams_match(self, team1: Optional[str], team2: Optional[str]) -> bool:
        """Check if two team names match."""
        if not team1 or not team2:
            return False
        
        norm1 = self.normalize_team_name(team1)
        norm2 = self.normalize_team_name(team2)
        
        return norm1 == norm2 or norm1 in norm2 or norm2 in norm1
    
    def find_arbitrage(self, matched_markets: List[Dict], elo_predictions: Optional[Dict] = None) -> List[Dict]:
        """
        Find arbitrage opportunities across platforms.
        
        Args:
            matched_markets: Markets matched across platforms
            elo_predictions: Optional Elo predictions to compare against
            
        Returns:
            List of arbitrage opportunities
        """
        print(f"💰 Analyzing arbitrage opportunities...")
        
        opportunities = []
        
        for match in matched_markets:
            platforms = match['platforms']
            
            if len(platforms) < 2:
                continue
            
            home_team = match['home_team']
            away_team = match['away_team']
            
            # Find best odds for each outcome
            best_home = {'platform': None, 'prob': 0, 'odds': None}
            best_away = {'platform': None, 'prob': 0, 'odds': None}
            
            for platform, data in platforms.items():
                home_prob = data.get('home_prob', 0)
                away_prob = data.get('away_prob', 0)
                
                if home_prob > best_home['prob']:
                    best_home = {
                        'platform': platform,
                        'prob': home_prob,
                        'odds': data.get('home_odds')
                    }
                
                if away_prob > best_away['prob']:
                    best_away = {
                        'platform': platform,
                        'prob': away_prob,
                        'odds': data.get('away_odds')
                    }
            
            # Check for arbitrage (when you can bet both sides profitably)
            total_prob = (1 / best_home['prob']) + (1 / best_away['prob']) if best_home['prob'] and best_away['prob'] else 2
            
            if total_prob < 1.0:
                # Pure arbitrage opportunity!
                profit_margin = 1.0 - total_prob
                
                opportunities.append({
                    'type': 'arbitrage',
                    'sport': match['sport'],
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_platform': best_home['platform'],
                    'away_platform': best_away['platform'],
                    'home_prob': best_home['prob'],
                    'away_prob': best_away['prob'],
                    'profit_margin': profit_margin,
                    'risk_free': True
                })
            
            # Check for value bets using Elo predictions
            if elo_predictions:
                elo_home_prob = elo_predictions.get(home_team, {}).get('win_prob', 0)
                
                if elo_home_prob:
                    # Compare Elo prediction with best available odds
                    for platform, data in platforms.items():
                        market_prob = data.get('home_prob', 0)
                        edge = elo_home_prob - market_prob
                        
                        if edge > 0.05:  # 5% edge threshold
                            opportunities.append({
                                'type': 'value_bet',
                                'sport': match['sport'],
                                'home_team': home_team,
                                'away_team': away_team,
                                'platform': platform,
                                'side': 'home',
                                'elo_prob': elo_home_prob,
                                'market_prob': market_prob,
                                'edge': edge,
                                'odds': data.get('home_odds')
                            })
        
        print(f"✓ Found {len(opportunities)} opportunities")
        return opportunities
    
    def save_opportunities(self, opportunities: List[Dict], date_str: str):
        """Save arbitrage opportunities to file and database."""
        
        # Save to JSON
        output_file = Path(f'data/arbitrage_opportunities_{date_str}.json')
        with open(output_file, 'w') as f:
            json.dump(opportunities, f, indent=2)
        
        print(f"💾 Saved {len(opportunities)} opportunities to {output_file}")
        
        # Also save to database
        self._save_to_database(opportunities, date_str)
    
    def _save_to_database(self, opportunities: List[Dict], date_str: str):
        """Save opportunities to DuckDB."""
        conn = duckdb.connect('data/nhlstats.duckdb')
        
        # Create table if it doesn't exist
        conn.execute("""
            CREATE TABLE IF NOT EXISTS arbitrage_opportunities (
                opportunity_id VARCHAR PRIMARY KEY,
                opportunity_date DATE NOT NULL,
                sport VARCHAR NOT NULL,
                opportunity_type VARCHAR NOT NULL,
                home_team VARCHAR,
                away_team VARCHAR,
                platform VARCHAR,
                home_platform VARCHAR,
                away_platform VARCHAR,
                edge DOUBLE,
                profit_margin DOUBLE,
                elo_prob DOUBLE,
                market_prob DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert opportunities
        for i, opp in enumerate(opportunities):
            opp_id = f"{opp['type']}_{date_str}_{i}_{opp['home_team']}_{opp['away_team']}"
            
            conn.execute("""
                INSERT OR REPLACE INTO arbitrage_opportunities
                (opportunity_id, opportunity_date, sport, opportunity_type, 
                 home_team, away_team, platform, home_platform, away_platform,
                 edge, profit_margin, elo_prob, market_prob)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                opp_id,
                date_str,
                opp['sport'],
                opp['type'],
                opp.get('home_team'),
                opp.get('away_team'),
                opp.get('platform'),
                opp.get('home_platform'),
                opp.get('away_platform'),
                opp.get('edge'),
                opp.get('profit_margin'),
                opp.get('elo_prob'),
                opp.get('market_prob')
            ))
        
        conn.close()
        print(f"✓ Saved {len(opportunities)} opportunities to database")


if __name__ == '__main__':
    from datetime import date
    
    today = date.today().strftime('%Y-%m-%d')
    
    comparator = OddsComparator()
    
    # Test matching markets
    for sport in ['nba', 'nhl', 'mlb', 'nfl']:
        matched = comparator.match_markets(sport, today)
        
        if matched:
            # Find arbitrage
            opportunities = comparator.find_arbitrage(matched)
            
            if opportunities:
                print(f"\n🎯 {sport.upper()} Opportunities:")
                for opp in opportunities[:5]:
                    print(f"  {opp['type']}: {opp['away_team']} @ {opp['home_team']}")
                    if opp['type'] == 'arbitrage':
                        print(f"    Profit margin: {opp['profit_margin']:.2%}")
                    else:
                        print(f"    Edge: {opp['edge']:.2%} on {opp['platform']}")
