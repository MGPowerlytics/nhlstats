-- Governed MLB predictive-modeling tables.
-- Grain and ownership:
--   * player-game tables: one row per player/pitcher per game
--   * rolling features: one row per player/window/split/as_of_date
--   * matchup/environment/travel/market/model tables: one row per explicit
--     pregame decision boundary so predictions are reproducible.

CREATE TABLE IF NOT EXISTS mlb_player_game_batting_stats (
    game_id VARCHAR NOT NULL,
    player_id VARCHAR NOT NULL,
    player_name VARCHAR NOT NULL,
    team VARCHAR NOT NULL,
    opponent VARCHAR,
    is_home BOOLEAN NOT NULL,
    batting_order INTEGER,
    bats VARCHAR,
    plate_appearances INTEGER,
    at_bats INTEGER,
    hits INTEGER,
    doubles INTEGER,
    triples INTEGER,
    home_runs INTEGER,
    walks INTEGER,
    strikeouts INTEGER,
    woba DOUBLE PRECISION,
    wrc_plus DOUBLE PRECISION,
    o_swing_pct DOUBLE PRECISION,
    z_contact_pct DOUBLE PRECISION,
    hard_hit_pct DOUBLE PRECISION,
    avg_exit_velocity DOUBLE PRECISION,
    avg_launch_angle DOUBLE PRECISION,
    whiff_rate DOUBLE PRECISION,
    csw_pct DOUBLE PRECISION,
    source VARCHAR NOT NULL,
    feature_version VARCHAR NOT NULL DEFAULT 'v1',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_mlb_batting_stats_player_date
    ON mlb_player_game_batting_stats (player_id, game_id);

CREATE TABLE IF NOT EXISTS mlb_player_game_pitching_stats (
    game_id VARCHAR NOT NULL,
    pitcher_id VARCHAR NOT NULL,
    pitcher_name VARCHAR NOT NULL,
    team VARCHAR NOT NULL,
    opponent VARCHAR,
    is_home BOOLEAN NOT NULL,
    is_starter BOOLEAN NOT NULL DEFAULT FALSE,
    throws VARCHAR,
    innings_pitched DOUBLE PRECISION,
    pitch_count INTEGER,
    batters_faced INTEGER,
    strikeouts INTEGER,
    walks INTEGER,
    home_runs_allowed INTEGER,
    earned_runs INTEGER,
    fip DOUBLE PRECISION,
    xfip DOUBLE PRECISION,
    siera DOUBLE PRECISION,
    k_bb_pct DOUBLE PRECISION,
    o_swing_pct DOUBLE PRECISION,
    z_contact_pct DOUBLE PRECISION,
    hard_hit_pct_allowed DOUBLE PRECISION,
    avg_exit_velocity_allowed DOUBLE PRECISION,
    whiff_rate DOUBLE PRECISION,
    csw_pct DOUBLE PRECISION,
    primary_pitch_type VARCHAR,
    primary_pitch_pct DOUBLE PRECISION,
    avg_velocity DOUBLE PRECISION,
    vertical_location_accuracy DOUBLE PRECISION,
    days_rest INTEGER,
    pitches_last_3_days INTEGER,
    pitches_last_5_days INTEGER,
    fatigue_velocity_penalty DOUBLE PRECISION,
    source VARCHAR NOT NULL,
    feature_version VARCHAR NOT NULL DEFAULT 'v1',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, pitcher_id)
);

CREATE INDEX IF NOT EXISTS idx_mlb_pitching_stats_pitcher_date
    ON mlb_player_game_pitching_stats (pitcher_id, game_id);

CREATE TABLE IF NOT EXISTS mlb_pitch_level_features (
    game_id VARCHAR NOT NULL,
    pitcher_id VARCHAR NOT NULL,
    batter_id VARCHAR NOT NULL,
    pitch_type VARCHAR NOT NULL,
    batter_side VARCHAR,
    pitcher_throw_side VARCHAR,
    pitch_count INTEGER NOT NULL DEFAULT 0,
    whiff_rate DOUBLE PRECISION,
    csw_pct DOUBLE PRECISION,
    z_contact_pct DOUBLE PRECISION,
    avg_vertical_location DOUBLE PRECISION,
    vertical_location_accuracy DOUBLE PRECISION,
    avg_velocity DOUBLE PRECISION,
    source VARCHAR NOT NULL,
    feature_version VARCHAR NOT NULL DEFAULT 'v1',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, pitcher_id, batter_id, pitch_type)
);

CREATE TABLE IF NOT EXISTS mlb_player_rolling_features (
    as_of_date DATE NOT NULL,
    player_id VARCHAR NOT NULL,
    player_name VARCHAR NOT NULL,
    team VARCHAR,
    role VARCHAR NOT NULL,
    window_name VARCHAR NOT NULL,
    handedness_split VARCHAR NOT NULL DEFAULT 'ALL',
    plate_appearances INTEGER,
    innings_pitched DOUBLE PRECISION,
    woba DOUBLE PRECISION,
    wrc_plus DOUBLE PRECISION,
    fip DOUBLE PRECISION,
    xfip DOUBLE PRECISION,
    siera DOUBLE PRECISION,
    k_bb_pct DOUBLE PRECISION,
    o_swing_pct DOUBLE PRECISION,
    z_contact_pct DOUBLE PRECISION,
    hard_hit_pct DOUBLE PRECISION,
    avg_exit_velocity DOUBLE PRECISION,
    avg_launch_angle DOUBLE PRECISION,
    whiff_rate DOUBLE PRECISION,
    csw_pct DOUBLE PRECISION,
    recency_weight DOUBLE PRECISION,
    source VARCHAR NOT NULL,
    feature_version VARCHAR NOT NULL DEFAULT 'v1',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (as_of_date, player_id, role, window_name, handedness_split)
);

CREATE TABLE IF NOT EXISTS mlb_environment_features (
    game_id VARCHAR PRIMARY KEY,
    game_date DATE NOT NULL,
    venue VARCHAR NOT NULL,
    park_factor_runs DOUBLE PRECISION,
    park_factor_hr DOUBLE PRECISION,
    park_factor_doubles_triples DOUBLE PRECISION,
    park_factor_singles DOUBLE PRECISION,
    altitude_ft DOUBLE PRECISION,
    temperature_f DOUBLE PRECISION,
    humidity_pct DOUBLE PRECISION,
    wind_speed_mph DOUBLE PRECISION,
    wind_direction_degrees DOUBLE PRECISION,
    hit_distance_adjustment_ft DOUBLE PRECISION,
    source VARCHAR NOT NULL,
    observed_at TIMESTAMP,
    feature_version VARCHAR NOT NULL DEFAULT 'v1',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mlb_travel_features (
    game_id VARCHAR NOT NULL,
    team VARCHAR NOT NULL,
    is_home BOOLEAN NOT NULL,
    previous_game_id VARCHAR,
    previous_game_date DATE,
    previous_venue VARCHAR,
    time_zones_crossed INTEGER NOT NULL DEFAULT 0,
    travel_direction VARCHAR NOT NULL DEFAULT 'none',
    west_to_east_penalty DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    circadian_advantage_hours DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    local_start_time TIME,
    days_rest INTEGER NOT NULL DEFAULT 2,
    source VARCHAR NOT NULL,
    feature_version VARCHAR NOT NULL DEFAULT 'v1',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, team)
);

CREATE TABLE IF NOT EXISTS mlb_matchup_features (
    game_id VARCHAR NOT NULL,
    side VARCHAR NOT NULL,
    home_team VARCHAR NOT NULL,
    away_team VARCHAR NOT NULL,
    as_of_ts TIMESTAMP NOT NULL,
    feature_version VARCHAR NOT NULL DEFAULT 'v1',
    feature_hash VARCHAR NOT NULL,
    feature_vector JSONB NOT NULL,
    feature_availability JSONB NOT NULL,
    abstention_reasons JSONB NOT NULL DEFAULT '[]'::JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, side, feature_version)
);

CREATE TABLE IF NOT EXISTS mlb_market_signals (
    market_signal_id VARCHAR PRIMARY KEY,
    game_id VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    outcome_name VARCHAR NOT NULL,
    snapshot_at TIMESTAMP NOT NULL,
    market_prob DOUBLE PRECISION NOT NULL,
    ticket_pct DOUBLE PRECISION,
    money_pct DOUBLE PRECISION,
    pro_edge DOUBLE PRECISION,
    line_move DOUBLE PRECISION,
    reverse_line_movement BOOLEAN NOT NULL DEFAULT FALSE,
    source VARCHAR NOT NULL,
    feature_version VARCHAR NOT NULL DEFAULT 'v1',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mlb_market_signals_game_snapshot
    ON mlb_market_signals (game_id, snapshot_at);

CREATE TABLE IF NOT EXISTS mlb_model_predictions (
    prediction_id VARCHAR PRIMARY KEY,
    model_version VARCHAR NOT NULL,
    game_id VARCHAR NOT NULL,
    market_name VARCHAR NOT NULL DEFAULT 'moneyline',
    outcome_name VARCHAR NOT NULL,
    run_date DATE NOT NULL,
    model_prob DOUBLE PRECISION NOT NULL,
    market_prob DOUBLE PRECISION,
    edge DOUBLE PRECISION,
    expected_value DOUBLE PRECISION,
    calibration_method VARCHAR,
    ece_at_train DOUBLE PRECISION,
    feature_hash VARCHAR NOT NULL,
    simulation_summary JSONB,
    abstain BOOLEAN NOT NULL DEFAULT FALSE,
    abstention_reason VARCHAR,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mlb_model_predictions_game_run
    ON mlb_model_predictions (game_id, run_date, model_version);

CREATE TABLE IF NOT EXISTS mlb_prop_predictions (
    prediction_id VARCHAR PRIMARY KEY,
    model_version VARCHAR NOT NULL,
    game_id VARCHAR NOT NULL,
    player_id VARCHAR NOT NULL,
    player_name VARCHAR NOT NULL,
    team VARCHAR,
    prop_type VARCHAR NOT NULL,
    line DOUBLE PRECISION,
    over_prob DOUBLE PRECISION NOT NULL,
    under_prob DOUBLE PRECISION NOT NULL,
    market_prob DOUBLE PRECISION,
    edge DOUBLE PRECISION,
    expected_value DOUBLE PRECISION,
    simulation_summary JSONB,
    abstain BOOLEAN NOT NULL DEFAULT FALSE,
    abstention_reason VARCHAR,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mlb_prop_predictions_game_player
    ON mlb_prop_predictions (game_id, player_id, prop_type);
