ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS source VARCHAR;

UPDATE placed_bets
SET source = COALESCE(source, 'system')
WHERE source IS NULL;
