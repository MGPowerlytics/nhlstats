"""
Multi-Sport Betting Workflow DAG
Unified workflow for NBA, NHL, MLB, and NFL betting opportunities using Elo ratings.
"""

from datetime import datetime, timedelta
from pathlib import Path
import sys
import json

# Add plugins directory to Python path
plugins_dir = Path(__file__).parent.parent / 'plugins'
if str(plugins_dir) not in sys.path:
    sys.path.insert(0, str(plugins_dir))

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# Sport configurations
SPORTS_CONFIG = {
    'nba': {
        'elo_module': 'nba_elo_rating',
        'games_module': 'nba_games',
        'kalshi_function': 'fetch_nba_markets',
        'elo_threshold': 0.64,
        'series_ticker': 'KXNBAGAME',
        'team_mapping': {
            'ATL': 'Hawks', 'BOS': 'Celtics', 'BKN': 'Nets', 'CHA': 'Hornets',
            'CHI': 'Bulls', 'CLE': 'Cavaliers', 'DAL': 'Mavericks', 'DEN': 'Nuggets',
            'DET': 'Pistons', 'GSW': 'Warriors', 'HOU': 'Rockets', 'IND': 'Pacers',
            'LAC': 'Clippers', 'LAL': 'Lakers', 'MEM': 'Grizzlies', 'MIA': 'Heat',
            'MIL': 'Bucks', 'MIN': 'Timberwolves', 'NOP': 'Pelicans', 'NYK': 'Knicks',
            'OKC': 'Thunder', 'ORL': 'Magic', 'PHI': '76ers', 'PHX': 'Suns',
            'POR': 'Trail Blazers', 'SAC': 'Kings', 'SAS': 'Spurs', 'TOR': 'Raptors',
            'UTA': 'Jazz', 'WAS': 'Wizards'
        }
    },
    'nhl': {
        'elo_module': 'nhl_elo_rating',
        'games_module': 'nhl_game_events',
        'kalshi_function': 'fetch_nhl_markets',
        'elo_threshold': 0.62,
        'series_ticker': 'KXNHLGAME',
        'team_mapping': {
            'ANA': 'ANA', 'BOS': 'BOS', 'BUF': 'BUF', 'CAR': 'CAR', 'CBJ': 'CBJ',
            'CGY': 'CGY', 'CHI': 'CHI', 'COL': 'COL', 'DAL': 'DAL', 'DET': 'DET',
            'EDM': 'EDM', 'FLA': 'FLA', 'LAK': 'LAK', 'MIN': 'MIN', 'MTL': 'MTL',
            'NJD': 'NJD', 'NSH': 'NSH', 'NYI': 'NYI', 'NYR': 'NYR', 'OTT': 'OTT',
            'PHI': 'PHI', 'PIT': 'PIT', 'SEA': 'SEA', 'SJS': 'SJS', 'STL': 'STL',
            'TBL': 'TBL', 'TOR': 'TOR', 'VAN': 'VAN', 'VGK': 'VGK', 'WPG': 'WPG',
            'WSH': 'WSH', 'ARI': 'ARI'
        }
    },
    'mlb': {
        'elo_module': 'mlb_elo_rating',
        'games_module': 'mlb_games',
        'kalshi_function': 'fetch_mlb_markets',
        'elo_threshold': 0.62,
        'series_ticker': 'KXMLBGAME',
        'team_mapping': {}  # Will be populated from database
    },
    'nfl': {
        'elo_module': 'nfl_elo_rating',
        'games_module': 'nfl_games',
        'kalshi_function': 'fetch_nfl_markets',
        'elo_threshold': 0.68,
        'series_ticker': 'KXNFLGAME',
        'team_mapping': {}  # Will be populated from database
    },
    'epl': {
        'elo_module': 'epl_elo_rating',
        'games_module': 'epl_games',
        'kalshi_function': 'fetch_epl_markets',
        'elo_threshold': 0.45,  # Threshold for 3-way markets
        'series_ticker': 'KXEPLGAME',
        'team_mapping': {
            'MCI': 'Man City', 'MUN': 'Man United', 'NEW': 'Newcastle', 
            'WHU': 'West Ham', 'AVL': 'Aston Villa', 'BHA': 'Brighton', 
            'WOL': 'Wolves', 'SHU': 'Sheffield United', 'NOT': 'Nott\'m Forest',
            'NFO': 'Nott\'m Forest', 'CRY': 'Crystal Palace', 'TOT': 'Tottenham',
            'SOU': 'Southampton', 'LEI': 'Leicester', 'LEE': 'Leeds'
        }
    }
}


def download_games(sport, **context):
    """Download latest games for a sport."""
    print(f"📥 Downloading {sport.upper()} games...")
    
    # Get date from context
    date_str = context.get('ds', datetime.now().strftime('%Y-%m-%d'))
    
    # Import the appropriate class
    if sport == 'nba':
        from nba_games import NBAGames
        games = NBAGames(date_folder=date_str)
        games.download_games_for_date(date_str)
    elif sport == 'nhl':
        from nhl_game_events import NHLGameEvents
        games = NHLGameEvents(date_folder=date_str)
        games.download_games_for_date(date_str)
    elif sport == 'mlb':
        from mlb_games import MLBGames
        games = MLBGames(date_folder=date_str)
        games.download_games_for_date(date_str)
    elif sport == 'nfl':
        from nfl_games import NFLGames
        games = NFLGames(date_folder=date_str)
        games.download_games_for_date(date_str)
    elif sport == 'epl':
        from epl_games import EPLGames
        games = EPLGames()
        games.download_games()
    
    print(f"✓ {sport.upper()} games downloaded")


def update_elo_ratings(sport, **context):
    """Calculate current Elo ratings for a sport."""
    print(f"📊 Updating {sport.upper()} Elo ratings...")
    
    config = SPORTS_CONFIG[sport]
    
    # Import sport-specific modules
    if sport == 'nba':
        from nba_elo_rating import NBAEloRating, load_nba_games_from_json
        import pandas as pd
        games_df = load_nba_games_from_json()
        elo = NBAEloRating(k_factor=20, home_advantage=100)
        for _, game in games_df.iterrows():
            elo.update(game['home_team'], game['away_team'], game['home_win'])
    elif sport == 'nhl':
        from nhl_elo_rating import NHLEloRating
        import duckdb
        # Use read_only to avoid locking conflicts if other processes are analyzing data
        conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)
        games = conn.execute("""
            SELECT game_date, home_team_abbrev as home_team, away_team_abbrev as away_team,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM games WHERE game_state IN ('OFF', 'FINAL') ORDER BY game_date, game_id
        """).fetchall()
        conn.close()
        
        elo = NHLEloRating(k_factor=10, home_advantage=50)
        
        last_date = None
        for game in games:
            game_date_str = game[0]
            current_date = datetime.strptime(game_date_str, '%Y-%m-%d').date()
            
            if last_date:
                days_diff = (current_date - last_date).days
                if days_diff > 90:  # New season detected
                    print(f"📅 New NHL season detected at {game_date_str} (Last game: {last_date}, Gap: {days_diff} days)")
                    elo.apply_season_reversion(0.35)
            
            last_date = current_date
            elo.update(game[1], game[2], game[3])
    elif sport == 'mlb':
        from mlb_elo_rating import calculate_current_elo_ratings
        elo = calculate_current_elo_ratings(output_path=f'data/{sport}_current_elo_ratings.csv')
        if not elo:
            print(f"⚠️  No MLB games available yet")
            return
    elif sport == 'nfl':
        from nfl_elo_rating import calculate_current_elo_ratings
        elo = calculate_current_elo_ratings(output_path=f'data/{sport}_current_elo_ratings.csv')
        if not elo:
            print(f"⚠️  No NFL games available yet")
            return
    elif sport == 'epl':
        from epl_elo_rating import calculate_current_elo_ratings
        elo = calculate_current_elo_ratings()
        if not elo:
            print(f"⚠️  No EPL games available yet")
            return
    
    # Save ratings to CSV
    if sport in ['nba', 'nhl', 'epl']:
        Path(f'data/{sport}_current_elo_ratings.csv').parent.mkdir(parents=True, exist_ok=True)
        with open(f'data/{sport}_current_elo_ratings.csv', 'w') as f:
            f.write('team,rating\n')
            for team in sorted(elo.ratings.keys()):
                f.write(f'{team},{elo.ratings[team]:.2f}\n')
    
    # Push to XCom
    context['task_instance'].xcom_push(key=f'{sport}_elo_ratings', value=elo.ratings)
    
    print(f"✓ {sport.upper()} Elo ratings updated: {len(elo.ratings)} teams")


def fetch_prediction_markets(sport, **context):
    """Fetch prediction markets for a sport."""
    print(f"💰 Fetching {sport.upper()} prediction markets...")
    
    from kalshi_markets import fetch_nba_markets, fetch_nhl_markets, fetch_mlb_markets, fetch_nfl_markets, fetch_epl_markets
    
    config = SPORTS_CONFIG[sport]
    fetch_function = {
        'nba': fetch_nba_markets,
        'nhl': fetch_nhl_markets,
        'mlb': fetch_mlb_markets,
        'nfl': fetch_nfl_markets,
        'epl': fetch_epl_markets
    }[sport]
    
    date_str = context['ds']
    markets = fetch_function(date_str)
    
    if not markets:
        print(f"ℹ️  No {sport.upper()} markets available")
        return
    
    # Helper for JSON serialization
    def json_serial(obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    # Save to file
    markets_file = Path(f'data/{sport}/markets_{date_str}.json')
    markets_file.parent.mkdir(parents=True, exist_ok=True)
    with open(markets_file, 'w') as f:
        json.dump(markets, f, indent=2, default=json_serial)
    
    # Push to XCom
    context['task_instance'].xcom_push(key=f'{sport}_markets', value=markets)
    
    print(f"✓ Found {len(markets)} {sport.upper()} markets")


def identify_good_bets(sport, **context):
    """Identify good betting opportunities for a sport."""
    print(f"🎯 Identifying {sport.upper()} betting opportunities...")
    
    # Pull data from XCom
    ti = context['task_instance']
    elo_ratings = ti.xcom_pull(key=f'{sport}_elo_ratings', task_ids=f'{sport}_update_elo')
    markets = ti.xcom_pull(key=f'{sport}_markets', task_ids=f'{sport}_fetch_markets')
    
    if not elo_ratings or not markets:
        print(f"⚠️  Missing data for {sport}")
        return
    
    config = SPORTS_CONFIG[sport]
    team_mapping = config['team_mapping']
    elo_threshold = config['elo_threshold']
    
    # Import Elo module to get predict function
    elo_module = __import__(config['elo_module'])
    elo_class = getattr(elo_module, f'{sport.upper()}EloRating')
    elo_system = elo_class()
    elo_system.ratings = elo_ratings
    
    good_bets = []
    
    for market in markets:
        ticker = market.get('ticker', '')
        if '-' not in ticker:
            continue
            
        parts = ticker.split('-')
        
        # EPL LOGIC
        if sport == 'epl':
            title = market.get('title', '')
            if ' vs ' not in title or ' Winner?' not in title:
                continue
                
            teams_str = title.split(' Winner?')[0]
            try:
                home_name, away_name = teams_str.split(' vs ')
            except ValueError:
                continue
                
            # Get predictions (Home, Draw, Away)
            try:
                probs = elo_system.predict_probs(home_name, away_name)
            except KeyError:
                # Try correcting names if needed or skip
                continue
                
            outcome_code = parts[-1]
            
            elo_prob = 0
            bet_on = 'Unknown'
            
            if outcome_code == 'TIE':
                elo_prob = probs[1]
                bet_on = 'Draw'
            else:
                # Determine if Home or Away
                # Check mapping first
                mapped_name = team_mapping.get(outcome_code)
                if mapped_name == home_name:
                    elo_prob = probs[0]
                    bet_on = 'Home'
                elif mapped_name == away_name:
                    elo_prob = probs[2]
                    bet_on = 'Away'
                else:
                    # Fallback to prefix matching
                    if home_name.upper().startswith(outcome_code):
                        elo_prob = probs[0]
                        bet_on = 'Home'
                    elif away_name.upper().startswith(outcome_code):
                        elo_prob = probs[2]
                        bet_on = 'Away'
                    else:
                        continue
            
            # Market Prob
            yes_ask = market.get('yes_ask', 0) / 100.0
            market_prob = yes_ask
            
            edge = elo_prob - market_prob
            
            if elo_prob > elo_threshold and edge > 0.05:
                confidence = "HIGH" if elo_prob > (elo_threshold + 0.1) else "MEDIUM"
                good_bets.append({
                    'home_team': home_name,
                    'away_team': away_name,
                    'elo_prob': elo_prob,
                    'market_prob': market_prob,
                    'edge': edge,
                    'bet_on': bet_on,
                    'confidence': confidence,
                    'yes_ask': market.get('yes_ask'),
                    'no_ask': market.get('no_ask')
                })
                print(f"  ✓ {away_name} @ {home_name}: Bet {bet_on} (Edge: {edge:.1%}, Elo: {elo_prob:.1%})")
            
            continue

        # STANDARD LOGIC (NBA, NHL, MLB, NFL)
        if len(parts) < 3:
            continue
        
        matchup = parts[1]
        team_code = parts[2]
        
        # Extract team codes from matchup (e.g., "26JAN19MIAGSW")
        if len(matchup) < 13:
            continue
        
        away_code = matchup[7:10]
        home_code = matchup[10:13]
        
        # Map to Elo team names
        away_team = team_mapping.get(away_code)
        home_team = team_mapping.get(home_code)
        
        if not away_team or not home_team:
            continue
        
        # Calculate Elo prediction
        try:
            home_win_prob = elo_system.predict(home_team, away_team)
        except:
            continue
        
        # Determine market probability
        yes_ask = market.get('yes_ask', 0) / 100.0
        no_ask = market.get('no_ask', 0) / 100.0
        
        if team_code == home_code:
            market_prob = yes_ask
            elo_prob = home_win_prob
            bet_on = 'home'
        else:
            market_prob = yes_ask
            elo_prob = 1 - home_win_prob
            bet_on = 'away'
        
        # Calculate edge
        edge = elo_prob - market_prob
        
        # Check if this is a good bet
        if elo_prob > elo_threshold and edge > 0.05:
            confidence = "HIGH" if elo_prob > (elo_threshold + 0.1) else "MEDIUM"
            
            good_bets.append({
                'home_team': home_team,
                'away_team': away_team,
                'elo_prob': elo_prob,
                'market_prob': market_prob,
                'edge': edge,
                'bet_on': bet_on,
                'confidence': confidence,
                'yes_ask': market.get('yes_ask'),
                'no_ask': market.get('no_ask')
            })
            
            print(f"  ✓ {away_team} @ {home_team}: Bet {bet_on} (Edge: {edge:.1%}, Elo: {elo_prob:.1%})")
    
    # Save results
    date_str = context['ds']
    bets_file = Path(f'data/{sport}/bets_{date_str}.json')
    bets_file.parent.mkdir(parents=True, exist_ok=True)
    with open(bets_file, 'w') as f:
        json.dump(good_bets, f, indent=2)
    
    print(f"✓ Found {len(good_bets)} {sport.upper()} betting opportunities")
    
    if good_bets:
        print(f"\n{sport.upper()} Betting Opportunities:")
        for bet in good_bets:
            print(f"  {bet['away_team']} @ {bet['home_team']}")
            print(f"    Bet: {bet['bet_on']} | Edge: {bet['edge']:.1%} | Confidence: {bet['confidence']}")


# Create DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'multi_sport_betting_workflow',
    default_args=default_args,
    description='Multi-sport betting opportunities using Elo ratings',
    schedule='0 10 * * *',  # Run daily at 10 AM
    catchup=False,
    tags=['betting', 'elo', 'multi-sport']
)

# Create tasks for each sport
for sport in ['nba', 'nhl', 'mlb', 'nfl']:
    download_task = PythonOperator(
        task_id=f'{sport}_download_games',
        python_callable=download_games,
        op_kwargs={'sport': sport},
        dag=dag
    )
    
    elo_task = PythonOperator(
        task_id=f'{sport}_update_elo',
        python_callable=update_elo_ratings,
        op_kwargs={'sport': sport},
        dag=dag
    )
    
    markets_task = PythonOperator(
        task_id=f'{sport}_fetch_markets',
        python_callable=fetch_prediction_markets,
        op_kwargs={'sport': sport},
        dag=dag
    )
    
    bets_task = PythonOperator(
        task_id=f'{sport}_identify_bets',
        python_callable=identify_good_bets,
        op_kwargs={'sport': sport},
        dag=dag
    )
    
    # Set task dependencies
    download_task >> elo_task >> markets_task >> bets_task
