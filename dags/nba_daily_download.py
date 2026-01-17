"""
Airflow DAG to download NBA game data daily.
NBA season runs October-June.
"""

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from nba_games import NBAGames
from nba_db_loader import load_nba_data_for_date


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'email': ['7244959219@vtext.com'],  # Verizon SMS gateway
    'retries': 3,
    'retry_delay': timedelta(minutes=10),
}


def download_nba_games(**context):
    """Download NBA games for a specific date."""
    logical_date = context['logical_date']
    date_str = logical_date.strftime('%Y-%m-%d')
    
    fetcher = NBAGames(date_folder=date_str)
    
    print(f"Downloading NBA games for {date_str}...")
    
    try:
        game_count = fetcher.download_games_for_date(date_str)
        print(f"Successfully downloaded {game_count} games for {date_str}")
        return game_count
    except Exception as e:
        error_msg = str(e)
        print(f"Error downloading NBA data: {error_msg}")
        # Don't raise for expected errors (no games, rate limits temporarily)
        if "404" in error_msg or "No games" in error_msg:
            print(f"  Data not available for {date_str} - likely no games scheduled")
            return 0
        raise


def load_into_duckdb(date_str, **context):
    """Load downloaded NBA data into DuckDB"""
    print(f"Loading NBA data for {date_str} into DuckDB...")
    
    try:
        games_count = load_nba_data_for_date(date_str)
        print(f"Successfully loaded {games_count} games into DuckDB")
    except Exception as e:
        print(f"Error loading data into DuckDB: {e}")
        raise


with DAG(
    'nba_daily_download',
    default_args=default_args,
    description='Download NBA game data daily and load into DuckDB',
    schedule='@daily',
    start_date=datetime(2021, 10, 1),  # Start of 2021-22 NBA season
    catchup=True,
    max_active_runs=10,  # Increased for faster backfill
    tags=['nba', 'sports', 'data'],
) as dag:
    
    download_games = PythonOperator(
        task_id='download_nba_games',
        python_callable=download_nba_games,
    )
    
    load_db = PythonOperator(
        task_id='load_into_duckdb',
        python_callable=load_into_duckdb,
        op_kwargs={
            'date_str': '{{ logical_date.strftime("%Y-%m-%d") }}'
        },
        pool='duckdb_nba_writer',  # Serialize database writes
    )
    
    # Define dependencies
    download_games >> load_db
