import pandas as pd
import numpy as np
import duckdb
import os
import sys
from datetime import datetime
import warnings

# Suppress warnings
warnings.filterwarnings('ignore')

# Add plugins to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'plugins'))

# Import Elo classes
try:
    from mlb_elo_rating import MLBEloRating
    from nhl_elo_rating import NHLEloRating
    from nfl_elo_rating import NFLEloRating
    from epl_elo_rating import EPLEloRating
except ImportError as e:
    print(f"Error importing Elo classes: {e}")

def load_data(league, db_path='data/nhlstats.duckdb'):
    """Load game data from DuckDB."""
    if not os.path.exists(db_path):
        return pd.DataFrame()
        
    conn = duckdb.connect(db_path, read_only=True)
    
    if league == 'NHL':
        query = """
            SELECT game_date, season, home_team_name as home_team, away_team_name as away_team,
                   home_score, away_score, 
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM games
            WHERE game_state IN ('FINAL', 'OFF') AND home_score IS NOT NULL AND away_score IS NOT NULL
              AND (game_type = '02' OR game_type = 2)
            ORDER BY game_date
        """
    elif league == 'MLB':
        query = """
            SELECT game_date, season, home_team, away_team, home_score, away_score,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM mlb_games
            WHERE status = 'Final' AND home_score IS NOT NULL AND away_score IS NOT NULL
              AND game_type = 'R'
            ORDER BY game_date
        """
    elif league == 'NFL':
        query = """
            SELECT game_date, season, home_team, away_team, home_score, away_score,
                   CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM nfl_games
            WHERE status = 'Final' AND home_score IS NOT NULL AND away_score IS NOT NULL
              AND game_type = 'REG'
            ORDER BY game_date
        """
    elif league == 'EPL':
        query = """
            SELECT game_date, season, home_team, away_team, home_score, away_score, result,
                   CASE WHEN result = 'H' THEN 1 ELSE 0 END as home_win
            FROM epl_games
            WHERE result IS NOT NULL
            ORDER BY game_date
        """
    else:
        return pd.DataFrame()

    df = conn.execute(query).fetchdf()
    conn.close()
    
    if not df.empty:
        df['game_date'] = pd.to_datetime(df['game_date'])
        
    return df

def run_simulation(df, league):
    """Run Elo simulation and return DF with probabilities."""
    if df.empty: return df
    
    # Defaults
    k, home_adv = 20, 50
    elo = None
    
    if league == 'MLB':
        elo = MLBEloRating(k_factor=20, home_advantage=50)
    elif league == 'NHL':
        elo = NHLEloRating(k_factor=10, home_advantage=100)
    elif league == 'NFL':
        elo = NFLEloRating(k_factor=20, home_advantage=65)
    elif league == 'EPL':
        elo = EPLEloRating(k_factor=20, home_advantage=60)
        
    if not elo: return df
    
    probs = []
    
    for _, row in df.iterrows():
        prob = elo.predict(row['home_team'], row['away_team'])
        probs.append(prob)
        
        if league == 'EPL':
            elo.update(row['home_team'], row['away_team'], row['result'])
        elif league == 'NBA': # Not implemented in load yet
            elo.update(row['home_team'], row['away_team'], row['home_win'])
        else:
            elo.update(row['home_team'], row['away_team'], row['home_score'], row['away_score'])
            
    df['elo_prob'] = probs
    return df

def analyze_season_timing():
    print("Running Seasonal Timing Analysis...")
    results = []
    
    for league in ['MLB', 'NHL', 'NFL', 'EPL']:
        print(f"Processing {league}...")
        df = load_data(league)
        if df.empty:
            print(f"  No data for {league}")
            continue
            
        df = run_simulation(df, league)
        
        # Calculate season progress
        df['season_rank'] = df.groupby('season')['game_date'].rank(method='dense')
        season_max = df.groupby('season')['season_rank'].transform('max')
        df['season_progress'] = df['season_rank'] / season_max
        
        # Bin into 10% chunks
        df['progress_bin'] = pd.cut(df['season_progress'], bins=10, labels=False) + 1
        
        # Analyze each bin
        for bin_id in range(1, 11):
            subset = df[df['progress_bin'] == bin_id]
            if subset.empty: continue
            
            # Calibration / Brier Score
            brier = ((subset['elo_prob'] - subset['home_win']) ** 2).mean()
            
            # Top Decile Performance (Best Bets)
            # Find bets where Prob > 0.60 (favorites)
            favorites = subset[subset['elo_prob'] > 0.60]
            fav_win_rate = favorites['home_win'].mean() if not favorites.empty else 0
            fav_count = len(favorites)
            
            # ROI for simple strategy (Bet Home if Prob > 0.55)
            # Assume -110 odds (implied 52.4%)
            bets = subset[subset['elo_prob'] > 0.55]
            if not bets.empty:
                wins = bets['home_win'].sum()
                losses = len(bets) - wins
                # Profit: Wins * 0.909 - Losses * 1
                roi = ((wins * 0.909) - losses) / len(bets)
            else:
                roi = 0
                
            results.append({
                'League': league,
                'Season_Bin': bin_id * 10, # 10%, 20%, etc.
                'Games': len(subset),
                'Brier_Score': brier,
                'Fav_Win_Rate_60plus': fav_win_rate,
                'ROI_Home_Favs': roi,
                'Avg_Prob': subset['elo_prob'].mean(),
                'Baseline_Win': subset['home_win'].mean()
            })
            
    # Output Results
    res_df = pd.DataFrame(results)
    print("\n--- Comparative Analysis: ROI by Season Stage ---")
    print(res_df.pivot(index='Season_Bin', columns='League', values='ROI_Home_Favs').to_markdown(floatfmt=".1%"))

    print("\n--- Comparative Analysis: Brier Score (Lower is Better) ---")
    print(res_df.pivot(index='Season_Bin', columns='League', values='Brier_Score').to_markdown(floatfmt=".4f"))
    
    return res_df

if __name__ == "__main__":
    analyze_season_timing()
