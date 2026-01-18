-- NBA Stats Database Schema for DuckDB
-- Stores NBA games, boxscores, and play-by-play data

-- Games table: One row per game
CREATE TABLE IF NOT EXISTS games (
    game_id VARCHAR PRIMARY KEY,
    game_date DATE NOT NULL,
    season VARCHAR,
    game_status VARCHAR,
    home_team_id INTEGER,
    away_team_id INTEGER,
    home_team_name VARCHAR,
    away_team_name VARCHAR,
    home_score INTEGER,
    away_score INTEGER,
    period INTEGER,
    playoffs BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Player stats table: One row per player per game
CREATE TABLE IF NOT EXISTS player_stats (
    id INTEGER PRIMARY KEY,
    game_id VARCHAR NOT NULL,
    team_id INTEGER,
    player_id INTEGER,
    player_name VARCHAR,
    start_position VARCHAR,
    minutes VARCHAR,
    fgm INTEGER,  -- Field goals made
    fga INTEGER,  -- Field goals attempted
    fg_pct DOUBLE,
    fg3m INTEGER,  -- 3-pointers made
    fg3a INTEGER,  -- 3-pointers attempted
    fg3_pct DOUBLE,
    ftm INTEGER,  -- Free throws made
    fta INTEGER,  -- Free throws attempted
    ft_pct DOUBLE,
    oreb INTEGER,  -- Offensive rebounds
    dreb INTEGER,  -- Defensive rebounds
    reb INTEGER,   -- Total rebounds
    ast INTEGER,   -- Assists
    stl INTEGER,   -- Steals
    blk INTEGER,   -- Blocks
    turnover INTEGER,
    pf INTEGER,    -- Personal fouls
    pts INTEGER,   -- Points
    plus_minus INTEGER,
    FOREIGN KEY (game_id) REFERENCES games(game_id)
);

-- Team stats table: One row per team per game
CREATE TABLE IF NOT EXISTS team_stats (
    id INTEGER PRIMARY KEY,
    game_id VARCHAR NOT NULL,
    team_id INTEGER,
    team_name VARCHAR,
    team_abbreviation VARCHAR,
    fgm INTEGER,
    fga INTEGER,
    fg_pct DOUBLE,
    fg3m INTEGER,
    fg3a INTEGER,
    fg3_pct DOUBLE,
    ftm INTEGER,
    fta INTEGER,
    ft_pct DOUBLE,
    oreb INTEGER,
    dreb INTEGER,
    reb INTEGER,
    ast INTEGER,
    stl INTEGER,
    blk INTEGER,
    turnover INTEGER,
    pf INTEGER,
    pts INTEGER,
    plus_minus INTEGER,
    FOREIGN KEY (game_id) REFERENCES games(game_id)
);

-- Play-by-play events table
CREATE TABLE IF NOT EXISTS play_by_play (
    id INTEGER PRIMARY KEY,
    game_id VARCHAR NOT NULL,
    action_number INTEGER,
    period INTEGER,
    clock VARCHAR,
    time_actual TIMESTAMP,
    team_id INTEGER,
    player_id INTEGER,
    player_name VARCHAR,
    action_type VARCHAR,
    sub_type VARCHAR,
    description VARCHAR,
    score_home INTEGER,
    score_away INTEGER,
    shot_result VARCHAR,
    shot_distance INTEGER,
    shot_x DOUBLE,
    shot_y DOUBLE,
    assist_player_id INTEGER,
    assist_player_name VARCHAR,
    FOREIGN KEY (game_id) REFERENCES games(game_id)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_games_date ON games(game_date);
CREATE INDEX IF NOT EXISTS idx_games_season ON games(season);
CREATE INDEX IF NOT EXISTS idx_player_stats_game ON player_stats(game_id);
CREATE INDEX IF NOT EXISTS idx_player_stats_player ON player_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_team_stats_game ON team_stats(game_id);
CREATE INDEX IF NOT EXISTS idx_team_stats_team ON team_stats(team_id);
CREATE INDEX IF NOT EXISTS idx_pbp_game ON play_by_play(game_id);
CREATE INDEX IF NOT EXISTS idx_pbp_period ON play_by_play(game_id, period);
