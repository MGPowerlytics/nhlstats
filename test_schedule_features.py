#!/usr/bin/env python3
"""
Test script for Schedule & Fatigue features
Tests the 10 newly implemented critical features
"""

from build_training_dataset import NHLTrainingDataset
import pandas as pd

def test_schedule_features():
    """Test the new schedule and fatigue features"""
    
    print("=" * 70)
    print("TESTING NHL SCHEDULE & FATIGUE FEATURES")
    print("=" * 70)
    
    # Build dataset with new features
    with NHLTrainingDataset() as dataset:
        print("\n1. Building training dataset with schedule features...")
        df = dataset.build_training_dataset(min_date='2024-01-01')
        
        print(f"\n2. Dataset shape: {df.shape}")
        print(f"   Total features: {df.shape[1] - 5}")  # Exclude ID/date columns
        
        # Check for new schedule features
        schedule_features = [
            'home_days_rest', 'away_days_rest',
            'home_back_to_back', 'away_back_to_back',
            'home_3_in_4', 'away_3_in_4',
            'home_4_in_6', 'away_4_in_6',
            'home_is_home', 'away_is_away',
            'home_just_came_home', 'away_just_came_home',
            'home_just_went_away', 'away_just_went_away',
            'home_back_to_backs_l10', 'away_back_to_backs_l10',
            'home_well_rested', 'away_well_rested',
            'rest_advantage'
        ]
        
        print("\n3. Checking for new features:")
        missing_features = [f for f in schedule_features if f not in df.columns]
        if missing_features:
            print(f"   ❌ Missing features: {missing_features}")
            return False
        else:
            print(f"   ✅ All {len(schedule_features)} schedule features present!")
        
        # Show summary statistics
        print("\n4. Feature Statistics:")
        print("-" * 70)
        
        print("\n   Days of Rest:")
        print(f"     Home avg: {df['home_days_rest'].mean():.2f} days")
        print(f"     Away avg: {df['away_days_rest'].mean():.2f} days")
        
        print("\n   Back-to-Back Games:")
        print(f"     Home: {df['home_back_to_back'].sum()} games ({100*df['home_back_to_back'].mean():.1f}%)")
        print(f"     Away: {df['away_back_to_back'].sum()} games ({100*df['away_back_to_back'].mean():.1f}%)")
        
        print("\n   Schedule Compression:")
        print(f"     3-in-4 (home): {df['home_3_in_4'].sum()} ({100*df['home_3_in_4'].mean():.1f}%)")
        print(f"     4-in-6 (home): {df['home_4_in_6'].sum()} ({100*df['home_4_in_6'].mean():.1f}%)")
        
        print("\n   Location Changes:")
        print(f"     Just came home: {df['home_just_came_home'].sum()} games")
        print(f"     Just went away: {df['away_just_went_away'].sum()} games")
        
        print("\n   Well Rested:")
        print(f"     Home well-rested (3+ days): {df['home_well_rested'].sum()} ({100*df['home_well_rested'].mean():.1f}%)")
        print(f"     Away well-rested (3+ days): {df['away_well_rested'].sum()} ({100*df['away_well_rested'].mean():.1f}%)")
        
        print("\n   Returning from Long Road Trip:")
        print(f"     Teams just came home: {df['home_just_came_home'].sum()} games")
        
        print("\n   Rest Advantage:")
        print(f"     Mean: {df['rest_advantage'].mean():.2f} days")
        print(f"     Std:  {df['rest_advantage'].std():.2f} days")
        print(f"     Range: {df['rest_advantage'].min():.0f} to {df['rest_advantage'].max():.0f}")
        
        # Show sample rows with interesting schedule scenarios
        print("\n5. Example Scenarios:")
        print("-" * 70)
        
        # Back-to-back games
        b2b_games = df[df['home_back_to_back'] == 1].head(3)
        if len(b2b_games) > 0:
            print("\n   Back-to-Back Example:")
            for idx, row in b2b_games.iterrows():
                print(f"     {row['game_date']}: {row['home_team_name']} vs {row['away_team_name']}")
                print(f"       Home B2B: Yes, Away B2B: {row['away_back_to_back'] == 1}")
        
        # Schedule advantage
        rest_adv = df[abs(df['rest_advantage']) >= 2].head(3)
        if len(rest_adv) > 0:
            print("\n   Schedule Advantage Examples (2+ days difference):")
            for idx, row in rest_adv.iterrows():
                print(f"     {row['game_date']}: {row['home_team_name']} vs {row['away_team_name']}")
                print(f"       Home rest: {row['home_days_rest']:.0f}d, Away rest: {row['away_days_rest']:.0f}d")
                print(f"       Advantage: {row['rest_advantage']:+.0f} days (favors {'home' if row['rest_advantage'] > 0 else 'away'})")
        
        # Coming home
        came_home = df[df['home_just_came_home'] == 1].head(3)
        if len(came_home) > 0:
            print("\n   Just Came Home Examples:")
            for idx, row in came_home.iterrows():
                print(f"     {row['game_date']}: {row['home_team_name']} vs {row['away_team_name']}")
                print(f"       {row['home_team_name']} just returned home")
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print("\nNext Steps:")
        print("  1. Train model with new features: python train_xgboost.py")
        print("  2. Compare accuracy vs baseline (expected +3-4% improvement)")
        print("  3. Analyze feature importance to see impact")
        
        return True

if __name__ == '__main__':
    try:
        success = test_schedule_features()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
