CREATE TABLE IF NOT EXISTS games (
    game_id VARCHAR PRIMARY KEY,
    season INTEGER,
    game_type VARCHAR,
    game_date DATE,
    start_time_utc TIMESTAMP,
    venue VARCHAR,
    venue_location VARCHAR,
    home_team_id INTEGER,
    home_team_abbrev VARCHAR,
    home_team_name VARCHAR,
    away_team_id INTEGER,
    away_team_abbrev VARCHAR,
    away_team_name VARCHAR,
    home_score INTEGER,
    away_score INTEGER,
    winning_team_id INTEGER,
    losing_team_id INTEGER,
    game_outcome_type VARCHAR,
    game_state VARCHAR,
    period_count INTEGER
);

CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY,
    team_abbrev VARCHAR,
    team_name VARCHAR,
    team_common_name VARCHAR
);

CREATE TABLE IF NOT EXISTS mlb_games (
    game_id INTEGER PRIMARY KEY,
    game_date DATE,
    season INTEGER,
    game_type VARCHAR,
    home_team VARCHAR,
    away_team VARCHAR,
    home_score INTEGER,
    away_score INTEGER,
    status VARCHAR
);

CREATE TABLE IF NOT EXISTS nfl_games (
    game_id VARCHAR PRIMARY KEY,
    game_date DATE,
    season INTEGER,
    week INTEGER,
    game_type VARCHAR,
    home_team VARCHAR,
    away_team VARCHAR,
    home_score INTEGER,
    away_score INTEGER,
    status VARCHAR
);

CREATE TABLE IF NOT EXISTS epl_games (
    game_id VARCHAR PRIMARY KEY,
    game_date DATE,
    season VARCHAR,
    home_team VARCHAR,
    away_team VARCHAR,
    home_score INTEGER,
    away_score INTEGER,
    result VARCHAR
);

CREATE TABLE IF NOT EXISTS ligue1_games (
    game_id VARCHAR PRIMARY KEY,
    game_date DATE,
    season VARCHAR,
    home_team VARCHAR,
    away_team VARCHAR,
    home_score INTEGER,
    away_score INTEGER,
    result VARCHAR
);

CREATE TABLE IF NOT EXISTS tennis_games (
    game_id VARCHAR PRIMARY KEY,
    game_date DATE,
    season VARCHAR,
    tour VARCHAR,
    tournament VARCHAR,
    surface VARCHAR,
    winner VARCHAR,
    loser VARCHAR,
    score VARCHAR
);

CREATE TABLE IF NOT EXISTS ncaab_games (
    game_id VARCHAR PRIMARY KEY,
    game_date DATE,
    season INTEGER,
    home_team VARCHAR,
    away_team VARCHAR,
    home_score INTEGER,
    away_score INTEGER,
    is_neutral BOOLEAN
);

CREATE TABLE IF NOT EXISTS wncaab_games (
    game_id VARCHAR PRIMARY KEY,
    game_date DATE,
    season INTEGER,
    home_team VARCHAR,
    away_team VARCHAR,
    home_score INTEGER,
    away_score INTEGER,
    is_neutral BOOLEAN
);

CREATE TABLE IF NOT EXISTS unrivaled_games (
    game_id VARCHAR PRIMARY KEY,
    game_date DATE,
    season INTEGER,
    home_team VARCHAR,
    away_team VARCHAR,
    home_score INTEGER,
    away_score INTEGER,
    is_neutral BOOLEAN
);

CREATE TABLE IF NOT EXISTS cba_games (
    game_id VARCHAR PRIMARY KEY,
    game_date DATE,
    season INTEGER,
    home_team VARCHAR,
    away_team VARCHAR,
    home_score INTEGER,
    away_score INTEGER,
    is_neutral BOOLEAN,
    status VARCHAR
);

CREATE TABLE IF NOT EXISTS game_odds (
    odds_id VARCHAR PRIMARY KEY,
    game_id VARCHAR NOT NULL,
    bookmaker VARCHAR NOT NULL,
    market_name VARCHAR NOT NULL,
    outcome_name VARCHAR,
    price DECIMAL(10, 4) NOT NULL,
    line DECIMAL(10, 4),
    last_update TIMESTAMP,
    is_pregame BOOLEAN DEFAULT TRUE,
    external_id VARCHAR,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS diagnostic_results (
    id SERIAL PRIMARY KEY,
    run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sport TEXT NOT NULL,
    settled_bets INTEGER,
    wins INTEGER,
    losses INTEGER,
    roi FLOAT,
    real_clv FLOAT,
    p_value FLOAT,
    passes_gate BOOLEAN,
    avg_hours_before_game FLOAT,
    timing_roi_under_2hr FLOAT,
    timing_roi_over_8hr FLOAT,
    bets_with_closing_price INTEGER,
    bets_flagged_stale INTEGER,
    recommendation TEXT,
    elo_replay_divergence FLOAT
);

CREATE INDEX IF NOT EXISTS idx_diagnostic_results_sport_date
    ON diagnostic_results (sport, run_date);

CREATE TABLE IF NOT EXISTS placed_bets (
    bet_id VARCHAR PRIMARY KEY,
    sport VARCHAR,
    placed_date DATE,
    placed_time_utc TIMESTAMP,
    ticker VARCHAR,
    home_team VARCHAR,
    away_team VARCHAR,
    bet_on VARCHAR,
    side VARCHAR,
    contracts INTEGER,
    price_cents INTEGER,
    cost_dollars DOUBLE PRECISION,
    fees_dollars DOUBLE PRECISION,
    elo_prob DOUBLE PRECISION,
    market_prob DOUBLE PRECISION,
    edge DOUBLE PRECISION,
    expected_value DOUBLE PRECISION,
    kelly_fraction DOUBLE PRECISION,
    confidence VARCHAR,
    market_title VARCHAR,
    market_close_time_utc TIMESTAMP,
    opening_line_prob DOUBLE PRECISION,
    bet_line_prob DOUBLE PRECISION,
    closing_line_prob DOUBLE PRECISION,
    clv DOUBLE PRECISION,
    status VARCHAR,
    settled_date DATE,
    payout_dollars DOUBLE PRECISION,
    profit_dollars DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
