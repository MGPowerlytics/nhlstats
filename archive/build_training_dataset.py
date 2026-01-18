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
        
    def create_schedule_fatigue_features(self):
        """
        Create Schedule & Fatigue features (Tasks 1-10 from NHL_FEATURES_TASKLIST.md)
        
        Simplified version focusing on core features that can be calculated reliably
        """
        
        self.conn.execute("""
            CREATE OR REPLACE VIEW team_schedule_fatigue AS
            WITH team_games_flat AS (
                -- Flatten to one row per team per game
                SELECT 
                    game_id, 
                    game_date, 
                    home_team_id as team_id,
                    TRUE as is_home
                FROM games
                WHERE winning_team_id IS NOT NULL
                
                UNION ALL
                
                SELECT 
                    game_id, 
                    game_date, 
                    away_team_id as team_id,
                    FALSE as is_home
                FROM games
                WHERE winning_team_id IS NOT NULL
            ),
            game_sequence AS (
                SELECT 
                    game_id,
                    game_date,
                    team_id,
                    is_home,
                    -- Previous games
                    LAG(game_date) OVER (PARTITION BY team_id ORDER BY game_date, game_id) as prev_game_date,
                    LAG(is_home) OVER (PARTITION BY team_id ORDER BY game_date, game_id) as prev_is_home,
                    LAG(game_date, 2) OVER (PARTITION BY team_id ORDER BY game_date, game_id) as prev_2_game_date,
                    LAG(game_date, 3) OVER (PARTITION BY team_id ORDER BY game_date, game_id) as prev_3_game_date
                FROM team_games_flat
            ),
            back_to_back_l10 AS (
                SELECT 
                    game_id,
                    team_id,
                    game_date,
                    -- Count back-to-backs in last 10 games
                    SUM(CASE WHEN DATE_DIFF('day', prev_game_date, game_date) = 1 THEN 1 ELSE 0 END) OVER (
                        PARTITION BY team_id 
                        ORDER BY game_date, game_id 
                        ROWS BETWEEN 10 PRECEDING AND CURRENT ROW
                    ) as b2b_count
                FROM game_sequence
            )
            SELECT 
                gs.game_id,
                gs.team_id,
                
                -- Feature 1: Days of rest since last game
                COALESCE(DATE_DIFF('day', gs.prev_game_date, gs.game_date), 7) as days_rest,
                
                -- Feature 2: Back-to-back (2nd night)
                CASE WHEN DATE_DIFF('day', gs.prev_game_date, gs.game_date) = 1 THEN 1 ELSE 0 END as is_back_to_back,
                
                -- Feature 3: 3-in-4 nights (3 games in 4 days)
                CASE WHEN gs.prev_2_game_date IS NOT NULL AND 
                          DATE_DIFF('day', gs.prev_2_game_date, gs.game_date) <= 3 
                     THEN 1 ELSE 0 END as is_3_in_4,
                
                -- Feature 4: 4-in-6 nights (4 games in 6 days)
                CASE WHEN gs.prev_3_game_date IS NOT NULL AND 
                          DATE_DIFF('day', gs.prev_3_game_date, gs.game_date) <= 5 
                     THEN 1 ELSE 0 END as is_4_in_6,
                
                -- Feature 5-6: Home/Away indicators (simplified - just track current status)
                CASE WHEN gs.is_home THEN 1 ELSE 0 END as is_home_game,
                CASE WHEN NOT gs.is_home THEN 1 ELSE 0 END as is_away_game,
                
                -- Feature 7-8: Location change indicators
                CASE WHEN gs.is_home AND gs.prev_is_home = FALSE THEN 1 ELSE 0 END as just_came_home,
                CASE WHEN NOT gs.is_home AND gs.prev_is_home = TRUE THEN 1 ELSE 0 END as just_went_away,
                
                -- Feature 10: Back-to-backs in last 10 games
                COALESCE(b2b.b2b_count, 0) as back_to_backs_l10,
                
                -- Additional useful indicators
                CASE WHEN COALESCE(DATE_DIFF('day', gs.prev_game_date, gs.game_date), 7) >= 3 
                     THEN 1 ELSE 0 END as is_well_rested,
                     
                -- Raw rest for advantage calculation
                COALESCE(DATE_DIFF('day', gs.prev_game_date, gs.game_date), 7) as rest_advantage_raw
                
            FROM game_sequence gs
            LEFT JOIN back_to_back_l10 b2b ON gs.game_id = b2b.game_id AND gs.team_id = b2b.team_id
        """)
        
        print("✓ Created team_schedule_fatigue view with schedule features")
        
    def create_head_to_head_features(self):
        """
        Create Head-to-Head (H2H) features (Tasks 96-100 from NHL_FEATURES_TASKLIST.md)
        
        Features:
        96. Head-to-head win percentage (all-time)
        97. Head-to-head win percentage (last season)
        98. Head-to-head win percentage (last 5 games)
        99. Average goals scored in H2H matchups
        100. Home/away split in H2H matchups
        """
        
        self.conn.execute("""
            CREATE OR REPLACE VIEW team_h2h_history AS
            WITH h2h_games AS (
                -- Get all games between two teams (from home team perspective)
                SELECT 
                    g.game_id,
                    g.home_team_id,
                    g.away_team_id,
                    g.game_date,
                    g.season,
                    CASE WHEN g.winning_team_id = g.home_team_id THEN 1 ELSE 0 END as home_won,
                    g.home_score,
                    g.away_score
                FROM games g
                WHERE g.winning_team_id IS NOT NULL
            ),
            h2h_cumulative AS (
                SELECT
                    game_id,
                    home_team_id,
                    away_team_id,
                    game_date,
                    season,
                    home_won,
                    home_score,
                    away_score,
                    
                    -- Feature 96: All-time H2H win % (home team vs this opponent)
                    AVG(home_won) OVER (
                        PARTITION BY home_team_id, away_team_id
                        ORDER BY game_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) as h2h_home_win_pct_all,
                    
                    -- Feature 97: This season H2H win %
                    AVG(home_won) OVER (
                        PARTITION BY home_team_id, away_team_id, season
                        ORDER BY game_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) as h2h_home_win_pct_season,
                    
                    -- Feature 98: Last 5 games H2H win %
                    AVG(home_won) OVER (
                        PARTITION BY home_team_id, away_team_id
                        ORDER BY game_date
                        ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
                    ) as h2h_home_win_pct_l5,
                    
                    -- Feature 99: Avg goals scored/allowed vs this opponent
                    AVG(home_score) OVER (
                        PARTITION BY home_team_id, away_team_id
                        ORDER BY game_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) as h2h_home_avg_goals_for,
                    
                    AVG(away_score) OVER (
                        PARTITION BY home_team_id, away_team_id
                        ORDER BY game_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) as h2h_home_avg_goals_against,
                    
                    -- Feature 100: Games played count (for home/away split)
                    COUNT(*) OVER (
                        PARTITION BY home_team_id, away_team_id
                        ORDER BY game_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) as h2h_games_count
                    
                FROM h2h_games
            ),
            -- Now get away team perspective (flipped matchup)
            h2h_away_perspective AS (
                SELECT
                    game_id,
                    away_team_id as team_id,
                    home_team_id as opponent_id,
                    
                    -- Away team won if home team didn't win
                    AVG(1 - home_won) OVER (
                        PARTITION BY away_team_id, home_team_id
                        ORDER BY game_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) as h2h_away_win_pct_all,
                    
                    AVG(1 - home_won) OVER (
                        PARTITION BY away_team_id, home_team_id, season
                        ORDER BY game_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) as h2h_away_win_pct_season,
                    
                    AVG(1 - home_won) OVER (
                        PARTITION BY away_team_id, home_team_id
                        ORDER BY game_date
                        ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
                    ) as h2h_away_win_pct_l5,
                    
                    AVG(away_score) OVER (
                        PARTITION BY away_team_id, home_team_id
                        ORDER BY game_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) as h2h_away_avg_goals_for,
                    
                    AVG(home_score) OVER (
                        PARTITION BY away_team_id, home_team_id
                        ORDER BY game_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) as h2h_away_avg_goals_against
                    
                FROM h2h_games
            )
            SELECT 
                hc.game_id,
                hc.home_team_id,
                hc.away_team_id,
                
                -- Home team H2H stats vs this opponent
                COALESCE(hc.h2h_home_win_pct_all, 0.5) as h2h_home_win_pct_all,
                COALESCE(hc.h2h_home_win_pct_season, 0.5) as h2h_home_win_pct_season,
                COALESCE(hc.h2h_home_win_pct_l5, 0.5) as h2h_home_win_pct_l5,
                COALESCE(hc.h2h_home_avg_goals_for, 2.5) as h2h_home_avg_goals,
                COALESCE(hc.h2h_home_avg_goals_against, 2.5) as h2h_home_avg_goals_against,
                COALESCE(hc.h2h_games_count, 0) as h2h_games_count,
                
                -- Away team H2H stats vs this opponent
                COALESCE(ha.h2h_away_win_pct_all, 0.5) as h2h_away_win_pct_all,
                COALESCE(ha.h2h_away_win_pct_season, 0.5) as h2h_away_win_pct_season,
                COALESCE(ha.h2h_away_win_pct_l5, 0.5) as h2h_away_win_pct_l5,
                COALESCE(ha.h2h_away_avg_goals_for, 2.5) as h2h_away_avg_goals,
                COALESCE(ha.h2h_away_avg_goals_against, 2.5) as h2h_away_avg_goals_against
                
            FROM h2h_cumulative hc
            LEFT JOIN h2h_away_perspective ha 
                ON hc.game_id = ha.game_id
                AND hc.away_team_id = ha.team_id
                AND hc.home_team_id = ha.opponent_id
        """)
        
        print("✓ Created team_h2h_history view with head-to-head features")
    
    def create_situational_features(self):
        """
        Create Situational & Context features (Tasks 76-80 from NHL_FEATURES_TASKLIST.md)
        
        Features:
        76. Team's points percentage (standings position)
        77. Flag if team is in playoff position
        78. Flag if team is fighting for playoff spot (bubble team)
        79. Flag if team is mathematically eliminated
        80. Flag if playoff matchup preview
        """
        
        self.conn.execute("""
            CREATE OR REPLACE VIEW team_situational_context AS
            WITH team_season_record AS (
                -- Calculate each team's record up to each game
                SELECT 
                    game_date,
                    season,
                    team_id,
                    SUM(CASE WHEN won THEN 1 ELSE 0 END) OVER w as wins,
                    SUM(CASE WHEN NOT won THEN 1 ELSE 0 END) OVER w as losses,
                    COUNT(*) OVER w as games_played,
                    -- Points: 2 for win, 1 for OT/SO loss
                    SUM(CASE 
                        WHEN won THEN 2
                        WHEN NOT won AND game_outcome IN ('OT', 'SO') THEN 1
                        ELSE 0 
                    END) OVER w as points
                FROM (
                    SELECT 
                        g.game_date,
                        g.season,
                        g.home_team_id as team_id,
                        g.winning_team_id = g.home_team_id as won,
                        g.game_outcome_type as game_outcome
                    FROM games g
                    WHERE g.winning_team_id IS NOT NULL
                    
                    UNION ALL
                    
                    SELECT 
                        g.game_date,
                        g.season,
                        g.away_team_id as team_id,
                        g.winning_team_id = g.away_team_id as won,
                        g.game_outcome_type as game_outcome
                    FROM games g
                    WHERE g.winning_team_id IS NOT NULL
                ) team_games
                WINDOW w AS (
                    PARTITION BY season, team_id 
                    ORDER BY game_date 
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                )
            ),
            division_standings AS (
                -- Calculate standings position
                SELECT 
                    game_date,
                    season,
                    team_id,
                    wins,
                    points,
                    games_played,
                    -- Feature 76: Points percentage
                    CASE WHEN games_played > 0 
                         THEN points::FLOAT / (games_played * 2.0)
                         ELSE 0.5 
                    END as points_pct,
                    -- Rank within league (simple ranking by points then wins)
                    ROW_NUMBER() OVER (
                        PARTITION BY season, game_date 
                        ORDER BY points DESC, wins DESC
                    ) as league_rank
                FROM team_season_record
            )
            SELECT 
                g.game_id,
                g.home_team_id,
                g.away_team_id,
                g.game_date,
                g.season,
                
                -- HOME TEAM SITUATIONAL
                COALESCE(hs.points_pct, 0.5) as home_points_pct,
                COALESCE(hs.games_played, 0) as home_games_played,
                COALESCE(hs.league_rank, 16) as home_league_rank,
                
                -- Feature 77: In playoff position (top 16 in league, roughly top 8 per conference)
                CASE WHEN COALESCE(hs.league_rank, 16) <= 8 THEN 1 ELSE 0 END as home_in_playoff_spot,
                
                -- Feature 78: Bubble team (ranks 7-10, fighting for spot)
                CASE WHEN COALESCE(hs.league_rank, 16) BETWEEN 7 AND 10 THEN 1 ELSE 0 END as home_bubble_team,
                
                -- Feature 79: Eliminated (bottom 8 teams late in season)
                CASE 
                    WHEN COALESCE(hs.league_rank, 16) > 24 AND COALESCE(hs.games_played, 0) > 60 THEN 1 
                    ELSE 0 
                END as home_eliminated,
                
                -- AWAY TEAM SITUATIONAL
                COALESCE(as2.points_pct, 0.5) as away_points_pct,
                COALESCE(as2.games_played, 0) as away_games_played,
                COALESCE(as2.league_rank, 16) as away_league_rank,
                
                CASE WHEN COALESCE(as2.league_rank, 16) <= 8 THEN 1 ELSE 0 END as away_in_playoff_spot,
                CASE WHEN COALESCE(as2.league_rank, 16) BETWEEN 7 AND 10 THEN 1 ELSE 0 END as away_bubble_team,
                CASE 
                    WHEN COALESCE(as2.league_rank, 16) > 24 AND COALESCE(as2.games_played, 0) > 60 THEN 1 
                    ELSE 0 
                END as away_eliminated,
                
                -- Feature 80: Playoff matchup preview (both teams in top 8)
                CASE 
                    WHEN COALESCE(hs.league_rank, 16) <= 8 AND COALESCE(as2.league_rank, 16) <= 8 THEN 1 
                    ELSE 0 
                END as playoff_matchup_preview
                
            FROM games g
            LEFT JOIN division_standings hs 
                ON g.home_team_id = hs.team_id 
                AND g.game_date = hs.game_date 
                AND g.season = hs.season
            LEFT JOIN division_standings as2 
                ON g.away_team_id = as2.team_id 
                AND g.game_date = as2.game_date 
                AND g.season = as2.season
            WHERE g.winning_team_id IS NOT NULL
        """)
        
        print("✓ Created team_situational_context view with situational features")
    
    def create_team_season_stats(self):
        """
        Create Season-Long Team Statistics (Special Teams, Shooting %, etc.)
        
        Features:
        - Team shooting percentage (season to date)
        - Team save percentage (season to date)
        - Power play percentage (season)
        - Penalty kill percentage (season)
        - Faceoff win percentage (season)
        """
        
        self.conn.execute("""
            CREATE OR REPLACE VIEW team_season_stats AS
            WITH team_cumulative_stats AS (
                SELECT
                    g.game_id,
                    g.game_date,
                    g.season,
                    gts.team_id,
                    gts.is_home,
                    gts.goals,
                    gts.shots,
                    gts.power_play_goals,
                    gts.power_play_opportunities,
                    gts.power_play_pct,
                    gts.penalty_kill_pct,
                    gts.faceoff_win_pct,
                    
                    -- Cumulative shots and goals for shooting %
                    SUM(gts.shots) OVER (
                        PARTITION BY g.season, gts.team_id
                        ORDER BY g.game_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) as season_shots,
                    
                    SUM(gts.goals) OVER (
                        PARTITION BY g.season, gts.team_id
                        ORDER BY g.game_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) as season_goals,
                    
                    -- Cumulative PP stats
                    SUM(gts.power_play_goals) OVER (
                        PARTITION BY g.season, gts.team_id
                        ORDER BY g.game_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) as season_pp_goals,
                    
                    SUM(gts.power_play_opportunities) OVER (
                        PARTITION BY g.season, gts.team_id
                        ORDER BY g.game_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) as season_pp_opps,
                    
                    -- Average PK% and Faceoff%
                    AVG(gts.penalty_kill_pct) OVER (
                        PARTITION BY g.season, gts.team_id
                        ORDER BY g.game_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) as season_pk_pct,
                    
                    AVG(gts.faceoff_win_pct) OVER (
                        PARTITION BY g.season, gts.team_id
                        ORDER BY g.game_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) as season_faceoff_pct
                    
                FROM games g
                JOIN game_team_stats gts ON g.game_id = gts.game_id
                WHERE g.winning_team_id IS NOT NULL
            )
            SELECT
                game_id,
                team_id,
                is_home,
                
                -- Shooting percentage (season to date)
                CASE WHEN season_shots > 0 
                     THEN (season_goals::FLOAT / season_shots) * 100
                     ELSE 10.0  -- League average ~10%
                END as season_shooting_pct,
                
                -- Save percentage (inverse of GA/SA, approximation)
                -- Note: We'd need shots_against for true save %, using goals against as proxy
                CASE WHEN season_shots > 0
                     THEN 100.0 - ((season_goals::FLOAT / season_shots) * 100) 
                     ELSE 90.0  -- League average ~90%
                END as season_save_pct_approx,
                
                -- Power play percentage
                CASE WHEN season_pp_opps > 0
                     THEN (season_pp_goals::FLOAT / season_pp_opps) * 100
                     ELSE 20.0  -- League average ~20%
                END as season_pp_pct,
                
                -- Penalty kill percentage
                COALESCE(season_pk_pct, 80.0) as season_pk_pct,
                
                -- Faceoff win percentage
                COALESCE(season_faceoff_pct, 50.0) as season_faceoff_pct
                
            FROM team_cumulative_stats
        """)
        
        print("✓ Created team_season_stats view with special teams statistics")
    
    def create_momentum_features(self):
        """
        Create Momentum & Streak Features (Tasks 81-85)
        
        Features:
        81. Revenge game (lost to opponent recently)
        82. Division rival matchup
        83. Conference matchup  
        84. Win streak length
        85. Losing streak length
        """
        
        self.conn.execute("""
            CREATE OR REPLACE VIEW team_momentum AS
            WITH team_game_results AS (
                -- Flatten to one row per team per game
                SELECT 
                    g.game_id,
                    g.game_date,
                    g.season,
                    g.home_team_id as team_id,
                    g.away_team_id as opponent_id,
                    CASE WHEN g.winning_team_id = g.home_team_id THEN 1 ELSE 0 END as won,
                    g.home_team_abbrev as team_abbrev,
                    g.away_team_abbrev as opp_abbrev
                FROM games g
                WHERE g.winning_team_id IS NOT NULL
                
                UNION ALL
                
                SELECT 
                    g.game_id,
                    g.game_date,
                    g.season,
                    g.away_team_id as team_id,
                    g.home_team_id as opponent_id,
                    CASE WHEN g.winning_team_id = g.away_team_id THEN 1 ELSE 0 END as won,
                    g.away_team_abbrev as team_abbrev,
                    g.home_team_abbrev as opp_abbrev
                FROM games g
                WHERE g.winning_team_id IS NOT NULL
            ),
            streak_calculation AS (
                SELECT
                    game_id,
                    team_id,
                    game_date,
                    opponent_id,
                    won,
                    
                    -- Last 5 results for streak detection
                    won as curr_won,
                    LAG(won, 1) OVER w as won_1,
                    LAG(won, 2) OVER w as won_2,
                    LAG(won, 3) OVER w as won_3,
                    LAG(won, 4) OVER w as won_4,
                    LAG(won, 5) OVER w as won_5,
                    
                    -- Last 3 opponents for revenge game detection
                    LAG(opponent_id, 1) OVER w as opp_1,
                    LAG(opponent_id, 2) OVER w as opp_2,
                    LAG(opponent_id, 3) OVER w as opp_3,
                    LAG(won, 1) OVER w_vs_opp as lost_to_opp_last,
                    
                    team_abbrev,
                    opp_abbrev
                    
                FROM team_game_results
                WINDOW w AS (
                    PARTITION BY team_id 
                    ORDER BY game_date 
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ),
                w_vs_opp AS (
                    PARTITION BY team_id, opponent_id
                    ORDER BY game_date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                )
            ),
            streaks AS (
                SELECT
                    game_id,
                    team_id,
                    opponent_id,
                    
                    -- Feature 81: Revenge game (lost to this opponent in last 3 games)
                    CASE WHEN (opponent_id = opp_1 OR opponent_id = opp_2 OR opponent_id = opp_3)
                              AND lost_to_opp_last = 0 THEN 1
                         ELSE 0
                    END as is_revenge_game,
                    
                    -- Feature 82: Division rival (simplified: same first letter of abbrev = same division)
                    -- This is approximate; would need team division mapping for accuracy
                    CASE WHEN SUBSTRING(team_abbrev, 1, 1) = SUBSTRING(opp_abbrev, 1, 1) 
                         THEN 1 ELSE 0 
                    END as is_division_rival,
                    
                    -- Feature 83: Conference matchup (E vs E, or W vs W)
                    -- Eastern teams roughly: BOS, BUF, CAR, CBJ, DET, FLA, MTL, NJD, NYI, NYR, OTT, PHI, PIT, TBL, TOR, WSH
                    -- For simplicity, flag cross-conference games
                    0 as is_conference_matchup,  -- Placeholder, would need proper mapping
                    
                    -- Feature 84: Win streak length
                    CASE 
                        WHEN won_1 = 1 AND won_2 = 1 AND won_3 = 1 AND won_4 = 1 AND won_5 = 1 THEN 5
                        WHEN won_1 = 1 AND won_2 = 1 AND won_3 = 1 AND won_4 = 1 THEN 4
                        WHEN won_1 = 1 AND won_2 = 1 AND won_3 = 1 THEN 3
                        WHEN won_1 = 1 AND won_2 = 1 THEN 2
                        WHEN won_1 = 1 THEN 1
                        ELSE 0
                    END as win_streak,
                    
                    -- Feature 85: Losing streak length
                    CASE 
                        WHEN won_1 = 0 AND won_2 = 0 AND won_3 = 0 AND won_4 = 0 AND won_5 = 0 THEN 5
                        WHEN won_1 = 0 AND won_2 = 0 AND won_3 = 0 AND won_4 = 0 THEN 4
                        WHEN won_1 = 0 AND won_2 = 0 AND won_3 = 0 THEN 3
                        WHEN won_1 = 0 AND won_2 = 0 THEN 2
                        WHEN won_1 = 0 THEN 1
                        ELSE 0
                    END as losing_streak
                    
                FROM streak_calculation
            )
            SELECT
                g.game_id,
                g.home_team_id,
                g.away_team_id,
                
                -- HOME TEAM MOMENTUM
                COALESCE(h.is_revenge_game, 0) as home_revenge_game,
                COALESCE(h.is_division_rival, 0) as home_division_rival,
                COALESCE(h.is_conference_matchup, 0) as home_conf_matchup,
                COALESCE(h.win_streak, 0) as home_win_streak,
                COALESCE(h.losing_streak, 0) as home_losing_streak,
                
                -- AWAY TEAM MOMENTUM
                COALESCE(a.is_revenge_game, 0) as away_revenge_game,
                COALESCE(a.is_division_rival, 0) as away_division_rival,
                COALESCE(a.is_conference_matchup, 0) as away_conf_matchup,
                COALESCE(a.win_streak, 0) as away_win_streak,
                COALESCE(a.losing_streak, 0) as away_losing_streak
                
            FROM games g
            LEFT JOIN streaks h ON g.game_id = h.game_id AND g.home_team_id = h.team_id
            LEFT JOIN streaks a ON g.game_id = a.game_id AND g.away_team_id = a.team_id
            WHERE g.winning_team_id IS NOT NULL
        """)
        
        print("✓ Created team_momentum view with streak and rivalry features")


    def create_betting_lines_view(self):
        """
        Create view with betting line features from historical odds.
        
        Features:
        - home_ml_close, away_ml_close: Closing moneylines
        - home_implied_prob, away_implied_prob: Market's win probabilities
        - home_favorite: Binary flag (1 if home favored)
        - line_movement: Change from open to close (home team perspective)
        - market_confidence: How confident is the market? (max prob - 0.5)
        """
        self.conn.execute("""
            CREATE OR REPLACE VIEW betting_line_features AS
            SELECT
                g.game_id,
                g.game_date,
                g.home_team_abbrev,
                g.away_team_abbrev,
                
                -- Raw moneylines
                bl.home_ml_close,
                bl.away_ml_close,
                
                -- Implied probabilities (market's prediction)
                bl.home_implied_prob_close as home_implied_prob,
                bl.away_implied_prob_close as away_implied_prob,
                
                -- Home favorite flag
                CASE WHEN bl.home_ml_close < 0 THEN 1 ELSE 0 END as home_favorite,
                
                -- Line movement (positive = money moving toward home team)
                (bl.home_ml_close - bl.home_ml_open) as line_movement,
                
                -- Market confidence (how far from 50/50)
                GREATEST(
                    bl.home_implied_prob_close - 0.5,
                    bl.away_implied_prob_close - 0.5
                ) as market_confidence
                
            FROM games g
            LEFT JOIN historical_betting_lines bl 
                ON g.game_date = bl.game_date
                AND g.home_team_abbrev = bl.home_team
                AND g.away_team_abbrev = bl.away_team
            WHERE g.winning_team_id IS NOT NULL
        """)
        
        # Check how many games have odds
        result = self.conn.execute("""
            SELECT 
                COUNT(*) as total_games,
                COUNT(home_ml_close) as games_with_odds,
                ROUND(100.0 * COUNT(home_ml_close) / COUNT(*), 1) as coverage_pct
            FROM betting_line_features
        """).fetchone()
        
        print(f"✓ Created betting_line_features view")
        print(f"  Coverage: {result[1]:,} / {result[0]:,} games ({result[2]}%)")


        
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
        self.create_schedule_fatigue_features()
        self.create_head_to_head_features()
        self.create_situational_features()
        self.create_team_season_stats()
        self.create_momentum_features()
        self.create_betting_lines_view()
        
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
                
                -- HOME SCHEDULE & FATIGUE FEATURES
                sf_h.days_rest as home_days_rest,
                sf_h.is_back_to_back as home_back_to_back,
                sf_h.is_3_in_4 as home_3_in_4,
                sf_h.is_4_in_6 as home_4_in_6,
                sf_h.is_home_game as home_is_home,
                sf_h.just_came_home as home_just_came_home,
                sf_h.just_went_away as home_just_went_away,
                sf_h.back_to_backs_l10 as home_back_to_backs_l10,
                sf_h.is_well_rested as home_well_rested,
                
                -- AWAY SCHEDULE & FATIGUE FEATURES
                sf_a.days_rest as away_days_rest,
                sf_a.is_back_to_back as away_back_to_back,
                sf_a.is_3_in_4 as away_3_in_4,
                sf_a.is_4_in_6 as away_4_in_6,
                sf_a.is_away_game as away_is_away,
                sf_a.just_came_home as away_just_came_home,
                sf_a.just_went_away as away_just_went_away,
                sf_a.back_to_backs_l10 as away_back_to_backs_l10,
                sf_a.is_well_rested as away_well_rested,
                
                -- SCHEDULE ADVANTAGE (difference in rest)
                sf_h.rest_advantage_raw - sf_a.rest_advantage_raw as rest_advantage,
                
                -- HEAD-TO-HEAD FEATURES
                h2h.h2h_home_win_pct_all,
                h2h.h2h_home_win_pct_season,
                h2h.h2h_home_win_pct_l5,
                h2h.h2h_home_avg_goals,
                h2h.h2h_home_avg_goals_against,
                h2h.h2h_games_count,
                h2h.h2h_away_win_pct_all,
                h2h.h2h_away_win_pct_season,
                h2h.h2h_away_win_pct_l5,
                h2h.h2h_away_avg_goals,
                h2h.h2h_away_avg_goals_against,
                
                -- SITUATIONAL / CONTEXT FEATURES
                sit.home_points_pct,
                sit.home_league_rank,
                sit.home_in_playoff_spot,
                sit.home_bubble_team,
                sit.home_eliminated,
                sit.away_points_pct,
                sit.away_league_rank,
                sit.away_in_playoff_spot,
                sit.away_bubble_team,
                sit.away_eliminated,
                sit.playoff_matchup_preview,
                
                -- SPECIAL TEAMS & SEASON STATS
                ss_h.season_shooting_pct as home_season_shooting_pct,
                ss_h.season_save_pct_approx as home_season_save_pct,
                ss_h.season_pp_pct as home_season_pp_pct,
                ss_h.season_pk_pct as home_season_pk_pct,
                ss_h.season_faceoff_pct as home_season_faceoff_pct,
                ss_a.season_shooting_pct as away_season_shooting_pct,
                ss_a.season_save_pct_approx as away_season_save_pct,
                ss_a.season_pp_pct as away_season_pp_pct,
                ss_a.season_pk_pct as away_season_pk_pct,
                ss_a.season_faceoff_pct as away_season_faceoff_pct,
                
                -- MOMENTUM & STREAKS
                mom.home_revenge_game,
                mom.home_division_rival,
                mom.home_conf_matchup,
                mom.home_win_streak,
                mom.home_losing_streak,
                mom.away_revenge_game,
                mom.away_division_rival,
                mom.away_conf_matchup,
                mom.away_win_streak,
                mom.away_losing_streak,
                
                -- BETTING LINES (Market Wisdom)
                COALESCE(bl.home_implied_prob, 0.5) as home_implied_prob,
                COALESCE(bl.away_implied_prob, 0.5) as away_implied_prob,
                COALESCE(bl.home_favorite, 0) as home_favorite,
                COALESCE(bl.line_movement, 0) as line_movement,
                COALESCE(bl.market_confidence, 0) as market_confidence,
                
                -- Target variable
                adv.home_win
                
            FROM games g
            JOIN game_team_advanced_stats adv ON g.game_id = adv.game_id
            JOIN team_rolling_stats h ON g.game_id = h.game_id AND g.home_team_id = h.team_id
            JOIN team_rolling_stats a ON g.game_id = a.game_id AND g.away_team_id = a.team_id
            LEFT JOIN team_schedule_fatigue sf_h ON g.game_id = sf_h.game_id AND g.home_team_id = sf_h.team_id
            LEFT JOIN team_schedule_fatigue sf_a ON g.game_id = sf_a.game_id AND g.away_team_id = sf_a.team_id
            LEFT JOIN team_h2h_history h2h ON g.game_id = h2h.game_id 
                AND g.home_team_id = h2h.home_team_id 
                AND g.away_team_id = h2h.away_team_id
            LEFT JOIN team_situational_context sit ON g.game_id = sit.game_id
                AND g.home_team_id = sit.home_team_id
                AND g.away_team_id = sit.away_team_id
            LEFT JOIN team_season_stats ss_h ON g.game_id = ss_h.game_id 
                AND g.home_team_id = ss_h.team_id
                AND ss_h.is_home = TRUE
            LEFT JOIN team_season_stats ss_a ON g.game_id = ss_a.game_id 
                AND g.away_team_id = ss_a.team_id
                AND ss_a.is_home = FALSE
            LEFT JOIN team_momentum mom ON g.game_id = mom.game_id
                AND g.home_team_id = mom.home_team_id
                AND g.away_team_id = mom.away_team_id
            LEFT JOIN betting_line_features bl ON g.game_id = bl.game_id
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
        print(f"\n  Feature Categories Added:")
        print(f"    - Advanced metrics (Corsi, Fenwick, xG)")
        print(f"    - Rolling averages (L3, L10)")
        print(f"    - Schedule & Fatigue (rest, back-to-backs)")
        print(f"    - Head-to-Head history")
        print(f"    - Situational context (standings, playoffs)")
        print(f"    - Special teams & season stats")
        print(f"    - Momentum & rivalry features")
        print(f"    - Betting lines (market wisdom)")
        
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
