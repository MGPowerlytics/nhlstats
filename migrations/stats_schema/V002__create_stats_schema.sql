CREATE TABLE IF NOT EXISTS unified_games (
    game_id VARCHAR PRIMARY KEY,
    sport VARCHAR NOT NULL,
    game_date DATE NOT NULL,
    season INTEGER,
    status VARCHAR,
    home_team_id VARCHAR,
    home_team_name VARCHAR,
    away_team_id VARCHAR,
    away_team_name VARCHAR,
    home_score INTEGER,
    away_score INTEGER,
    commence_time TIMESTAMP,
    venue VARCHAR,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_game_stats (
    game_id VARCHAR NOT NULL,
    sport VARCHAR NOT NULL,
    team VARCHAR NOT NULL,
    opponent VARCHAR NOT NULL,
    is_home BOOLEAN NOT NULL,
    game_date DATE NOT NULL,
    season VARCHAR NOT NULL,
    points_for INTEGER,
    points_against INTEGER,
    won BOOLEAN,
    off_rating NUMERIC(6,2),
    def_rating NUMERIC(6,2),
    pace NUMERIC(6,2),
    margin INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, team),
    FOREIGN KEY (game_id) REFERENCES unified_games(game_id)
);

CREATE INDEX IF NOT EXISTS idx_tgs_sport_date ON team_game_stats (sport, game_date);
CREATE INDEX IF NOT EXISTS idx_tgs_team_date ON team_game_stats (team, game_date);
CREATE INDEX IF NOT EXISTS idx_tgs_sport_season ON team_game_stats (sport, season);

CREATE TABLE IF NOT EXISTS nba_team_game_stats_ext (
    game_id VARCHAR NOT NULL,
    team VARCHAR NOT NULL,
    fg_pct NUMERIC(5,4),
    fg3m INTEGER,
    fg3a INTEGER,
    fg3_pct NUMERIC(5,4),
    ast INTEGER,
    reb INTEGER,
    oreb INTEGER,
    dreb INTEGER,
    stl INTEGER,
    blk INTEGER,
    tov INTEGER,
    pf INTEGER,
    ts_pct NUMERIC(5,4),
    efg_pct NUMERIC(5,4),
    usage_pct NUMERIC(5,4),
    PRIMARY KEY (game_id, team),
    FOREIGN KEY (game_id, team) REFERENCES team_game_stats(game_id, team)
);

CREATE TABLE IF NOT EXISTS nhl_team_game_stats_ext (
    game_id VARCHAR NOT NULL,
    team VARCHAR NOT NULL,
    shots INTEGER,
    sog INTEGER,
    hits INTEGER,
    blocks INTEGER,
    pim INTEGER,
    faceoff_pct NUMERIC(5,4),
    pp_goals INTEGER,
    pp_opportunities INTEGER,
    pp_pct NUMERIC(5,4),
    pk_goals_against INTEGER,
    pk_opportunities INTEGER,
    pk_pct NUMERIC(5,4),
    shooting_pct NUMERIC(5,4),
    PRIMARY KEY (game_id, team),
    FOREIGN KEY (game_id, team) REFERENCES team_game_stats(game_id, team)
);

CREATE TABLE IF NOT EXISTS mlb_team_game_stats_ext (
    game_id VARCHAR NOT NULL,
    team VARCHAR NOT NULL,
    hits INTEGER,
    errors INTEGER,
    lob INTEGER,
    doubles INTEGER,
    triples INTEGER,
    home_runs INTEGER,
    rbi INTEGER,
    stolen_bases INTEGER,
    strikeouts INTEGER,
    walks INTEGER,
    at_bats INTEGER,
    obp NUMERIC(5,4),
    slg NUMERIC(5,4),
    ops NUMERIC(5,4),
    woba NUMERIC(5,4),
    era NUMERIC(6,2),
    PRIMARY KEY (game_id, team),
    FOREIGN KEY (game_id, team) REFERENCES team_game_stats(game_id, team)
);

CREATE TABLE IF NOT EXISTS nfl_team_game_stats_ext (
    game_id VARCHAR NOT NULL,
    team VARCHAR NOT NULL,
    passing_yards INTEGER,
    passing_tds INTEGER,
    passing_ints INTEGER,
    rushing_yards INTEGER,
    rushing_tds INTEGER,
    rushing_attempts INTEGER,
    total_yards INTEGER,
    turnovers INTEGER,
    third_down_conversions INTEGER,
    third_down_attempts INTEGER,
    third_down_pct NUMERIC(5,4),
    time_of_possession INTEGER,
    penalties INTEGER,
    penalty_yards INTEGER,
    sacks_allowed INTEGER,
    first_downs INTEGER,
    PRIMARY KEY (game_id, team),
    FOREIGN KEY (game_id, team) REFERENCES team_game_stats(game_id, team)
);

CREATE TABLE IF NOT EXISTS soccer_team_game_stats_ext (
    game_id VARCHAR NOT NULL,
    team VARCHAR NOT NULL,
    shots INTEGER,
    shots_on_target INTEGER,
    possession_pct NUMERIC(5,4),
    passes INTEGER,
    pass_accuracy NUMERIC(5,4),
    xg NUMERIC(6,3),
    xga NUMERIC(6,3),
    fouls INTEGER,
    yellow_cards INTEGER,
    red_cards INTEGER,
    corners INTEGER,
    offsides INTEGER,
    saves INTEGER,
    PRIMARY KEY (game_id, team),
    FOREIGN KEY (game_id, team) REFERENCES team_game_stats(game_id, team)
);

CREATE TABLE IF NOT EXISTS ncaab_team_game_stats_ext (
    game_id VARCHAR NOT NULL,
    team VARCHAR NOT NULL,
    fg_pct NUMERIC(5,4),
    fg3m INTEGER,
    fg3a INTEGER,
    fg3_pct NUMERIC(5,4),
    ast INTEGER,
    reb INTEGER,
    stl INTEGER,
    blk INTEGER,
    tov INTEGER,
    pf INTEGER,
    ts_pct NUMERIC(5,4),
    efg_pct NUMERIC(5,4),
    PRIMARY KEY (game_id, team),
    FOREIGN KEY (game_id, team) REFERENCES team_game_stats(game_id, team)
);

CREATE TABLE IF NOT EXISTS wncaab_team_game_stats_ext (
    game_id VARCHAR NOT NULL,
    team VARCHAR NOT NULL,
    fg_pct NUMERIC(5,4),
    fg3m INTEGER,
    fg3a INTEGER,
    fg3_pct NUMERIC(5,4),
    ast INTEGER,
    reb INTEGER,
    stl INTEGER,
    blk INTEGER,
    tov INTEGER,
    pf INTEGER,
    ts_pct NUMERIC(5,4),
    efg_pct NUMERIC(5,4),
    PRIMARY KEY (game_id, team),
    FOREIGN KEY (game_id, team) REFERENCES team_game_stats(game_id, team)
);

CREATE TABLE IF NOT EXISTS tennis_player_match_stats (
    game_id VARCHAR NOT NULL,
    player_name VARCHAR NOT NULL,
    aces INTEGER,
    double_faults INTEGER,
    first_serve_pct NUMERIC(5,4),
    first_serve_won_pct NUMERIC(5,4),
    second_serve_won_pct NUMERIC(5,4),
    break_points_saved INTEGER,
    break_points_faced INTEGER,
    winners INTEGER,
    unforced_errors INTEGER,
    sets_won INTEGER,
    games_won INTEGER,
    won BOOLEAN,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, player_name),
    FOREIGN KEY (game_id) REFERENCES unified_games(game_id)
);

CREATE INDEX IF NOT EXISTS idx_tpms_game_id ON tennis_player_match_stats (game_id);
CREATE INDEX IF NOT EXISTS idx_tpms_player ON tennis_player_match_stats (player_name);

CREATE TABLE IF NOT EXISTS bet_reconciliation_audit (
    audit_id SERIAL PRIMARY KEY,
    bet_id VARCHAR NOT NULL,
    field_changed VARCHAR NOT NULL,
    old_value TEXT,
    new_value TEXT,
    source VARCHAR NOT NULL,
    reconciled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reason TEXT,
    discrepancy_type VARCHAR,
    run_id VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_bra_bet_id ON bet_reconciliation_audit (bet_id);
CREATE INDEX IF NOT EXISTS idx_bra_reconciled_at ON bet_reconciliation_audit (reconciled_at);
