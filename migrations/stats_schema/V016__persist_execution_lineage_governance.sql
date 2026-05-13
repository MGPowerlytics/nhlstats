-- Wave 4 execution-lineage hardening.
-- Persist executable-entry and close-line lineage on consuming evidence rows
-- while preserving dashboard_*_v1 compatibility.

ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS canonical_game_id VARCHAR;
ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS quote_price_cents INTEGER;
ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS quote_price_role VARCHAR;
ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS quote_source_system VARCHAR;
ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS quote_bookmaker VARCHAR;
ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS quote_observed_at TIMESTAMP;
ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS quote_loaded_at TIMESTAMP;
ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS quote_payload_ref VARCHAR;
ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS quote_freshness_result VARCHAR;
ALTER TABLE bet_recommendations
    ADD COLUMN IF NOT EXISTS quote_fallback_status VARCHAR;

ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS recommendation_id VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS recommendation_canonical_game_id VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS recommendation_market_ticker VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS recommendation_selection_key VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS recommendation_linkage_status VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS recommendation_linkage_basis VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS entry_price_cents INTEGER;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS entry_quote_role VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS entry_price_source VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS entry_quote_source_system VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS entry_quote_bookmaker VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS entry_quote_observed_at TIMESTAMP;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS entry_quote_loaded_at TIMESTAMP;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS entry_quote_payload_ref VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS entry_quote_freshness_result VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS entry_quote_fallback_status VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS close_quote_source VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS close_quote_at TIMESTAMP;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS close_quote_loaded_at TIMESTAMP;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS close_quote_payload_ref VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS close_price_role VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS close_freshness_result VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS selected_close_rule VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS selected_close_provenance VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS close_fallback_status VARCHAR;
ALTER TABLE placed_bets
    ADD COLUMN IF NOT EXISTS clv_source_type VARCHAR;

DROP VIEW IF EXISTS governed_evidence_record_v1;
DROP VIEW IF EXISTS governed_recommendation_execution_link_v1;
DROP VIEW IF EXISTS governed_clv_evidence_envelope_v1;

CREATE VIEW governed_evidence_record_v1 AS
WITH market_context AS (
    SELECT DISTINCT ON (go.external_id)
        go.odds_id::VARCHAR AS quote_payload_ref,
        go.external_id::VARCHAR AS market_ticker,
        ug.game_id::VARCHAR AS canonical_game_id,
        UPPER(ug.sport)::VARCHAR AS sport,
        LOWER(go.market_name)::VARCHAR AS market_name,
        go.outcome_name::VARCHAR AS outcome_name,
        go.bookmaker::VARCHAR AS quote_bookmaker,
        go.last_update::TIMESTAMP AS quote_observed_at,
        go.loaded_at::TIMESTAMP AS quote_loaded_at
    FROM game_odds go
    LEFT JOIN unified_games ug
        ON ug.game_id = go.game_id
    WHERE go.external_id IS NOT NULL
      AND go.external_id <> ''
    ORDER BY go.external_id, go.last_update DESC NULLS LAST, go.odds_id ASC
),
recommendation_context AS (
    SELECT
        br.*,
        COALESCE(br.canonical_game_id, mc.canonical_game_id)::VARCHAR AS resolved_canonical_game_id,
        mc.sport AS market_sport,
        mc.market_name,
        mc.outcome_name,
        mc.quote_bookmaker AS linked_quote_bookmaker,
        mc.quote_observed_at AS linked_quote_observed_at,
        mc.quote_loaded_at AS linked_quote_loaded_at,
        mc.quote_payload_ref AS linked_quote_payload_ref,
        mc.market_ticker AS linked_market_ticker,
        validation.evidence_state_scope AS validation_evidence_state_scope,
        validation.evidence_state AS validation_evidence_state,
        validation.evidence_state_reason AS validation_evidence_state_reason,
        validation.evidence_state_as_of AS validation_evidence_state_as_of,
        validation.evidence_state_source_artifact AS validation_evidence_state_source_artifact,
        validation.governance_status AS validation_governance_status,
        validation.descriptive_only_flag AS validation_descriptive_only_flag,
        validation.contamination_flag AS validation_contamination_flag,
        validation.contamination_reason AS validation_contamination_reason,
        validation.excluded_from_approval_flag AS validation_excluded_from_approval_flag,
        CASE
            WHEN br.ticker IS NULL OR br.ticker = '' THEN 'missing_market_ticker'
            WHEN COALESCE(br.canonical_game_id, mc.canonical_game_id) IS NULL THEN 'market_link_unresolved'
            ELSE NULL
        END::VARCHAR AS local_contamination_reason
    FROM bet_recommendations br
    LEFT JOIN market_context mc
        ON mc.market_ticker = br.ticker
    LEFT JOIN sport_validation_state_v1 validation
        ON validation.sport = UPPER(COALESCE(NULLIF(br.sport, ''), NULLIF(mc.sport, ''), 'UNKNOWN'))
)
SELECT
    UPPER(COALESCE(NULLIF(br.sport, ''), NULLIF(br.market_sport, ''), 'UNKNOWN'))::VARCHAR AS sport,
    CASE
        WHEN UPPER(COALESCE(NULLIF(br.sport, ''), NULLIF(br.market_sport, ''), 'UNKNOWN')) IN ('TENNIS', 'EPL', 'LIGUE1')
            THEN 'match_winner'
        ELSE COALESCE(NULLIF(br.market_name, ''), 'moneyline')
    END::VARCHAR AS market_type,
    'recommendation_rows'::VARCHAR AS cohort_type,
    'read_model'::VARCHAR AS evidence_dimension,
    br.resolved_canonical_game_id::VARCHAR AS canonical_game_id,
    NULLIF(br.ticker, '')::VARCHAR AS market_ticker,
    COALESCE(NULLIF(br.bet_on, ''), br.outcome_name)::VARCHAR AS selection_key,
    'bet_recommendations'::VARCHAR AS source_relation,
    br.bet_id::VARCHAR AS source_record_id,
    COALESCE(br.validation_evidence_state_scope, 'sport')::VARCHAR AS evidence_state_scope,
    COALESCE(br.evidence_state, br.validation_evidence_state, 'blocked')::VARCHAR AS evidence_state,
    COALESCE(
        br.abstention_reason,
        br.evidence_state_reason,
        br.validation_evidence_state_reason,
        br.local_contamination_reason,
        'Sport baseline missing from governed validation state.'
    )::VARCHAR AS evidence_state_reason,
    COALESCE(
        br.validation_evidence_state_as_of,
        TIMESTAMP '2026-05-12 00:00:00'
    ) AS evidence_state_as_of,
    COALESCE(
        br.evidence_state_source_artifact,
        br.validation_evidence_state_source_artifact,
        'docs/plan/2026-05-12-betting-pipeline-audit/evidence-readmodel-spec.md'
    )::VARCHAR AS evidence_state_source_artifact,
    COALESCE(br.governance_status, br.validation_governance_status, 'descriptive_only')::VARCHAR AS governance_status,
    COALESCE(br.validation_descriptive_only_flag, TRUE) AS descriptive_only_flag,
    CASE
        WHEN COALESCE(br.validation_contamination_flag, FALSE) THEN TRUE
        WHEN br.local_contamination_reason IS NOT NULL THEN TRUE
        ELSE FALSE
    END AS contamination_flag,
    CASE
        WHEN COALESCE(br.validation_contamination_flag, FALSE)
             AND br.local_contamination_reason IS NOT NULL
            THEN CONCAT(br.validation_contamination_reason, ';', br.local_contamination_reason)
        WHEN COALESCE(br.validation_contamination_flag, FALSE)
            THEN br.validation_contamination_reason
        ELSE br.local_contamination_reason
    END::VARCHAR AS contamination_reason,
    (
        COALESCE(br.validation_excluded_from_approval_flag, TRUE)
        OR br.local_contamination_reason IS NOT NULL
    ) AS excluded_from_approval_flag,
    br.created_at::TIMESTAMP AS observed_at,
    COALESCE(br.quote_loaded_at, br.linked_quote_loaded_at)::TIMESTAMP AS loaded_at,
    COALESCE(br.created_at, br.quote_observed_at, br.linked_quote_observed_at, br.quote_loaded_at, br.linked_quote_loaded_at)::TIMESTAMP AS last_updated_at,
    br.bet_id::VARCHAR AS recommendation_id,
    br.created_at::TIMESTAMP AS recommendation_created_at,
    'bet_recommendations'::VARCHAR AS recommendation_source_surface,
    COALESCE(br.probability_source, 'elo_prob')::VARCHAR AS probability_source,
    br.elo_prob::DOUBLE PRECISION AS calibrated_probability,
    br.market_prob::DOUBLE PRECISION AS market_probability,
    br.edge::DOUBLE PRECISION AS edge,
    COALESCE(br.expected_value, 0.0)::DOUBLE PRECISION AS expected_value,
    COALESCE(br.kelly_fraction, 0.0)::DOUBLE PRECISION AS kelly_fraction,
    UPPER(br.confidence)::VARCHAR AS confidence_label,
    COALESCE(
        br.quote_source_system,
        CASE
            WHEN br.linked_market_ticker IS NULL THEN 'quote_lineage_placeholder'
            ELSE 'game_odds'
        END
    )::VARCHAR AS quote_source_system,
    COALESCE(br.quote_bookmaker, br.linked_quote_bookmaker)::VARCHAR AS quote_bookmaker,
    COALESCE(br.quote_observed_at, br.linked_quote_observed_at)::TIMESTAMP AS quote_observed_at,
    COALESCE(br.quote_loaded_at, br.linked_quote_loaded_at)::TIMESTAMP AS quote_loaded_at,
    COALESCE(br.quote_payload_ref, br.linked_quote_payload_ref, br.ticker)::VARCHAR AS quote_payload_ref,
    CASE
        WHEN br.linked_market_ticker IS NULL
            THEN 'missing_market_quote'
        ELSE 'linked_market_quote'
    END::VARCHAR AS quote_lineage_status,
    COALESCE(br.quote_price_cents, br.yes_ask, br.no_ask)::INTEGER AS quote_price_cents,
    COALESCE(br.quote_price_role, 'executable')::VARCHAR AS quote_price_role,
    COALESCE(
        br.quote_freshness_result,
        CASE
            WHEN COALESCE(br.quote_observed_at, br.linked_quote_observed_at) IS NULL
                THEN 'missing_source_timestamp'
            ELSE 'fresh'
        END
    )::VARCHAR AS quote_freshness_result,
    COALESCE(
        br.quote_fallback_status,
        CASE
            WHEN br.quote_price_cents IS NOT NULL THEN 'direct_quote'
            WHEN COALESCE(br.yes_ask, br.no_ask) IS NOT NULL THEN 'payload_only_quote'
            ELSE 'missing_quote'
        END
    )::VARCHAR AS quote_fallback_status
FROM recommendation_context br
WHERE br.bet_id IS NOT NULL
  AND br.bet_id <> '';

CREATE VIEW governed_recommendation_execution_link_v1 AS
WITH market_context AS (
    SELECT DISTINCT ON (go.external_id)
        go.odds_id::VARCHAR AS quote_payload_ref,
        go.external_id::VARCHAR AS market_ticker,
        ug.game_id::VARCHAR AS canonical_game_id,
        UPPER(ug.sport)::VARCHAR AS sport,
        LOWER(go.market_name)::VARCHAR AS market_name,
        go.outcome_name::VARCHAR AS outcome_name,
        go.bookmaker::VARCHAR AS quote_bookmaker,
        go.last_update::TIMESTAMP AS quote_observed_at,
        go.loaded_at::TIMESTAMP AS quote_loaded_at
    FROM game_odds go
    LEFT JOIN unified_games ug
        ON ug.game_id = go.game_id
    WHERE go.external_id IS NOT NULL
      AND go.external_id <> ''
    ORDER BY go.external_id, go.last_update DESC NULLS LAST, go.odds_id ASC
),
latest_recommendations AS (
    SELECT DISTINCT ON (
        COALESCE(NULLIF(br.ticker, ''), ''),
        COALESCE(NULLIF(br.bet_on, ''), mc.outcome_name, ''),
        COALESCE(COALESCE(br.canonical_game_id, mc.canonical_game_id), '')
    )
        NULLIF(br.ticker, '')::VARCHAR AS market_ticker,
        COALESCE(br.canonical_game_id, mc.canonical_game_id)::VARCHAR AS canonical_game_id,
        COALESCE(NULLIF(br.bet_on, ''), mc.outcome_name)::VARCHAR AS selection_key,
        br.bet_id::VARCHAR AS recommendation_id,
        br.created_at::TIMESTAMP AS recommendation_created_at,
        br.quote_price_cents,
        br.quote_price_role,
        br.quote_source_system,
        br.quote_bookmaker,
        br.quote_observed_at,
        br.quote_loaded_at,
        br.quote_payload_ref,
        br.quote_freshness_result,
        br.quote_fallback_status
    FROM bet_recommendations br
    LEFT JOIN market_context mc
        ON mc.market_ticker = br.ticker
    WHERE br.bet_id IS NOT NULL
      AND br.bet_id <> ''
    ORDER BY
        COALESCE(NULLIF(br.ticker, ''), ''),
        COALESCE(NULLIF(br.bet_on, ''), mc.outcome_name, ''),
        COALESCE(COALESCE(br.canonical_game_id, mc.canonical_game_id), ''),
        br.created_at DESC NULLS LAST,
        br.bet_id ASC
),
execution_context AS (
    SELECT
        pb.*,
        mc.canonical_game_id,
        mc.sport AS market_sport,
        mc.market_name,
        mc.outcome_name,
        mc.quote_bookmaker,
        mc.quote_observed_at,
        mc.quote_loaded_at,
        mc.quote_payload_ref,
        mc.market_ticker AS linked_market_ticker,
        lr.recommendation_id AS joined_recommendation_id,
        lr.recommendation_created_at AS joined_recommendation_created_at,
        lr.canonical_game_id AS joined_recommendation_canonical_game_id,
        lr.market_ticker AS joined_recommendation_market_ticker,
        lr.selection_key AS joined_recommendation_selection_key,
        lr.quote_price_cents AS joined_quote_price_cents,
        lr.quote_price_role AS joined_quote_price_role,
        lr.quote_source_system AS joined_quote_source_system,
        lr.quote_bookmaker AS joined_quote_bookmaker,
        lr.quote_observed_at AS joined_quote_observed_at,
        lr.quote_loaded_at AS joined_quote_loaded_at,
        lr.quote_payload_ref AS joined_quote_payload_ref,
        lr.quote_freshness_result AS joined_quote_freshness_result,
        lr.quote_fallback_status AS joined_quote_fallback_status,
        validation.evidence_state_scope,
        validation.evidence_state,
        validation.evidence_state_reason,
        validation.evidence_state_as_of,
        validation.evidence_state_source_artifact,
        validation.governance_status,
        validation.descriptive_only_flag,
        validation.contamination_flag AS validation_contamination_flag,
        validation.contamination_reason AS validation_contamination_reason,
        validation.excluded_from_approval_flag,
        CASE
            WHEN pb.ticker IS NULL OR pb.ticker = '' THEN 'missing_market_ticker'
            WHEN mc.canonical_game_id IS NULL THEN 'market_link_unresolved'
            WHEN COALESCE(pb.recommendation_linkage_status, CASE WHEN lr.recommendation_id IS NULL THEN 'unlinked' ELSE 'linked' END) = 'unlinked'
                THEN 'recommendation_link_unresolved'
            ELSE NULL
        END::VARCHAR AS local_contamination_reason
    FROM placed_bets pb
    LEFT JOIN market_context mc
        ON mc.market_ticker = pb.ticker
    LEFT JOIN latest_recommendations lr
        ON lr.market_ticker = NULLIF(pb.ticker, '')
       AND (
           lr.selection_key IS NULL
           OR lr.selection_key = COALESCE(NULLIF(pb.bet_on, ''), mc.outcome_name)
       )
       AND (
           lr.canonical_game_id IS NULL
           OR mc.canonical_game_id IS NULL
           OR lr.canonical_game_id = mc.canonical_game_id
       )
    LEFT JOIN sport_validation_state_v1 validation
        ON validation.sport = UPPER(COALESCE(NULLIF(pb.sport, ''), NULLIF(mc.sport, ''), 'UNKNOWN'))
)
SELECT
    UPPER(COALESCE(NULLIF(pb.sport, ''), NULLIF(pb.market_sport, ''), 'UNKNOWN'))::VARCHAR AS sport,
    CASE
        WHEN UPPER(COALESCE(NULLIF(pb.sport, ''), NULLIF(pb.market_sport, ''), 'UNKNOWN')) IN ('TENNIS', 'EPL', 'LIGUE1')
            THEN 'match_winner'
        ELSE COALESCE(NULLIF(pb.market_name, ''), 'moneyline')
    END::VARCHAR AS market_type,
    'execution_rows'::VARCHAR AS cohort_type,
    'read_model'::VARCHAR AS evidence_dimension,
    pb.canonical_game_id,
    NULLIF(pb.ticker, '')::VARCHAR AS market_ticker,
    COALESCE(NULLIF(pb.bet_on, ''), pb.outcome_name)::VARCHAR AS selection_key,
    'placed_bets'::VARCHAR AS source_relation,
    pb.bet_id::VARCHAR AS source_record_id,
    COALESCE(pb.evidence_state_scope, 'sport')::VARCHAR AS evidence_state_scope,
    COALESCE(pb.evidence_state, 'blocked')::VARCHAR AS evidence_state,
    COALESCE(pb.evidence_state_reason, 'Sport baseline missing from governed validation state.')::VARCHAR AS evidence_state_reason,
    COALESCE(pb.evidence_state_as_of, TIMESTAMP '2026-05-12 00:00:00') AS evidence_state_as_of,
    COALESCE(
        pb.evidence_state_source_artifact,
        'docs/plan/2026-05-12-betting-pipeline-audit/evidence-readmodel-spec.md'
    )::VARCHAR AS evidence_state_source_artifact,
    COALESCE(pb.governance_status, 'descriptive_only')::VARCHAR AS governance_status,
    COALESCE(pb.descriptive_only_flag, TRUE) AS descriptive_only_flag,
    CASE
        WHEN COALESCE(pb.validation_contamination_flag, FALSE) THEN TRUE
        WHEN pb.local_contamination_reason IS NOT NULL THEN TRUE
        ELSE FALSE
    END AS contamination_flag,
    CASE
        WHEN COALESCE(pb.validation_contamination_flag, FALSE)
             AND pb.local_contamination_reason IS NOT NULL
            THEN CONCAT(pb.validation_contamination_reason, ';', pb.local_contamination_reason)
        WHEN COALESCE(pb.validation_contamination_flag, FALSE)
            THEN pb.validation_contamination_reason
        ELSE pb.local_contamination_reason
    END::VARCHAR AS contamination_reason,
    (
        COALESCE(pb.excluded_from_approval_flag, TRUE)
        OR pb.local_contamination_reason IS NOT NULL
    ) AS excluded_from_approval_flag,
    pb.placed_time_utc::TIMESTAMP AS observed_at,
    COALESCE(pb.entry_quote_loaded_at, pb.created_at)::TIMESTAMP AS loaded_at,
    COALESCE(pb.updated_at, pb.entry_quote_observed_at, pb.entry_quote_loaded_at, pb.created_at, pb.placed_time_utc)::TIMESTAMP AS last_updated_at,
    pb.bet_id::VARCHAR AS placed_bet_id,
    COALESCE(pb.recommendation_id, pb.joined_recommendation_id)::VARCHAR AS recommendation_id,
    'placed_bets'::VARCHAR AS execution_source_surface,
    LOWER(pb.status)::VARCHAR AS execution_status,
    pb.placed_time_utc::TIMESTAMP AS submitted_at,
    CASE
        WHEN LOWER(COALESCE(pb.status, '')) IN ('filled', 'won', 'lost', 'settled')
            THEN COALESCE(pb.updated_at, pb.placed_time_utc)::TIMESTAMP
        ELSE NULL::TIMESTAMP
    END AS filled_at,
    COALESCE(pb.contracts, 0)::INTEGER AS contracts,
    COALESCE(pb.cost_dollars, 0.0)::DOUBLE PRECISION AS execution_cost_dollars,
    COALESCE(pb.cost_dollars, pb.payout_dollars, 0.0)::DOUBLE PRECISION AS notional_exposure,
    COALESCE(pb.bet_line_prob, pb.market_prob)::DOUBLE PRECISION AS entry_probability,
    COALESCE(pb.entry_quote_role, 'executable')::VARCHAR AS entry_quote_role,
    COALESCE(pb.entry_price_source, NULLIF(pb.source, ''), 'placed_bets')::VARCHAR AS entry_price_source,
    COALESCE(
        pb.recommendation_linkage_status,
        CASE
            WHEN COALESCE(pb.recommendation_id, pb.joined_recommendation_id) IS NULL THEN 'unlinked'
            ELSE 'linked'
        END
    )::VARCHAR AS linkage_status,
    COALESCE(
        pb.recommendation_linkage_basis,
        CASE
            WHEN COALESCE(pb.recommendation_id, pb.joined_recommendation_id) IS NULL THEN 'unlinked'
            WHEN COALESCE(pb.recommendation_canonical_game_id, pb.joined_recommendation_canonical_game_id, pb.canonical_game_id) IS NOT NULL
                 AND COALESCE(pb.recommendation_selection_key, pb.joined_recommendation_selection_key, COALESCE(NULLIF(pb.bet_on, ''), pb.outcome_name)) IS NOT NULL
                THEN 'market_ticker_selection_key_canonical_game_id'
            WHEN COALESCE(pb.recommendation_selection_key, pb.joined_recommendation_selection_key, COALESCE(NULLIF(pb.bet_on, ''), pb.outcome_name)) IS NOT NULL
                THEN 'market_ticker_selection_key'
            ELSE 'market_ticker'
        END
    )::VARCHAR AS linkage_basis,
    COALESCE(pb.recommendation_canonical_game_id, pb.joined_recommendation_canonical_game_id, pb.canonical_game_id)::VARCHAR AS linked_canonical_game_id,
    COALESCE(pb.recommendation_market_ticker, pb.joined_recommendation_market_ticker, NULLIF(pb.ticker, ''))::VARCHAR AS linked_market_ticker,
    COALESCE(pb.recommendation_selection_key, pb.joined_recommendation_selection_key, COALESCE(NULLIF(pb.bet_on, ''), pb.outcome_name))::VARCHAR AS linked_selection_key,
    COALESCE(
        pb.entry_quote_source_system,
        CASE
            WHEN pb.linked_market_ticker IS NULL THEN 'placed_bets'
            ELSE 'game_odds'
        END
    )::VARCHAR AS entry_quote_source_system,
    COALESCE(pb.entry_quote_bookmaker, pb.quote_bookmaker, pb.joined_quote_bookmaker)::VARCHAR AS entry_quote_bookmaker,
    COALESCE(pb.entry_quote_observed_at, pb.quote_observed_at, pb.joined_quote_observed_at, pb.placed_time_utc)::TIMESTAMP AS entry_quote_observed_at,
    COALESCE(pb.entry_quote_loaded_at, pb.quote_loaded_at, pb.joined_quote_loaded_at, pb.created_at)::TIMESTAMP AS entry_quote_loaded_at,
    COALESCE(pb.entry_quote_payload_ref, pb.quote_payload_ref, pb.joined_quote_payload_ref, pb.bet_id)::VARCHAR AS entry_quote_payload_ref,
    CASE
        WHEN pb.linked_market_ticker IS NULL THEN 'placeholder_from_execution'
        ELSE 'linked_market_quote'
    END::VARCHAR AS entry_quote_lineage_status,
    COALESCE(pb.entry_price_cents, pb.price_cents, pb.joined_quote_price_cents)::INTEGER AS entry_price_cents,
    COALESCE(
        pb.entry_quote_freshness_result,
        pb.joined_quote_freshness_result,
        CASE
            WHEN COALESCE(pb.entry_quote_observed_at, pb.quote_observed_at, pb.joined_quote_observed_at) IS NULL
                THEN 'missing_source_timestamp'
            ELSE 'fresh'
        END
    )::VARCHAR AS entry_quote_freshness_result,
    COALESCE(
        pb.entry_quote_fallback_status,
        pb.joined_quote_fallback_status,
        CASE
            WHEN pb.entry_price_source LIKE 'recommendation_%' THEN 'recommendation_fallback'
            WHEN pb.entry_price_cents IS NOT NULL THEN 'direct_market_quote'
            ELSE 'missing_quote'
        END
    )::VARCHAR AS entry_quote_fallback_status
FROM execution_context pb
WHERE pb.bet_id IS NOT NULL
  AND pb.bet_id <> '';

CREATE VIEW governed_clv_evidence_envelope_v1 AS
WITH market_context AS (
    SELECT DISTINCT ON (go.external_id)
        go.external_id::VARCHAR AS market_ticker,
        ug.game_id::VARCHAR AS canonical_game_id,
        UPPER(ug.sport)::VARCHAR AS sport,
        LOWER(go.market_name)::VARCHAR AS market_name,
        go.outcome_name::VARCHAR AS outcome_name
    FROM game_odds go
    LEFT JOIN unified_games ug
        ON ug.game_id = go.game_id
    WHERE go.external_id IS NOT NULL
      AND go.external_id <> ''
    ORDER BY go.external_id, go.last_update DESC NULLS LAST, go.odds_id ASC
),
latest_recommendations AS (
    SELECT DISTINCT ON (ticker)
        ticker,
        bet_id::VARCHAR AS recommendation_id,
        canonical_game_id::VARCHAR AS recommendation_canonical_game_id,
        COALESCE(NULLIF(bet_on, ''), home_team)::VARCHAR AS recommendation_selection_key
    FROM bet_recommendations
    WHERE ticker IS NOT NULL
    ORDER BY ticker, created_at DESC NULLS LAST, bet_id ASC
),
close_quote_context AS (
    SELECT
        pb.bet_id::VARCHAR AS placed_bet_id,
        go.bookmaker::VARCHAR AS close_bookmaker,
        go.last_update::TIMESTAMP AS close_observed_at,
        go.loaded_at::TIMESTAMP AS close_loaded_at,
        COALESCE(go.odds_id, go.external_id)::VARCHAR AS close_payload_ref,
        go.price::DOUBLE PRECISION AS close_decimal_price,
        CASE
            WHEN go.last_update IS NULL THEN 'missing_source_timestamp'
            WHEN pb.market_close_time_utc IS NOT NULL
                 AND go.last_update < (pb.market_close_time_utc - INTERVAL '4 hours')
                THEN 'stale'
            ELSE 'fresh'
        END::VARCHAR AS close_freshness_result,
        'latest_admissible_pregame_quote'::VARCHAR AS selected_close_rule,
        CASE
            WHEN go.last_update IS NULL THEN NULL::VARCHAR
            ELSE CONCAT(
                go.bookmaker,
                '|',
                COALESCE(NULLIF(pb.bet_on, ''), go.outcome_name),
                '|',
                go.last_update::VARCHAR
            )::VARCHAR
        END AS selected_close_provenance
    FROM placed_bets pb
    LEFT JOIN LATERAL (
        SELECT
            odds_id,
            external_id,
            bookmaker,
            outcome_name,
            price,
            last_update,
            loaded_at
        FROM game_odds
        WHERE external_id = pb.ticker
          AND (
              pb.market_close_time_utc IS NULL
              OR last_update IS NULL
              OR last_update <= pb.market_close_time_utc
          )
        ORDER BY
            last_update DESC NULLS LAST,
            CASE bookmaker
                WHEN 'Pinnacle' THEN 0
                WHEN 'Circa' THEN 1
                WHEN 'Bookmaker' THEN 2
                WHEN 'BetMGM' THEN 3
                WHEN 'DraftKings' THEN 4
                WHEN 'FanDuel' THEN 5
                WHEN 'Kalshi' THEN 6
                WHEN 'SBR' THEN 7
                ELSE 8
            END ASC,
            odds_id ASC
        LIMIT 1
    ) go ON TRUE
),
clv_context AS (
    SELECT
        pb.*,
        mc.canonical_game_id AS market_canonical_game_id,
        mc.sport AS market_sport,
        mc.market_name,
        mc.outcome_name,
        lr.recommendation_id AS joined_recommendation_id,
        lr.recommendation_canonical_game_id AS joined_recommendation_canonical_game_id,
        lr.ticker AS joined_recommendation_market_ticker,
        lr.recommendation_selection_key AS joined_recommendation_selection_key,
        close_quote.close_bookmaker,
        close_quote.close_observed_at,
        close_quote.close_loaded_at,
        close_quote.close_payload_ref,
        close_quote.close_decimal_price,
        close_quote.close_freshness_result AS computed_close_freshness_result,
        close_quote.selected_close_rule AS computed_selected_close_rule,
        close_quote.selected_close_provenance AS computed_selected_close_provenance,
        validation.evidence_state_scope,
        validation.evidence_state,
        validation.evidence_state_reason,
        validation.evidence_state_as_of,
        validation.evidence_state_source_artifact,
        validation.governance_status,
        validation.descriptive_only_flag,
        validation.contamination_flag AS validation_contamination_flag,
        validation.contamination_reason AS validation_contamination_reason,
        validation.excluded_from_approval_flag,
        CASE
            WHEN COALESCE(pb.clv_source_type, '') <> '' THEN pb.clv_source_type
            WHEN pb.closing_line_prob IN (0.0, 1.0)
                 AND LOWER(COALESCE(pb.status, '')) IN ('won', 'lost', 'settled')
                THEN 'binary_result_placeholder'
            WHEN pb.closing_line_prob IS NULL THEN 'missing_close'
            WHEN pb.ticker IS NULL OR pb.ticker = '' THEN 'unlinked_close'
            WHEN close_quote.close_bookmaker IS NULL THEN 'unlinked_close'
            ELSE 'market_close'
        END::VARCHAR AS resolved_clv_source_type,
        CASE
            WHEN pb.ticker IS NULL OR pb.ticker = '' THEN 'missing_market_ticker'
            WHEN mc.canonical_game_id IS NULL THEN 'market_link_unresolved'
            WHEN COALESCE(pb.recommendation_id, lr.recommendation_id) IS NULL THEN 'recommendation_link_unresolved'
            WHEN pb.closing_line_prob IN (0.0, 1.0)
                 AND LOWER(COALESCE(pb.status, '')) IN ('won', 'lost', 'settled')
                THEN 'binary_result_placeholder'
            WHEN pb.closing_line_prob IS NULL THEN 'closing_probability_missing'
            ELSE NULL
        END::VARCHAR AS local_contamination_reason
    FROM placed_bets pb
    LEFT JOIN market_context mc
        ON mc.market_ticker = pb.ticker
    LEFT JOIN latest_recommendations lr
        ON lr.ticker = pb.ticker
    LEFT JOIN close_quote_context close_quote
        ON close_quote.placed_bet_id = pb.bet_id
    LEFT JOIN sport_validation_state_v1 validation
        ON validation.sport = UPPER(COALESCE(NULLIF(pb.sport, ''), NULLIF(mc.sport, ''), 'UNKNOWN'))
)
SELECT
    UPPER(COALESCE(NULLIF(pb.sport, ''), NULLIF(pb.market_sport, ''), 'UNKNOWN'))::VARCHAR AS sport,
    CASE
        WHEN UPPER(COALESCE(NULLIF(pb.sport, ''), NULLIF(pb.market_sport, ''), 'UNKNOWN')) IN ('TENNIS', 'EPL', 'LIGUE1')
            THEN 'match_winner'
        ELSE COALESCE(NULLIF(pb.market_name, ''), 'moneyline')
    END::VARCHAR AS market_type,
    'clv_rows'::VARCHAR AS cohort_type,
    'pricing_clv'::VARCHAR AS evidence_dimension,
    pb.market_canonical_game_id::VARCHAR AS canonical_game_id,
    NULLIF(pb.ticker, '')::VARCHAR AS market_ticker,
    COALESCE(NULLIF(pb.bet_on, ''), pb.outcome_name)::VARCHAR AS selection_key,
    'placed_bets'::VARCHAR AS source_relation,
    pb.bet_id::VARCHAR AS source_record_id,
    COALESCE(pb.evidence_state_scope, 'sport')::VARCHAR AS evidence_state_scope,
    COALESCE(pb.evidence_state, 'blocked')::VARCHAR AS evidence_state,
    COALESCE(
        pb.evidence_state_reason,
        'Sport baseline missing from governed validation state.'
    )::VARCHAR AS evidence_state_reason,
    COALESCE(
        pb.evidence_state_as_of,
        TIMESTAMP '2026-05-12 00:00:00'
    ) AS evidence_state_as_of,
    COALESCE(
        pb.evidence_state_source_artifact,
        'docs/plan/2026-05-12-betting-pipeline-audit/evidence-readmodel-spec.md'
    )::VARCHAR AS evidence_state_source_artifact,
    COALESCE(pb.governance_status, 'descriptive_only')::VARCHAR AS governance_status,
    COALESCE(pb.descriptive_only_flag, TRUE) AS descriptive_only_flag,
    CASE
        WHEN COALESCE(pb.validation_contamination_flag, FALSE) THEN TRUE
        WHEN pb.local_contamination_reason IS NOT NULL THEN TRUE
        ELSE FALSE
    END AS contamination_flag,
    CASE
        WHEN COALESCE(pb.validation_contamination_flag, FALSE)
             AND pb.local_contamination_reason IS NOT NULL
            THEN CONCAT(pb.validation_contamination_reason, ';', pb.local_contamination_reason)
        WHEN COALESCE(pb.validation_contamination_flag, FALSE)
            THEN pb.validation_contamination_reason
        ELSE pb.local_contamination_reason
    END::VARCHAR AS contamination_reason,
    (
        COALESCE(pb.excluded_from_approval_flag, TRUE)
        OR pb.local_contamination_reason IS NOT NULL
    ) AS excluded_from_approval_flag,
    pb.placed_time_utc::TIMESTAMP AS observed_at,
    COALESCE(pb.entry_quote_loaded_at, pb.created_at)::TIMESTAMP AS loaded_at,
    COALESCE(pb.updated_at, pb.created_at, pb.placed_time_utc)::TIMESTAMP AS last_updated_at,
    pb.bet_id::VARCHAR AS placed_bet_id,
    COALESCE(pb.recommendation_id, pb.joined_recommendation_id)::VARCHAR AS recommendation_id,
    COALESCE(
        pb.recommendation_canonical_game_id,
        pb.joined_recommendation_canonical_game_id,
        pb.market_canonical_game_id
    )::VARCHAR AS linked_canonical_game_id,
    COALESCE(pb.recommendation_market_ticker, pb.joined_recommendation_market_ticker, NULLIF(pb.ticker, ''))::VARCHAR AS linked_market_ticker,
    COALESCE(pb.recommendation_selection_key, pb.joined_recommendation_selection_key, COALESCE(NULLIF(pb.bet_on, ''), pb.outcome_name))::VARCHAR AS linked_selection_key,
    pb.resolved_clv_source_type AS clv_source_type,
    COALESCE(pb.updated_at, pb.created_at, pb.placed_time_utc)::TIMESTAMP AS clv_computed_at,
    COALESCE(pb.bet_line_prob, pb.market_prob)::DOUBLE PRECISION AS entry_probability,
    COALESCE(pb.entry_quote_role, 'executable')::VARCHAR AS entry_price_role,
    pb.closing_line_prob::DOUBLE PRECISION AS closing_probability,
    pb.clv::DOUBLE PRECISION AS clv_delta,
    CASE
        WHEN COALESCE(pb.clv, 0.0) > 0.0 THEN 'positive'
        WHEN COALESCE(pb.clv, 0.0) < 0.0 THEN 'negative'
        ELSE 'flat'
    END::VARCHAR AS clv_direction,
    CASE
        WHEN pb.resolved_clv_source_type = 'binary_result_placeholder'
            THEN 'binary_result_placeholder'
        WHEN pb.resolved_clv_source_type = 'missing_close'
            THEN 'unavailable'
        ELSE COALESCE(pb.close_quote_source, pb.close_bookmaker, 'unlinked_close')
    END::VARCHAR AS closing_quote_source,
    CASE
        WHEN pb.resolved_clv_source_type = 'market_close'
            THEN COALESCE(pb.close_quote_at, pb.close_observed_at)
        ELSE NULL::TIMESTAMP
    END AS closing_quote_at,
    COALESCE(
        pb.close_price_role,
        CASE
            WHEN pb.resolved_clv_source_type = 'market_close' THEN 'close'
            ELSE 'descriptive_placeholder'
        END
    )::VARCHAR AS close_price_role,
    CASE
        WHEN pb.resolved_clv_source_type IN ('binary_result_placeholder', 'missing_close')
            THEN 'missing_close'
        ELSE COALESCE(
            pb.close_freshness_result,
            pb.computed_close_freshness_result,
            'missing_source_timestamp'
        )
    END::VARCHAR AS close_freshness_result,
    CASE
        WHEN pb.resolved_clv_source_type = 'binary_result_placeholder'
            THEN 'binary_result_placeholder'
        WHEN pb.resolved_clv_source_type = 'missing_close'
            THEN 'missing_close'
        WHEN pb.resolved_clv_source_type = 'unlinked_close'
            THEN 'unlinked_close'
        ELSE COALESCE(
            pb.selected_close_rule,
            pb.computed_selected_close_rule,
            'latest_admissible_pregame_quote'
        )
    END::VARCHAR AS selected_close_rule,
    COALESCE(
        pb.selected_close_provenance,
        pb.computed_selected_close_provenance
    )::VARCHAR AS selected_close_provenance,
    CASE
        WHEN pb.resolved_clv_source_type = 'market_close'
             AND COALESCE(pb.close_quote_source, pb.close_bookmaker) IS NOT NULL
             AND COALESCE(pb.close_quote_at, pb.close_observed_at) IS NOT NULL
            THEN 'partially_evidenced'
        WHEN pb.resolved_clv_source_type = 'market_close'
            THEN 'descriptive_only'
        ELSE 'descriptive_only'
    END::VARCHAR AS clv_evidence_tier,
    (
        pb.resolved_clv_source_type = 'binary_result_placeholder'
    ) AS binary_result_placeholder_flag,
    (
        pb.resolved_clv_source_type = 'market_close'
        AND COALESCE(
            pb.close_freshness_result,
            pb.computed_close_freshness_result,
            'missing_source_timestamp'
        ) = 'stale'
    ) AS stale_close_flag,
    FALSE AS proxy_close_flag,
    (
        pb.resolved_clv_source_type <> 'market_close'
        OR COALESCE(
            pb.close_freshness_result,
            pb.computed_close_freshness_result,
            'missing_source_timestamp'
        ) = 'missing_source_timestamp'
    ) AS clv_contaminated_flag,
    COALESCE(pb.entry_price_cents, pb.price_cents)::INTEGER AS entry_price_cents,
    COALESCE(pb.entry_price_source, NULLIF(pb.source, ''), 'placed_bets')::VARCHAR AS entry_price_source,
    COALESCE(pb.entry_quote_source_system, 'placed_bets')::VARCHAR AS entry_quote_source_system,
    COALESCE(pb.entry_quote_bookmaker, 'Kalshi')::VARCHAR AS entry_quote_bookmaker,
    COALESCE(pb.entry_quote_observed_at, pb.placed_time_utc)::TIMESTAMP AS entry_quote_observed_at,
    COALESCE(pb.entry_quote_loaded_at, pb.created_at)::TIMESTAMP AS entry_quote_loaded_at,
    COALESCE(pb.entry_quote_payload_ref, pb.bet_id)::VARCHAR AS entry_quote_payload_ref,
    COALESCE(
        pb.entry_quote_freshness_result,
        CASE
            WHEN COALESCE(pb.entry_quote_observed_at, pb.placed_time_utc) IS NULL THEN 'missing_source_timestamp'
            ELSE 'fresh'
        END
    )::VARCHAR AS entry_freshness_result,
    COALESCE(
        pb.entry_quote_fallback_status,
        CASE
            WHEN pb.entry_price_source LIKE 'recommendation_%' THEN 'recommendation_fallback'
            WHEN pb.entry_price_cents IS NOT NULL THEN 'direct_market_quote'
            ELSE 'missing_quote'
        END
    )::VARCHAR AS entry_fallback_status,
    COALESCE(pb.close_quote_loaded_at, pb.close_loaded_at)::TIMESTAMP AS closing_quote_loaded_at,
    COALESCE(pb.close_quote_payload_ref, pb.close_payload_ref)::VARCHAR AS closing_quote_payload_ref,
    COALESCE(
        pb.close_fallback_status,
        pb.selected_close_rule,
        pb.computed_selected_close_rule,
        'missing_close'
    )::VARCHAR AS close_fallback_status
FROM clv_context pb
WHERE pb.bet_id IS NOT NULL
  AND pb.bet_id <> '';
