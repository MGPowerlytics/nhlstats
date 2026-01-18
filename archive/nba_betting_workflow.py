"""NBA Betting Workflow DAG"""
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from nba_games import NBAGames
from nba_elo_rating import NBAEloRating, load_nba_games_from_json
import pandas as pd

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

def download_nba_games(date_str, **context):
    print(f"📥 Downloading NBA games for {date_str}...")
    try:
        nba = NBAGames()
        games = nba.fetch_scoreboard(date_str)
        if games:
            date_path = Path(f'data/nba/scoreboard_{date_str}.json')
            date_path.parent.mkdir(parents=True, exist_ok=True)
            with open(date_path, 'w') as f:
                json.dump(games, f, indent=2)
            print(f"✅ Downloaded {len(games)} games")
    except Exception as e:
        print(f"⚠️  Error: {e}")

def update_elo_ratings(**context):
    print("📊 Updating Elo...")
    games_df = load_nba_games_from_json()
    elo = NBAEloRating(k_factor=20, home_advantage=100)
    for _, game in games_df.iterrows():
        elo.update(game['home_team'], game['away_team'], game['home_win'])
    ratings_df = pd.DataFrame([{'team': t, 'elo_rating': r} for t, r in elo.ratings.items()])
    ratings_df.to_csv('data/nba_current_elo_ratings.csv', index=False)
    print(f"✅ Updated {len(elo.ratings)} teams")
    context['task_instance'].xcom_push(key='elo_ratings', value=elo.ratings)
    context['task_instance'].xcom_push(key='elo_system', value={'k_factor': 20, 'home_advantage': 100})

def fetch_prediction_markets(date_str, **context):
    print(f"💰 Fetching markets...")
    try:
        from kalshi_markets import fetch_nba_markets
        markets = fetch_nba_markets(date_str)
        if markets:
            serializable = []
            for m in markets:
                s = {}
                for k, v in m.items():
                    s[k] = v.isoformat() if hasattr(v, 'isoformat') else v
                serializable.append(s)
            Path(f'data/nba/markets_{date_str}.json').parent.mkdir(parents=True, exist_ok=True)
            with open(f'data/nba/markets_{date_str}.json', 'w') as f:
                json.dump(serializable, f, indent=2)
            print(f"✅ Fetched {len(markets)} markets")
            context['task_instance'].xcom_push(key='markets', value=serializable)
        else:
            context['task_instance'].xcom_push(key='markets', value=[])
    except Exception as e:
        print(f"⚠️  Error: {e}")
        context['task_instance'].xcom_push(key='markets', value=[])

def identify_good_bets(**context):
    print("🎯 Identifying bets...")
    elo_ratings = context['task_instance'].xcom_pull(task_ids='update_elo_ratings', key='elo_ratings')
    elo_params = context['task_instance'].xcom_pull(task_ids='update_elo_ratings', key='elo_system')
    markets = context['task_instance'].xcom_pull(task_ids='fetch_prediction_markets', key='markets')
    
    if not elo_ratings or not markets:
        print("⚠️  No data")
        return 0
    
    KALSHI_TO_ELO = {'MIA':'Heat','GSW':'Warriors','IND':'Pacers','PHI':'76ers','BOS':'Celtics','DET':'Pistons','PHX':'Suns','BKN':'Nets','LAC':'Clippers','WAS':'Wizards','OKC':'Thunder','CLE':'Cavaliers','ORL':'Magic','MEM':'Grizzlies','NOP':'Pelicans','HOU':'Rockets','UTA':'Jazz','SAS':'Spurs','TOR':'Raptors','LAL':'Lakers','CHA':'Hornets','DEN':'Nuggets','MIL':'Bucks','ATL':'Hawks','NYK':'Knicks','CHI':'Bulls','MIN':'Timberwolves','DAL':'Mavericks','SAC':'Kings','POR':'Trail Blazers'}
    
    elo = NBAEloRating(k_factor=elo_params['k_factor'], home_advantage=elo_params['home_advantage'])
    elo.ratings = elo_ratings
    good_bets, seen = [], set()
    
    for market in markets:
        ticker = market.get('ticker', '')
        parts = ticker.split('-')
        if len(parts) < 3 or len(parts[1]) < 13:
            continue
        teams_str = parts[1][7:]
        if len(teams_str) != 6:
            continue
        away_code, home_code, team_code = teams_str[:3], teams_str[3:], parts[-1]
        home_team, away_team = KALSHI_TO_ELO.get(home_code), KALSHI_TO_ELO.get(away_code)
        if not home_team or not away_team or f"{away_team}@{home_team}" in seen:
            continue
        seen.add(f"{away_team}@{home_team}")
        yes_ask = market.get('yes_ask', 0) / 100
        market_home_prob = yes_ask if team_code == home_code else (1 - yes_ask if team_code == away_code else None)
        if market_home_prob is None:
            continue
        elo_home_prob = elo.predict(home_team, away_team)
        edge = elo_home_prob - market_home_prob
        if elo_home_prob > 0.64 and edge > 0.05:
            good_bets.append({'home_team': home_team, 'away_team': away_team, 'elo_prob': elo_home_prob, 'market_prob': market_home_prob, 'edge': edge, 'bet_on': 'home' if elo_home_prob > 0.5 else 'away', 'confidence': 'HIGH' if elo_home_prob > 0.86 else 'MEDIUM', 'yes_ask': market.get('yes_ask'), 'no_ask': market.get('no_ask')})
    
    good_bets.sort(key=lambda x: x['edge'], reverse=True)
    date_str = context.get('logical_date', datetime.now()).strftime('%Y-%m-%d')
    print("\n" + "="*80)
    print(f"🎲 NBA BETTING RECOMMENDATIONS for {date_str}")
    print("="*80)
    if good_bets:
        print(f"\n✅ Found {len(good_bets)} opportunities:\n")
        for i, bet in enumerate(good_bets, 1):
            print(f"{i}. {bet['away_team']} @ {bet['home_team']}")
            print(f"   Elo: {bet['elo_prob']*100:.1f}% | Market: {bet['market_prob']*100:.1f}% | Edge: +{bet['edge']*100:.1f}%")
            print(f"   Bet: {bet['bet_on'].upper()} | YES ${bet['yes_ask']/100:.2f} NO ${bet['no_ask']/100:.2f}\n")
    else:
        print("ℹ️  No opportunities")
    print("="*80 + "\n")
    
    Path(f'data/nba/bets_{date_str}.json').parent.mkdir(parents=True, exist_ok=True)
    with open(f'data/nba/bets_{date_str}.json', 'w') as f:
        json.dump(good_bets, f, indent=2)
    context['task_instance'].xcom_push(key='good_bets', value=good_bets)
    return len(good_bets)

with DAG('nba_betting_workflow', default_args=default_args, schedule='0 10 * * *', start_date=datetime(2026, 1, 18), catchup=False, tags=['nba', 'betting']) as dag:
    download = PythonOperator(task_id='download_games', python_callable=download_nba_games, op_kwargs={'date_str': '{{ (logical_date - macros.timedelta(days=1)).strftime("%Y-%m-%d") }}'})
    update = PythonOperator(task_id='update_elo_ratings', python_callable=update_elo_ratings)
    fetch = PythonOperator(task_id='fetch_prediction_markets', python_callable=fetch_prediction_markets, op_kwargs={'date_str': '{{ logical_date.strftime("%Y-%m-%d") }}'})
    identify = PythonOperator(task_id='identify_good_bets', python_callable=identify_good_bets)
    download >> update >> fetch >> identify
