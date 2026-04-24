import os
from dags.multi_sport_betting_workflow import update_elo_ratings

os.environ['POSTGRES_HOST'] = 'localhost'
os.environ['POSTGRES_USER'] = 'airflow'
os.environ['POSTGRES_PASSWORD'] = 'airflow'
os.environ['POSTGRES_DB'] = 'airflow'

try:
    update_elo_ratings("epl")
except Exception as e:
    print("Error:", e)
