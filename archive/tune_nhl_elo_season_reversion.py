#!/usr/bin/env python3
"""
Tune NHL Elo parameters to maximize prediction accuracy.
"""

import duckdb
import pandas as pd
import numpy as np
from collections import defaultdict
from datetime import datetime

class SimpleElo:
    def __init__(self, k, ha, revert_factor=0.0, initial=1500):
        self.k = k
        self.ha = ha
        self.revert_factor = revert_factor
        self.initial = initial
        self.ratings = defaultdict(lambda: initial)
        self.last_season = None
        
    def predict(self, home, away):
        r_home = self.ratings[home] + self.ha
        r_away = self.ratings[away]
        return 1 / (1 + 10 ** ((r_away - r_home) / 400))
        
    def revert_ratings(self):
        # Revert all ratings towards mean (1500)
        # New = Old * (1 - factor) + 1500 * factor
        # If factor is 0.25 (25%), then 75% returned, 25% mean
        for team in self.ratings:
            self.ratings[team] = self.ratings[team] * (1 - self.revert_factor) + self.initial * self.revert_factor

def load_games():
    """Load ordered games from DuckDB"""
    # Create temp copy to avoid lock
    import shutil
    import os
    
    # Check if temp file exists and remove it if so (cleanup from previous run)
    temp_db = 'data/nhlstats_tuning_temp.duckdb'
    if os.path.exists(temp_db):
        try:
            os.remove(temp_db)
        except:
            pass
            
    shutil.copy2('data/nhlstats.duckdb', temp_db)
    
    try:
        conn = duckdb.connect(temp_db, read_only=True)
        query = """
            SELECT 
                game_date,
                home_team_name,
                away_team_name,
                CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
            FROM games 
            WHERE game_state IN ('OFF', 'FINAL') 
              AND home_score IS NOT NULL 
              AND away_score IS NOT NULL
            ORDER BY game_date, game_id
        """
        df = conn.execute(query).fetchdf()
        conn.close()
    finally:
        if os.path.exists(temp_db):
            os.remove(temp_db)
            
    return df

def run_tuning():
    print("Loading data...")
    df = load_games()
    print(f"Loaded {len(df)} games")
    
    # Split point for current season (approx)
    current_season_start = '2025-10-01'
    
    # Best params from previous run
    BEST_K = 10
    BEST_HA = 50
    
    # Test Reversion Factors
    REVERT_FACTORS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8]
    
    print(f"Testing season reversion factors with K={BEST_K}, HA={BEST_HA}...")
    print("-" * 80)
    print(f"{'Revert':<8} {'Acc (All)':<12} {'LL (All)':<12} {'Acc (25-26)':<12} {'LL (25-26)':<12}")
    print("-" * 80)
    
    for r in REVERT_FACTORS:
        elo = SimpleElo(BEST_K, BEST_HA, revert_factor=r)
        
        correct = 0
        log_loss = 0
        
        curr_correct = 0
        curr_log_loss = 0
        curr_count = 0
        
        for _, row in df.iterrows():
            home = row['home_team_name']
            away = row['away_team_name']
            win = row['home_win']
            date = str(row['game_date'])
            
            # Determine season
            game_date_str = str(date)
            year = int(game_date_str[:4])
            month = int(game_date_str[5:7])
            season = year if month >= 9 else year - 1
            
            # Check for season change
            if elo.last_season is not None and season > elo.last_season:
                 elo.revert_ratings()
            elo.last_season = season
            
            prob = elo.predict(home, away)
            
            # Check prediction
            is_correct = (prob > 0.5 and win == 1) or (prob < 0.5 and win == 0)
            ll = -np.log(prob if win == 1 else 1 - prob)
            
            # Update total stats
            if is_correct: correct += 1
            log_loss += ll
            
            # Update current season stats
            if date >= current_season_start:
                if is_correct: curr_correct += 1
                curr_log_loss += ll
                curr_count += 1
            
            # Update ratings
            actual = 1.0 if win else 0.0
            change = elo.k * (actual - prob)
            elo.ratings[home] += change
            elo.ratings[away] -= change
            
        acc_all = correct / len(df)
        ll_all = log_loss / len(df)
        
        acc_curr = curr_correct / curr_count if curr_count > 0 else 0
        ll_curr = curr_log_loss / curr_count if curr_count > 0 else 0
        
        print(f"{r:<8.1f} {acc_all:.4f}       {ll_all:.4f}       {acc_curr:.4f}        {ll_curr:.4f}")

    print("-" * 80)

if __name__ == "__main__":
    run_tuning()
