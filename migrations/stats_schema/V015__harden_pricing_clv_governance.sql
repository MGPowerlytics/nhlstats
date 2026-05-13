-- Wave 3 pricing/CLV governance hardening.
-- Keep dashboard_*_v1 contracts unchanged while making governed CLV evidence
-- explicit about price roles, freshness, close selection, and evidence tiering.

DROP VIEW IF EXISTS governed_clv_evidence_envelope_v1;

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
        mc.canonical_game_id,
        mc.sport AS market_sport,
        mc.market_name,
        mc.outcome_name,
        close_quote.close_bookmaker,
        close_quote.close_observed_at,
        close_quote.close_loaded_at,
        close_quote.close_payload_ref,
        close_quote.close_decimal_price,
        close_quote.close_freshness_result,
        close_quote.selected_close_rule,
        close_quote.selected_close_provenance,
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
            WHEN pb.closing_line_prob IN (0.0, 1.0)
                 AND LOWER(COALESCE(pb.status, '')) IN ('won', 'lost', 'settled')
                THEN 'binary_result_placeholder'
            WHEN pb.closing_line_prob IS NULL THEN 'missing_close'
            WHEN pb.ticker IS NULL OR pb.ticker = '' THEN 'unlinked_close'
            WHEN close_quote.close_bookmaker IS NULL THEN 'unlinked_close'
            ELSE 'market_close'
        END::VARCHAR AS clv_source_type,
        CASE
            WHEN pb.ticker IS NULL OR pb.ticker = '' THEN 'missing_market_ticker'
            WHEN mc.canonical_game_id IS NULL THEN 'market_link_unresolved'
            WHEN pb.closing_line_prob IN (0.0, 1.0)
                 AND LOWER(COALESCE(pb.status, '')) IN ('won', 'lost', 'settled')
                THEN 'binary_result_placeholder'
            WHEN pb.closing_line_prob IS NULL THEN 'closing_probability_missing'
            ELSE NULL
        END::VARCHAR AS local_contamination_reason
    FROM placed_bets pb
    LEFT JOIN market_context mc
        ON mc.market_ticker = pb.ticker
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
    pb.canonical_game_id,
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
    pb.created_at::TIMESTAMP AS loaded_at,
    COALESCE(pb.updated_at, pb.created_at, pb.placed_time_utc)::TIMESTAMP AS last_updated_at,
    pb.bet_id::VARCHAR AS placed_bet_id,
    pb.clv_source_type,
    COALESCE(pb.updated_at, pb.created_at, pb.placed_time_utc)::TIMESTAMP AS clv_computed_at,
    COALESCE(pb.bet_line_prob, pb.market_prob)::DOUBLE PRECISION AS entry_probability,
    'executable'::VARCHAR AS entry_price_role,
    pb.closing_line_prob::DOUBLE PRECISION AS closing_probability,
    pb.clv::DOUBLE PRECISION AS clv_delta,
    CASE
        WHEN COALESCE(pb.clv, 0.0) > 0.0 THEN 'positive'
        WHEN COALESCE(pb.clv, 0.0) < 0.0 THEN 'negative'
        ELSE 'flat'
    END::VARCHAR AS clv_direction,
    CASE
        WHEN pb.clv_source_type = 'binary_result_placeholder'
            THEN 'binary_result_placeholder'
        WHEN pb.clv_source_type = 'missing_close'
            THEN 'unavailable'
        ELSE COALESCE(pb.close_bookmaker, 'unlinked_close')
    END::VARCHAR AS closing_quote_source,
    CASE
        WHEN pb.clv_source_type = 'market_close'
            THEN pb.close_observed_at
        ELSE NULL::TIMESTAMP
    END AS closing_quote_at,
    CASE
        WHEN pb.clv_source_type = 'market_close' THEN 'close'
        ELSE 'descriptive_placeholder'
    END::VARCHAR AS close_price_role,
    CASE
        WHEN pb.clv_source_type = 'binary_result_placeholder' THEN 'missing_close'
        WHEN pb.clv_source_type = 'missing_close' THEN 'missing_close'
        ELSE COALESCE(pb.close_freshness_result, 'missing_source_timestamp')
    END::VARCHAR AS close_freshness_result,
    CASE
        WHEN pb.clv_source_type = 'binary_result_placeholder'
            THEN 'binary_result_placeholder'
        WHEN pb.clv_source_type = 'missing_close'
            THEN 'missing_close'
        WHEN pb.clv_source_type = 'unlinked_close'
            THEN 'unlinked_close'
        ELSE COALESCE(pb.selected_close_rule, 'latest_admissible_pregame_quote')
    END::VARCHAR AS selected_close_rule,
    pb.selected_close_provenance,
    CASE
        WHEN pb.clv_source_type = 'market_close'
             AND pb.close_bookmaker IS NOT NULL
             AND pb.close_observed_at IS NOT NULL
            THEN 'partially_evidenced'
        WHEN pb.clv_source_type = 'market_close'
            THEN 'descriptive_only'
        ELSE 'descriptive_only'
    END::VARCHAR AS clv_evidence_tier,
    (
        pb.clv_source_type = 'binary_result_placeholder'
    ) AS binary_result_placeholder_flag,
    (
        pb.clv_source_type = 'market_close'
        AND pb.close_freshness_result = 'stale'
    ) AS stale_close_flag,
    FALSE AS proxy_close_flag,
    (
        pb.clv_source_type <> 'market_close'
        OR pb.close_freshness_result = 'missing_source_timestamp'
    ) AS clv_contaminated_flag
FROM clv_context pb
WHERE pb.bet_id IS NOT NULL
  AND pb.bet_id <> '';
