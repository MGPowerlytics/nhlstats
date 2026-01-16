"""
Airflow DAG to download NHL game data daily at 7am.
Downloads games from the previous day and loads them into DuckDB.
"""

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path to import NHL modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from nhl_game_events import NHLGameEvents
from nhl_shifts import NHLShifts
from nhl_db_loader import load_nhl_data_for_date


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
    print(f"Getting NHL games for {date_str}")
    
    # Get schedule for the specific date
    fetcher = NHLGameEvents()
    schedule = fetcher.get_schedule_by_date(date_str)
    
    # Find games matching the date
    game_ids = []
    for week in schedule.get('gameWeek', []):
        for game in week.get('games', []):
            game_id = game.get('id')
            if game_id:
                game_ids.append(game_id)
    
    print(f"Found {len(game_ids)} games for {date_str}: {game_ids}")
    
    # Push game IDs and date to XCom for downstream tasks
    context['task_instance'].xcom_push(key='game_ids', value=game_ids)
    context['task_instance'].xcom_push(key='date_str', value=date_str)
    return game_ids


def download_game_events(**context):
    """Download play-by-play and boxscore data for all games."""
    import time
    
    game_ids = context['task_instance'].xcom_pull(
        task_ids='get_games_for_date', 
        key='game_ids'
    )
    date_str = context['task_instance'].xcom_pull(
        task_ids='get_games_for_date',
        key='date_str'
    )
    
    if not game_ids:
        print("No games to download")
        return
    
    # Create fetcher with date folder
    fetcher = NHLGameEvents(date_folder=date_str)
    
    for i, game_id in enumerate(game_ids, 1):
        try:
            print(f"[{i}/{len(game_ids)}] Downloading game {game_id}")
            fetcher.download_game(game_id, include_boxscore=True)
            # Rate limiting between games
            if i < len(game_ids):
                time.sleep(2)
        except Exception as e:
            print(f"Error downloading game {game_id}: {e}")
            raise


def download_game_shifts(**context):
    """Download shift data for all games."""
    import time
    
    game_ids = context['task_instance'].xcom_pull(
        task_ids='get_games_for_date', 
        key='game_ids'
    )
    date_str = context['task_instance'].xcom_pull(
        task_ids='get_games_for_date',
        key='date_str'
    )
    
    if not game_ids:
        print("No shifts to download")
        return
    
    # Create fetcher with date folder
    fetcher = NHLShifts(date_folder=date_str)
    
    for i, game_id in enumerate(game_ids, 1):
        try:
            print(f"[{i}/{len(game_ids)}] Downloading shifts for game {game_id}")
            fetcher.download_game_shifts(game_id, format='json')
            fetcher.download_game_shifts(game_id, format='csv')
            # Longer delay for shifts API (more aggressive rate limiting)
            if i < len(game_ids):
                time.sleep(3)
        except Exception as e:
            print(f"Error downloading shifts for game {game_id}: {e}")
            # Don't raise - shifts might not be available yet


def load_into_duckdb(date_str, **context):
    """Load downloaded NHL data into DuckDB"""
    print(f"Loading NHL data for {date_str} into DuckDB...")
    
    try:
        games_count = load_nhl_data_for_date(date_str)
        print(f"Successfully loaded {games_count} games into DuckDB")
    except Exception as e:
        print(f"Error loading data into DuckDB: {e}")
        raise


with DAG(
    'nhl_daily_download',
    default_args=default_args,
    description='Download NHL game data daily',
    schedule='@daily',  # Run daily at midnight
    start_date=datetime(2021, 10, 1),  # Start of 2021-2022 season
    catchup=True,  # Enable backfill to get historical data
    max_active_runs=2,  # Reduced to avoid API rate limits
    tags=['nhl', 'sports', 'data'],
) as dag:
    
    # Task 1: Get list of games from logical date
    get_games = PythonOperator(
        task_id='get_games_for_date',
        python_callable=get_games_for_date,
        op_kwargs={
            'date_str': '{{ logical_date.strftime("%Y-%m-%d") }}'
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
    
    # Task 4: Load data into DuckDB
    load_db = PythonOperator(
        task_id='load_into_duckdb',
        python_callable=load_into_duckdb,
        op_kwargs={
            'date_str': '{{ logical_date.strftime("%Y-%m-%d") }}'
        },
        pool='duckdb_writer',  # Serialize database writes
    )
    
    # Define task dependencies
    get_games >> download_events >> download_shifts >> load_db
    get_games >> download_events >> download_shifts
