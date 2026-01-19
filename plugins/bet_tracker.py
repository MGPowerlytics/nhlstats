"""
Track bet outcomes by querying Kalshi API for positions and market results.
"""
import duckdb
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
import sys

sys.path.insert(0, str(Path(__file__).parent))
from kalshi_betting import KalshiBetting


def create_bets_table(conn):
    """Create bets tracking table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS placed_bets (
            bet_id VARCHAR PRIMARY KEY,
            sport VARCHAR,
            placed_date DATE,
            ticker VARCHAR,
            home_team VARCHAR,
            away_team VARCHAR,
            bet_on VARCHAR,
            side VARCHAR,
            contracts INTEGER,
            price_cents INTEGER,
            cost_dollars DOUBLE,
            fees_dollars DOUBLE,
            elo_prob DOUBLE,
            market_prob DOUBLE,
            edge DOUBLE,
            confidence VARCHAR,
            status VARCHAR,  -- open, won, lost, settled
            settled_date DATE,
            payout_dollars DOUBLE,
            profit_dollars DOUBLE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def load_fills_from_kalshi(client: KalshiBetting, days_back: int = 30) -> List[Dict]:
    """Load all fills from Kalshi API."""
    try:
        response = client._get(f'/trade-api/v2/portfolio/fills?limit=500')
        fills = response.get('fills', [])
        print(f"✓ Loaded {len(fills)} fills from Kalshi")
        return fills
    except Exception as e:
        print(f"⚠️  Error loading fills: {e}")
        return []


def get_market_status(client: KalshiBetting, ticker: str) -> Dict:
    """Get current market status and result."""
    try:
        market = client.get_market_details(ticker)
        if market:
            return {
                'status': market.get('status'),
                'result': market.get('result'),
                'close_time': market.get('close_time'),
                'title': market.get('title')
            }
    except:
        pass
    return {}


def sync_bets_to_database(db_path: str = 'data/nhlstats.duckdb'):
    """Sync all bets from Kalshi API to database."""
    
    # Load Kalshi credentials
    kalshkey_file = Path('kalshkey')
    with open(kalshkey_file, 'r') as f:
        first_line = f.readline().strip()
        api_key_id = first_line.split('API key id:')[1].strip()
    
    private_key_path = Path('kalshi_private_key.pem')
    
    # Initialize client
    client = KalshiBetting(
        api_key_id=api_key_id,
        private_key_path=str(private_key_path),
        max_bet_size=5.0,
        production=True
    )
    
    # Load fills from Kalshi
    fills = load_fills_from_kalshi(client)
    
    if not fills:
        print("⚠️  No fills found")
        return
    
    # Connect to database
    conn = duckdb.connect(db_path)
    create_bets_table(conn)
    
    # Load existing bets to avoid duplicates
    existing_bets = set(conn.execute("SELECT bet_id FROM placed_bets").fetchdf()['bet_id'].tolist())
    
    added_count = 0
    updated_count = 0
    
    for fill in fills:
        ticker = fill.get('ticker', '')
        trade_id = fill.get('trade_id', '')
        bet_id = f"{ticker}_{trade_id}"
        
        # Parse ticker to determine sport
        sport = 'UNKNOWN'
        if 'NBAGAME' in ticker:
            sport = 'NBA'
        elif 'NHLGAME' in ticker:
            sport = 'NHL'
        elif 'MLBGAME' in ticker:
            sport = 'MLB'
        elif 'NFLGAME' in ticker:
            sport = 'NFL'
        elif 'NCAAMBGAME' in ticker:
            sport = 'NCAAB'
        elif 'ATPMATCH' in ticker or 'WTAMATCH' in ticker:
            sport = 'TENNIS'
        elif 'EPLGAME' in ticker:
            sport = 'EPL'
        
        side = fill.get('side', '')
        count = fill.get('count', 0)
        price = fill.get('yes_price', 0) if side == 'yes' else fill.get('no_price', 0)
        cost = count * price / 100
        created_time = fill.get('created_time', '')
        placed_date = created_time.split('T')[0] if created_time else None
        
        # Get market status
        market_info = get_market_status(client, ticker)
        market_status = market_info.get('status', 'unknown')
        market_result = market_info.get('result', '')
        
        # Determine bet status
        if market_status in ['closed', 'finalized']:
            if market_result == side:
                status = 'won'
                payout = count * 1.0  # $1 per contract
                profit = payout - cost
            elif market_result and market_result != side:
                status = 'lost'
                payout = 0
                profit = -cost
            else:
                status = 'settled'
                payout = 0
                profit = -cost
            settled_date = datetime.now().strftime('%Y-%m-%d')
        else:
            status = 'open'
            payout = None
            profit = None
            settled_date = None
        
        if bet_id in existing_bets:
            # Update existing bet
            conn.execute("""
                UPDATE placed_bets
                SET status = ?, settled_date = ?, payout_dollars = ?, profit_dollars = ?
                WHERE bet_id = ?
            """, [status, settled_date, payout, profit, bet_id])
            updated_count += 1
        else:
            # Insert new bet
            conn.execute("""
                INSERT INTO placed_bets (
                    bet_id, sport, placed_date, ticker, side, contracts,
                    price_cents, cost_dollars, fees_dollars, status,
                    settled_date, payout_dollars, profit_dollars
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                bet_id, sport, placed_date, ticker, side, count,
                price, cost, 0, status, settled_date, payout, profit
            ])
            added_count += 1
    
    conn.close()
    
    print(f"\n✓ Synced bets to database:")
    print(f"  Added: {added_count}")
    print(f"  Updated: {updated_count}")
    
    return added_count, updated_count


def get_betting_summary(db_path: str = 'data/nhlstats.duckdb', date: str = None):
    """Get summary of betting performance."""
    conn = duckdb.connect(db_path, read_only=True)
    
    if date:
        where_clause = f"WHERE placed_date = '{date}'"
    else:
        where_clause = ""
    
    summary = conn.execute(f"""
        SELECT 
            COUNT(*) as total_bets,
            SUM(contracts) as total_contracts,
            SUM(cost_dollars) as total_cost,
            SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_bets,
            SUM(CASE WHEN status IN ('won', 'lost') THEN profit_dollars ELSE 0 END) as total_profit,
            AVG(CASE WHEN status IN ('won', 'lost') THEN profit_dollars ELSE NULL END) as avg_profit_per_bet
        FROM placed_bets
        {where_clause}
    """).fetchdf()
    
    conn.close()
    
    return summary


if __name__ == '__main__':
    print("Syncing bets from Kalshi API to database...")
    sync_bets_to_database()
    
    print("\n" + "="*80)
    print("BETTING SUMMARY")
    print("="*80)
    
    summary = get_betting_summary()
    print(summary.to_string(index=False))
