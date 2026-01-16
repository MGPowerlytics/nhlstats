"""
Airflow DAG to download NHL game data daily at 7am.
Downloads games from the previous day.
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path to import NHL modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from nhl_game_events import NHLGameEvents
from nhl_shifts import NHLShifts


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}


def get_games_for_date(date_str, **context):
    """Get list of game IDs for a specific date."""
    fetcher = NHLGameEvents()
    
    # Determine current season
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    year = date_obj.year
    
    # NHL season runs Oct-Apr, so if month < 7, season started previous year
    if date_obj.month < 7:
        season_start = year - 1
    else:
        season_start = year
    
    season = f"{season_start}{season_start + 1}"
    
    # Get schedule for the season
    schedule = fetcher.get_season_schedule(season)
    
    # Find games matching the date
    game_ids = []
    for week in schedule.get('gameWeek', []):
        for game in week.get('games', []):
            game_date = game.get('gameDate', '')[:10]  # Extract YYYY-MM-DD
            if game_date == date_str:
                game_ids.append(game.get('id'))
    
    print(f"Found {len(game_ids)} games for {date_str}: {game_ids}")
    
    # Push game IDs to XCom for downstream tasks
    context['task_instance'].xcom_push(key='game_ids', value=game_ids)
    return game_ids


def download_game_events(**context):
    """Download play-by-play and boxscore data for all games."""
    game_ids = context['task_instance'].xcom_pull(
        task_ids='get_games_for_date', 
        key='game_ids'
    )
    
    if not game_ids:
        print("No games to download")
        return
    
    fetcher = NHLGameEvents()
    
    for i, game_id in enumerate(game_ids, 1):
        try:
            print(f"[{i}/{len(game_ids)}] Downloading game {game_id}")
            fetcher.download_game(game_id, include_boxscore=True)
        except Exception as e:
            print(f"Error downloading game {game_id}: {e}")
            raise


def download_game_shifts(**context):
    """Download shift data for all games."""
    game_ids = context['task_instance'].xcom_pull(
        task_ids='get_games_for_date', 
        key='game_ids'
    )
    
    if not game_ids:
        print("No shifts to download")
        return
    
    fetcher = NHLShifts()
    
    for i, game_id in enumerate(game_ids, 1):
        try:
            print(f"[{i}/{len(game_ids)}] Downloading shifts for game {game_id}")
            fetcher.download_game_shifts(game_id, format='json')
            fetcher.download_game_shifts(game_id, format='csv')
        except Exception as e:
            print(f"Error downloading shifts for game {game_id}: {e}")
            # Don't raise - shifts might not be available yet


with DAG(
    'nhl_daily_download',
    default_args=default_args,
    description='Download NHL game data daily at 7am',
    schedule_interval='0 7 * * *',  # Run at 7am daily
    start_date=datetime(2024, 10, 1),
    catchup=False,
    tags=['nhl', 'sports', 'data'],
) as dag:
    
    # Task 1: Get list of games from previous day
    get_games = PythonOperator(
        task_id='get_games_for_date',
        python_callable=get_games_for_date,
        op_kwargs={
            'date_str': '{{ (execution_date - macros.timedelta(days=1)).strftime("%Y-%m-%d") }}'
        },
    )
    
    # Task 2: Download game events (play-by-play and boxscore)
    download_events = PythonOperator(
        task_id='download_game_events',
        python_callable=download_game_events,
    )
    
    # Task 3: Download shift data
    download_shifts = PythonOperator(
        task_id='download_game_shifts',
        python_callable=download_game_shifts,
    )
    
    # Define task dependencies
    get_games >> download_events >> download_shifts
