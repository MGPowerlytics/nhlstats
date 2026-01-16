"""
Airflow DAG to download Hong Kong horse racing results daily at 7am.
Downloads race results from previous day for both Happy Valley and Sha Tin.
"""

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from hk_racing_scraper import HKJCRacingScraper


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=10),
}


def scrape_previous_day_races(**context):
    """Scrape race results from previous day."""
    logical_date = context['logical_date']
    previous_day = (logical_date - timedelta(days=1)).date()
    
    print(f"Scraping HK racing results for {previous_day}")
    
    scraper = HKJCRacingScraper()
    
    # Try both venues (Happy Valley and Sha Tin)
    # HKJC typically races on Wed (HV) and Sat/Sun (ST), but we check both
    day_data = scraper.download_race_day(previous_day, venues=['HV', 'ST'])
    
    if day_data['meetings']:
        total_races = sum(len(m['races']) for m in day_data['meetings'])
        print(f"Successfully scraped {total_races} races from {len(day_data['meetings'])} meeting(s)")
        
        # Push summary to XCom
        context['task_instance'].xcom_push(key='races_count', value=total_races)
        context['task_instance'].xcom_push(key='meetings_count', value=len(day_data['meetings']))
    else:
        print(f"No races found for {previous_day} (likely not a race day)")
        context['task_instance'].xcom_push(key='races_count', value=0)


with DAG(
    'hk_racing_daily_download',
    default_args=default_args,
    description='Download HK horse racing results daily at 7am',
    schedule='0 7 * * *',  # Run at 7am daily
    start_date=datetime(2024, 10, 1),
    catchup=False,
    tags=['hk_racing', 'sports', 'data'],
) as dag:
    
    scrape_races = PythonOperator(
        task_id='scrape_previous_day_races',
        python_callable=scrape_previous_day_races,
    )
