"""
Load bet recommendations into DuckDB for historical analysis.
"""

import json
from pathlib import Path
from datetime import datetime
import duckdb


class BetLoader:
    """Loads bet recommendations into DuckDB."""
    
    def __init__(self, db_path='data/nhlstats.duckdb'):
        self.db_path = db_path
        self._ensure_table()
    
    def _ensure_table(self):
        """Create bet_recommendations table if it doesn't exist."""
        conn = duckdb.connect(self.db_path)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bet_recommendations (
                bet_id VARCHAR PRIMARY KEY,
                sport VARCHAR NOT NULL,
                recommendation_date DATE NOT NULL,
                home_team VARCHAR NOT NULL,
                away_team VARCHAR NOT NULL,
                bet_on VARCHAR NOT NULL,
                elo_prob DOUBLE NOT NULL,
                market_prob DOUBLE NOT NULL,
                edge DOUBLE NOT NULL,
                confidence VARCHAR NOT NULL,
                yes_ask INTEGER,
                no_ask INTEGER,
                ticker VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index for efficient querying
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_bet_recs_date_sport 
            ON bet_recommendations(recommendation_date, sport)
        """)
        
        conn.close()
    
    def load_bets_for_date(self, sport: str, date_str: str) -> int:
        """
        Load bets from JSON file into database.
        
        Args:
            sport: Sport name (nba, nhl, mlb, nfl, epl, ncaab, tennis)
            date_str: Date string in YYYY-MM-DD format
            
        Returns:
            Number of bets loaded
        """
        bets_file = Path(f'data/{sport}/bets_{date_str}.json')
        
        if not bets_file.exists():
            print(f"⚠️  No bets file found for {sport} on {date_str}")
            return 0
        
        with open(bets_file, 'r') as f:
            bets = json.load(f)
        
        if not bets:
            print(f"ℹ️  No bets to load for {sport} on {date_str}")
            return 0
        
        conn = duckdb.connect(self.db_path)
        
        loaded = 0
        for i, bet in enumerate(bets):
            # Create unique bet ID
            bet_id = f"{sport}_{date_str}_{i}_{bet['home_team']}_{bet['away_team']}"
            
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO bet_recommendations 
                    (bet_id, sport, recommendation_date, home_team, away_team, 
                     bet_on, elo_prob, market_prob, edge, confidence, 
                     yes_ask, no_ask, ticker)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    bet_id,
                    sport,
                    date_str,
                    bet['home_team'],
                    bet['away_team'],
                    bet['bet_on'],
                    bet['elo_prob'],
                    bet['market_prob'],
                    bet['edge'],
                    bet['confidence'],
                    bet.get('yes_ask'),
                    bet.get('no_ask'),
                    bet.get('ticker')
                ))
                loaded += 1
            except Exception as e:
                print(f"⚠️  Error loading bet {bet_id}: {e}")
        
        conn.close()
        
        print(f"✓ Loaded {loaded} {sport.upper()} bets for {date_str}")
        return loaded
    
    def get_bets_summary(self, start_date=None, end_date=None):
        """Get summary of bet recommendations by sport and date."""
        conn = duckdb.connect(self.db_path, read_only=True)
        
        query = """
            SELECT 
                sport,
                recommendation_date,
                COUNT(*) as num_bets,
                AVG(edge) as avg_edge,
                AVG(elo_prob) as avg_elo_prob,
                SUM(CASE WHEN confidence = 'HIGH' THEN 1 ELSE 0 END) as high_confidence_bets
            FROM bet_recommendations
        """
        
        if start_date or end_date:
            query += " WHERE 1=1"
            if start_date:
                query += f" AND recommendation_date >= '{start_date}'"
            if end_date:
                query += f" AND recommendation_date <= '{end_date}'"
        
        query += " GROUP BY sport, recommendation_date ORDER BY recommendation_date DESC, sport"
        
        result = conn.execute(query).fetchall()
        conn.close()
        
        return result


if __name__ == '__main__':
    # Test loading today's bets
    from datetime import date
    
    loader = BetLoader()
    today = date.today().strftime('%Y-%m-%d')
    
    print(f"Loading bets for {today}...")
    total = 0
    for sport in ['nba', 'nhl', 'mlb', 'nfl', 'epl', 'ncaab', 'tennis']:
        count = loader.load_bets_for_date(sport, today)
        total += count
    
    print(f"\n✓ Total bets loaded: {total}")
    
    print("\n📊 Recent bets summary:")
    summary = loader.get_bets_summary()
    for row in summary[:20]:
        print(f"  {row[0]:6} {row[1]}: {row[2]:2} bets, avg edge: {row[3]:.1%}, avg prob: {row[4]:.1%}, {row[5]} high conf")
