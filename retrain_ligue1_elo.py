
import os
import sys
import pandas as pd
from pathlib import Path

# Add plugins directory to path
sys.path.insert(0, os.path.join(os.getcwd(), "plugins"))
sys.path.insert(0, os.path.join(os.getcwd(), "plugins", "elo"))

from db_manager import DBManager
from ligue1_elo_rating import Ligue1EloRating

def retrain_elo():
    db = DBManager()

    # Use K=30 as per research (though research said 20 for draws,
    # let's start with 30 and see if we can implement the variable K)
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
        print("❌ No games found. Did you run the backfill?")
        return

    print("🏃 Processing games...")
    for _, row in df.iterrows():
        # result is 'H', 'D', 'A'
        outcome = row['result']
        if outcome == 'H':
            home_won = 1.0
        elif outcome == 'A':
            home_won = 0.0
        else:
            home_won = 0.5

        elo.update(row['home_team'], row['away_team'], home_won)

    print("\n✅ Retraining complete!")
    print(f"Final ratings for {len(elo.ratings)} teams.")

    # Sort and print top 5
    sorted_ratings = sorted(elo.ratings.items(), key=lambda x: x[1], reverse=True)
    print("\nTop 5 teams:")
    for team, rating in sorted_ratings[:5]:
        print(f"  {team}: {rating:.2f}")

    # Save to CSV
    output_path = "data/ligue1_current_elo_ratings.csv"
    pd.DataFrame(sorted_ratings, columns=['team', 'rating']).to_csv(output_path, index=False)
    print(f"\n💾 Saved updated ratings to {output_path}")

if __name__ == "__main__":
    retrain_elo()
