"""
Airflow DAG to download MLB game data daily.
MLB season runs April-October.
"""

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mlb_games import MLBGames


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'email': ['7244959219@vtext.com'],  # Verizon SMS gateway
    'retries': 3,
    'retry_delay': timedelta(minutes=10),
}


def download_mlb_games(**context):
    """Download MLB games for a specific date."""
    logical_date = context['logical_date']
    date_str = logical_date.strftime('%Y-%m-%d')
    
    fetcher = MLBGames(date_folder=date_str)
    
    print(f"Downloading MLB games for {date_str}...")
    
    try:
        game_count = fetcher.download_games_for_date(date_str)
        print(f"Successfully downloaded {game_count} games for {date_str}")
    except Exception as e:
        print(f"Error downloading MLB data: {e}")
        # Don't raise - may not be games every day
        if "404" not in str(e):
            raise


with DAG(
    'mlb_daily_download',
    default_args=default_args,
    description='Download MLB game data daily',
    schedule='@daily',
    start_date=datetime(2021, 4, 1),  # Start of 2021 MLB season
    catchup=True,
    max_active_runs=2,  # Limit concurrent runs
    tags=['mlb', 'sports', 'data'],
) as dag:
    
    download_games = PythonOperator(
        task_id='download_mlb_games',
        python_callable=download_mlb_games,
    )
