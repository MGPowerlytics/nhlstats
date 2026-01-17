-- NHL DuckDB Schema for Machine Learning & Betting Analysis
-- Normalized structure optimized for feature engineering

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Games: Core game information
CREATE TABLE IF NOT EXISTS games (
    game_id VARCHAR PRIMARY KEY,
    season INTEGER NOT NULL,
    game_type INTEGER NOT NULL,  -- 2=regular, 3=playoffs
    game_date DATE NOT NULL,
    start_time_utc TIMESTAMP,
    
    -- Venue
    venue VARCHAR,
    venue_location VARCHAR,
    
    -- Teams
    home_team_id INTEGER NOT NULL,
    home_team_abbrev VARCHAR NOT NULL,
    home_team_name VARCHAR NOT NULL,
    away_team_id INTEGER NOT NULL,
    away_team_abbrev VARCHAR NOT NULL,
    away_team_name VARCHAR NOT NULL,
    
    -- Score
    home_score INTEGER,
    away_score INTEGER,
    
    -- Game outcome
    winning_team_id INTEGER,
    losing_team_id INTEGER,
    game_outcome_type VARCHAR,  -- REG, OT, SO
    
    -- State
    game_state VARCHAR,
    period_count INTEGER,
    
    -- Timestamps
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_games_date ON games(game_date);
CREATE INDEX IF NOT EXISTS idx_games_season ON games(season);
CREATE INDEX IF NOT EXISTS idx_games_home_team ON games(home_team_id);
CREATE INDEX IF NOT EXISTS idx_games_away_team ON games(away_team_id);


-- Teams: Team master data
CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY,
    team_abbrev VARCHAR NOT NULL,
    team_name VARCHAR NOT NULL,
    team_common_name VARCHAR,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- Players: Player master data
CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY,
    first_name VARCHAR,
    last_name VARCHAR,
    sweater_number INTEGER,
    position_code VARCHAR,
    shoots_catches VARCHAR,
    height_in_inches INTEGER,
    weight_in_pounds INTEGER,
    birth_date DATE,
    birth_city VARCHAR,
    birth_country VARCHAR,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================================
-- GAME STATISTICS
-- ============================================================================

-- Game Team Stats: Aggregated team performance per game
CREATE TABLE IF NOT EXISTS game_team_stats (
    game_id VARCHAR NOT NULL,
    team_id INTEGER NOT NULL,
    is_home BOOLEAN NOT NULL,
    
    -- Score
    goals INTEGER,
    
    -- Shots
    shots INTEGER,
    blocked_shots INTEGER,
    
    -- Special teams
    power_play_goals INTEGER,
    power_play_opportunities INTEGER,
    power_play_pct DECIMAL(5,2),
    penalty_kill_pct DECIMAL(5,2),
    
    -- Penalties
    pim INTEGER,  -- Penalty minutes
    
    -- Face-offs
    faceoff_win_pct DECIMAL(5,2),
    
    -- Hits & blocks
    hits INTEGER,
    
    PRIMARY KEY (game_id, team_id),
    FOREIGN KEY (game_id) REFERENCES games(game_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);


-- Player Game Stats: Player performance per game
CREATE TABLE IF NOT EXISTS player_game_stats (
    game_id VARCHAR NOT NULL,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    
    -- Position
    position VARCHAR,
    
    -- Skater stats
    goals INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    plus_minus INTEGER DEFAULT 0,
    shots INTEGER DEFAULT 0,
    hits INTEGER DEFAULT 0,
    blocked_shots INTEGER DEFAULT 0,
    pim INTEGER DEFAULT 0,
    toi_seconds INTEGER,  -- Time on ice in seconds
    power_play_goals INTEGER DEFAULT 0,
    power_play_points INTEGER DEFAULT 0,
    shorthanded_goals INTEGER DEFAULT 0,
    game_winning_goals INTEGER DEFAULT 0,
    faceoff_wins INTEGER DEFAULT 0,
    faceoff_attempts INTEGER DEFAULT 0,
    
    -- Goalie stats  
    shots_against INTEGER,
    goals_against INTEGER,
    saves INTEGER,
    save_pct DECIMAL(5,3),
    shutout BOOLEAN DEFAULT FALSE,
    toi_goalie_seconds INTEGER,
    
    PRIMARY KEY (game_id, player_id),
    FOREIGN KEY (game_id) REFERENCES games(game_id),
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

CREATE INDEX IF NOT EXISTS idx_player_stats_player ON player_game_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_player_stats_game ON player_game_stats(game_id);


-- ============================================================================
-- PLAY-BY-PLAY DATA
-- ============================================================================

-- Play Events: All in-game events
CREATE TABLE IF NOT EXISTS play_events (
    event_id INTEGER NOT NULL,
    game_id VARCHAR NOT NULL,
    
    -- Timing
    period INTEGER NOT NULL,
    period_type VARCHAR,  -- REG, OT, SO
    time_in_period VARCHAR,
    time_remaining VARCHAR,
    sort_order INTEGER,
    
    -- Event details
    type_code INTEGER NOT NULL,
    type_desc_key VARCHAR NOT NULL,
    
    -- Teams involved
    event_owner_team_id INTEGER,
    
    -- Scoring details (for goals)
    scoring_player_id INTEGER,
    assist1_player_id INTEGER,
    assist2_player_id INTEGER,
    shot_type VARCHAR,
    
    -- Penalty details
    penalty_player_id INTEGER,
    penalty_type VARCHAR,
    penalty_duration INTEGER,
    
    -- Location
    x_coord INTEGER,
    y_coord INTEGER,
    zone_code VARCHAR,
    
    -- Situation
    home_team_defending_side VARCHAR,
    away_score INTEGER,
    home_score INTEGER,
    
    PRIMARY KEY (game_id, event_id),
    FOREIGN KEY (game_id) REFERENCES games(game_id)
);

CREATE INDEX IF NOT EXISTS idx_events_game ON play_events(game_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON play_events(type_desc_key);


-- ============================================================================
-- SHIFTS DATA
-- ============================================================================

-- Player Shifts: Time on ice tracking
CREATE TABLE IF NOT EXISTS player_shifts (
    shift_id VARCHAR PRIMARY KEY,
    game_id VARCHAR NOT NULL,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    
    -- Shift details
    period INTEGER NOT NULL,
    shift_number INTEGER NOT NULL,
    start_time VARCHAR NOT NULL,
    end_time VARCHAR NOT NULL,
    duration VARCHAR NOT NULL,
    
    -- Event tracking
    event_number INTEGER,
    event_description VARCHAR,
    
    FOREIGN KEY (game_id) REFERENCES games(game_id),
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

CREATE INDEX IF NOT EXISTS idx_shifts_game ON player_shifts(game_id);
CREATE INDEX IF NOT EXISTS idx_shifts_player ON player_shifts(player_id);


-- ============================================================================
-- TRUESKILL RATING TABLES
-- ============================================================================

-- Player TrueSkill Ratings: Current skill ratings
CREATE TABLE IF NOT EXISTS player_trueskill_ratings (
    player_id INTEGER PRIMARY KEY,
    mu DOUBLE NOT NULL,
    sigma DOUBLE NOT NULL,
    skill_estimate DOUBLE NOT NULL,  -- mu - 3*sigma (conservative estimate)
    games_played INTEGER DEFAULT 0,
    last_updated TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES players(player_id)
);

CREATE INDEX IF NOT EXISTS idx_trueskill_skill ON player_trueskill_ratings(skill_estimate DESC);


-- Player TrueSkill History: Track rating changes over time
CREATE TABLE IF NOT EXISTS player_trueskill_history (
    player_id INTEGER NOT NULL,
    game_id VARCHAR NOT NULL,
    game_date DATE NOT NULL,
    mu_before DOUBLE NOT NULL,
    sigma_before DOUBLE NOT NULL,
    mu_after DOUBLE NOT NULL,
    sigma_after DOUBLE NOT NULL,
    toi_seconds INTEGER,
    team_won BOOLEAN NOT NULL,
    PRIMARY KEY (player_id, game_id),
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (game_id) REFERENCES games(game_id)
);

CREATE INDEX IF NOT EXISTS idx_trueskill_history_player ON player_trueskill_history(player_id, game_date);
CREATE INDEX IF NOT EXISTS idx_trueskill_history_game ON player_trueskill_history(game_id);


-- ============================================================================
-- ML FEATURE VIEWS (to be created later for analysis)
-- ============================================================================

-- These will be materialized views for common ML features:
-- - team_rolling_stats (last 5, 10, 20 games)
-- - head_to_head_history
-- - home_away_splits
-- - rest_days_impact
-- - player_injury_impact
-- - goalie_matchups
