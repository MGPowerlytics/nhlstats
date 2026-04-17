import sys
sys.path.insert(0, '/mnt/data2/nhlstats/plugins')
sys.path.insert(0, '/mnt/data2/nhlstats')

try:
    from backtest_from_results import load_ml_games_from_csv, compute_elo_ratings
    print("Imports successful")

    df = load_ml_games_from_csv('/mnt/data2/nhlstats/mlb_backtest_data')
    print(f"Loaded {len(df)} games")

    # Try computing Elo ratings
    from collections import defaultdict
    import pandas as pd

    ratings = defaultdict(lambda: 1500.0)
    for idx, game in df.iterrows():
        home_team = game["home_team"]
        away_team = game["away_team"]
        home_rating = ratings[home_team]
        away_rating = ratings[away_team]
        # Just test first iteration
        if idx == 0:
            print(f"First game: {home_team} vs {away_team}")
            print(f"  Home rating: {home_rating}, Away rating: {away_rating}")

except Exception as e:
    import traceback
    traceback.print_exc()
