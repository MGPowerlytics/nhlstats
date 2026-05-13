-- Governed dashboard PostgreSQL read-model views.
-- These views are the stable Streamlit dashboard boundary.

CREATE TABLE IF NOT EXISTS portfolio_value_snapshots (
    snapshot_hour_utc TIMESTAMP PRIMARY KEY,
    balance_dollars DOUBLE PRECISION,
    portfolio_value_dollars DOUBLE PRECISION,
    cumulative_deposits_dollars DOUBLE PRECISION DEFAULT 0.0,
    created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE portfolio_value_snapshots
    ADD COLUMN IF NOT EXISTS balance_dollars DOUBLE PRECISION;

ALTER TABLE portfolio_value_snapshots
    ADD COLUMN IF NOT EXISTS portfolio_value_dollars DOUBLE PRECISION;

ALTER TABLE portfolio_value_snapshots
    ADD COLUMN IF NOT EXISTS cumulative_deposits_dollars DOUBLE PRECISION DEFAULT 0.0;

ALTER TABLE portfolio_value_snapshots
    ADD COLUMN IF NOT EXISTS created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS bet_recommendations (
    bet_id VARCHAR PRIMARY KEY,
    sport VARCHAR NOT NULL,
    recommendation_date DATE NOT NULL,
    home_team VARCHAR NOT NULL,
    away_team VARCHAR NOT NULL,
    home_rating DOUBLE PRECISION,
    away_rating DOUBLE PRECISION,
    bet_on VARCHAR NOT NULL,
    elo_prob DOUBLE PRECISION NOT NULL,
    market_prob DOUBLE PRECISION NOT NULL,
    edge DOUBLE PRECISION NOT NULL,
    expected_value DOUBLE PRECISION,
    kelly_fraction DOUBLE PRECISION,
    confidence VARCHAR NOT NULL,
    yes_ask INTEGER,
    no_ask INTEGER,
    ticker VARCHAR,
    probability_source VARCHAR,
    evidence_state VARCHAR,
    evidence_state_reason VARCHAR,
    evidence_state_source_artifact VARCHAR,
    governance_status VARCHAR,
    clv_evidence_tier VARCHAR,
    calibration_evidence_tier VARCHAR,
    walk_forward_evidence_tier VARCHAR,
    approval_grade_evidence BOOLEAN DEFAULT FALSE,
    sizing_eligible BOOLEAN DEFAULT FALSE,
    abstain BOOLEAN DEFAULT FALSE,
    abstention_reason VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS sport VARCHAR;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS recommendation_date DATE;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS home_team VARCHAR;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS away_team VARCHAR;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS home_rating DOUBLE PRECISION;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS away_rating DOUBLE PRECISION;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS bet_on VARCHAR;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS elo_prob DOUBLE PRECISION;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS market_prob DOUBLE PRECISION;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS edge DOUBLE PRECISION;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS expected_value DOUBLE PRECISION;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS kelly_fraction DOUBLE PRECISION;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS confidence VARCHAR;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS yes_ask INTEGER;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS no_ask INTEGER;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS ticker VARCHAR;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS probability_source VARCHAR;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS evidence_state VARCHAR;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS evidence_state_reason VARCHAR;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS evidence_state_source_artifact VARCHAR;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS governance_status VARCHAR;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS clv_evidence_tier VARCHAR;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS calibration_evidence_tier VARCHAR;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS walk_forward_evidence_tier VARCHAR;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS approval_grade_evidence BOOLEAN DEFAULT FALSE;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS sizing_eligible BOOLEAN DEFAULT FALSE;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS abstain BOOLEAN DEFAULT FALSE;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS abstention_reason VARCHAR;

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_bet_recs_date_sport
    ON bet_recommendations (recommendation_date, sport);

DROP VIEW IF EXISTS dashboard_portfolio_v1;
DROP VIEW IF EXISTS dashboard_live_markets_v1;
DROP VIEW IF EXISTS dashboard_rankings_v1;
DROP VIEW IF EXISTS dashboard_calibration_v1;
DROP VIEW IF EXISTS dashboard_data_quality_v1;
DROP VIEW IF EXISTS dashboard_bet_detail_v1;

CREATE VIEW dashboard_portfolio_v1 AS
WITH bet_summary AS (
    SELECT
        COALESCE(SUM(profit_dollars) FILTER (
            WHERE LOWER(status) IN ('won', 'lost', 'settled', 'cancelled', 'canceled', 'void', 'settlement_pending')
        ), 0.0)::DOUBLE PRECISION AS realized_profit_dollars,
        COALESCE(SUM(cost_dollars) FILTER (
            WHERE LOWER(status) IN ('pending', 'open', 'placed')
        ), 0.0)::DOUBLE PRECISION AS open_risk_dollars,
        COUNT(*) FILTER (
            WHERE LOWER(status) IN ('won', 'lost', 'settled', 'cancelled', 'canceled', 'void', 'settlement_pending')
        )::INTEGER AS settled_bet_count,
        COUNT(*) FILTER (
            WHERE LOWER(status) IN ('pending', 'open', 'placed')
        )::INTEGER AS open_bet_count
    FROM placed_bets
)
SELECT
    pvs.snapshot_hour_utc,
    COALESCE(pvs.balance_dollars, 0.0)::DOUBLE PRECISION AS balance_dollars,
    COALESCE(pvs.portfolio_value_dollars, 0.0)::DOUBLE PRECISION AS portfolio_value_dollars,
    COALESCE(pvs.cumulative_deposits_dollars, 0.0)::DOUBLE PRECISION AS cumulative_deposits_dollars,
    bs.realized_profit_dollars,
    bs.open_risk_dollars,
    bs.settled_bet_count,
    bs.open_bet_count,
    CASE
        WHEN COALESCE(pvs.cumulative_deposits_dollars, 0.0) = 0.0 THEN NULL
        ELSE (
            pvs.portfolio_value_dollars - pvs.cumulative_deposits_dollars
        ) / pvs.cumulative_deposits_dollars
    END::DOUBLE PRECISION AS roi,
    COALESCE(pvs.created_at_utc, pvs.snapshot_hour_utc)::TIMESTAMP AS created_at_utc
FROM portfolio_value_snapshots pvs
CROSS JOIN bet_summary bs;

CREATE VIEW dashboard_live_markets_v1 AS
WITH latest_recommendations AS (
    SELECT DISTINCT ON (ticker)
        bet_id,
        ticker,
        edge,
        expected_value,
        confidence,
        created_at
    FROM bet_recommendations
    WHERE ticker IS NOT NULL
      AND ticker <> ''
    ORDER BY ticker, created_at DESC NULLS LAST, bet_id ASC
)
SELECT
    go.external_id AS market_external_id,
    ug.game_date,
    ug.commence_time,
    ug.home_team_name,
    ug.away_team_name,
    go.bookmaker,
    go.market_name,
    go.outcome_name,
    go.price::DOUBLE PRECISION AS price,
    go.last_update,
    lr.bet_id AS recommendation_bet_id,
    lr.edge::DOUBLE PRECISION AS edge,
    lr.expected_value::DOUBLE PRECISION AS expected_value,
    CASE
        WHEN UPPER(lr.confidence) IN ('HIGH', 'MEDIUM', 'LOW') THEN UPPER(lr.confidence)
        ELSE NULL
    END AS confidence,
    lr.ticker
FROM game_odds go
JOIN unified_games ug
    ON ug.game_id = go.game_id
LEFT JOIN latest_recommendations lr
    ON lr.ticker = go.external_id
WHERE go.external_id IS NOT NULL
  AND go.external_id <> ''
  AND ug.home_team_name IS NOT NULL
  AND ug.home_team_name <> ''
  AND ug.away_team_name IS NOT NULL
  AND ug.away_team_name <> ''
  AND go.bookmaker IS NOT NULL
  AND go.bookmaker <> ''
  AND go.market_name IS NOT NULL
  AND go.market_name <> ''
  AND go.outcome_name IS NOT NULL
  AND go.outcome_name <> '';

CREATE VIEW dashboard_rankings_v1 AS
SELECT
    UPPER(er.sport) AS sport,
    er.entity_type,
    er.entity_id,
    er.entity_name,
    er.rating::DOUBLE PRECISION AS rating,
    RANK() OVER (
        PARTITION BY UPPER(er.sport), er.entity_type
        ORDER BY er.rating DESC, er.entity_name ASC, er.entity_id ASC
    )::INTEGER AS rank,
    COALESCE(er.games_played, 0)::INTEGER AS games_played,
    er.valid_from,
    er.valid_to,
    er.created_at
FROM elo_ratings er
WHERE er.valid_to IS NULL
  AND er.entity_id IS NOT NULL
  AND er.entity_id <> ''
  AND er.entity_name IS NOT NULL
  AND er.entity_name <> '';

CREATE VIEW dashboard_calibration_v1 AS
WITH recommendation_outcomes AS (
    SELECT
        br.bet_id,
        br.elo_prob,
        br.market_prob,
        br.edge,
        br.expected_value,
        LOWER(pb.status) AS placed_status
    FROM bet_recommendations br
    LEFT JOIN placed_bets pb
        ON pb.bet_id = br.bet_id
    WHERE br.elo_prob BETWEEN 0.0 AND 1.0
),
bucketed AS (
    SELECT
        (LEAST(FLOOR(elo_prob * 10.0), 9.0) / 10.0)::DOUBLE PRECISION AS bucket_start,
        ((LEAST(FLOOR(elo_prob * 10.0), 9.0) + 1.0) / 10.0)::DOUBLE PRECISION AS bucket_end,
        elo_prob,
        market_prob,
        edge,
        expected_value,
        placed_status
    FROM recommendation_outcomes
)
SELECT
    bucket_start,
    bucket_end,
    COUNT(*)::INTEGER AS prediction_count,
    AVG(elo_prob)::DOUBLE PRECISION AS avg_elo_prob,
    AVG(market_prob)::DOUBLE PRECISION AS avg_market_prob,
    CASE
        WHEN COUNT(*) FILTER (WHERE placed_status IN ('won', 'lost')) = 0 THEN NULL
        ELSE (
            COUNT(*) FILTER (WHERE placed_status = 'won')::DOUBLE PRECISION
            / COUNT(*) FILTER (WHERE placed_status IN ('won', 'lost'))::DOUBLE PRECISION
        )
    END::DOUBLE PRECISION AS observed_win_rate,
    AVG(edge)::DOUBLE PRECISION AS avg_edge,
    AVG(expected_value)::DOUBLE PRECISION AS avg_expected_value,
    COUNT(*) FILTER (
        WHERE placed_status IN ('won', 'lost', 'settled', 'cancelled', 'canceled', 'void', 'settlement_pending')
    )::INTEGER AS settled_count,
    COUNT(*) FILTER (
        WHERE placed_status IS NULL
           OR placed_status NOT IN ('won', 'lost', 'settled', 'cancelled', 'canceled', 'void', 'settlement_pending')
    )::INTEGER AS unsettled_count
FROM bucketed
GROUP BY bucket_start, bucket_end
ORDER BY bucket_start;

CREATE VIEW dashboard_data_quality_v1 AS
WITH checked_at AS (
    SELECT CURRENT_TIMESTAMP::TIMESTAMP AS checked_at_utc
),
view_checks AS (
    SELECT
        view_name,
        EXISTS (
            SELECT 1
            FROM information_schema.views
            WHERE table_schema = CURRENT_SCHEMA()
              AND table_name = view_name
        ) AS view_exists
    FROM (
        VALUES
            ('dashboard_portfolio_v1'),
            ('dashboard_live_markets_v1'),
            ('dashboard_rankings_v1'),
            ('dashboard_calibration_v1'),
            ('dashboard_data_quality_v1'),
            ('dashboard_bet_detail_v1')
    ) AS required_views(view_name)
),
source_checks AS (
    SELECT
        'portfolio_value_snapshots_rows'::VARCHAR AS check_name,
        'portfolio_value_snapshots'::VARCHAR AS relation_name,
        'table'::VARCHAR AS relation_type,
        COUNT(*)::INTEGER AS row_count,
        MAX(created_at_utc)::TIMESTAMP AS freshness_timestamp,
        1440::INTEGER AS max_allowed_lag_minutes
    FROM portfolio_value_snapshots
    UNION ALL
    SELECT
        'game_odds_rows'::VARCHAR AS check_name,
        'game_odds'::VARCHAR AS relation_name,
        'table'::VARCHAR AS relation_type,
        COUNT(*)::INTEGER AS row_count,
        MAX(COALESCE(last_update, loaded_at))::TIMESTAMP AS freshness_timestamp,
        240::INTEGER AS max_allowed_lag_minutes
    FROM game_odds
    UNION ALL
    SELECT
        'bet_recommendations_rows'::VARCHAR AS check_name,
        'bet_recommendations'::VARCHAR AS relation_name,
        'table'::VARCHAR AS relation_type,
        COUNT(*)::INTEGER AS row_count,
        MAX(created_at)::TIMESTAMP AS freshness_timestamp,
        1440::INTEGER AS max_allowed_lag_minutes
    FROM bet_recommendations
    UNION ALL
    SELECT
        'elo_ratings_rows'::VARCHAR AS check_name,
        'elo_ratings'::VARCHAR AS relation_name,
        'table'::VARCHAR AS relation_type,
        COUNT(*)::INTEGER AS row_count,
        MAX(created_at)::TIMESTAMP AS freshness_timestamp,
        10080::INTEGER AS max_allowed_lag_minutes
    FROM elo_ratings
    WHERE valid_to IS NULL
)
SELECT
    (vc.view_name || '_exists')::VARCHAR AS check_name,
    vc.view_name::VARCHAR AS relation_name,
    'view'::VARCHAR AS relation_type,
    CASE WHEN vc.view_exists THEN 'pass' ELSE 'fail' END::VARCHAR AS status,
    NULL::INTEGER AS row_count,
    NULL::TIMESTAMP AS freshness_timestamp,
    NULL::INTEGER AS max_allowed_lag_minutes,
    NULL::INTEGER AS actual_lag_minutes,
    CASE
        WHEN vc.view_exists THEN 'Dashboard view exists'
        ELSE 'Dashboard view is missing'
    END::VARCHAR AS message,
    ca.checked_at_utc
FROM view_checks vc
CROSS JOIN checked_at ca
UNION ALL
SELECT
    sc.check_name,
    sc.relation_name,
    sc.relation_type,
    CASE
        WHEN sc.row_count = 0 THEN 'warn'
        WHEN sc.freshness_timestamp IS NULL THEN 'warn'
        WHEN EXTRACT(EPOCH FROM (ca.checked_at_utc - sc.freshness_timestamp)) / 60.0
             > sc.max_allowed_lag_minutes THEN 'warn'
        ELSE 'pass'
    END::VARCHAR AS status,
    sc.row_count,
    sc.freshness_timestamp,
    sc.max_allowed_lag_minutes,
    CASE
        WHEN sc.freshness_timestamp IS NULL THEN NULL
        ELSE GREATEST(
            FLOOR(EXTRACT(EPOCH FROM (ca.checked_at_utc - sc.freshness_timestamp)) / 60.0),
            0
        )::INTEGER
    END AS actual_lag_minutes,
    CASE
        WHEN sc.row_count = 0 THEN 'No source rows available'
        WHEN sc.freshness_timestamp IS NULL THEN 'Freshness timestamp unavailable'
        WHEN EXTRACT(EPOCH FROM (ca.checked_at_utc - sc.freshness_timestamp)) / 60.0
             > sc.max_allowed_lag_minutes THEN 'Source data is stale'
        ELSE 'Source data available'
    END::VARCHAR AS message,
    ca.checked_at_utc
FROM source_checks sc
CROSS JOIN checked_at ca;

CREATE VIEW dashboard_bet_detail_v1 AS
WITH odds_context AS (
    SELECT DISTINCT ON (go.external_id)
        go.external_id,
        go.outcome_name,
        ug.home_team_name,
        ug.away_team_name,
        go.last_update
    FROM game_odds go
    LEFT JOIN unified_games ug
        ON ug.game_id = go.game_id
    WHERE go.external_id IS NOT NULL
      AND go.external_id <> ''
    ORDER BY go.external_id, go.last_update DESC NULLS LAST, go.odds_id ASC
)
SELECT
    br.bet_id,
    br.recommendation_date::VARCHAR AS recommendation_date,
    pb.placed_time_utc,
    COALESCE(NULLIF(br.home_team, ''), oc.home_team_name) AS home_team,
    COALESCE(NULLIF(br.away_team, ''), oc.away_team_name) AS away_team,
    COALESCE(NULLIF(br.bet_on, ''), oc.outcome_name) AS bet_on,
    br.ticker,
    br.elo_prob::DOUBLE PRECISION AS elo_prob,
    br.market_prob::DOUBLE PRECISION AS market_prob,
    br.edge::DOUBLE PRECISION AS edge,
    COALESCE(br.expected_value, 0.0)::DOUBLE PRECISION AS expected_value,
    COALESCE(br.kelly_fraction, 0.0)::DOUBLE PRECISION AS kelly_fraction,
    UPPER(br.confidence) AS confidence,
    br.yes_ask::DOUBLE PRECISION AS yes_ask,
    br.no_ask::DOUBLE PRECISION AS no_ask,
    LOWER(pb.status) AS status,
    pb.cost_dollars::DOUBLE PRECISION AS cost_dollars,
    pb.payout_dollars::DOUBLE PRECISION AS payout_dollars,
    pb.profit_dollars::DOUBLE PRECISION AS profit_dollars,
    COALESCE(br.created_at, CURRENT_TIMESTAMP)::TIMESTAMP AS created_at
FROM bet_recommendations br
LEFT JOIN placed_bets pb
    ON pb.bet_id = br.bet_id
LEFT JOIN odds_context oc
    ON oc.external_id = br.ticker
WHERE br.bet_id IS NOT NULL
  AND br.bet_id <> ''
  AND br.recommendation_date IS NOT NULL
  AND COALESCE(NULLIF(br.home_team, ''), oc.home_team_name) IS NOT NULL
  AND COALESCE(NULLIF(br.home_team, ''), oc.home_team_name) <> ''
  AND COALESCE(NULLIF(br.away_team, ''), oc.away_team_name) IS NOT NULL
  AND COALESCE(NULLIF(br.away_team, ''), oc.away_team_name) <> ''
  AND COALESCE(NULLIF(br.bet_on, ''), oc.outcome_name) IS NOT NULL
  AND COALESCE(NULLIF(br.bet_on, ''), oc.outcome_name) <> ''
  AND br.elo_prob BETWEEN 0.0 AND 1.0
  AND br.market_prob BETWEEN 0.0 AND 1.0
  AND br.edge BETWEEN -1.0 AND 1.0
  AND COALESCE(br.kelly_fraction, 0.0) >= 0.0
  AND UPPER(br.confidence) IN ('HIGH', 'MEDIUM', 'LOW');
