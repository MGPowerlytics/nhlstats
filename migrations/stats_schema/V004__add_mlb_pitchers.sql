
-- Add pitcher tracking to MLB games
ALTER TABLE mlb_games ADD COLUMN IF NOT EXISTS home_pitcher_id VARCHAR;
ALTER TABLE mlb_games ADD COLUMN IF NOT EXISTS away_pitcher_id VARCHAR;
ALTER TABLE mlb_games ADD COLUMN IF NOT EXISTS home_pitcher_name VARCHAR;
ALTER TABLE mlb_games ADD COLUMN IF NOT EXISTS away_pitcher_name VARCHAR;

-- Add pitcher tracking to unified games (useful for all sports but starting with MLB)
ALTER TABLE unified_games ADD COLUMN IF NOT EXISTS home_pitcher_id VARCHAR;
ALTER TABLE unified_games ADD COLUMN IF NOT EXISTS away_pitcher_id VARCHAR;
ALTER TABLE unified_games ADD COLUMN IF NOT EXISTS home_pitcher_name VARCHAR;
ALTER TABLE unified_games ADD COLUMN IF NOT EXISTS away_pitcher_name VARCHAR;
