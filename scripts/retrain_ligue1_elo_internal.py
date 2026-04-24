
import os
import sys
import pandas as pd
from pathlib import Path

# In the container, /opt/airflow is the workdir
# PYTHONPATH includes /opt/airflow/plugins and /opt/airflow
sys.path.insert(0, "/opt/airflow/plugins")
sys.path.insert(0, "/opt/airflow/plugins/elo")

from db_manager import DBManager
from ligue1_elo_rating import Ligue1EloRating

def retrain_elo():
    # Use the internal postgres host
    db = DBManager(connection_string="postgresql+psycopg2://airflow:airflow@postgres:5432/airflow")

    # Initialize with 30.0 (though it's variable in the class)
    elo = Ligue1EloRating(k_factor=30.0)

    print("📊 Loading Ligue 1 games for retraining...")
    query = """
    SELECT game_date, home_team, away_team, home_score, away_score, result
    FROM ligue1_games
    WHERE home_score IS NOT NULL
    ORDER BY game_date
    """
    df = db.fetch_df(query)
    print(f"  Loaded {len(df)} games.")

    if df.empty:
        print("❌ No games found in ligue1_games table.")
        return

    print("🏃 Processing games...")
    for _, row in df.iterrows():
        outcome = row['result']
        if outcome == 'H':
            home_won = 1.0
        elif outcome == 'A':
            home_won = 0.0
        else:
            home_won = 0.5

        elo.update(row['home_team'], row['away_team'], home_won)

    print("\n✅ Retraining complete!")

    # Sort
    sorted_ratings = sorted(elo.ratings.items(), key=lambda x: x[1], reverse=True)

    # Save to CSV
    output_path = "/opt/airflow/data/ligue1_current_elo_ratings.csv"
    pd.DataFrame(sorted_ratings, columns=['team', 'rating']).to_csv(output_path, index=False)
    print(f"\n💾 Saved updated ratings to {output_path}")

if __name__ == "__main__":
    retrain_elo()
