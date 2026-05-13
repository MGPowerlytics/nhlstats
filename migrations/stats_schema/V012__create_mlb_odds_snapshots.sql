-- Governed MLB odds snapshot store for ROI and CLV evidence.
-- Grain: one row per source snapshot, event, bookmaker, market, and outcome.

CREATE TABLE IF NOT EXISTS mlb_odds_snapshots (
    snapshot_id VARCHAR PRIMARY KEY,
    source VARCHAR NOT NULL,
    sport VARCHAR NOT NULL DEFAULT 'MLB',
    source_event_id VARCHAR NOT NULL,
    game_id VARCHAR NOT NULL,
    home_team VARCHAR NOT NULL,
    away_team VARCHAR NOT NULL,
    commence_time TIMESTAMP NOT NULL,
    requested_snapshot_at TIMESTAMP,
    source_snapshot_at TIMESTAMP NOT NULL,
    previous_snapshot_at TIMESTAMP,
    next_snapshot_at TIMESTAMP,
    snapshot_type VARCHAR NOT NULL DEFAULT 'intraday' CHECK (
        snapshot_type IN ('open', 'close', 'intraday')
    ),
    bookmaker_key VARCHAR NOT NULL,
    bookmaker_title VARCHAR,
    market_key VARCHAR NOT NULL,
    outcome_name VARCHAR NOT NULL,
    outcome_role VARCHAR NOT NULL CHECK (outcome_role IN ('home', 'away', 'unknown')),
    decimal_price DOUBLE PRECISION NOT NULL CHECK (decimal_price > 1.0),
    implied_probability DOUBLE PRECISION NOT NULL CHECK (
        implied_probability > 0.0 AND implied_probability < 1.0
    ),
    is_pregame BOOLEAN NOT NULL DEFAULT TRUE,
    raw_payload JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (
        source,
        source_event_id,
        source_snapshot_at,
        snapshot_type,
        bookmaker_key,
        market_key,
        outcome_role
    )
);

CREATE INDEX IF NOT EXISTS idx_mlb_odds_snapshots_game_snapshot
    ON mlb_odds_snapshots (game_id, source_snapshot_at);

CREATE INDEX IF NOT EXISTS idx_mlb_odds_snapshots_event_snapshot
    ON mlb_odds_snapshots (source_event_id, source_snapshot_at);

CREATE INDEX IF NOT EXISTS idx_mlb_odds_snapshots_closing_lookup
    ON mlb_odds_snapshots (game_id, outcome_role, commence_time, source_snapshot_at);
