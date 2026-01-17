"""
Daily NHL Betting DAG
- Generates betting recommendations from Kalshi markets
- Tracks performance of previous day's bets
- No backfill (catchup=False)
"""

from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from airflow.models import DAG
from airflow.providers.standard.operators.python import PythonOperator

import json


def load_kalshi_credentials():
    """Load Kalshi API credentials"""
    key_file = Path("/opt/airflow/kalshkey")
    content = key_file.read_text()
    
    api_key_id = None
    for line in content.split('\n'):
        if 'API key id:' in line:
            api_key_id = line.split(':', 1)[1].strip()
            break
    
    private_key_lines = []
    in_key = False
    for line in content.split('\n'):
        if '-----BEGIN RSA PRIVATE KEY-----' in line:
            in_key = True
        if in_key:
            private_key_lines.append(line)
        if '-----END RSA PRIVATE KEY-----' in line:
            break
    
    private_key = '\n'.join(private_key_lines)
    return api_key_id, private_key


def fetch_kalshi_markets(**context):
    """Fetch NHL markets from Kalshi API"""
    from kalshi_python import Configuration, ApiClient, MarketsApi
    from pathlib import Path
    
    print("=" * 80)
    print("📡 FETCHING KALSHI MARKETS")
    print("=" * 80)
    
    # Load credentials
    api_key_id, private_key = load_kalshi_credentials()
    
    # Setup Kalshi client
    config = Configuration()
    config.host = "https://api.elections.kalshi.com/trade-api/v2"
    
    client = ApiClient(configuration=config)
    client.configuration.access_token = api_key_id
    client.configuration.private_key = private_key
    
    markets_api = MarketsApi(client)
    
    # Fetch NHL markets
    print("\nSearching for NHL markets...")
    response = markets_api.get_markets(
        series_ticker="KXNHLGAME",
        limit=200,
        status="open"
    )
    
    markets = response.markets if hasattr(response, 'markets') else []
    print(f"✓ Found {len(markets)} NHL markets")
    
    # Extract market data
    market_data = []
    for market in markets:
        market_data.append({
            'ticker': market.ticker,
            'event_ticker': market.event_ticker,
            'subtitle': market.subtitle,
            'yes_ask': market.yes_ask,
            'yes_bid': market.yes_bid,
            'no_ask': market.no_ask,
            'no_bid': market.no_bid,
            'last_price': market.last_price,
            'volume': market.volume,
            'open_time': str(market.open_time) if hasattr(market, 'open_time') else None,
            'close_time': str(market.close_time) if hasattr(market, 'close_time') else None,
        })
    
    # Get execution date
    logical_date = context['logical_date']
    date_str = logical_date.strftime('%Y-%m-%d')
    
    # Save markets
    output_dir = Path(f"/opt/airflow/data/betting/{date_str}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    markets_file = output_dir / "markets.json"
    with open(markets_file, 'w') as f:
        json.dump({
            'date': date_str,
            'timestamp': datetime.now().isoformat(),
            'count': len(market_data),
            'markets': market_data
        }, f, indent=2)
    
    print(f"\n✅ Saved {len(market_data)} markets to: {markets_file}")
    
    # Push count to XCom
    context['task_instance'].xcom_push(
        key='market_count',
        value=len(market_data)
    )


def generate_predictions(**context):
    """Generate predictions from saved Kalshi markets"""
    from betting_workflow import NHLBettingWorkflow
    from pathlib import Path
    
    print("=" * 80)
    print("🤖 GENERATING PREDICTIONS")
    print("=" * 80)
    
    # Get execution date
    logical_date = context['logical_date']
    date_str = logical_date.strftime('%Y-%m-%d')
    
    # Load markets from previous task
    markets_file = Path(f"/opt/airflow/data/betting/{date_str}/markets.json")
    
    if not markets_file.exists():
        print(f"⚠️ No markets file found: {markets_file}")
        return
    
    with open(markets_file, 'r') as f:
        markets_data = json.load(f)
    
    markets = markets_data.get('markets', [])
    print(f"\n✓ Loaded {len(markets)} markets from file")
    
    # Create workflow (DB + Model only, no Kalshi)
    workflow = NHLBettingWorkflow()
    
    try:
        workflow.connect_db()
        workflow.load_model()
        
        # Group markets by game
        games = {}
        for market in markets:
            subtitle = market.get('subtitle', '')
            if not subtitle:
                continue
            
            # Parse "Team A vs Team B"
            if ' vs ' in subtitle:
                parts = subtitle.split(' vs ')
                if len(parts) == 2:
                    away_team = parts[0].strip()
                    home_team = parts[1].strip()
                    game_key = f"{away_team} @ {home_team}"
                    
                    if game_key not in games:
                        games[game_key] = {
                            'away_team': away_team,
                            'home_team': home_team,
                            'markets': []
                        }
                    
                    games[game_key]['markets'].append(market)
        
        print(f"✓ Grouped into {len(games)} games")
        
        # Analyze each game
        opportunities = []
        
        for i, (game_str, game_data) in enumerate(games.items(), 1):
            away_team_kalshi = game_data['away_team']
            home_team_kalshi = game_data['home_team']
            
            print(f"\n{i}. {game_str}")
            print(f"   Mapping teams...")
            
            # Map to DB names
            away_team = workflow.map_team_names(away_team_kalshi)
            home_team = workflow.map_team_names(home_team_kalshi)
            
            if not away_team or not home_team:
                print(f"   ⚠️ Could not map teams")
                continue
            
            print(f"   Mapped: {away_team} @ {home_team}")
            
            # Get prediction
            prediction = workflow.predict_game(away_team, home_team)
            
            if prediction is None:
                print(f"   ⚠️ Insufficient data for prediction")
                continue
            
            home_prob = prediction
            away_prob = 1 - prediction
            
            print(f"   Model: Home {home_prob:.1%} | Away {away_prob:.1%}")
            
            # Find market prices
            home_market = None
            away_market = None
            
            for market in game_data['markets']:
                ticker = market.get('ticker', '')
                if home_team_kalshi.upper() in ticker.upper():
                    home_market = market
                elif away_team_kalshi.upper() in ticker.upper():
                    away_market = market
            
            if not home_market or not away_market:
                print(f"   ⚠️ Missing market prices")
                continue
            
            # Calculate prices (use last_price or midpoint of bid/ask)
            def get_price(market):
                if market.get('last_price'):
                    return market['last_price'] / 100.0
                yes_bid = market.get('yes_bid', 0)
                yes_ask = market.get('yes_ask', 0)
                if yes_bid and yes_ask:
                    return (yes_bid + yes_ask) / 200.0
                return None
            
            home_price = get_price(home_market)
            away_price = get_price(away_market)
            
            if not home_price or not away_price:
                print(f"   ⚠️ Could not calculate prices")
                continue
            
            print(f"   Kalshi: Home ${home_price:.2f} | Away ${away_price:.2f}")
            
            # Calculate edges and EVs
            home_edge = home_prob - home_price
            away_edge = away_prob - away_price
            home_ev = (home_prob * 1.0) - home_price
            away_ev = (away_prob * 1.0) - away_price
            
            print(f"   Edge: Home {home_edge:+.1%} | Away {away_edge:+.1%}")
            print(f"   EV: Home ${home_ev:+.2f} | Away ${away_ev:+.2f}")
            
            # Check for opportunities (min 5% edge, min $0.05 EV)
            if home_edge >= 0.05 and home_ev >= 0.05:
                print(f"   ✅ BET HOME: Edge {home_edge:.1%}, EV ${home_ev:.2f}")
                opportunities.append({
                    'game': game_str,
                    'bet': 'HOME',
                    'team': home_team_kalshi,
                    'model_prob': home_prob,
                    'market_price': home_price,
                    'edge': home_edge,
                    'ev': home_ev,
                    'ticker': home_market.get('ticker'),
                    'date': date_str
                })
            
            if away_edge >= 0.05 and away_ev >= 0.05:
                print(f"   ✅ BET AWAY: Edge {away_edge:.1%}, EV ${away_ev:.2f}")
                opportunities.append({
                    'game': game_str,
                    'bet': 'AWAY',
                    'team': away_team_kalshi,
                    'model_prob': away_prob,
                    'market_price': away_price,
                    'edge': away_edge,
                    'ev': away_ev,
                    'ticker': away_market.get('ticker'),
                    'date': date_str
                })
        
        # Save recommendations
        output_dir = Path(f"/opt/airflow/data/betting/{date_str}")
        recommendations_file = output_dir / "recommendations.json"
        
        with open(recommendations_file, 'w') as f:
            json.dump({
                'date': date_str,
                'timestamp': datetime.now().isoformat(),
                'count': len(opportunities),
                'opportunities': opportunities,
                'total_ev': sum(opp['ev'] for opp in opportunities)
            }, f, indent=2)
        
        print(f"\n✅ Generated {len(opportunities)} recommendations")
        print(f"   Total EV: ${sum(opp['ev'] for opp in opportunities):+.2f}")
        print(f"   Saved to: {recommendations_file}")
        
        # Push to XCom
        context['task_instance'].xcom_push(
            key='recommendations_count',
            value=len(opportunities)
        )
        context['task_instance'].xcom_push(
            key='total_ev',
            value=sum(opp['ev'] for opp in opportunities)
        )
        
    finally:
        workflow.close()


def track_betting_performance(**context):
    """Track performance of previous day's bets"""
    
    import duckdb
    from pathlib import Path
    
    print("=" * 80)
    print("📈 TRACKING BETTING PERFORMANCE")
    print("=" * 80)
    
    # Get previous day
    logical_date = context['logical_date']
    prev_date = logical_date - timedelta(days=1)
    prev_date_str = prev_date.strftime('%Y-%m-%d')
    
    print(f"\nChecking bets from: {prev_date_str}")
    
    # Load previous day's recommendations
    recommendations_file = Path(f"/opt/airflow/data/betting/{prev_date_str}/recommendations.json")
    
    if not recommendations_file.exists():
        print(f"⚠️ No recommendations found for {prev_date_str}")
        return
    
    with open(recommendations_file, 'r') as f:
        prev_data = json.load(f)
    
    opportunities = prev_data.get('opportunities', [])
    
    if not opportunities:
        print(f"⚠️ No betting opportunities from {prev_date_str}")
        return
    
    print(f"✓ Found {len(opportunities)} bets to track")
    
    # Connect to DuckDB to get actual results
    conn = duckdb.connect("/opt/airflow/data/nhlstats.duckdb", read_only=True)
    
    results = []
    total_profit = 0
    wins = 0
    losses = 0
    
    for i, opp in enumerate(opportunities, 1):
        game = opp['game']
        bet_side = opp['bet']  # 'HOME' or 'AWAY'
        team = opp['team']
        model_prob = opp['model_prob']
        market_price = opp['market_price']
        edge = opp['edge']
        ev = opp['ev']
        
        print(f"\n{i}. {game}")
        print(f"   Bet: {team} ({bet_side})")
        print(f"   Price: ${market_price:.2f} | EV: ${ev:+.2f}")
        
        # Query game result
        # Extract team names from game string (format: "Team A @ Team B")
        parts = game.split(' @ ')
        if len(parts) != 2:
            print(f"   ⚠️ Could not parse game string")
            continue
        
        away_team_kalshi = parts[0].strip()
        home_team_kalshi = parts[1].strip()
        
        # Map to DB names
        from betting_workflow import NHLBettingWorkflow
        workflow = NHLBettingWorkflow()
        workflow.conn = conn
        
        away_team_db = workflow.map_team_names(away_team_kalshi)
        home_team_db = workflow.map_team_names(home_team_kalshi)
        
        # Find the game in DuckDB (look for games on prev_date or day after)
        query = """
        SELECT 
            g.game_id,
            g.game_date,
            g.home_team_id,
            g.away_team_id,
            g.winning_team_id,
            ht.team_name as home_team,
            away_t.team_name as away_team,
            wt.team_name as winning_team
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.team_id
        JOIN teams away_t ON g.away_team_id = away_t.team_id
        LEFT JOIN teams wt ON g.winning_team_id = wt.team_id
        WHERE g.game_date >= ?
          AND g.game_date <= ?
          AND ht.team_name = ?
          AND away_t.team_name = ?
        LIMIT 1
        """
        
        # Check prev_date and next 2 days (games might be recorded on different dates)
        start_date = prev_date_str
        end_date = (prev_date + timedelta(days=2)).strftime('%Y-%m-%d')
        
        result = conn.execute(query, (start_date, end_date, home_team_db, away_team_db)).fetchone()
        
        if not result:
            print(f"   ⚠️ Game result not found in database yet")
            result_dict = {
                'game': game,
                'bet': team,
                'bet_side': bet_side,
                'model_prob': model_prob,
                'market_price': market_price,
                'edge': edge,
                'ev': ev,
                'status': 'pending',
                'won': None,
                'profit': 0
            }
            results.append(result_dict)
            continue
        
        game_id, game_date, home_id, away_id, winning_id, home_name, away_name, winning_name = result
        
        # Determine if bet won
        if winning_id is None:
            print(f"   ⚠️ Game not finished yet")
            result_dict = {
                'game': game,
                'bet': team,
                'bet_side': bet_side,
                'model_prob': model_prob,
                'market_price': market_price,
                'edge': edge,
                'ev': ev,
                'status': 'in_progress',
                'won': None,
                'profit': 0
            }
            results.append(result_dict)
            continue
        
        # Check if our bet won
        bet_won = False
        if bet_side == 'HOME' and winning_id == home_id:
            bet_won = True
        elif bet_side == 'AWAY' and winning_id == away_id:
            bet_won = True
        
        # Calculate profit (assuming $1 bet)
        # If won: payout is $1, cost is market_price, profit = 1 - market_price
        # If lost: profit = -market_price
        if bet_won:
            profit = 1.0 - market_price
            wins += 1
            print(f"   ✅ WON! Profit: ${profit:+.2f}")
        else:
            profit = -market_price
            losses += 1
            print(f"   ❌ LOST! Profit: ${profit:+.2f}")
        
        total_profit += profit
        
        result_dict = {
            'game': game,
            'bet': team,
            'bet_side': bet_side,
            'model_prob': model_prob,
            'market_price': market_price,
            'edge': edge,
            'ev': ev,
            'actual_winner': winning_name,
            'won': bet_won,
            'profit': profit,
            'status': 'completed'
        }
        results.append(result_dict)
    
    conn.close()
    
    # Calculate summary stats
    completed = wins + losses
    win_rate = wins / completed if completed > 0 else 0
    
    print("\n" + "=" * 80)
    print("📊 PERFORMANCE SUMMARY")
    print("=" * 80)
    print(f"Total Bets: {len(opportunities)}")
    print(f"Completed: {completed}")
    print(f"Wins: {wins}")
    print(f"Losses: {losses}")
    if completed > 0:
        print(f"Win Rate: {win_rate:.1%}")
        print(f"Total Profit: ${total_profit:+.2f}")
        print(f"Avg Profit per Bet: ${total_profit/completed:+.2f}")
    
    # Save performance results
    performance_file = Path(f"/opt/airflow/data/betting/{prev_date_str}/performance.json")
    with open(performance_file, 'w') as f:
        json.dump({
            'date': prev_date_str,
            'tracked_at': datetime.now().isoformat(),
            'total_bets': len(opportunities),
            'completed': completed,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_profit': total_profit,
            'avg_profit': total_profit / completed if completed > 0 else 0,
            'results': results
        }, f, indent=2)
    
    print(f"\n💾 Saved performance to: {performance_file}")
    
    # Update cumulative stats
    update_cumulative_stats()


def update_cumulative_stats():
    """Update cumulative betting statistics across all days"""
    
    betting_dir = Path("/opt/airflow/data/betting")
    
    if not betting_dir.exists():
        print("⚠️ No betting data directory found")
        return
    
    # Collect all performance files
    all_results = []
    total_bets = 0
    total_wins = 0
    total_losses = 0
    total_profit = 0.0
    
    for date_dir in sorted(betting_dir.iterdir()):
        if not date_dir.is_dir():
            continue
        
        perf_file = date_dir / "performance.json"
        if not perf_file.exists():
            continue
        
        with open(perf_file, 'r') as f:
            perf = json.load(f)
        
        total_bets += perf.get('completed', 0)
        total_wins += perf.get('wins', 0)
        total_losses += perf.get('losses', 0)
        total_profit += perf.get('total_profit', 0)
        
        all_results.append({
            'date': perf['date'],
            'bets': perf.get('completed', 0),
            'wins': perf.get('wins', 0),
            'losses': perf.get('losses', 0),
            'win_rate': perf.get('win_rate', 0),
            'profit': perf.get('total_profit', 0)
        })
    
    # Calculate cumulative stats
    cumulative_win_rate = total_wins / total_bets if total_bets > 0 else 0
    
    cumulative = {
        'last_updated': datetime.now().isoformat(),
        'total_days': len(all_results),
        'total_bets': total_bets,
        'total_wins': total_wins,
        'total_losses': total_losses,
        'win_rate': cumulative_win_rate,
        'total_profit': total_profit,
        'avg_profit_per_bet': total_profit / total_bets if total_bets > 0 else 0,
        'by_date': all_results
    }
    
    # Save cumulative stats
    cumulative_file = betting_dir / "cumulative_stats.json"
    with open(cumulative_file, 'w') as f:
        json.dump(cumulative, f, indent=2)
    
    print("\n" + "=" * 80)
    print("🏆 CUMULATIVE BETTING STATISTICS")
    print("=" * 80)
    print(f"Days Tracked: {len(all_results)}")
    print(f"Total Bets: {total_bets}")
    print(f"Wins: {total_wins} | Losses: {total_losses}")
    if total_bets > 0:
        print(f"Win Rate: {cumulative_win_rate:.1%}")
        print(f"Total Profit: ${total_profit:+.2f}")
        print(f"ROI: {(total_profit/total_bets)*100:+.1f}%")
    print(f"\n💾 Saved to: {cumulative_file}")


# Define the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'email': ['7244959219@vtext.com'],  # Verizon SMS gateway
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'nhl_betting_daily',
    default_args=default_args,
    description='Daily NHL betting recommendations and performance tracking',
    schedule='0 10 * * *',  # Run at 10 AM UTC daily
    start_date=datetime(2026, 1, 16),  # Start from today
    catchup=False,  # Do NOT backfill
    tags=['betting', 'nhl', 'kalshi'],
)

# Task 1: Fetch markets from Kalshi
fetch_markets = PythonOperator(
    task_id='fetch_kalshi_markets',
    python_callable=fetch_kalshi_markets,
    dag=dag,
)

# Task 2: Generate predictions from markets
generate_preds = PythonOperator(
    task_id='generate_predictions',
    python_callable=generate_predictions,
    dag=dag,
)

# Task 3: Track previous day's performance
track_performance = PythonOperator(
    task_id='track_betting_performance',
    python_callable=track_betting_performance,
    dag=dag,
)

# Set task dependencies
fetch_markets >> generate_preds >> track_performance
