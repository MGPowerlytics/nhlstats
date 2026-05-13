-- Governed dashboard read model for actionable tennis predictions.

DROP VIEW IF EXISTS dashboard_tennis_predictions_v1;

CREATE VIEW dashboard_tennis_predictions_v1 AS
WITH latest_odds AS (
    SELECT DISTINCT ON (go.external_id)
        go.external_id,
        ug.commence_time
    FROM game_odds go
    JOIN unified_games ug
        ON ug.game_id = go.game_id
    WHERE go.external_id IS NOT NULL
      AND go.external_id <> ''
    ORDER BY go.external_id, go.last_update DESC NULLS LAST, go.odds_id ASC
)
SELECT
    br.bet_id,
    'TENNIS'::VARCHAR AS sport,
    br.recommendation_date,
    lo.commence_time,
    br.home_team,
    br.away_team,
    br.bet_on,
    br.ticker,
    br.elo_prob::DOUBLE PRECISION AS model_prob,
    br.market_prob::DOUBLE PRECISION AS market_prob,
    br.edge::DOUBLE PRECISION AS edge,
    br.expected_value::DOUBLE PRECISION AS expected_value,
    br.kelly_fraction::DOUBLE PRECISION AS kelly_fraction,
    CASE
        WHEN UPPER(br.confidence) IN ('HIGH', 'MEDIUM', 'LOW') THEN UPPER(br.confidence)
        ELSE 'LOW'
    END AS confidence,
    br.yes_ask,
    br.no_ask,
    br.created_at
FROM bet_recommendations br
LEFT JOIN latest_odds lo
    ON lo.external_id = br.ticker
WHERE UPPER(br.sport) = 'TENNIS'
  AND br.bet_id IS NOT NULL
  AND br.bet_id <> ''
  AND br.recommendation_date IS NOT NULL
  AND br.home_team IS NOT NULL
  AND br.home_team <> ''
  AND br.away_team IS NOT NULL
  AND br.away_team <> ''
  AND br.bet_on IS NOT NULL
  AND br.bet_on <> ''
  AND br.elo_prob BETWEEN 0.0 AND 1.0
  AND br.market_prob BETWEEN 0.0 AND 1.0
  AND br.edge >= 0.03
  AND br.edge <= 0.40;
