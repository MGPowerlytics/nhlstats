#!/usr/bin/env python3
"""
NBA Elo Rating System - Calculate and evaluate Elo ratings for NBA teams.
Loads data directly from JSON files.
"""

import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score, accuracy_score, log_loss
from collections import defaultdict


class NBAEloRating:
    """NBA-specific Elo rating system."""
    
    def __init__(self, k_factor=20, home_advantage=100, initial_rating=1500):
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.ratings = {}
        self.game_history = []
        
    def get_rating(self, team_name):
        """Get current Elo rating for a team."""
        if team_name not in self.ratings:
            self.ratings[team_name] = self.initial_rating
        return self.ratings[team_name]
    
    def expected_score(self, rating_a, rating_b):
        """Calculate expected score for team A vs team B."""
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    
    def predict(self, home_team, away_team):
        """Predict probability of home team winning."""
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)
        return self.expected_score(home_rating + self.home_advantage, away_rating)
    
    def update(self, home_team, away_team, home_won):
        """Update Elo ratings after a game."""
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)
        
        expected_home = self.expected_score(home_rating + self.home_advantage, away_rating)
        actual_home = 1.0 if home_won else 0.0
        
        # Update ratings
        home_change = self.k_factor * (actual_home - expected_home)
        self.ratings[home_team] = home_rating + home_change
        self.ratings[away_team] = away_rating - home_change


def load_nba_games_from_json():
    """Load NBA games from JSON files."""
    nba_dir = Path('data/nba')
    games = []
    
    print("📂 Loading NBA games from JSON files...")
    
    # Get all date directories
    date_dirs = sorted([d for d in nba_dir.iterdir() if d.is_dir()])
    
    for date_dir in date_dirs:
        scoreboard_file = date_dir / f"scoreboard_{date_dir.name}.json"
        
        if not scoreboard_file.exists():
            continue
        
        try:
            with open(scoreboard_file) as f:
                data = json.load(f)
            
            # Parse scoreboard
            if 'resultSets' not in data:
                continue
            
            for result_set in data['resultSets']:
                if result_set['name'] == 'GameHeader':
                    headers = result_set['headers']
                    
                    # Get column indices
                    idx_game_id = headers.index('GAME_ID')
                    idx_game_date = headers.index('GAME_DATE_EST')
                    idx_home_team_id = headers.index('HOME_TEAM_ID')
                    idx_visitor_team_id = headers.index('VISITOR_TEAM_ID')
                    idx_status = headers.index('GAME_STATUS_TEXT')
                    
                    for row in result_set['rowSet']:
                        game_status = row[idx_status]
                        
                        # Only include finished games
                        if 'Final' not in game_status:
                            continue
                        
                        game_id = str(row[idx_game_id])
                        game_date = row[idx_game_date]
                        
                        # Load boxscore for this game
                        boxscore_file = date_dir / f"boxscore_{game_id}.json"
                        
                        if not boxscore_file.exists():
                            continue
                        
                        with open(boxscore_file) as bf:
                            boxscore = json.load(bf)
                        
                        # Extract team stats
                        home_team_name = None
                        away_team_name = None
                        home_score = None
                        away_score = None
                        
                        for bs_result in boxscore['resultSets']:
                            if bs_result['name'] == 'TeamStats':
                                bs_headers = bs_result['headers']
                                idx_team_id = bs_headers.index('TEAM_ID')
                                idx_team_name = bs_headers.index('TEAM_NAME')
                                idx_pts = bs_headers.index('PTS')
                                
                                for bs_row in bs_result['rowSet']:
                                    team_id = bs_row[idx_team_id]
                                    team_name = bs_row[idx_team_name]
                                    pts = bs_row[idx_pts]
                                    
                                    if team_id == row[idx_home_team_id]:
                                        home_team_name = team_name
                                        home_score = pts
                                    elif team_id == row[idx_visitor_team_id]:
                                        away_team_name = team_name
                                        away_score = pts
                        
                        if home_team_name and away_team_name and home_score is not None and away_score is not None:
                            games.append({
                                'game_id': game_id,
                                'game_date': game_date,
                                'home_team': home_team_name,
                                'away_team': away_team_name,
                                'home_score': home_score,
                                'away_score': away_score,
                                'home_win': 1 if home_score > away_score else 0
                            })
        
        except Exception as e:
            # Skip problematic files
            continue
    
    df = pd.DataFrame(games)
    
    if len(df) > 0:
        df['game_date'] = pd.to_datetime(df['game_date'])
        df = df.sort_values('game_date').reset_index(drop=True)
    
    print(f"✅ Loaded {len(df)} completed NBA games")
    if len(df) > 0:
        print(f"📅 Date range: {df['game_date'].min()} to {df['game_date'].max()}")
    
    return df


def evaluate_nba_elo():
    """Evaluate NBA Elo system."""
    print("=" * 80)
    print("🏀 NBA ELO RATING SYSTEM EVALUATION")
    print("=" * 80)
    
    # Load games
    games_df = load_nba_games_from_json()
    
    if len(games_df) == 0:
        print("❌ No NBA games found!")
        return
    
    # Split into train/test (80/20 temporal split)
    split_idx = int(len(games_df) * 0.8)
    train_df = games_df.iloc[:split_idx].copy()
    test_df = games_df.iloc[split_idx:].copy()
    
    print(f"\n📊 Dataset Split:")
    print(f"   Training: {len(train_df)} games")
    print(f"   Test: {len(test_df)} games")
    
    # Train Elo on training set
    print("\n🎯 Training Elo ratings...")
    elo = NBAEloRating(k_factor=20, home_advantage=100)
    
    train_predictions = []
    for _, game in train_df.iterrows():
        # Predict
        prob = elo.predict(game['home_team'], game['away_team'])
        train_predictions.append(prob)
        
        # Update
        elo.update(game['home_team'], game['away_team'], game['home_win'])
    
    train_df['elo_prob'] = train_predictions
    
    # Evaluate on test set
    print("🧪 Evaluating on test set...")
    test_predictions = []
    for _, game in test_df.iterrows():
        prob = elo.predict(game['home_team'], game['away_team'])
        test_predictions.append(prob)
        
        # Continue updating (simulate production)
        elo.update(game['home_team'], game['away_team'], game['home_win'])
    
    test_df['elo_prob'] = test_predictions
    
    # Calculate metrics
    y_true = test_df['home_win'].values
    y_pred_proba = test_df['elo_prob'].values
    y_pred = (y_pred_proba >= 0.5).astype(int)
    
    accuracy = accuracy_score(y_true, y_pred)
    auc = roc_auc_score(y_true, y_pred_proba)
    logloss = log_loss(y_true, y_pred_proba)
    
    correct = (y_pred == y_true).sum()
    total = len(y_true)
    
    # Print results
    print("\n" + "=" * 80)
    print("📊 NBA ELO TEST SET RESULTS")
    print("=" * 80)
    print(f"")
    print(f"  Games:      {total}")
    print(f"  Accuracy:   {accuracy:.1%} ({correct}/{total} correct)")
    print(f"  ROC-AUC:    {auc:.4f}")
    print(f"  Log Loss:   {logloss:.4f}")
    print("")
    
    # Show team ratings
    print("=" * 80)
    print("🏆 TOP 10 NBA TEAMS BY ELO RATING")
    print("=" * 80)
    
    team_ratings = sorted(elo.ratings.items(), key=lambda x: x[1], reverse=True)[:10]
    for i, (team, rating) in enumerate(team_ratings, 1):
        print(f"{i:2d}. {team:25s} {rating:7.1f}")
    
    # Save results
    results = {
        'model': 'NBA Elo',
        'test_games': int(total),
        'accuracy': float(accuracy),
        'auc': float(auc),
        'log_loss': float(logloss),
        'correct': int(correct),
        'k_factor': elo.k_factor,
        'home_advantage': elo.home_advantage,
        'initial_rating': elo.initial_rating
    }
    
    import json
    with open('data/nba_elo_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Save team ratings
    ratings_df = pd.DataFrame([
        {'team': team, 'elo_rating': rating}
        for team, rating in sorted(elo.ratings.items(), key=lambda x: x[1], reverse=True)
    ])
    ratings_df.to_csv('data/nba_team_elo_ratings.csv', index=False)
    
    print("\n💾 Files saved:")
    print("   - data/nba_elo_results.json")
    print("   - data/nba_team_elo_ratings.csv")
    
    print("\n" + "=" * 80)
    print("✅ NBA Elo evaluation complete!")
    print("=" * 80)
    
    return results


if __name__ == '__main__':
    evaluate_nba_elo()
