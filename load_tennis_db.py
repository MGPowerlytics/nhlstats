import os
from plugins.db_manager import DBManager
from plugins.db_loader import NHLDatabaseLoader

def load_tennis():
    # Force use of localhost instead of postgres container
    os.environ['POSTGRES_HOST'] = 'localhost'
    os.environ['POSTGRES_USER'] = 'airflow'
    os.environ['POSTGRES_PASSWORD'] = 'airflow'
    os.environ['POSTGRES_DB'] = 'airflow'

    db = DBManager()
    loader = NHLDatabaseLoader(db_manager=db, sport="tennis")

    print("Loading tennis history...")
    loader.load_csv_history("Tennis")
    print("Done loading.")

if __name__ == "__main__":
    load_tennis()
