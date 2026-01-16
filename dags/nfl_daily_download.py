"""
Airflow DAG to download NFL game data daily.
NFL season runs September-February.
"""

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path to import NFL modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from nfl_games import NFLGames


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
}


def download_nfl_games(**context):
    """Download NFL games for a specific date."""
    logical_date = context['logical_date']
    date_str = logical_date.strftime('%Y-%m-%d')
    
    fetcher = NFLGames(date_folder=date_str)
    
    print(f"Downloading NFL games for {date_str}...")
    
    try:
        game_count = fetcher.download_games_for_date(date_str)
        print(f"Successfully downloaded {game_count} games for {date_str}")
    except Exception as e:
        error_msg = str(e)
        print(f"Error downloading NFL data: {error_msg}")
        # Don't raise for expected errors: 404 (no data), games not yet played
        if "404" in error_msg or "Not Found" in error_msg:
            print(f"  Data not available for {date_str} - likely no games or future date")
            return
        # For other errors, log and raise
        raise


with DAG(
    'nfl_daily_download',
    default_args=default_args,
    description='Download NFL game data daily',
    schedule='@daily',
    start_date=datetime(2021, 9, 1),  # Start of 2021 NFL season
    catchup=True,
    max_active_runs=2,  # Limit concurrent runs to avoid rate limits
    tags=['nfl', 'sports', 'data'],
) as dag:
    
    download_games = PythonOperator(
        task_id='download_nfl_games',
        python_callable=download_nfl_games,
    )

