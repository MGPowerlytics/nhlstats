#!/usr/bin/env python3
"""
CLV (Closing Line Value) Tracker

This module tracks closing line values to validate that our model beats the market.

CLV = Bet Line Probability - Closing Line Probability

- Positive CLV means we got better odds than the closing line (good!)
- Negative CLV means the market moved against us (bad)

Consistent positive CLV is the #1 indicator of long-term profitability.
"""

import duckdb
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
import requests


class CLVTracker:
    """Track and analyze closing line values for bets."""
    
    def __init__(self, db_path: str = 'data/nhlstats.duckdb', odds_api_key: Optional[str] = None):
        self.db_path = db_path
        self.odds_api_key = odds_api_key
        
    def record_bet_line(self, bet_id: str, market_prob: float):
        """Record the line we bet at."""
        conn = duckdb.connect(self.db_path)
        conn.execute("""
            UPDATE placed_bets 
            SET bet_line_prob = ?, updated_at = CURRENT_TIMESTAMP
            WHERE bet_id = ?
        """, [market_prob, bet_id])
        conn.close()
        
    def update_closing_line(self, bet_id: str, closing_prob: float):
        """Update the closing line for a bet."""
        conn = duckdb.connect(self.db_path)
        
        # Get the bet line probability
        bet_line = conn.execute("""
            SELECT bet_line_prob FROM placed_bets WHERE bet_id = ?
        """, [bet_id]).fetchone()
        
        if bet_line and bet_line[0]:
            clv = bet_line[0] - closing_prob
            
            conn.execute("""
                UPDATE placed_bets 
                SET closing_line_prob = ?, clv = ?, updated_at = CURRENT_TIMESTAMP
                WHERE bet_id = ?
            """, [closing_prob, clv, bet_id])
            
            print(f"  CLV for {bet_id}: {clv:+.2%} ({bet_line[0]:.1%} bet → {closing_prob:.1%} close)")
        
        conn.close()
        
    def fetch_closing_lines_from_kalshi(self, days_back: int = 7):
        """Fetch recent Kalshi markets to get closing lines."""
        # TODO: Implement using Kalshi API to get market close prices
        pass
    
    def fetch_closing_lines_from_odds_api(self, days_back: int = 7):
        """Fetch closing lines from The Odds API."""
        if not self.odds_api_key:
            print("⚠️  No Odds API key - cannot fetch closing lines")
            return
        
        conn = duckdb.connect(self.db_path)
        
        # Get recent bets that need closing lines
        cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        bets = conn.execute("""
            SELECT bet_id, sport, home_team, away_team, placed_date, bet_line_prob
            FROM placed_bets
            WHERE placed_date >= ?
            AND closing_line_prob IS NULL
            AND status = 'settled'
        """, [cutoff_date]).fetchall()
        
        print(f"📊 Fetching closing lines for {len(bets)} bets...")
        
        sport_map = {
            'nba': 'basketball_nba',
            'nhl': 'icehockey_nhl',
            'mlb': 'baseball_mlb',
            'nfl': 'americanfootball_nfl',
            'ncaab': 'basketball_ncaab'
        }
        
        for bet_id, sport, home_team, away_team, placed_date, bet_line_prob in bets:
            sport_key = sport_map.get(sport.lower())
            if not sport_key:
                continue
                
            try:
                # Get scores/results which include closing odds
                url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/scores/'
                params = {
                    'apiKey': self.odds_api_key,
                    'daysFrom': 3,
                    'dateFormat': 'iso'
                }
                
                response = requests.get(url, params=params, timeout=10)
                if response.status_code != 200:
                    continue
                    
                games = response.json()
                
                # Find matching game
                for game in games:
                    if game.get('home_team') == home_team and game.get('away_team') == away_team:
                        # Get closing odds (last available odds before game)
                        # This would need more sophisticated parsing
                        # For now, just mark as processed
                        pass
                        
            except Exception as e:
                print(f"  ⚠️  Error fetching closing line for {bet_id}: {e}")
                
        conn.close()
    
    def analyze_clv(self, days_back: int = 30) -> Dict:
        """
        Analyze CLV performance over recent bets.
        
        Returns dict with:
        - avg_clv: Average CLV across all bets
        - positive_clv_pct: Percentage of bets with positive CLV
        - clv_by_sport: CLV broken down by sport
        """
        conn = duckdb.connect(self.db_path, read_only=True)
        
        cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        # Overall CLV
        overall = conn.execute("""
            SELECT 
                COUNT(*) as num_bets,
                AVG(clv) as avg_clv,
                SUM(CASE WHEN clv > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as positive_clv_pct
            FROM placed_bets
            WHERE placed_date >= ?
            AND clv IS NOT NULL
        """, [cutoff_date]).fetchone()
        
        # By sport
        by_sport = conn.execute("""
            SELECT 
                sport,
                COUNT(*) as num_bets,
                AVG(clv) as avg_clv,
                SUM(CASE WHEN clv > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as positive_clv_pct
            FROM placed_bets
            WHERE placed_date >= ?
            AND clv IS NOT NULL
            GROUP BY sport
            ORDER BY avg_clv DESC
        """, [cutoff_date]).fetchall()
        
        conn.close()
        
        if not overall or overall[0] == 0:
            return {'num_bets': 0, 'message': 'No CLV data available'}
        
        return {
            'num_bets': overall[0],
            'avg_clv': overall[1],
            'positive_clv_pct': overall[2],
            'by_sport': [{
                'sport': row[0],
                'num_bets': row[1],
                'avg_clv': row[2],
                'positive_clv_pct': row[3]
            } for row in by_sport]
        }
    
    def print_clv_report(self, days_back: int = 30):
        """Print a formatted CLV report."""
        analysis = self.analyze_clv(days_back)
        
        if analysis.get('num_bets', 0) == 0:
            print("❌ No CLV data available")
            return
        
        print(f"\n{'='*60}")
        print(f"CLV ANALYSIS - Last {days_back} Days")
        print(f"{'='*60}\n")
        
        print(f"Overall Performance:")
        print(f"  Total Bets: {analysis['num_bets']}")
        print(f"  Average CLV: {analysis['avg_clv']:+.2%}")
        print(f"  Positive CLV %: {analysis['positive_clv_pct']:.1f}%")
        
        if analysis['avg_clv'] > 0:
            print(f"  ✅ POSITIVE CLV - Model is beating closing lines!")
        else:
            print(f"  ❌ NEGATIVE CLV - Model is NOT beating closing lines")
        
        print(f"\nBy Sport:")
        for sport_data in analysis['by_sport']:
            indicator = "✅" if sport_data['avg_clv'] > 0 else "❌"
            print(f"  {indicator} {sport_data['sport'].upper():8} | "
                  f"Bets: {sport_data['num_bets']:3} | "
                  f"CLV: {sport_data['avg_clv']:+.2%} | "
                  f"Positive: {sport_data['positive_clv_pct']:.0f}%")
        
        print(f"\n{'='*60}\n")


def main():
    """Run CLV analysis."""
    # Load Odds API key
    odds_api_key = None
    if Path('odds_api_key').exists():
        with open('odds_api_key', 'r') as f:
            odds_api_key = f.read().strip()
    
    tracker = CLVTracker(odds_api_key=odds_api_key)
    
    # Fetch closing lines for recent bets
    # tracker.fetch_closing_lines_from_odds_api(days_back=7)
    
    # Print CLV report
    tracker.print_clv_report(days_back=30)


if __name__ == '__main__':
    main()
