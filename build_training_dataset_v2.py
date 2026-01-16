#!/usr/bin/env python3
"""
Build ML training dataset with offensive and defensive stats.
Includes Corsi/Fenwick FOR and AGAINST for each team.
"""

import duckdb
import pandas as pd
from pathlib import Path


class NHLTrainingDataset:
    def __init__(self, db_path="data/nhlstats.duckdb"):
        self.db_path = Path(db_path)
        self.conn = None
    
    def connect(self):
        self.conn = duckdb.connect(str(self.db_path))
        print(f"Connected to {self.db_path}")
    
    def close(self):
        if self.conn:
            self.conn.close()
    
    def build_training_dataset(self, min_date=None):
        """Build the full training dataset with rolling features"""
        
        print("\nBuilding NHL training dataset with offensive & defensive stats...")
        
        # Build the SQL query
        query = """
        WITH team_game_stats AS (
            -- Get per-game stats for each team
            SELECT 
                g.game_id,
                g.game_date,
                g.home_team_id as team_id,
                ht.team_name,
                -- Offensive stats (what this team generated)
                COUNT(CASE WHEN pe.type_desc_key IN ('shot-on-goal', 'missed-shot', 'blocked-shot') THEN 1 END) as corsi_for,
                COUNT(CASE WHEN pe.type_desc_key IN ('shot-on-goal', 'missed-shot') THEN 1 END) as fenwick_for,
                COUNT(CASE WHEN pe.type_desc_key = 'shot-on-goal' THEN 1 END) as shots_for,
                COUNT(CASE WHEN pe.type_desc_key = 'goal' THEN 1 END) as goals_for,
                -- Defensive stats (what this team allowed = opponent's offense)
                COUNT(CASE WHEN pe2.type_desc_key IN ('shot-on-goal', 'missed-shot', 'blocked-shot') THEN 1 END) as corsi_against,
                COUNT(CASE WHEN pe2.type_desc_key IN ('shot-on-goal', 'missed-shot') THEN 1 END) as fenwick_against,
                -- Goalie stats
                COALESCE(AVG(pgs.save_pct), 0) as save_pct
            FROM games g
            LEFT JOIN teams ht ON g.home_team_id = ht.team_id
            LEFT JOIN play_events pe ON g.game_id = pe.game_id AND pe.event_owner_team_id = g.home_team_id
            LEFT JOIN play_events pe2 ON g.game_id = pe2.game_id AND pe2.event_owner_team_id = g.away_team_id
            LEFT JOIN player_game_stats pgs ON g.game_id = pgs.game_id AND pgs.team_id = g.home_team_id AND pgs.shots_against IS NOT NULL
            WHERE g.winning_team_id IS NOT NULL
            GROUP BY g.game_id, g.game_date, g.home_team_id, ht.team_name
            
            UNION ALL
            
            SELECT 
                g.game_id,
                g.game_date,
                g.away_team_id as team_id,
                at.team_name,
                -- Offensive stats
                COUNT(CASE WHEN pe.type_desc_key IN ('shot-on-goal', 'missed-shot', 'blocked-shot') THEN 1 END) as corsi_for,
                COUNT(CASE WHEN pe.type_desc_key IN ('shot-on-goal', 'missed-shot') THEN 1 END) as fenwick_for,
                COUNT(CASE WHEN pe.type_desc_key = 'shot-on-goal' THEN 1 END) as shots_for,
                COUNT(CASE WHEN pe.type_desc_key = 'goal' THEN 1 END) as goals_for,
                -- Defensive stats
                COUNT(CASE WHEN pe2.type_desc_key IN ('shot-on-goal', 'missed-shot', 'blocked-shot') THEN 1 END) as corsi_against,
                COUNT(CASE WHEN pe2.type_desc_key IN ('shot-on-goal', 'missed-shot') THEN 1 END) as fenwick_against,
                -- Goalie stats
                COALESCE(AVG(pgs.save_pct), 0) as save_pct
            FROM games g
            LEFT JOIN teams at ON g.away_team_id = at.team_id
            LEFT JOIN play_events pe ON g.game_id = pe.game_id AND pe.event_owner_team_id = g.away_team_id
            LEFT JOIN play_events pe2 ON g.game_id = pe2.game_id AND pe2.event_owner_team_id = g.home_team_id
            LEFT JOIN player_game_stats pgs ON g.game_id = pgs.game_id AND pgs.team_id = g.away_team_id AND pgs.shots_against IS NOT NULL
            WHERE g.winning_team_id IS NOT NULL
            GROUP BY g.game_id, g.game_date, g.away_team_id, at.team_name
        ),
        rolling_stats AS (
            SELECT 
                game_id,
                game_date,
                team_id,
                team_name,
                
                -- Last 3 games
                AVG(corsi_for) OVER w3 as corsi_for_l3,
                AVG(corsi_against) OVER w3 as corsi_against_l3,
                AVG(fenwick_for) OVER w3 as fenwick_for_l3,
                AVG(fenwick_against) OVER w3 as fenwick_against_l3,
                AVG(shots_for) OVER w3 as shots_l3,
                AVG(goals_for) OVER w3 as goals_l3,
                AVG(save_pct) OVER w3 as save_pct_l3,
                
                -- Last 10 games
                AVG(corsi_for) OVER w10 as corsi_for_l10,
                AVG(corsi_against) OVER w10 as corsi_against_l10,
                AVG(fenwick_for) OVER w10 as fenwick_for_l10,
                AVG(fenwick_against) OVER w10 as fenwick_against_l10,
                AVG(shots_for) OVER w10 as shots_l10,
                AVG(goals_for) OVER w10 as goals_l10,
                AVG(save_pct) OVER w10 as save_pct_l10
                
            FROM team_game_stats
            WINDOW 
                w3 AS (PARTITION BY team_id ORDER BY game_date, game_id ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING),
                w10 AS (PARTITION BY team_id ORDER BY game_date, game_id ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING)
        )
        SELECT 
            g.game_id,
            g.game_date,
            ht.team_name as home_team_name,
            at.team_name as away_team_name,
            
            -- Home team offensive stats
            rs_h.corsi_for_l3 as home_corsi_for_l3,
            rs_h.fenwick_for_l3 as home_fenwick_for_l3,
            rs_h.shots_l3 as home_shots_l3,
            rs_h.goals_l3 as home_goals_l3,
            rs_h.save_pct_l3 as home_save_pct_l3,
            rs_h.corsi_for_l10 as home_corsi_for_l10,
            rs_h.fenwick_for_l10 as home_fenwick_for_l10,
            rs_h.shots_l10 as home_shots_l10,
            rs_h.goals_l10 as home_goals_l10,
            rs_h.save_pct_l10 as home_save_pct_l10,
            
            -- Home team defensive stats
            rs_h.corsi_against_l3 as home_corsi_against_l3,
            rs_h.fenwick_against_l3 as home_fenwick_against_l3,
            rs_h.corsi_against_l10 as home_corsi_against_l10,
            rs_h.fenwick_against_l10 as home_fenwick_against_l10,
            
            -- Away team offensive stats
            rs_a.corsi_for_l3 as away_corsi_for_l3,
            rs_a.fenwick_for_l3 as away_fenwick_for_l3,
            rs_a.shots_l3 as away_shots_l3,
            rs_a.goals_l3 as away_goals_l3,
            rs_a.save_pct_l3 as away_save_pct_l3,
            rs_a.corsi_for_l10 as away_corsi_for_l10,
            rs_a.fenwick_for_l10 as away_fenwick_for_l10,
            rs_a.shots_l10 as away_shots_l10,
            rs_a.goals_l10 as away_goals_l10,
            rs_a.save_pct_l10 as away_save_pct_l10,
            
            -- Away team defensive stats
            rs_a.corsi_against_l3 as away_corsi_against_l3,
            rs_a.fenwick_against_l3 as away_fenwick_against_l3,
            rs_a.corsi_against_l10 as away_corsi_against_l10,
            rs_a.fenwick_against_l10 as away_fenwick_against_l10,
            
            -- Target variable
            CASE WHEN g.winning_team_id = g.home_team_id THEN 1 ELSE 0 END as home_win
            
        FROM games g
        LEFT JOIN teams ht ON g.home_team_id = ht.team_id
        LEFT JOIN teams at ON g.away_team_id = at.team_id
        LEFT JOIN rolling_stats rs_h ON g.game_id = rs_h.game_id AND g.home_team_id = rs_h.team_id
        LEFT JOIN rolling_stats rs_a ON g.game_id = rs_a.game_id AND g.away_team_id = rs_a.team_id
        WHERE g.winning_team_id IS NOT NULL
            AND rs_h.corsi_for_l10 IS NOT NULL  -- Must have 10 games of history
            AND rs_a.corsi_for_l10 IS NOT NULL
        ORDER BY g.game_date, g.game_id
        """
        
        if min_date:
            query += f" AND g.game_date >= '{min_date}'"
        
        df = self.conn.execute(query).df()
        
        print(f"\n✓ Built training dataset:")
        print(f"  Total games: {len(df)}")
        print(f"  Features: {len(df.columns) - 5}")  # Exclude meta columns
        print(f"  Date range: {df.game_date.min()} to {df.game_date.max()}")
        print(f"  Home wins: {df.home_win.sum()} ({df.home_win.mean()*100:.1f}%)")
        
        return df


def main():
    builder = NHLTrainingDataset()
    builder.connect()
    
    try:
        df = builder.build_training_dataset()
        
        # Save
        output_file = Path("data/nhl_training_data.csv")
        df.to_csv(output_file, index=False)
        print(f"\n✅ Saved training dataset to {output_file}")
        
        # Show sample
        print(f"\n📊 Sample data:")
        print(df[['game_date', 'home_team_name', 'away_team_name', 'home_corsi_for_l3', 'home_corsi_against_l3', 'home_win']].head())
        
        print(f"\n📈 Feature list ({len(df.columns)} total):")
        for i, col in enumerate(df.columns, 1):
            print(f"  {i:2}. {col}")
        
    finally:
        builder.close()


if __name__ == "__main__":
    main()
