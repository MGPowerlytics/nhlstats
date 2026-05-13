-- Governed approval-facing PostgreSQL read models.
-- preserve existing dashboard_*_v1 contracts unchanged this cycle.
-- Introduce new governed, versioned approval-facing read models instead of mutating dashboard_*_v1 semantics in place.

DROP VIEW IF EXISTS governed_portfolio_risk_state_v1;
DROP VIEW IF EXISTS governed_clv_evidence_envelope_v1;
DROP VIEW IF EXISTS governed_recommendation_execution_link_v1;
DROP VIEW IF EXISTS governed_evidence_record_v1;
DROP VIEW IF EXISTS sport_validation_state_v1;

CREATE VIEW sport_validation_state_v1 AS
WITH sport_baseline AS (
    SELECT *
    FROM (
        VALUES
            (
                'MLB',
                'shadow_only',
                'MLB remains shadow-only because approval-grade CLV, calibration, and runtime parity evidence are still incomplete.',
                'binary_result_clv_contamination',
                'dags.multi_sport_betting_workflow.identify_good_mlb_bets',
                'mlb_model_predictions',
                'descriptive-shadow-baseline',
                TRUE,
                FALSE,
                FALSE,
                FALSE
            ),
            (
                'TENNIS',
                'shadow_only',
                'TENNIS remains shadow-only because descriptive evidence exists but approval-grade runtime provenance is incomplete.',
                'binary_result_clv_contamination;synthetic_ticker_contamination',
                'plugins.elo.tennis_elo_rating.predict_with_payload',
                'tennis_calibrated_elo',
                'descriptive-shadow-baseline',
                TRUE,
                FALSE,
                TRUE,
                FALSE
            ),
            (
                'EPL',
                'shadow_only',
                'EPL remains shadow-only because descriptive ensemble evidence exists but governed live DAG parity is incomplete.',
                'binary_result_clv_contamination',
                'dags.multi_sport_betting_workflow.identify_good_epl_bets',
                'epl_offline_ensemble',
                'descriptive-shadow-baseline',
                TRUE,
                FALSE,
                FALSE,
                FALSE
            ),
            (
                'LIGUE1',
                'shadow_only',
                'LIGUE1 remains shadow-only because live ensemble evidence exists but governed provenance and parity are incomplete.',
                'binary_result_clv_contamination',
                'dags.multi_sport_betting_workflow.identify_good_epl_bets',
                'ligue1_live_ensemble',
                'descriptive-shadow-baseline',
                TRUE,
                FALSE,
                FALSE,
                FALSE
            ),
            (
                'NBA',
                'blocked',
                'NBA remains blocked because no repeatable approval-grade validation path is currently governed.',
                NULL,
                NULL,
                NULL,
                'approval_evidence_unavailable',
                FALSE,
                FALSE,
                FALSE,
                FALSE
            ),
            (
                'NHL',
                'blocked',
                'NHL remains blocked because offline coefficients exist without governed live approval evidence.',
                NULL,
                NULL,
                NULL,
                'approval_evidence_unavailable',
                FALSE,
                FALSE,
                FALSE,
                FALSE
            ),
            (
                'NFL',
                'blocked',
                'NFL remains blocked because current evidence is descriptive-only and not approval-grade.',
                NULL,
                NULL,
                NULL,
                'approval_evidence_unavailable',
                FALSE,
                FALSE,
                FALSE,
                FALSE
            ),
            (
                'NCAAB',
                'blocked',
                'NCAAB remains blocked because offline calibration metadata lacks governed runtime consumer parity.',
                NULL,
                NULL,
                NULL,
                'approval_evidence_unavailable',
                FALSE,
                FALSE,
                FALSE,
                FALSE
            ),
            (
                'WNCAAB',
                'blocked',
                'WNCAAB remains blocked because offline calibration metadata lacks governed runtime consumer parity.',
                NULL,
                NULL,
                NULL,
                'approval_evidence_unavailable',
                FALSE,
                FALSE,
                FALSE,
                FALSE
            )
    ) AS baseline(
        sport,
        evidence_state,
        evidence_state_reason,
        contamination_reason,
        runtime_consumer,
        artifact_id,
        artifact_version,
        artifact_available_flag,
        placed_bet_only_flag,
        synthetic_identity_flag,
        backfill_flag
    )
)
SELECT
    baseline.sport::VARCHAR AS sport,
    CASE
        WHEN baseline.sport IN ('TENNIS', 'EPL', 'LIGUE1') THEN 'match_winner'
        ELSE 'moneyline'
    END::VARCHAR AS market_type,
    'approval_review'::VARCHAR AS cohort_type,
    'validation'::VARCHAR AS evidence_dimension,
    NULL::VARCHAR AS canonical_game_id,
    NULL::VARCHAR AS market_ticker,
    NULL::VARCHAR AS selection_key,
    'governed_validation_publication'::VARCHAR AS source_relation,
    baseline.sport::VARCHAR AS source_record_id,
    'sport'::VARCHAR AS evidence_state_scope,
    baseline.evidence_state::VARCHAR AS evidence_state,
    baseline.evidence_state_reason::VARCHAR AS evidence_state_reason,
    TIMESTAMP '2026-05-12 00:00:00' AS evidence_state_as_of,
    'tests/contracts/fixtures/sport_validation_samples.py;plugins/sport_validation.py'::VARCHAR AS evidence_state_source_artifact,
    CASE
        WHEN baseline.evidence_state = 'candidate' THEN 'candidate_ready'
        ELSE 'descriptive_only'
    END::VARCHAR AS governance_status,
    (baseline.evidence_state <> 'candidate') AS descriptive_only_flag,
    (baseline.contamination_reason IS NOT NULL) AS contamination_flag,
    baseline.contamination_reason::VARCHAR AS contamination_reason,
    (baseline.evidence_state <> 'candidate') AS excluded_from_approval_flag,
    TIMESTAMP '2026-05-12 00:00:00' AS observed_at,
    NULL::TIMESTAMP AS loaded_at,
    TIMESTAMP '2026-05-12 00:00:00' AS last_updated_at,
    TIMESTAMP '2026-05-12 00:00:00' AS review_timestamp,
    baseline.runtime_consumer::VARCHAR AS runtime_consumer,
    baseline.artifact_id::VARCHAR AS artifact_id,
    baseline.artifact_version::VARCHAR AS artifact_version,
    'approval_evidence_read_model'::VARCHAR AS artifact_family,
    baseline.artifact_available_flag AS artifact_available_flag,
    baseline.placed_bet_only_flag AS placed_bet_only_flag,
    baseline.synthetic_identity_flag AS synthetic_identity_flag,
    baseline.backfill_flag AS backfill_flag
FROM sport_baseline baseline;

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
        COALESCE(
            NULLIF(to_jsonb(br)->>'canonical_game_id', ''),
            mc.canonical_game_id
        )::VARCHAR AS resolved_canonical_game_id,
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
            WHEN COALESCE(
                NULLIF(to_jsonb(br)->>'canonical_game_id', ''),
                mc.canonical_game_id
            ) IS NULL THEN 'market_link_unresolved'
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
    COALESCE(
        NULLIF(to_jsonb(br)->>'quote_loaded_at', '')::TIMESTAMP,
        br.linked_quote_loaded_at
    ) AS loaded_at,
    COALESCE(
        br.created_at,
        NULLIF(to_jsonb(br)->>'quote_observed_at', '')::TIMESTAMP,
        br.linked_quote_observed_at,
        NULLIF(to_jsonb(br)->>'quote_loaded_at', '')::TIMESTAMP,
        br.linked_quote_loaded_at
    )::TIMESTAMP AS last_updated_at,
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
    CASE
        WHEN br.linked_market_ticker IS NULL THEN 'quote_lineage_placeholder'
        ELSE 'game_odds'
    END::VARCHAR AS quote_source_system,
    COALESCE(
        NULLIF(to_jsonb(br)->>'quote_bookmaker', ''),
        br.linked_quote_bookmaker
    )::VARCHAR AS quote_bookmaker,
    COALESCE(
        NULLIF(to_jsonb(br)->>'quote_observed_at', '')::TIMESTAMP,
        br.linked_quote_observed_at
    )::TIMESTAMP AS quote_observed_at,
    COALESCE(
        NULLIF(to_jsonb(br)->>'quote_loaded_at', '')::TIMESTAMP,
        br.linked_quote_loaded_at
    )::TIMESTAMP AS quote_loaded_at,
    COALESCE(
        NULLIF(to_jsonb(br)->>'quote_payload_ref', ''),
        br.linked_quote_payload_ref,
        br.ticker
    )::VARCHAR AS quote_payload_ref,
    CASE
        WHEN br.linked_market_ticker IS NULL THEN 'missing_market_quote'
        ELSE 'linked_market_quote'
    END::VARCHAR AS quote_lineage_status
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
        COALESCE(mc.canonical_game_id, '')
    )
        NULLIF(br.ticker, '')::VARCHAR AS market_ticker,
        mc.canonical_game_id,
        COALESCE(NULLIF(br.bet_on, ''), mc.outcome_name)::VARCHAR AS selection_key,
        br.bet_id::VARCHAR AS recommendation_id
    FROM bet_recommendations br
    LEFT JOIN market_context mc
        ON mc.market_ticker = br.ticker
    WHERE br.bet_id IS NOT NULL
      AND br.bet_id <> ''
    ORDER BY
        COALESCE(NULLIF(br.ticker, ''), ''),
        COALESCE(NULLIF(br.bet_on, ''), mc.outcome_name, ''),
        COALESCE(mc.canonical_game_id, ''),
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
        lr.recommendation_id,
        lr.canonical_game_id AS recommendation_canonical_game_id,
        lr.market_ticker AS recommendation_market_ticker,
        lr.selection_key AS recommendation_selection_key,
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
            WHEN lr.recommendation_id IS NULL THEN 'recommendation_link_unresolved'
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
    pb.recommendation_id,
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
    'executable'::VARCHAR AS entry_quote_role,
    COALESCE(NULLIF(pb.source, ''), 'placed_bets')::VARCHAR AS entry_price_source,
    CASE
        WHEN pb.recommendation_id IS NULL THEN 'unlinked'
        ELSE 'linked'
    END::VARCHAR AS linkage_status,
    CASE
        WHEN pb.recommendation_id IS NULL THEN 'unlinked'
        WHEN pb.canonical_game_id IS NOT NULL
             AND COALESCE(NULLIF(pb.bet_on, ''), pb.outcome_name) IS NOT NULL
            THEN 'market_ticker_selection_key_canonical_game_id'
        WHEN COALESCE(NULLIF(pb.bet_on, ''), pb.outcome_name) IS NOT NULL
            THEN 'market_ticker_selection_key'
        ELSE 'market_ticker'
    END::VARCHAR AS linkage_basis,
    COALESCE(pb.recommendation_canonical_game_id, pb.canonical_game_id)::VARCHAR AS linked_canonical_game_id,
    COALESCE(pb.recommendation_market_ticker, NULLIF(pb.ticker, ''))::VARCHAR AS linked_market_ticker,
    COALESCE(pb.recommendation_selection_key, COALESCE(NULLIF(pb.bet_on, ''), pb.outcome_name))::VARCHAR AS linked_selection_key,
    CASE
        WHEN pb.linked_market_ticker IS NULL THEN 'placed_bets'
        ELSE 'game_odds'
    END::VARCHAR AS entry_quote_source_system,
    pb.quote_bookmaker AS entry_quote_bookmaker,
    pb.quote_observed_at AS entry_quote_observed_at,
    pb.quote_loaded_at AS entry_quote_loaded_at,
    pb.quote_payload_ref AS entry_quote_payload_ref,
    CASE
        WHEN pb.linked_market_ticker IS NULL THEN 'placeholder_from_execution'
        ELSE 'linked_market_quote'
    END::VARCHAR AS entry_quote_lineage_status
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
clv_context AS (
    SELECT
        pb.*,
        mc.canonical_game_id,
        mc.sport AS market_sport,
        mc.market_name,
        mc.outcome_name,
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
            WHEN pb.closing_line_prob IS NULL THEN 'closing_probability_missing'
            ELSE NULL
        END::VARCHAR AS local_contamination_reason
    FROM placed_bets pb
    LEFT JOIN market_context mc
        ON mc.market_ticker = pb.ticker
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
    CASE
        WHEN pb.closing_line_prob IS NULL THEN 'missing_close'
        WHEN pb.ticker IS NULL OR pb.ticker = '' THEN 'unlinked_close'
        ELSE 'market_close'
    END::VARCHAR AS clv_source_type,
    COALESCE(pb.updated_at, pb.created_at, pb.placed_time_utc)::TIMESTAMP AS clv_computed_at,
    COALESCE(pb.bet_line_prob, pb.market_prob)::DOUBLE PRECISION AS entry_probability,
    pb.closing_line_prob::DOUBLE PRECISION AS closing_probability,
    pb.clv::DOUBLE PRECISION AS clv_delta,
    CASE
        WHEN COALESCE(pb.clv, 0.0) > 0.0 THEN 'positive'
        WHEN COALESCE(pb.clv, 0.0) < 0.0 THEN 'negative'
        ELSE 'flat'
    END::VARCHAR AS clv_direction,
    CASE
        WHEN pb.closing_line_prob IS NULL THEN 'unavailable'
        ELSE COALESCE(NULLIF(pb.source, ''), 'placed_bets')
    END::VARCHAR AS closing_quote_source,
    pb.market_close_time_utc::TIMESTAMP AS closing_quote_at,
    (
        pb.closing_line_prob IS NULL
        AND LOWER(COALESCE(pb.status, '')) IN ('won', 'lost', 'settled')
    ) AS binary_result_placeholder_flag,
    (
        pb.market_close_time_utc IS NOT NULL
        AND pb.updated_at IS NOT NULL
        AND pb.updated_at > (pb.market_close_time_utc + INTERVAL '24 hours')
    ) AS stale_close_flag,
    FALSE AS proxy_close_flag,
    (
        pb.ticker IS NULL
        OR pb.ticker = ''
        OR pb.canonical_game_id IS NULL
        OR pb.closing_line_prob IS NULL
        OR (
            pb.market_close_time_utc IS NOT NULL
            AND pb.updated_at IS NOT NULL
            AND pb.updated_at > (pb.market_close_time_utc + INTERVAL '24 hours')
        )
    ) AS clv_contaminated_flag
FROM clv_context pb
WHERE pb.bet_id IS NOT NULL
  AND pb.bet_id <> '';

CREATE VIEW governed_portfolio_risk_state_v1 AS
WITH latest_snapshot AS (
    SELECT
        pvs.snapshot_hour_utc::TIMESTAMP AS snapshot_hour_utc,
        pvs.portfolio_value_dollars::DOUBLE PRECISION AS portfolio_value_dollars,
        pvs.created_at_utc::TIMESTAMP AS created_at_utc
    FROM portfolio_value_snapshots pvs
    ORDER BY pvs.snapshot_hour_utc DESC NULLS LAST
    LIMIT 1
),
sport_exposure AS (
    SELECT
        UPPER(COALESCE(NULLIF(pb.sport, ''), 'UNKNOWN'))::VARCHAR AS sport,
        COALESCE(
            SUM(
                CASE
                    WHEN LOWER(COALESCE(pb.status, '')) IN ('pending', 'open', 'placed', 'filled')
                        THEN COALESCE(pb.cost_dollars, 0.0)
                    ELSE 0.0
                END
            ),
            0.0
        )::DOUBLE PRECISION AS open_exposure_amount,
        COALESCE(
            SUM(
                CASE
                    WHEN LOWER(COALESCE(pb.status, '')) IN ('pending', 'open', 'placed')
                        THEN COALESCE(pb.cost_dollars, 0.0)
                    ELSE 0.0
                END
            ),
            0.0
        )::DOUBLE PRECISION AS resting_order_exposure_amount,
        COUNT(*) FILTER (
            WHERE LOWER(COALESCE(pb.status, '')) IN ('pending', 'open', 'placed')
        )::INTEGER AS resting_order_count,
        COALESCE(
            SUM(
                CASE
                    WHEN LOWER(COALESCE(pb.status, '')) = 'filled'
                        THEN COALESCE(pb.cost_dollars, 0.0)
                    ELSE 0.0
                END
            ),
            0.0
        )::DOUBLE PRECISION AS executed_unsettled_exposure_amount,
        COUNT(*) FILTER (
            WHERE LOWER(COALESCE(pb.status, '')) = 'filled'
        )::INTEGER AS executed_unsettled_count,
        COUNT(*) FILTER (
            WHERE LOWER(COALESCE(pb.status, '')) IN ('pending', 'open', 'placed', 'filled')
        )::INTEGER AS open_position_count,
        MAX(COALESCE(pb.updated_at, pb.created_at, pb.placed_time_utc))::TIMESTAMP AS observed_at
    FROM placed_bets pb
    GROUP BY UPPER(COALESCE(NULLIF(pb.sport, ''), 'UNKNOWN'))
)
SELECT
    se.sport,
    CASE
        WHEN se.sport IN ('TENNIS', 'EPL', 'LIGUE1') THEN 'match_winner'
        ELSE 'moneyline'
    END::VARCHAR AS market_type,
    'sport_open_exposure'::VARCHAR AS cohort_type,
    'portfolio_risk'::VARCHAR AS evidence_dimension,
    NULL::VARCHAR AS canonical_game_id,
    NULL::VARCHAR AS market_ticker,
    NULL::VARCHAR AS selection_key,
    'placed_bets'::VARCHAR AS source_relation,
    se.sport::VARCHAR AS source_record_id,
    COALESCE(validation.evidence_state_scope, 'sport')::VARCHAR AS evidence_state_scope,
    COALESCE(validation.evidence_state, 'blocked')::VARCHAR AS evidence_state,
    COALESCE(
        validation.evidence_state_reason,
        'Sport baseline missing from governed validation state.'
    )::VARCHAR AS evidence_state_reason,
    COALESCE(
        validation.evidence_state_as_of,
        TIMESTAMP '2026-05-12 00:00:00'
    ) AS evidence_state_as_of,
    COALESCE(
        validation.evidence_state_source_artifact,
        'docs/plan/2026-05-12-betting-pipeline-audit/evidence-readmodel-spec.md'
    )::VARCHAR AS evidence_state_source_artifact,
    COALESCE(validation.governance_status, 'descriptive_only')::VARCHAR AS governance_status,
    COALESCE(validation.descriptive_only_flag, TRUE) AS descriptive_only_flag,
    COALESCE(validation.contamination_flag, FALSE) AS contamination_flag,
    validation.contamination_reason::VARCHAR AS contamination_reason,
    COALESCE(validation.excluded_from_approval_flag, TRUE) AS excluded_from_approval_flag,
    se.observed_at,
    latest_snapshot.created_at_utc AS loaded_at,
    COALESCE(se.observed_at, latest_snapshot.created_at_utc, latest_snapshot.snapshot_hour_utc)::TIMESTAMP AS last_updated_at,
    latest_snapshot.snapshot_hour_utc,
    (se.open_position_count > 0) AS open_exposure_flag,
    se.open_exposure_amount,
    CASE
        WHEN se.open_position_count > 0 THEN 'open'
        ELSE 'closed'
    END::VARCHAR AS position_status,
    CASE
        WHEN se.open_position_count > 0 THEN 'included_open_risk'
        ELSE 'settled_only'
    END::VARCHAR AS exposure_inclusion_state,
    se.open_exposure_amount AS sport_exposure_amount,
    NULL::DOUBLE PRECISION AS same_event_exposure_amount,
    NULL::DOUBLE PRECISION AS same_side_exposure_amount,
    (se.open_position_count > 0) AS existing_position_flag,
    se.resting_order_exposure_amount,
    se.resting_order_count,
    se.executed_unsettled_exposure_amount,
    se.executed_unsettled_count,
    CASE
        WHEN se.resting_order_count > 0 AND se.executed_unsettled_count > 0
            THEN 'mixed_open_exposure'
        WHEN se.resting_order_count > 0 THEN 'resting_order_only'
        WHEN se.executed_unsettled_count > 0 THEN 'executed_unsettled_only'
        ELSE 'settled_only'
    END::VARCHAR AS exposure_state,
    'portfolio_value_snapshots'::VARCHAR AS bankroll_source,
    latest_snapshot.portfolio_value_dollars AS bankroll_amount,
    latest_snapshot.snapshot_hour_utc AS bankroll_observed_at,
    TO_CHAR(latest_snapshot.snapshot_hour_utc, 'YYYY-MM-DD"T"HH24:MI:SS')::VARCHAR AS bankroll_snapshot_id
FROM sport_exposure se
LEFT JOIN latest_snapshot
    ON TRUE
LEFT JOIN sport_validation_state_v1 validation
    ON validation.sport = se.sport;
