-- Migration to create elo_ratings table for storing historical and current Elo ratings.
CREATE TABLE IF NOT EXISTS elo_ratings (
    rating_id SERIAL PRIMARY KEY,
    sport VARCHAR NOT NULL,
    entity_id VARCHAR NOT NULL,
    entity_name VARCHAR NOT NULL,
    rating DECIMAL(10,2) NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE,
    games_played INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_elo_ratings_lookup ON elo_ratings (sport, entity_id, valid_from);

-- Unique constraint to prevent duplicate active ratings
-- Using COALESCE for valid_to because UNIQUE constraints treat NULL as distinct
CREATE UNIQUE INDEX IF NOT EXISTS idx_elo_ratings_unique_active ON elo_ratings (sport, entity_id, valid_from);
