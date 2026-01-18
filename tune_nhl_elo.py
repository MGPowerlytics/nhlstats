#!/usr/bin/env python3
"""
Tune NHL Elo parameters to maximize prediction accuracy.
"""

import duckdb
import pandas as pd
import numpy as np
from collections import defaultdict
from datetime import datetime

# Define parameter grid
K_FACTORS = [6, 10, 15, 20, 25, 30]
HOME_ADVANTAGES = [25, 50, 75, 100, 125, 150]

class SimpleElo:
    def __init__(self, k, ha, initial=1500):
        self.k = k
        self.ha = ha
        self.ratings = defaultdict(lambda: initial)
        
    def predict(self, home, away):
        r_home = self.ratings[home] + self.ha
        r_away = self.ratings[away]
        return 1 / (1 + 10 ** ((r_away - r_home) / 400))
        
    def update(self, home, away, home_win):
        pred = self.predict(home, away)
        actual = 1.0 if home_win else 0.0
        change = self.k * (actual - pred)
        self.ratings[home] += change
        self.ratings[away] -= change
        return pred

def load_games():
    """Load ordered games from DuckDB"""
    conn = duckdb.connect('data/nhlstats.duckdb', read_only=True)
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
    return df

def run_tuning():
    print("Loading data...")
    df = load_games()
    print(f"Loaded {len(df)} games")
    
    # Split point for current season (approx)
    current_season_start = '2025-10-01'
    
    results = []
    
    print(f"Testing {len(K_FACTORS) * len(HOME_ADVANTAGES)} combinations...")
    print("-" * 80)
    print(f"{'K':<5} {'HA':<5} {'Acc (All)':<12} {'LL (All)':<12} {'Acc (25-26)':<12} {'LL (25-26)':<12}")
    print("-" * 80)
    
    for k in K_FACTORS:
        for ha in HOME_ADVANTAGES:
            elo = SimpleElo(k, ha)
            
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
                elo.update(home, away, win)
            
            acc_all = correct / len(df)
            ll_all = log_loss / len(df)
            
            acc_curr = curr_correct / curr_count if curr_count > 0 else 0
            ll_curr = curr_log_loss / curr_count if curr_count > 0 else 0
            
            results.append({
                'k': k,
                'ha': ha,
                'acc_all': acc_all,
                'll_all': ll_all,
                'acc_curr': acc_curr,
                'll_curr': ll_curr
            })
            
            print(f"{k:<5} {ha:<5} {acc_all:.4f}       {ll_all:.4f}       {acc_curr:.4f}        {ll_curr:.4f}")

    print("-" * 80)
    
    # Find best params based on Log Loss (better measure of probability quality)
    best_all = min(results, key=lambda x: x['ll_all'])
    best_curr = min(results, key=lambda x: x['ll_curr'])
    
    print("\nBest Parameters (Overall Log Loss):")
    print(f"K={best_all['k']}, HA={best_all['ha']} -> Acc: {best_all['acc_all']:.4f}, LL: {best_all['ll_all']:.4f}")
    
    print("\nBest Parameters (Current Season Log Loss):")
    print(f"K={best_curr['k']}, HA={best_curr['ha']} -> Acc: {best_curr['acc_curr']:.4f}, LL: {best_curr['ll_curr']:.4f}")

def analyze_distribution(k, ha):
    print(f"\nAnalyzing Distribution for K={k}, HA={ha}")
    print("-" * 60)
    
    df = load_games()
    elo = SimpleElo(k, ha)
    probs = []
    
    for _, row in df.iterrows():
        home = row['home_team_name']
        away = row['away_team_name']
        win = row['home_win']
        
        prob = elo.predict(home, away)
        probs.append(prob)
        elo.update(home, away, win)
    
    probs = np.array(probs)
    print(f"Mean Probability: {np.mean(probs):.4f}")
    print(f"Std Dev: {np.std(probs):.4f}")
    print(f"Min: {np.min(probs):.4f}")
    print(f"Max: {np.max(probs):.4f}")
    
    thresholds = [0.55, 0.60, 0.65, 0.70, 0.75]
    for t in thresholds:
        count = np.sum(probs > t)
        print(f"Games > {t*100}%: {count} ({count/len(probs)*100:.1f}%)")

if __name__ == "__main__":
    # Run distribution analysis for the proposed parameters
    analyze_distribution(10, 50)
