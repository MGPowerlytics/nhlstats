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


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
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
    except Exception as e:
        print(f"Error downloading NBA data: {e}")
        # Don't raise - may not be games every day
        if "404" not in str(e):
            raise


with DAG(
    'nba_daily_download',
    default_args=default_args,
    description='Download NBA game data daily',
    schedule='@daily',
    start_date=datetime(2021, 10, 1),  # Start of 2021-22 NBA season
    catchup=True,
    max_active_runs=2,  # Limit concurrent runs
    tags=['nba', 'sports', 'data'],
) as dag:
    
    download_games = PythonOperator(
        task_id='download_nba_games',
        python_callable=download_nba_games,
    )
