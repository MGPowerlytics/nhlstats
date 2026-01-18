"""
NHL ML Training Dataset Builder V3 - Enhanced Feature Engineering

New features added:
- Rest days between games
- Back-to-back game indicators
- Win/loss streaks (last 3, 5 games)
- Goal differential trends
- Home/away split performance
- Head-to-head records
- Special teams performance (PP%, PK%)
- Recent momentum indicators
- Travel distance estimation
- Season timing (month, days into season)
"""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

class NHLTrainingDatasetV3:
    """Build enhanced ML training dataset from DuckDB"""
    
    def __init__(self, db_path: str = "data/nhlstats.duckdb"):
        self.db_path = Path(db_path)
        self.conn = None
        
    def __enter__(self):
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
        
    def connect(self):
        self.conn = duckdb.connect(str(self.db_path), read_only=True)
        print(f"✅ Connected to {self.db_path}")
        
    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def build_dataset(self):
        """Build complete training dataset with all features"""
        
        print("\n🔨 Building Enhanced Training Dataset...")
        print("="*70)
        
        # Step 1: Get base game data with stats
        print("\n1️⃣ Loading base game statistics...")
        base_df = self.get_base_game_stats()
        print(f"   ✅ Loaded {len(base_df)} games")
        
        # Step 2: Add rolling statistics
        print("\n2️⃣ Computing rolling statistics (L3, L5, L10)...")
        enhanced_df = self.add_rolling_stats(base_df)
        print(f"   ✅ Added rolling window features")
        
        # Step 3: Add rest days and back-to-back indicators
        print("\n3️⃣ Computing rest days and back-to-back indicators...")
        enhanced_df = self.add_rest_features(enhanced_df)
        print(f"   ✅ Added rest/fatigue features")
        
        # Step 4: Add streak features
        print("\n4️⃣ Computing win/loss streaks...")
        enhanced_df = self.add_streak_features(enhanced_df)
        print(f"   ✅ Added momentum features")
        
        # Step 5: Add head-to-head records
        print("\n5️⃣ Computing head-to-head records...")
        enhanced_df = self.add_head_to_head(enhanced_df)
        print(f"   ✅ Added H2H matchup features")
        
        # Step 6: Add home/away splits
        print("\n6️⃣ Computing home/away performance splits...")
        enhanced_df = self.add_venue_splits(enhanced_df)
        print(f"   ✅ Added venue-specific features")
        
        # Step 7: Add temporal features
        print("\n7️⃣ Adding temporal features...")
        enhanced_df = self.add_temporal_features(enhanced_df)
        print(f"   ✅ Added season timing features")
        
        # Step 8: Add special teams stats
        print("\n8️⃣ Computing special teams performance...")
        enhanced_df = self.add_special_teams(enhanced_df)
        print(f"   ✅ Added PP/PK features")
        
        # Step 9: Add Elo ratings
        print("\n9️⃣ Computing Elo ratings...")
        enhanced_df = self.add_elo_ratings(enhanced_df)
        print(f"   ✅ Added Elo rating features")
        
        # Step 10: Clean up and finalize
        print("\n🔟 Finalizing dataset...")
        final_df = self.finalize_dataset(enhanced_df)
        
        print(f"\n✅ Final dataset: {len(final_df)} games, {len(final_df.columns)} features")
        print(f"   Date range: {final_df['game_date'].min()} to {final_df['game_date'].max()}")
        
        return final_df
    
    def get_base_game_stats(self):
        """Get base game statistics"""
        
        query = """
        WITH game_stats AS (
            SELECT 
                g.game_id,
                g.game_date,
                g.home_team_id,
                g.away_team_id,
                ht.team_name as home_team_name,
                at.team_name as away_team_name,
                g.home_score,
                g.away_score,
                CASE WHEN g.home_score > g.away_score THEN 1 ELSE 0 END as home_win,
                
                -- Home team stats
                home_stats.corsi_for as home_corsi_for,
                home_stats.fenwick_for as home_fenwick_for,
                home_stats.shots_for as home_shots,
                home_stats.goals_for as home_goals,
                home_stats.high_danger_chances_for as home_hd_chances,
                home_stats.corsi_against as home_corsi_against,
                home_stats.fenwick_against as home_fenwick_against,
                home_stats.save_pct as home_save_pct,
                home_stats.powerplay_goals as home_pp_goals,
                home_stats.powerplay_opportunities as home_pp_opps,
                home_stats.penalty_kill_pct as home_pk_pct,
                
                -- Away team stats  
                away_stats.corsi_for as away_corsi_for,
                away_stats.fenwick_for as away_fenwick_for,
                away_stats.shots_for as away_shots,
                away_stats.goals_for as away_goals,
                away_stats.high_danger_chances_for as away_hd_chances,
                away_stats.corsi_against as away_corsi_against,
                away_stats.fenwick_against as away_fenwick_against,
                away_stats.save_pct as away_save_pct,
                away_stats.powerplay_goals as away_pp_goals,
                away_stats.powerplay_opportunities as away_pp_opps,
                away_stats.penalty_kill_pct as away_pk_pct
                
            FROM games g
            JOIN teams ht ON g.home_team_id = ht.team_id
            JOIN teams at ON g.away_team_id = at.team_id
            LEFT JOIN game_team_stats home_stats ON g.game_id = home_stats.game_id AND g.home_team_id = home_stats.team_id
            LEFT JOIN game_team_stats away_stats ON g.game_id = away_stats.game_id AND g.away_team_id = away_stats.team_id
            WHERE g.game_type = 2  -- Regular season only
            ORDER BY g.game_date, g.game_id
        )
        SELECT * FROM game_stats
        """
        
        df = self.conn.execute(query).fetchdf()
        df['game_date'] = pd.to_datetime(df['game_date'])
        
        # Fill NaN values
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = df[numeric_cols].fillna(0)
        
        return df
    
    def add_rolling_stats(self, df):
        """Add rolling statistics (L3, L5, L10)"""
        
        df = df.sort_values('game_date').copy()
        
        stat_cols = [
            'corsi_for', 'corsi_against', 'fenwick_for', 'fenwick_against',
            'shots', 'goals', 'hd_chances', 'save_pct',
            'pp_goals', 'pp_opps', 'pk_pct'
        ]
        
        windows = [3, 5, 10]
        
        for prefix in ['home', 'away']:
            team_col = f'{prefix}_team_id'
            
            for stat in stat_cols:
                col_name = f'{prefix}_{stat}'
                
                if col_name not in df.columns:
                    continue
                
                for window in windows:
                    # Rolling mean
                    df[f'{col_name}_l{window}'] = df.groupby(team_col)[col_name].transform(
                        lambda x: x.rolling(window=window, min_periods=1).mean().shift(1)
                    )
        
        # Add points percentage (win rate)
        for prefix in ['home', 'away']:
            team_col = f'{prefix}_team_id'
            
            if prefix == 'home':
                df['home_won_last'] = (df['home_score'] > df['away_score']).astype(int)
                df['home_points_pct'] = df.groupby(team_col)['home_won_last'].transform(
                    lambda x: x.rolling(window=10, min_periods=1).mean().shift(1)
                )
            else:
                df['away_won_last'] = (df['away_score'] > df['home_score']).astype(int)
                df['away_points_pct'] = df.groupby(team_col)['away_won_last'].transform(
                    lambda x: x.rolling(window=10, min_periods=1).mean().shift(1)
                )
        
        return df
    
    def add_rest_features(self, df):
        """Add rest days and back-to-back indicators"""
        
        df = df.sort_values('game_date').copy()
        
        for prefix in ['home', 'away']:
            team_col = f'{prefix}_team_id'
            
            # Days since last game
            df[f'{prefix}_days_rest'] = df.groupby(team_col)['game_date'].diff().dt.days.fillna(3)
            
            # Back-to-back indicator
            df[f'{prefix}_back_to_back'] = (df[f'{prefix}_days_rest'] <= 1).astype(int)
            
            # Well-rested indicator (3+ days)
            df[f'{prefix}_well_rested'] = (df[f'{prefix}_days_rest'] >= 3).astype(int)
        
        # Rest advantage (positive = home team more rested)
        df['rest_advantage'] = df['home_days_rest'] - df['away_days_rest']
        
        return df
    
    def add_streak_features(self, df):
        """Add win/loss streak indicators"""
        
        df = df.sort_values('game_date').copy()
        
        for prefix in ['home', 'away']:
            team_col = f'{prefix}_team_id'
            won_col = f'{prefix}_won_last'
            
            # Current streak (positive = wins, negative = losses)
            def calculate_streak(group):
                streak = []
                current = 0
                for won in group:
                    if pd.isna(won):
                        streak.append(0)
                    elif won == 1:
                        current = current + 1 if current >= 0 else 1
                        streak.append(current)
                    else:
                        current = current - 1 if current <= 0 else -1
                        streak.append(current)
                return pd.Series(streak, index=group.index)
            
            df[f'{prefix}_streak'] = df.groupby(team_col)[won_col].transform(calculate_streak).shift(1).fillna(0)
            
            # Recent form (wins in last 5 games)
            df[f'{prefix}_form_l5'] = df.groupby(team_col)[won_col].transform(
                lambda x: x.rolling(window=5, min_periods=1).sum().shift(1)
            ).fillna(0)
        
        return df
    
    def add_head_to_head(self, df):
        """Add head-to-head matchup records"""
        
        df = df.sort_values('game_date').copy()
        
        # Create matchup key (sorted team IDs)
        df['matchup'] = df.apply(
            lambda x: tuple(sorted([x['home_team_id'], x['away_team_id']])), axis=1
        )
        
        # Home team wins in this matchup
        df['h2h_home_wins'] = 0
        df['h2h_total_games'] = 0
        
        for idx in df.index:
            matchup = df.loc[idx, 'matchup']
            home_team = df.loc[idx, 'home_team_id']
            game_date = df.loc[idx, 'game_date']
            
            # Get previous games in this matchup
            prev_games = df[(df['matchup'] == matchup) & (df['game_date'] < game_date)]
            
            if len(prev_games) > 0:
                # Count home team wins (considering they might have been away in previous games)
                home_wins = len(prev_games[
                    ((prev_games['home_team_id'] == home_team) & (prev_games['home_win'] == 1)) |
                    ((prev_games['away_team_id'] == home_team) & (prev_games['home_win'] == 0))
                ])
                
                df.loc[idx, 'h2h_home_wins'] = home_wins
                df.loc[idx, 'h2h_total_games'] = len(prev_games)
        
        # H2H win rate
        df['h2h_home_win_pct'] = df.apply(
            lambda x: x['h2h_home_wins'] / x['h2h_total_games'] if x['h2h_total_games'] > 0 else 0.5,
            axis=1
        )
        
        return df
    
    def add_venue_splits(self, df):
        """Add home/away performance splits"""
        
        df = df.sort_values('game_date').copy()
        
        # Home team home record
        home_games = df.copy()
        home_games['home_record'] = home_games['home_won_last']
        df['home_home_win_pct'] = df.groupby('home_team_id')['home_record'].transform(
            lambda x: x.rolling(window=10, min_periods=1).mean().shift(1)
        ).fillna(0.5)
        
        # Away team away record
        away_games = df.copy()
        away_games['away_record'] = away_games['away_won_last']
        df['away_away_win_pct'] = df.groupby('away_team_id')['away_record'].transform(
            lambda x: x.rolling(window=10, min_periods=1).mean().shift(1)
        ).fillna(0.5)
        
        return df
    
    def add_temporal_features(self, df):
        """Add temporal features (month, day of week, season progression)"""
        
        df['month'] = df['game_date'].dt.month
        df['day_of_week'] = df['game_date'].dt.dayofweek
        
        # Season progression (days since season start, normalized)
        df['season'] = df['game_date'].dt.year
        df['season'] = df['season'].where(df['month'] >= 10, df['season'] - 1)
        
        df['season_day'] = df.groupby('season')['game_date'].transform(
            lambda x: (x - x.min()).dt.days
        )
        
        return df
    
    def add_special_teams(self, df):
        """Add special teams statistics"""
        
        df = df.sort_values('game_date').copy()
        
        for prefix in ['home', 'away']:
            team_col = f'{prefix}_team_id'
            
            # Power play percentage
            pp_goals_col = f'{prefix}_pp_goals'
            pp_opps_col = f'{prefix}_pp_opps'
            
            if pp_goals_col in df.columns and pp_opps_col in df.columns:
                df[f'{prefix}_pp_pct'] = df.apply(
                    lambda x: x[pp_goals_col] / x[pp_opps_col] if x[pp_opps_col] > 0 else 0,
                    axis=1
                )
                
                # Rolling PP%
                df[f'{prefix}_pp_pct_l10'] = df.groupby(team_col)[f'{prefix}_pp_pct'].transform(
                    lambda x: x.rolling(window=10, min_periods=1).mean().shift(1)
                ).fillna(0)
        
        return df
    
    def add_elo_ratings(self, df):
        """
        Add Elo rating features for each team
        
        Features added:
        - home_elo: Current Elo rating of home team
        - away_elo: Current Elo rating of away team
        - elo_diff: Home Elo - Away Elo (with home advantage)
        - elo_prob: Predicted probability of home win from Elo
        
        IMPORTANT: Calculate in temporal order to avoid data leakage
        """
        from nhl_elo_rating import NHLEloRating
        
        # Sort by date to ensure temporal order
        df_sorted = df.sort_values('game_date').copy()
        
        # Initialize Elo system
        elo = NHLEloRating(k_factor=20, home_advantage=100, initial_rating=1500)
        
        # Storage for features
        home_elo_list = []
        away_elo_list = []
        elo_diff_list = []
        elo_prob_list = []
        
        # Process each game in chronological order
        for idx, row in df_sorted.iterrows():
            home_team = row['home_team_name']
            away_team = row['away_team_name']
            home_won = row['home_win']
            
            # Get current ratings BEFORE this game (no data leakage)
            home_elo_rating = elo.get_rating(home_team)
            away_elo_rating = elo.get_rating(away_team)
            
            # Calculate Elo prediction
            elo_prob = elo.predict(home_team, away_team)
            
            # Calculate difference (with home advantage already applied in predict)
            elo_diff = home_elo_rating - away_elo_rating
            
            # Store features
            home_elo_list.append(home_elo_rating)
            away_elo_list.append(away_elo_rating)
            elo_diff_list.append(elo_diff)
            elo_prob_list.append(elo_prob)
            
            # Update Elo ratings AFTER recording features
            elo.update(home_team, away_team, home_won)
        
        # Add features to dataframe (in sorted order)
        df_sorted['home_elo'] = home_elo_list
        df_sorted['away_elo'] = away_elo_list
        df_sorted['elo_diff'] = elo_diff_list
        df_sorted['elo_prob'] = elo_prob_list
        
        # Return in original order
        return df_sorted.sort_index()
    
    def finalize_dataset(self, df):
        """Clean up and prepare final dataset"""
        
        # Select feature columns
        exclude_cols = [
            'matchup', 'home_won_last', 'away_won_last', 
            'home_record', 'away_record', 'season'
        ]
        
        # Keep metadata and target
        metadata_cols = ['game_id', 'game_date', 'home_team_name', 'away_team_name']
        target_col = ['home_win']
        
        # Get all feature columns
        feature_cols = [col for col in df.columns 
                       if col not in metadata_cols + target_col + exclude_cols]
        
        # Final column order
        final_cols = metadata_cols + feature_cols + target_col
        final_df = df[final_cols].copy()
        
        # Replace inf with nan, then fill with 0
        final_df = final_df.replace([np.inf, -np.inf], np.nan)
        numeric_cols = final_df.select_dtypes(include=[np.number]).columns
        final_df[numeric_cols] = final_df[numeric_cols].fillna(0)
        
        # Drop rows with missing target
        final_df = final_df.dropna(subset=['home_win'])
        
        return final_df


def main():
    print("🏒 NHL Training Dataset Builder V3 - Enhanced Features")
    print("="*70)
    
    with NHLTrainingDatasetV3() as builder:
        # Build dataset
        df = builder.build_dataset()
        
        # Save
        output_path = Path("data/nhl_training_data_v3.csv")
        df.to_csv(output_path, index=False)
        
        print(f"\n💾 Dataset saved to: {output_path}")
        print(f"\n📊 Dataset Summary:")
        print(f"   Games: {len(df):,}")
        print(f"   Features: {len(df.columns) - 5}")  # Exclude metadata + target
        print(f"   Date range: {df['game_date'].min().date()} to {df['game_date'].max().date()}")
        print(f"   Home win rate: {df['home_win'].mean():.1%}")
        
        # Show feature categories
        feature_cols = [col for col in df.columns if col not in 
                       ['game_id', 'game_date', 'home_team_name', 'away_team_name', 'home_win']]
        
        print(f"\n🎯 Feature Categories:")
        categories = {
            'Elo ratings': len([c for c in feature_cols if 'elo' in c]),
            'Rolling stats (L3/L5/L10)': len([c for c in feature_cols if '_l' in c and any(x in c for x in ['_l3', '_l5', '_l10'])]),
            'Rest & fatigue': len([c for c in feature_cols if 'rest' in c or 'back_to_back' in c]),
            'Streaks & momentum': len([c for c in feature_cols if 'streak' in c or 'form' in c]),
            'Head-to-head': len([c for c in feature_cols if 'h2h' in c]),
            'Venue splits': len([c for c in feature_cols if 'home_win_pct' in c or 'away_win_pct' in c]),
            'Temporal': len([c for c in feature_cols if c in ['month', 'day_of_week', 'season_day']]),
            'Special teams': len([c for c in feature_cols if 'pp_' in c or 'pk_' in c]),
            'Base stats': len([c for c in feature_cols if not any(x in c for x in ['elo', '_l', 'rest', 'streak', 'form', 'h2h', 'win_pct', 'month', 'day', 'season', 'pp_', 'pk_'])])
        }
        
        for cat, count in categories.items():
            print(f"   {cat}: {count}")
        
        print(f"\n✅ Ready for model training!")


if __name__ == "__main__":
    main()
