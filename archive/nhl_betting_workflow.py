"""
NHL Betting Workflow DAG
Daily workflow: Download games → Load to DB → Update Elo → Identify bets
"""

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from nhl_game_events import NHLGameEvents
from nhl_elo_rating import NHLEloRating
import duckdb
import pandas as pd


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': True,
    'email': ['7244959219@vtext.com'],
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}


def download_nhl_games(date_str, **context):
    """Download NHL games for date."""
    print(f"📥 Downloading NHL games for {date_str}...")
    
    fetcher = NHLGameEvents()
    schedule = fetcher.get_schedule_by_date(date_str)
    
    game_ids = []
    for week in schedule.get('gameWeek', []):
        for game in week.get('games', []):
            game_id = game.get('id')
            if game_id:
                game_ids.append(game_id)
    
    if not game_ids:
        print(f"ℹ️  No games scheduled for {date_str}")
        return 0
    
    fetcher = NHLGameEvents(date_folder=date_str)
    
    for i, game_id in enumerate(game_ids, 1):
        try:
            print(f"[{i}/{len(game_ids)}] Downloading game {game_id}")
            fetcher.download_game(game_id, include_boxscore=True)
        except Exception as e:
            print(f"⚠️  Error downloading {game_id}: {e}")
    
    print(f"✅ Downloaded {len(game_ids)} games")
    return len(game_ids)


def update_elo_ratings(**context):
    """Update NHL Elo ratings with latest games."""
    print("📊 Updating NHL Elo ratings...")
    
    # Load completed games from database
    conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)
    
    games_query = """
    SELECT 
        game_id,
        game_date,
        home_team_name,
        away_team_name,
        home_score,
        away_score,
        CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
    FROM games
    WHERE game_type = 2
    AND game_state = 'OFF'
    AND home_score IS NOT NULL
    AND away_score IS NOT NULL
    ORDER BY game_date, game_id
    """
    
    games_df = conn.execute(games_query).fetchdf()
    conn.close()
    
    if len(games_df) == 0:
        print("⚠️  No games found")
        return
    
    # Initialize Elo system
    elo = NHLEloRating(k_factor=20, home_advantage=100)
    
    # Process all games chronologically
    for _, game in games_df.iterrows():
        prob = elo.predict(game['home_team_name'], game['away_team_name'])
        elo.update(game['home_team_name'], game['away_team_name'], game['home_win'])
    
    # Save current ratings
    ratings_df = pd.DataFrame([
        {'team': team, 'elo_rating': rating, 'updated_at': datetime.now()}
        for team, rating in elo.ratings.items()
    ]).sort_values('elo_rating', ascending=False)
    
    ratings_df.to_csv('data/nhl_current_elo_ratings.csv', index=False)
    
    print(f"✅ Updated {len(elo.ratings)} NHL team ratings")
    print(f"🏆 Top 3: {ratings_df.head(3)[['team', 'elo_rating']].to_dict('records')}")
    
    # Push to XCom
    context['task_instance'].xcom_push(key='elo_ratings', value=elo.ratings)
    context['task_instance'].xcom_push(key='elo_system', value={
        'k_factor': elo.k_factor,
        'home_advantage': elo.home_advantage
    })


def fetch_prediction_markets(date_str, **context):
    """Fetch prediction market data for NHL games."""
    print(f"💰 Fetching NHL prediction markets for {date_str}...")
    
    try:
        # Try to fetch from Kalshi
        from kalshi_markets import fetch_nhl_markets
        from datetime import datetime
        
        markets = fetch_nhl_markets(date_str)
        
        if markets:
            # Convert datetime objects to strings for JSON serialization
            serializable_markets = []
            for market in markets:
                serialized = {}
                for key, value in market.items():
                    if isinstance(value, datetime):
                        serialized[key] = value.isoformat()
                    else:
                        serialized[key] = value
                serializable_markets.append(serialized)
            
            markets_file = Path(f'data/nhl/markets_{date_str}.json')
            markets_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(markets_file, 'w') as f:
                json.dump(serializable_markets, f, indent=2, default=str)
            
            print(f"✅ Fetched {len(markets)} markets")
            context['task_instance'].xcom_push(key='markets', value=serializable_markets)
        else:
            print("ℹ️  No markets available")
            context['task_instance'].xcom_push(key='markets', value=[])
            
    except ImportError:
        print("⚠️  Kalshi integration not available")
        context['task_instance'].xcom_push(key='markets', value=[])
    except Exception as e:
        print(f"⚠️  Error fetching markets: {e}")
        import traceback
        traceback.print_exc()
        context['task_instance'].xcom_push(key='markets', value=[])
    except Exception as e:
        print(f"⚠️  Error fetching markets: {e}")
        context['task_instance'].xcom_push(key='markets', value=[])


def identify_good_bets(**context):
    """Identify NHL betting opportunities based on Elo vs market."""
    print("🎯 Identifying NHL betting opportunities...")
    
    # Get Elo ratings
    elo_ratings = context['task_instance'].xcom_pull(
        task_ids='update_elo_ratings',
        key='elo_ratings'
    )
    
    elo_params = context['task_instance'].xcom_pull(
        task_ids='update_elo_ratings',
        key='elo_system'
    )
    
    markets = context['task_instance'].xcom_pull(
        task_ids='fetch_prediction_markets',
        key='markets'
    )
    
    if not elo_ratings:
        print("⚠️  No Elo ratings available")
        return
    
    if not markets:
        print("ℹ️  No markets to analyze")
        return
    
    # Recreate Elo system
    elo = NHLEloRating(
        k_factor=elo_params['k_factor'],
        home_advantage=elo_params['home_advantage']
    )
    elo.ratings = elo_ratings
    
    # Analyze markets
    good_bets = []
    
    for market in markets:
        home_team = market.get('home_team')
        away_team = market.get('away_team')
        market_prob = market.get('home_win_prob')
        
        if not home_team or not away_team or market_prob is None:
            continue
        
        # Calculate Elo probability
        elo_prob = elo.predict(home_team, away_team)
        
        # Calculate edge
        edge = elo_prob - market_prob
        edge_pct = (edge / market_prob * 100) if market_prob > 0 else 0
        
        # NHL strategy: Only bet if prob > 77% (based on decile analysis) AND edge > 5%
        if elo_prob > 0.77 and edge > 0.05:
            good_bets.append({
                'home_team': home_team,
                'away_team': away_team,
                'elo_prob': elo_prob,
                'market_prob': market_prob,
                'edge': edge,
                'edge_pct': edge_pct,
                'bet_on': 'home' if elo_prob > 0.5 else 'away',
                'confidence': 'HIGH' if elo_prob > 0.82 else 'MEDIUM',
                'market_id': market.get('id'),
                'odds': market.get('odds')
            })
    
    # Sort by edge
    good_bets.sort(key=lambda x: x['edge'], reverse=True)
    
    # Save recommendations
    date_str = context['logical_date'].strftime('%Y-%m-%d')
    recommendations_file = Path(f'data/nhl/bets_{date_str}.json')
    recommendations_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(recommendations_file, 'w') as f:
        json.dump(good_bets, f, indent=2)
    
    # Print summary
    print(f"\n{'='*80}")
    print(f"🎲 NHL BETTING RECOMMENDATIONS for {date_str}")
    print(f"{'='*80}")
    
    if good_bets:
        for i, bet in enumerate(good_bets[:5], 1):
            print(f"{i}. {bet['home_team']} vs {bet['away_team']}")
            print(f"   Bet: {bet['bet_on'].upper()} | Elo: {bet['elo_prob']:.1%} | Market: {bet['market_prob']:.1%}")
            print(f"   Edge: {bet['edge']:+.1%} ({bet['edge_pct']:+.1f}%) | Confidence: {bet['confidence']}")
            print()
        
        if len(good_bets) > 5:
            print(f"   ... and {len(good_bets) - 5} more bets")
    else:
        print("ℹ️  No good betting opportunities found today")
        print("   (NHL requires high confidence: prob > 77%, edge > 5%)")
    
    print(f"{'='*80}\n")
    
    return len(good_bets)


with DAG(
    'nhl_betting_workflow',
    default_args=default_args,
    description='NHL daily betting workflow: data → Elo → betting opportunities',
    schedule='0 10 * * *',  # 10 AM daily (after games complete)
    start_date=datetime(2026, 1, 18),
    catchup=False,
    max_active_runs=1,
    tags=['nhl', 'betting', 'elo', 'production'],
) as dag:
    
    # Task 1: Download yesterday's games
    download_games = PythonOperator(
        task_id='download_games',
        python_callable=download_nhl_games,
        op_kwargs={
            'date_str': '{{ (logical_date - macros.timedelta(days=1)).strftime("%Y-%m-%d") }}'
        },
    )
    
    # Task 2: Update Elo ratings
    update_elo = PythonOperator(
        task_id='update_elo_ratings',
        python_callable=update_elo_ratings,
    )
    
    # Task 3: Fetch prediction markets
    fetch_markets = PythonOperator(
        task_id='fetch_prediction_markets',
        python_callable=fetch_prediction_markets,
        op_kwargs={
            'date_str': '{{ logical_date.strftime("%Y-%m-%d") }}'
        },
    )
    
    # Task 4: Identify good bets
    find_bets = PythonOperator(
        task_id='identify_good_bets',
        python_callable=identify_good_bets,
    )
    
    # Dependencies
    download_games >> update_elo
    update_elo >> find_bets
    fetch_markets >> find_bets
