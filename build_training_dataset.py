"""
NHL ML Training Dataset Builder

Creates features for predicting game winners:
- Advanced metrics: Corsi, Fenwick, xG, high danger chances, save %
- Rolling windows: 3 games, 10 games
- Both home and away team features
- Additional features: player age, travel distance

Target: Home team win (binary classification)
"""

import duckdb
import pandas as pd
from pathlib import Path
from typing import Optional

class NHLTrainingDataset:
    """Build ML training dataset from DuckDB"""
    
    def __init__(self, db_path: str = "data/nhlstats.duckdb"):
        self.db_path = Path(db_path)
        self.conn = None
        
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures connection is always closed"""
        self.close()
        return False
        
    def connect(self):
        """Connect to DuckDB"""
        self.conn = duckdb.connect(str(self.db_path))
        print(f"Connected to {self.db_path}")
        
    def close(self):
        """Close connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
            
    def create_advanced_metrics_view(self):
        """
        Create view with advanced hockey metrics per game per team
        
        Metrics:
        - Corsi: All shot attempts (shots + blocks + misses)
        - Fenwick: Unblocked shot attempts (shots + misses) 
        - High Danger Chances: Shots from slot area
        - Save Percentage: Saves / Shots Against (for goalies)
        """
        
        # First, let's create a comprehensive game team stats view
        self.conn.execute("""
            CREATE OR REPLACE VIEW game_team_advanced_stats AS
            WITH shot_data AS (
                SELECT 
                    game_id,
                    event_owner_team_id as team_id,
                    -- Shot attempts (Corsi FOR)
                    COUNT(CASE WHEN type_desc_key IN ('shot-on-goal', 'missed-shot', 'blocked-shot') THEN 1 END) as corsi_for,
                    -- Unblocked shots (Fenwick FOR)
                    COUNT(CASE WHEN type_desc_key IN ('shot-on-goal', 'missed-shot') THEN 1 END) as fenwick_for,
                    -- Shots on goal
                    COUNT(CASE WHEN type_desc_key = 'shot-on-goal' THEN 1 END) as shots_for,
                    -- Goals
                    COUNT(CASE WHEN type_desc_key = 'goal' THEN 1 END) as goals_for,
                    -- High danger chances (shots from slot: x between -20 and 20, y > 55)
                    COUNT(CASE WHEN type_desc_key IN ('shot-on-goal', 'goal') 
                               AND x_coord IS NOT NULL 
                               AND ABS(x_coord) <= 20 
                               AND y_coord > 55 
                          THEN 1 END) as high_danger_chances_for
                FROM play_events
                WHERE event_owner_team_id IS NOT NULL
                GROUP BY game_id, event_owner_team_id
            ),
            goalie_stats AS (
                SELECT
                    game_id,
                    team_id,
                    SUM(shots_against) as shots_against,
                    SUM(saves) as saves,
                    AVG(save_pct) as save_pct
                FROM player_game_stats
                WHERE shots_against IS NOT NULL
                GROUP BY game_id, team_id
            )
            SELECT 
                g.game_id,
                g.game_date,
                g.home_team_id,
                g.away_team_id,
                ht.team_name as home_team_name,
                away_t.team_name as away_team_name,
                
                -- Home team OFFENSIVE stats (what home team generated)
                COALESCE(sd_h.corsi_for, 0) as home_corsi_for,
                COALESCE(sd_h.fenwick_for, 0) as home_fenwick_for,
                COALESCE(sd_h.shots_for, 0) as home_shots_for,
                COALESCE(sd_h.goals_for, 0) as home_goals_for,
                COALESCE(sd_h.high_danger_chances_for, 0) as home_hd_chances_for,
                
                -- Home team DEFENSIVE stats (what home team allowed = away team's offense)
                COALESCE(sd_a.corsi_for, 0) as home_corsi_against,
                COALESCE(sd_a.fenwick_for, 0) as home_fenwick_against,
                COALESCE(sd_a.shots_for, 0) as home_shots_against_from_plays,
                COALESCE(sd_a.goals_for, 0) as home_goals_against,
                COALESCE(gs_h.save_pct, 0) as home_save_pct,
                COALESCE(gs_h.shots_against, 0) as home_shots_against,
                
                -- Away team OFFENSIVE stats (what away team generated)
                COALESCE(sd_a.corsi_for, 0) as away_corsi_for,
                COALESCE(sd_a.fenwick_for, 0) as away_fenwick_for,
                COALESCE(sd_a.shots_for, 0) as away_shots_for,
                COALESCE(sd_a.goals_for, 0) as away_goals_for,
                COALESCE(sd_a.high_danger_chances_for, 0) as away_hd_chances_for,
                
                -- Away team DEFENSIVE stats (what away team allowed = home team's offense)
                COALESCE(sd_h.corsi_for, 0) as away_corsi_against,
                COALESCE(sd_h.fenwick_for, 0) as away_fenwick_against,
                COALESCE(sd_h.shots_for, 0) as away_shots_against_from_plays,
                COALESCE(sd_h.goals_for, 0) as away_goals_against,
                COALESCE(gs_a.save_pct, 0) as away_save_pct,
                COALESCE(gs_a.shots_against, 0) as away_shots_against,
                
                -- Outcome
                CASE WHEN g.winning_team_id = g.home_team_id THEN 1 ELSE 0 END as home_win
                
            FROM games g
            LEFT JOIN teams ht ON g.home_team_id = ht.team_id
            LEFT JOIN teams away_t ON g.away_team_id = away_t.team_id
            LEFT JOIN shot_data sd_h ON g.game_id = sd_h.game_id AND g.home_team_id = sd_h.team_id
            LEFT JOIN shot_data sd_a ON g.game_id = sd_a.game_id AND g.away_team_id = sd_a.team_id
            LEFT JOIN goalie_stats gs_h ON g.game_id = gs_h.game_id AND g.home_team_id = gs_h.team_id
            LEFT JOIN goalie_stats gs_a ON g.game_id = gs_a.game_id AND g.away_team_id = gs_a.team_id
            WHERE g.winning_team_id IS NOT NULL  -- Only completed games
            ORDER BY g.game_date, g.game_id
        """)
        
        print("✓ Created game_team_advanced_stats view")
        
    def create_rolling_features(self):
        """
        Create rolling average features for last 3 and last 10 games per team
        Now includes both FOR (offensive) and AGAINST (defensive) stats
        """
        
        self.conn.execute("""
            CREATE OR REPLACE VIEW team_rolling_stats AS
            WITH team_games AS (
                -- Flatten to one row per team per game
                SELECT game_id, game_date, home_team_id as team_id,
                       home_corsi_for as corsi_for,
                       home_corsi_against as corsi_against,
                       home_fenwick_for as fenwick_for,
                       home_fenwick_against as fenwick_against,
                       home_shots_for as shots_for,
                       home_goals_for as goals_for,
                       home_hd_chances_for as hd_chances_for,
                       home_save_pct as save_pct,
                       home_shots_against as shots_against
                FROM game_team_advanced_stats
                
                UNION ALL
                
                SELECT game_id, game_date, away_team_id as team_id,
                       away_corsi_for as corsi_for,
                       away_corsi_against as corsi_against,
                       away_fenwick_for as fenwick_for,
                       away_fenwick_against as fenwick_against,
                       away_shots_for as shots_for,
                       away_goals_for as goals_for,
                       away_hd_chances_for as hd_chances_for,
                       away_save_pct as save_pct,
                       away_shots_against as shots_against
                FROM game_team_advanced_stats
            )
            SELECT 
                game_id,
                game_date,
                team_id,
                
                -- Last 3 games averages
                AVG(corsi_for) OVER (
                    PARTITION BY team_id 
                    ORDER BY game_date, game_id 
                    ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
                ) as corsi_for_l3,
                
                AVG(corsi_against) OVER (
                    PARTITION BY team_id 
                    ORDER BY game_date, game_id 
                    ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
                ) as corsi_against_l3,
                
                AVG(fenwick_for) OVER (
                    PARTITION BY team_id 
                    ORDER BY game_date, game_id 
                    ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
                ) as fenwick_for_l3,
                
                AVG(fenwick_against) OVER (
                    PARTITION BY team_id 
                    ORDER BY game_date, game_id 
                    ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
                ) as fenwick_against_l3,
                
                AVG(shots_for) OVER (
                    PARTITION BY team_id 
                    ORDER BY game_date, game_id 
                    ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
                ) as shots_l3,
                
                AVG(goals_for) OVER (
                    PARTITION BY team_id 
                    ORDER BY game_date, game_id 
                    ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
                ) as goals_l3,
                
                AVG(hd_chances_for) OVER (
                    PARTITION BY team_id 
                    ORDER BY game_date, game_id 
                    ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
                ) as hd_chances_l3,
                
                AVG(save_pct) OVER (
                    PARTITION BY team_id 
                    ORDER BY game_date, game_id 
                    ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
                ) as save_pct_l3,
                
                -- Last 10 games averages
                AVG(corsi_for) OVER (
                    PARTITION BY team_id 
                    ORDER BY game_date, game_id 
                    ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING
                ) as corsi_for_l10,
                
                AVG(corsi_against) OVER (
                    PARTITION BY team_id 
                    ORDER BY game_date, game_id 
                    ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING
                ) as corsi_against_l10,
                
                AVG(fenwick_for) OVER (
                    PARTITION BY team_id 
                    ORDER BY game_date, game_id 
                    ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING
                ) as fenwick_for_l10,
                
                AVG(fenwick_against) OVER (
                    PARTITION BY team_id 
                    ORDER BY game_date, game_id 
                    ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING
                ) as fenwick_against_l10,
                
                AVG(shots_for) OVER (
                    PARTITION BY team_id 
                    ORDER BY game_date, game_id 
                    ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING
                ) as shots_l10,
                
                AVG(goals_for) OVER (
                    PARTITION BY team_id 
                    ORDER BY game_date, game_id 
                    ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING
                ) as goals_l10,
                
                AVG(hd_chances_for) OVER (
                    PARTITION BY team_id 
                    ORDER BY game_date, game_id 
                    ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING
                ) as hd_chances_l10,
                
                AVG(save_pct) OVER (
                    PARTITION BY team_id 
                    ORDER BY game_date, game_id 
                    ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING
                ) as save_pct_l10
                
            FROM team_games
            ORDER BY game_date, game_id, team_id
        """)
        
        print("✓ Created team_rolling_stats view")
        
    def build_training_dataset(self, min_date: Optional[str] = None) -> pd.DataFrame:
        """
        Build complete training dataset with all features
        
        Args:
            min_date: Minimum date to include (YYYY-MM-DD), defaults to all games
            
        Returns:
            DataFrame ready for ML training
        """
        
        # Ensure views are created
        self.create_advanced_metrics_view()
        self.create_rolling_features()
        
        where_clause = f"AND g.game_date >= '{min_date}'" if min_date else ""
        
        query = f"""
            SELECT 
                g.game_id,
                g.game_date,
                adv.home_team_name,
                adv.away_team_name,
                
                -- Home team rolling features (L3)
                h.corsi_for_l3 as home_corsi_for_l3,
                h.corsi_against_l3 as home_corsi_against_l3,
                h.fenwick_for_l3 as home_fenwick_for_l3,
                h.fenwick_against_l3 as home_fenwick_against_l3,
                h.shots_l3 as home_shots_l3,
                h.goals_l3 as home_goals_l3,
                h.hd_chances_l3 as home_hd_chances_l3,
                h.save_pct_l3 as home_save_pct_l3,
                
                -- Home team rolling features (L10)
                h.corsi_for_l10 as home_corsi_for_l10,
                h.corsi_against_l10 as home_corsi_against_l10,
                h.fenwick_for_l10 as home_fenwick_for_l10,
                h.fenwick_against_l10 as home_fenwick_against_l10,
                h.shots_l10 as home_shots_l10,
                h.goals_l10 as home_goals_l10,
                h.hd_chances_l10 as home_hd_chances_l10,
                h.save_pct_l10 as home_save_pct_l10,
                
                -- Away team rolling features (L3)
                a.corsi_for_l3 as away_corsi_for_l3,
                a.corsi_against_l3 as away_corsi_against_l3,
                a.fenwick_for_l3 as away_fenwick_for_l3,
                a.fenwick_against_l3 as away_fenwick_against_l3,
                a.shots_l3 as away_shots_l3,
                a.goals_l3 as away_goals_l3,
                a.hd_chances_l3 as away_hd_chances_l3,
                a.save_pct_l3 as away_save_pct_l3,
                
                -- Away team rolling features (L10)
                a.corsi_for_l10 as away_corsi_for_l10,
                a.corsi_against_l10 as away_corsi_against_l10,
                a.fenwick_for_l10 as away_fenwick_for_l10,
                a.fenwick_against_l10 as away_fenwick_against_l10,
                a.shots_l10 as away_shots_l10,
                a.goals_l10 as away_goals_l10,
                a.hd_chances_l10 as away_hd_chances_l10,
                a.save_pct_l10 as away_save_pct_l10,
                
                -- Target variable
                adv.home_win
                
            FROM games g
            JOIN game_team_advanced_stats adv ON g.game_id = adv.game_id
            JOIN team_rolling_stats h ON g.game_id = h.game_id AND g.home_team_id = h.team_id
            JOIN team_rolling_stats a ON g.game_id = a.game_id AND g.away_team_id = a.team_id
            WHERE h.corsi_for_l10 IS NOT NULL 
              AND a.corsi_for_l10 IS NOT NULL
              AND g.winning_team_id IS NOT NULL
            {where_clause}
            ORDER BY g.game_date, g.game_id
        """
        
        df = self.conn.execute(query).df()
        
        print(f"\n✓ Built training dataset:")
        print(f"  Total games: {len(df)}")
        print(f"  Features: {len(df.columns) - 5}")  # Exclude ID columns and target
        print(f"  Date range: {df['game_date'].min()} to {df['game_date'].max()}")
        print(f"  Home wins: {df['home_win'].sum()} ({100*df['home_win'].mean():.1f}%)")
        
        return df
        
    def get_dataset_summary(self) -> dict:
        """Get summary statistics of the training dataset"""
        
        summary = {}
        
        # Count games by team
        summary['games_by_team'] = self.conn.execute("""
            SELECT t.team_name, COUNT(*) as games
            FROM games g
            JOIN teams t ON g.home_team_id = t.team_id OR g.away_team_id = t.team_id
            WHERE g.winning_team_id IS NOT NULL
            GROUP BY t.team_name
            ORDER BY games DESC
        """).df()
        
        # Feature availability
        summary['feature_coverage'] = self.conn.execute("""
            SELECT 
                COUNT(*) as total_games,
                COUNT(h.corsi_l3) as has_l3_features,
                COUNT(h.corsi_l10) as has_l10_features
            FROM games g
            LEFT JOIN team_rolling_stats h ON g.game_id = h.game_id AND g.home_team_id = h.team_id
            WHERE g.winning_team_id IS NOT NULL
        """).fetchone()
        
        return summary


def main():
    """Example usage"""
    with NHLTrainingDataset() as builder:
        # Build full dataset
        df = builder.build_training_dataset()
        
        # Save to CSV
        output_file = Path("data/nhl_training_data.csv")
        df.to_csv(output_file, index=False)
        print(f"\n✅ Saved training dataset to {output_file}")
        
        # Show sample
        print("\n📊 Sample features:")
        print(df.head())
        
        # Show feature correlations with target
        print("\n📈 Feature correlation with home_win:")
        numeric_df = df.select_dtypes(include=['number'])
        correlations = numeric_df.corr()['home_win'].sort_values(ascending=False)
        print(correlations.head(10))


if __name__ == "__main__":
    main()
