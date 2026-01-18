"""
Add Elo rating features to existing training dataset
"""

import pandas as pd
import numpy as np
from pathlib import Path
from nhl_elo_rating import NHLEloRating


def add_elo_features(input_csv='data/nhl_training_data.csv', 
                     output_csv='data/nhl_training_data_with_elo.csv'):
    """Add Elo rating features to existing training dataset"""
    
    print("=" * 70)
    print("Adding Elo Rating Features to Training Dataset")
    print("=" * 70)
    
    # Load existing dataset
    print(f"\n📂 Loading dataset from {input_csv}...")
    df = pd.read_csv(input_csv)
    print(f"   ✅ Loaded {len(df)} games with {len(df.columns)} columns")
    
    # Ensure date column is datetime
    df['game_date'] = pd.to_datetime(df['game_date'])
    
    # Sort by date for temporal processing
    print("\n🔄 Sorting by date...")
    df_sorted = df.sort_values('game_date').copy()
    print(f"   ✅ Date range: {df_sorted['game_date'].min().date()} to {df_sorted['game_date'].max().date()}")
    
    # Initialize Elo system
    print("\n⚡ Initializing Elo rating system...")
    print("   K-factor: 20")
    print("   Home advantage: 100")
    print("   Initial rating: 1500")
    
    elo = NHLEloRating(k_factor=20, home_advantage=100, initial_rating=1500)
    
    # Storage for features
    home_elo_list = []
    away_elo_list = []
    elo_diff_list = []
    elo_prob_list = []
    
    # Process each game in chronological order
    print("\n🏒 Computing Elo ratings game by game...")
    print("   (This ensures no data leakage - only past games affect ratings)")
    
    for idx, row in df_sorted.iterrows():
        home_team = row['home_team_name']
        away_team = row['away_team_name']
        home_won = row['home_win']
        
        # Get current ratings BEFORE this game (no data leakage)
        home_elo_rating = elo.get_rating(home_team)
        away_elo_rating = elo.get_rating(away_team)
        
        # Calculate Elo prediction
        elo_prob = elo.predict(home_team, away_team)
        
        # Calculate difference
        elo_diff = home_elo_rating - away_elo_rating
        
        # Store features
        home_elo_list.append(home_elo_rating)
        away_elo_list.append(away_elo_rating)
        elo_diff_list.append(elo_diff)
        elo_prob_list.append(elo_prob)
        
        # Update Elo ratings AFTER recording features
        elo.update(home_team, away_team, home_won)
    
    print(f"   ✅ Processed {len(df_sorted)} games")
    
    # Add features to dataframe
    print("\n➕ Adding Elo features...")
    df_sorted['home_elo'] = home_elo_list
    df_sorted['away_elo'] = away_elo_list
    df_sorted['elo_diff'] = elo_diff_list
    df_sorted['elo_prob'] = elo_prob_list
    
    # Show top teams by final Elo
    print("\n🏆 Final Elo Rankings (Top 10):")
    rankings = elo.get_rankings(top_n=10)
    for i, (team, rating) in enumerate(rankings, 1):
        print(f"   {i:2d}. {team:30s} {rating:7.1f}")
    
    # Return to original order
    df_final = df_sorted.sort_index()
    
    # Save
    output_path = Path(output_csv)
    df_final.to_csv(output_path, index=False)
    
    print(f"\n💾 Enhanced dataset saved to: {output_path}")
    print(f"\n📊 Dataset Summary:")
    print(f"   Total games: {len(df_final):,}")
    print(f"   Total features: {len(df_final.columns) - 5}")  # Exclude metadata + target
    print(f"   New Elo features: 4 (home_elo, away_elo, elo_diff, elo_prob)")
    print(f"   Home win rate: {df_final['home_win'].mean():.1%}")
    
    # Show sample
    print(f"\n🔍 Sample rows with Elo features:")
    sample_cols = ['game_date', 'home_team_name', 'away_team_name', 
                   'home_elo', 'away_elo', 'elo_diff', 'elo_prob', 'home_win']
    print(df_final[sample_cols].tail(5).to_string(index=False))
    
    print(f"\n✅ Ready for XGBoost training with Elo features!")
    
    return df_final


if __name__ == "__main__":
    add_elo_features()
