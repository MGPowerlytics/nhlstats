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
    },
    'tennis': {
        'elo_module': 'tennis_elo_rating',
        'games_module': 'tennis_games',
        'kalshi_function': 'fetch_tennis_markets',
        'elo_threshold': 0.60,
        'series_ticker': 'TENNIS', # Placeholder
        'team_mapping': {}
    },
    'ncaab': {
        'elo_module': 'ncaab_elo_rating',
        'games_module': 'ncaab_games',
        'kalshi_function': 'fetch_ncaab_markets',
        'elo_threshold': 0.65,
        'series_ticker': 'KXNCAAMBGAME',
        'team_mapping': {}
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
    elif sport == 'tennis':
        from tennis_games import TennisGames
        games = TennisGames()
        games.download_games()
    elif sport == 'ncaab':
        from ncaab_games import NCAABGames
        games = NCAABGames()
        games.download_games()
    
    print(f"✓ {sport.upper()} games downloaded")


def load_data_to_db(sport, **context):
    """Load downloaded games into DuckDB."""
    print(f"💾 Loading {sport.upper()} games into database...")
    
    date_str = context.get('ds', datetime.now().strftime('%Y-%m-%d'))
    from db_loader import NHLDatabaseLoader
    
    with NHLDatabaseLoader() as loader:
        count = loader.load_date(date_str)
        
    print(f"✓ Loaded {count} new games/updates for {date_str}")


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
            game_date = game[0]
            # Handle both string and date objects from DuckDB
            if isinstance(game_date, str):
                current_date = datetime.strptime(game_date, '%Y-%m-%d').date()
            else:
                current_date = game_date
            
            if last_date:
                days_diff = (current_date - last_date).days
                if days_diff > 90:  # New season detected
                    print(f"📅 New NHL season detected at {current_date} (Last game: {last_date}, Gap: {days_diff} days)")
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
    elif sport == 'ncaab':
        from ncaab_elo_rating import NCAABEloRating
        from ncaab_games import NCAABGames
        
        elo = NCAABEloRating(k_factor=20, home_advantage=100)
        games_obj = NCAABGames()
        # Ensure data exists essentially
        df = games_obj.load_games()
        
        if df.empty:
            print("⚠️ No NCAAB games loaded")
            return
            
        df = df.sort_values('date')
        for _, game in df.iterrows():
            home_won = 1.0 if game['home_score'] > game['away_score'] else 0.0
            # load_games returns neutral flag
            elo.update(game['home_team'], game['away_team'], home_won, is_neutral=game['neutral'])
            
    elif sport == 'tennis':
        # Tennis is unique, we compute globally usually
        # But for DAG, let's just create a dummy object or compute current
        # For now, let's calculate from scratch from DB
        import duckdb
        from tennis_elo_rating import TennisEloRating
        
        conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)
        games = conn.execute("SELECT winner, loser FROM tennis_games ORDER BY game_date").fetchall()
        conn.close()
        
        elo = TennisEloRating()
        for w, l in games:
            elo.update(w, l)
            
    # Save ratings to CSV
    if sport in ['nba', 'nhl', 'epl', 'tennis']:
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
    
    from kalshi_markets import fetch_nba_markets, fetch_nhl_markets, fetch_mlb_markets, fetch_nfl_markets, fetch_epl_markets, fetch_tennis_markets, fetch_ncaab_markets
    
    config = SPORTS_CONFIG[sport]
    fetch_function = {
        'nba': fetch_nba_markets,
        'nhl': fetch_nhl_markets,
        'mlb': fetch_mlb_markets,
        'nfl': fetch_nfl_markets,
        'epl': fetch_epl_markets,
        'tennis': fetch_tennis_markets,
        'ncaab': fetch_ncaab_markets
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


def update_glicko2_ratings(sport, **context):
    """Calculate current Glicko-2 ratings for a sport."""
    print(f"📊 Updating {sport.upper()} Glicko-2 ratings...")
    
    from glicko2_rating import (NBAGlicko2Rating, NHLGlicko2Rating, 
                                 MLBGlicko2Rating, NFLGlicko2Rating)
    
    # Create sport-specific Glicko-2 instance
    glicko_classes = {
        'nba': NBAGlicko2Rating,
        'nhl': NHLGlicko2Rating,
        'mlb': MLBGlicko2Rating,
        'nfl': NFLGlicko2Rating
    }
    
    if sport not in glicko_classes:
        print(f"⚠️  Glicko-2 not implemented for {sport}")
        return
    
    glicko = glicko_classes[sport]()
    
    # Load and process games (similar to Elo)
    if sport == 'nba':
        from nba_elo_rating import load_nba_games_from_json
        import pandas as pd
        games_df = load_nba_games_from_json()
        for _, game in games_df.iterrows():
            glicko.update(game['home_team'], game['away_team'], game['home_win'])
    elif sport == 'nhl':
        import duckdb
        conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)
        games = conn.execute("""
            SELECT game_date, home_team_abbrev as home_team, away_team_abbrev as away_team,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM games WHERE game_state IN ('OFF', 'FINAL') ORDER BY game_date, game_id
        """).fetchall()
        conn.close()
        
        for game in games:
            glicko.update(game[1], game[2], game[3])
    elif sport in ['mlb', 'nfl']:
        # Load from database
        import duckdb
        conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)
        table_name = f'{sport}_games'
        games = conn.execute(f"""
            SELECT game_date, home_team, away_team,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM {table_name} WHERE game_date IS NOT NULL
            ORDER BY game_date
        """).fetchall()
        conn.close()
        
        for game in games:
            glicko.update(game[1], game[2], game[3])
    
    # Save ratings to CSV
    Path(f'data/{sport}_current_glicko2_ratings.csv').parent.mkdir(parents=True, exist_ok=True)
    with open(f'data/{sport}_current_glicko2_ratings.csv', 'w') as f:
        f.write('team,rating,rd,volatility\n')
        for team in sorted(glicko.ratings.keys()):
            r = glicko.ratings[team]
            f.write(f'{team},{r["rating"]:.2f},{r["rd"]:.2f},{r["vol"]:.6f}\n')
    
    # Push to XCom
    context['task_instance'].xcom_push(key=f'{sport}_glicko2_ratings', value=glicko.ratings)
    
    print(f"✓ {sport.upper()} Glicko-2 ratings updated: {len(glicko.ratings)} teams")


def load_bets_to_db(sport, **context):
    """Load bet recommendations into database."""
    print(f"💾 Loading {sport.upper()} bets into database...")
    
    from bet_loader import BetLoader
    
    date_str = context['ds']
    loader = BetLoader()
    count = loader.load_bets_for_date(sport, date_str)
    
    print(f"✓ Loaded {count} {sport.upper()} bets into database")


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
        
        # NCAAB LOGIC
        if sport == 'ncaab':
            title = market.get('title', '')
            if ' at ' not in title:
                continue
                
            # Parse "TeamA at TeamB Winner?" or just "TeamA at TeamB"
            teams_part = title.split(' Winner?')[0] if ' Winner?' in title else title
            try:
                away_raw, home_raw = teams_part.split(' at ')
            except ValueError:
                continue
            
            # Find closest match in Elo ratings
            # Simple normalization helper
            def normalize(s):
                return s.replace('St', 'State').replace('Univ', '').replace('.', '').strip()

            params = [away_raw, home_raw]
            matched_teams = []
            
            for p in params:
                 # 1. Exact match
                 if p in elo_ratings:
                     matched_teams.append(p)
                     continue
                 
                 # 2. Normalized match
                 norm_p = normalize(p)
                 found = None
                 for k in elo_ratings.keys():
                     if normalize(k) == norm_p:
                         found = k
                         break
                 if found:
                     matched_teams.append(found)
                     continue
                 
                 # 3. Substring match (dangerous but useful for UMass -> Massachusetts?)
                 # Massachusetts contains Mass? No.
                 # UMass -> Massachusetts.
                 # Let's skip obscure ones and focus on clean matches
                 matched_teams.append(None)
            
            if None in matched_teams:
                continue
                
            away_team, home_team = matched_teams
            
            # Predict
            try:
                prob = elo_system.predict(home_team, away_team)
            except:
                continue
                
            # Market Prob
            yes_ask = market.get('yes_ask', 0) / 100.0
            
            # Identify which side is Yes
            # Ticker: KXNCAAMBGAME-DATE-AWAY-HOME-WINNER
            # If ticker ends with HOME, Yes = Home Win.
            # But ticker uses abbreviations!
            # We can't easily rely on ticker to know who is who if mappings are unknown.
            # But the Title says "Toledo at UMass Winner?" (Yes/No).
            # Usually "Yes" means the named event happens?
            # Wait, Kalshi structure for "Winner?" markets:
            # Title: "Toledo at UMass Winner?"
            # Subtitle: "Toledo" (Option Yes?) No, unrelated.
            
            # Actually, "Winner?" markets are often:
            # Title: "Toledo at UMass Winner?"
            # This is ambiguous. Does Yes mean Home wins? Or simple match winner?
            
            # Let's check verify_ncaab_series.py output again
            # Ticker: KXNCAAMBGAME-26JAN20TOLMASS-TOL
            # Title: Toledo at UMass Winner?
            # The last part of ticker is TOL.
            # This implies the market is "Will TOL win?"
            
            # So if ticker ends with TOL, and Away is Toledo, then YES = Away Win.
            # We need to extract the target from ticker.
            
            target_abbr = parts[-1]
            
            # Need to match target_abbr to away_team or home_team.
            # We don't have abbreviations in elo_ratings keys (full names).
            # But we have `away_raw` ("Toledo") and `home_raw` ("UMass").
            # TOL matches Toledo? Yes (Startswith).
            # MASS matches UMass? Yes (Contains/Ending).
            
            target_side = 'Unknown'
            if away_raw.upper().startswith(target_abbr) or target_abbr in away_raw.upper():
                target_side = 'away'
            elif home_raw.upper().startswith(target_abbr) or target_abbr in home_raw.upper():
                target_side = 'home'
            else:
                 continue
                 
            market_prob = yes_ask
            elo_prob = prob if target_side == 'home' else (1.0 - prob)
            
            edge = elo_prob - market_prob
            if elo_prob > elo_threshold and edge > 0.05:
                confidence = "HIGH" if elo_prob > (elo_threshold + 0.1) else "MEDIUM"
                good_bets.append({
                    'home_team': home_team,
                    'away_team': away_team,
                    'elo_prob': elo_prob,
                    'market_prob': market_prob,
                    'edge': edge,
                    'bet_on': target_side,
                    'confidence': confidence,
                    'ticker': ticker
                })
            
            continue # Skip standard logic
        
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
            
        # TENNIS LOGIC (Placeholder)
        if sport == 'tennis':
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


            print(f"  {bet['away_team']} @ {bet['home_team']}")
            print(f"    Bet: {bet['bet_on']} | Edge: {bet['edge']:.1%} | Confidence: {bet['confidence']}")


def place_bets_on_recommendations(sport, **context):
    """
    Place bets on recommended games (NBA and NCAAB only).
    
    CRITICAL: Verifies games have not started using The Odds API.
    
    Args:
        sport: Sport name (nba, ncaab)
        **context: Airflow context with bet recommendations
    """
    # Only bet on basketball
    if sport not in ['nba', 'ncaab']:
        print(f"⚠️  Skipping {sport.upper()} - only betting on NBA/NCAAB")
        return
    
    print(f"\n{'='*80}")
    print(f"🎰 PLACING BETS FOR {sport.upper()}")
    print(f"{'='*80}\n")
    
    # Load bet recommendations from file
    bet_file = f'data/{sport}/bets_{context["ds"]}.json'
    
    if not Path(bet_file).exists():
        print(f"⚠️  No bet file found: {bet_file}")
        return
    
    with open(bet_file, 'r') as f:
        recommendations = json.load(f)
    
    if not recommendations:
        print(f"ℹ️  No recommendations for {sport.upper()}")
        return
    
    print(f"📊 Found {len(recommendations)} recommendations")
    
    # Load Kalshi credentials
    kalshkey_file = Path('/mnt/data2/nhlstats/kalshkey')
    if not kalshkey_file.exists():
        print("❌ Kalshi credentials not found")
        return
    
    # Parse API key ID from kalshkey
    with open(kalshkey_file, 'r') as f:
        first_line = f.readline().strip()
        if 'API key id:' in first_line:
            api_key_id = first_line.split('API key id:')[1].strip()
        else:
            print("❌ Invalid Kalshi credentials format")
            return
    
    # Load Odds API key for game start verification
    odds_api_key = None
    odds_key_file = Path('/mnt/data2/nhlstats/odds_api_key')
    if odds_key_file.exists():
        with open(odds_key_file, 'r') as f:
            odds_api_key = f.read().strip()
        print(f"✅ Loaded Odds API key for game verification")
    else:
        print(f"⚠️  No Odds API key - cannot verify game start times!")
    
    # Initialize betting client
    from kalshi_betting import KalshiBetting
    
    try:
        client = KalshiBetting(
            api_key_id=api_key_id,
            private_key_path='/mnt/data2/nhlstats/kalshi_private_key.pem',
            max_bet_size=5.0,
            production=True,
            odds_api_key=odds_api_key
        )
        
        # Add sport to recommendations
        for rec in recommendations:
            rec['sport'] = sport.upper()
        
        # Process recommendations
        result = client.process_bet_recommendations(
            recommendations=recommendations,
            sport_filter=[sport.upper()],
            min_confidence=0.75,  # Only bet on >75% confidence
            min_edge=0.05,  # Minimum 5% edge
            dry_run=False  # Set to True for testing
        )
        
        # Save betting results
        result_file = f'data/{sport}/betting_results_{context["ds"]}.json'
        with open(result_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        
        print(f"\n💾 Results saved to {result_file}")
        print(f"✅ Placed: {len(result['placed'])}")
        print(f"⏭️  Skipped: {len(result['skipped'])}")
        print(f"❌ Errors: {len(result['errors'])}")
        
        # Push to XCom
        context['task_instance'].xcom_push(key=f'{sport}_bets_placed', value=len(result['placed']))
        
    except Exception as e:
        print(f"❌ Betting failed: {e}")
        import traceback
        traceback.print_exc()
        print("\n⚠️  Continuing with workflow (bets not placed)")


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
for sport in ['nba', 'nhl', 'mlb', 'nfl', 'epl', 'tennis', 'ncaab']:
    download_task = PythonOperator(
        task_id=f'{sport}_download_games',
        python_callable=download_games,
        op_kwargs={'sport': sport},
        dag=dag
    )
    
    load_task = PythonOperator(
        task_id=f'{sport}_load_db',
        python_callable=load_data_to_db,
        op_kwargs={'sport': sport},
        dag=dag,
        pool='duckdb_pool'
    )
    
    elo_task = PythonOperator(
        task_id=f'{sport}_update_elo',
        python_callable=update_elo_ratings,
        op_kwargs={'sport': sport},
        dag=dag,
        pool='duckdb_pool'
    )
    
    # Add Glicko-2 task for supported sports
    if sport in ['nba', 'nhl', 'mlb', 'nfl']:
        glicko2_task = PythonOperator(
            task_id=f'{sport}_update_glicko2',
            python_callable=update_glicko2_ratings,
            op_kwargs={'sport': sport},
            dag=dag,
            pool='duckdb_pool'
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
    
    load_bets_task = PythonOperator(
        task_id=f'{sport}_load_bets_db',
        python_callable=load_bets_to_db,
        op_kwargs={'sport': sport},
        dag=dag,
        pool='duckdb_pool'
    )
    
    # Place bets task (only for NBA and NCAAB)
    if sport in ['nba', 'ncaab']:
        place_bets_task = PythonOperator(
            task_id=f'{sport}_place_bets',
            python_callable=place_bets_on_recommendations,
            op_kwargs={'sport': sport},
            dag=dag,
            pool='duckdb_pool'
        )
    
    # Set task dependencies
    if sport in ['nba', 'nhl', 'mlb', 'nfl']:
        # With Glicko-2
        download_task >> load_task >> [elo_task, glicko2_task] >> markets_task >> bets_task
        if sport in ['nba', 'ncaab']:
            # Place bets, then load to DB
            bets_task >> place_bets_task >> load_bets_task
        else:
            bets_task >> load_bets_task
    else:
        # Without Glicko-2
        download_task >> load_task >> elo_task >> markets_task >> bets_task
        if sport in ['ncaab']:
            bets_task >> place_bets_task >> load_bets_task
        else:
            bets_task >> load_bets_task
