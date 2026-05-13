-- Canonicalize elo_ratings for active/historical Elo snapshots.
ALTER TABLE elo_ratings
    ADD COLUMN IF NOT EXISTS entity_type VARCHAR NOT NULL DEFAULT 'team';

ALTER TABLE elo_ratings
    ALTER COLUMN valid_from TYPE TIMESTAMP USING valid_from::timestamp,
    ALTER COLUMN valid_from SET DEFAULT CURRENT_TIMESTAMP,
    ALTER COLUMN valid_to TYPE TIMESTAMP USING valid_to::timestamp;

DROP INDEX IF EXISTS idx_elo_ratings_lookup;
DROP INDEX IF EXISTS idx_elo_ratings_unique_active;

CREATE INDEX IF NOT EXISTS idx_elo_ratings_lookup
    ON elo_ratings (sport, entity_type, entity_id, valid_from);

CREATE UNIQUE INDEX IF NOT EXISTS idx_elo_ratings_unique_active
    ON elo_ratings (sport, entity_type, entity_id)
    WHERE valid_to IS NULL;
