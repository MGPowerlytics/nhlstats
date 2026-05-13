DROP VIEW IF EXISTS governed_portfolio_risk_state_v1;

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
peak_snapshot AS (
    SELECT
        MAX(pvs.portfolio_value_dollars)::DOUBLE PRECISION AS peak_portfolio_value_dollars
    FROM portfolio_value_snapshots pvs
),
open_positions AS (
    SELECT
        UPPER(COALESCE(NULLIF(pb.sport, ''), 'UNKNOWN'))::VARCHAR AS sport,
        COALESCE(
            NULLIF(pb.recommendation_canonical_game_id, ''),
            NULLIF(to_jsonb(pb)->>'canonical_game_id', ''),
            NULLIF(pb.recommendation_market_ticker, ''),
            NULLIF(pb.ticker, '')
        )::VARCHAR AS canonical_match_key,
        COALESCE(
            NULLIF(pb.recommendation_selection_key, ''),
            NULLIF(pb.bet_on, ''),
            NULLIF(to_jsonb(pb)->>'outcome_name', '')
        )::VARCHAR AS selection_key,
        LOWER(COALESCE(pb.status, ''))::VARCHAR AS position_status,
        COALESCE(pb.cost_dollars, 0.0)::DOUBLE PRECISION AS exposure_amount,
        COALESCE(pb.updated_at, pb.created_at, pb.placed_time_utc)::TIMESTAMP AS observed_at
    FROM placed_bets pb
    WHERE LOWER(COALESCE(pb.status, '')) IN ('pending', 'open', 'placed', 'filled')
),
same_event_exposure AS (
    SELECT
        sport,
        MAX(event_exposure)::DOUBLE PRECISION AS same_event_exposure_amount
    FROM (
        SELECT
            sport,
            canonical_match_key,
            SUM(exposure_amount)::DOUBLE PRECISION AS event_exposure
        FROM open_positions
        WHERE canonical_match_key IS NOT NULL
          AND canonical_match_key <> ''
        GROUP BY sport, canonical_match_key
    ) grouped_event_exposure
    GROUP BY sport
),
same_side_exposure AS (
    SELECT
        sport,
        MAX(side_exposure)::DOUBLE PRECISION AS same_side_exposure_amount
    FROM (
        SELECT
            sport,
            canonical_match_key,
            selection_key,
            SUM(exposure_amount)::DOUBLE PRECISION AS side_exposure
        FROM open_positions
        WHERE canonical_match_key IS NOT NULL
          AND canonical_match_key <> ''
          AND selection_key IS NOT NULL
          AND selection_key <> ''
        GROUP BY sport, canonical_match_key, selection_key
    ) grouped_side_exposure
    GROUP BY sport
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
),
portfolio_exposure AS (
    SELECT
        COALESCE(SUM(se.open_exposure_amount), 0.0)::DOUBLE PRECISION AS total_open_exposure_amount
    FROM sport_exposure se
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
    see.same_event_exposure_amount,
    sse.same_side_exposure_amount,
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
    (COALESCE(latest_snapshot.portfolio_value_dollars, 0.0) * 0.25)::DOUBLE PRECISION AS daily_risk_cap_dollars,
    GREATEST(
        (COALESCE(latest_snapshot.portfolio_value_dollars, 0.0) * 0.25) - COALESCE(portfolio_exposure.total_open_exposure_amount, 0.0),
        0.0
    )::DOUBLE PRECISION AS remaining_daily_risk_budget_dollars,
    peak_snapshot.peak_portfolio_value_dollars,
    latest_snapshot.portfolio_value_dollars AS current_portfolio_value_dollars,
    GREATEST(
        COALESCE(peak_snapshot.peak_portfolio_value_dollars, COALESCE(latest_snapshot.portfolio_value_dollars, 0.0))
        - COALESCE(latest_snapshot.portfolio_value_dollars, 0.0),
        0.0
    )::DOUBLE PRECISION AS drawdown_amount_dollars,
    CASE
        WHEN COALESCE(peak_snapshot.peak_portfolio_value_dollars, 0.0) <= 0.0 THEN NULL
        ELSE GREATEST(
            COALESCE(peak_snapshot.peak_portfolio_value_dollars, 0.0)
            - COALESCE(latest_snapshot.portfolio_value_dollars, 0.0),
            0.0
        ) / peak_snapshot.peak_portfolio_value_dollars
    END::DOUBLE PRECISION AS drawdown_ratio,
    CASE
        WHEN latest_snapshot.portfolio_value_dollars IS NULL
            OR peak_snapshot.peak_portfolio_value_dollars IS NULL
            THEN 'drawdown_state_unavailable'
        WHEN COALESCE(latest_snapshot.portfolio_value_dollars, 0.0) < COALESCE(peak_snapshot.peak_portfolio_value_dollars, 0.0)
            THEN 'drawdown_active'
        ELSE 'at_peak'
    END::VARCHAR AS drawdown_state,
    CASE
        WHEN latest_snapshot.portfolio_value_dollars IS NULL
            THEN 'risk_of_ruin_state_unavailable'
        WHEN COALESCE(latest_snapshot.portfolio_value_dollars, 0.0) <= 0.0
            THEN 'bankroll_exhausted'
        WHEN COALESCE(portfolio_exposure.total_open_exposure_amount, 0.0) >= COALESCE(latest_snapshot.portfolio_value_dollars, 0.0)
             AND COALESCE(portfolio_exposure.total_open_exposure_amount, 0.0) > 0.0
            THEN 'open_exposure_exhausts_bankroll'
        ELSE 'capital_available'
    END::VARCHAR AS risk_of_ruin_state,
    CASE
        WHEN latest_snapshot.portfolio_value_dollars IS NULL THEN 'blocked_risk_of_ruin'
        WHEN COALESCE(latest_snapshot.portfolio_value_dollars, 0.0) <= 0.0
            OR (
                COALESCE(portfolio_exposure.total_open_exposure_amount, 0.0) >= COALESCE(latest_snapshot.portfolio_value_dollars, 0.0)
                AND COALESCE(portfolio_exposure.total_open_exposure_amount, 0.0) > 0.0
            )
            THEN 'blocked_risk_of_ruin'
        ELSE 'eligible'
    END::VARCHAR AS portfolio_guardrail_state,
    CASE
        WHEN latest_snapshot.portfolio_value_dollars IS NULL
            OR COALESCE(latest_snapshot.portfolio_value_dollars, 0.0) <= 0.0
            OR (
                COALESCE(portfolio_exposure.total_open_exposure_amount, 0.0) >= COALESCE(latest_snapshot.portfolio_value_dollars, 0.0)
                AND COALESCE(portfolio_exposure.total_open_exposure_amount, 0.0) > 0.0
            )
            THEN 'risk_of_ruin_gate_blocked'
        ELSE NULL
    END::VARCHAR AS portfolio_guardrail_reason_code,
    CASE
        WHEN latest_snapshot.portfolio_value_dollars IS NULL
            THEN 'Portfolio drawdown state is unavailable because no governed bankroll snapshot is available.'
        WHEN COALESCE(latest_snapshot.portfolio_value_dollars, 0.0) <= 0.0
            THEN 'Portfolio bankroll is exhausted; new approvals stay blocked.'
        WHEN COALESCE(portfolio_exposure.total_open_exposure_amount, 0.0) >= COALESCE(latest_snapshot.portfolio_value_dollars, 0.0)
             AND COALESCE(portfolio_exposure.total_open_exposure_amount, 0.0) > 0.0
            THEN 'Governed open exposure already exhausts current portfolio value.'
        ELSE NULL
    END::VARCHAR AS portfolio_guardrail_reason_detail,
    CASE
        WHEN COALESCE(sse.same_side_exposure_amount, 0.0) > 0.0 THEN 'same_side'
        WHEN COALESCE(see.same_event_exposure_amount, 0.0) > 0.0 THEN 'same_event'
        ELSE 'sport'
    END::VARCHAR AS concentration_bucket,
    CASE
        WHEN COALESCE(validation.descriptive_only_flag, TRUE)
            THEN 'descriptive_only_no_governed_limit'
        WHEN COALESCE(sse.same_side_exposure_amount, 0.0) > 0.0
            THEN 'same_side_open_exposure_present'
        WHEN COALESCE(see.same_event_exposure_amount, 0.0) > 0.0
            THEN 'same_event_open_exposure_present'
        ELSE 'no_open_concentration'
    END::VARCHAR AS concentration_state,
    CASE
        WHEN se.resting_order_count > 0 AND se.executed_unsettled_count > 0
            THEN 'mixed_open_exposure'
        WHEN se.resting_order_count > 0 THEN 'resting_order_only'
        WHEN se.executed_unsettled_count > 0 THEN 'executed_unsettled_only'
        ELSE 'no_existing_position'
    END::VARCHAR AS existing_position_state,
    (COALESCE(see.same_event_exposure_amount, 0.0) > 0.0) AS same_match_conflict,
    CASE
        WHEN COALESCE(validation.contamination_flag, FALSE) THEN 'contaminated_evidence'
        WHEN COALESCE(validation.excluded_from_approval_flag, TRUE) THEN 'missing_evidence'
        WHEN (
            latest_snapshot.portfolio_value_dollars IS NULL
            OR COALESCE(latest_snapshot.portfolio_value_dollars, 0.0) <= 0.0
            OR (
                COALESCE(portfolio_exposure.total_open_exposure_amount, 0.0) >= COALESCE(latest_snapshot.portfolio_value_dollars, 0.0)
                AND COALESCE(portfolio_exposure.total_open_exposure_amount, 0.0) > 0.0
            )
        ) THEN 'risk_of_ruin_gate_blocked'
        WHEN se.open_position_count > 0 THEN 'existing_position_conflict'
        ELSE NULL
    END::VARCHAR AS rejection_reason_code,
    CASE
        WHEN COALESCE(validation.contamination_flag, FALSE)
            THEN COALESCE(validation.contamination_reason, 'Governed evidence is contaminated.')
        WHEN COALESCE(validation.excluded_from_approval_flag, TRUE)
            THEN COALESCE(
                validation.evidence_state_reason,
                'Approval-grade evidence is missing for this sport.'
            )
        WHEN latest_snapshot.portfolio_value_dollars IS NULL
            THEN 'Portfolio drawdown state is unavailable because no governed bankroll snapshot is available.'
        WHEN COALESCE(latest_snapshot.portfolio_value_dollars, 0.0) <= 0.0
            THEN 'Portfolio bankroll is exhausted; new approvals stay blocked.'
        WHEN COALESCE(portfolio_exposure.total_open_exposure_amount, 0.0) >= COALESCE(latest_snapshot.portfolio_value_dollars, 0.0)
             AND COALESCE(portfolio_exposure.total_open_exposure_amount, 0.0) > 0.0
            THEN 'Governed open exposure already exhausts current portfolio value.'
        WHEN se.open_position_count > 0
            THEN 'Resting orders and executed-but-unsettled positions remain in governed open exposure.'
        ELSE NULL
    END::VARCHAR AS rejection_reason_detail,
    'portfolio_risk_state_v1'::VARCHAR AS operator_semantics_version,
    'portfolio_value_snapshots'::VARCHAR AS bankroll_source,
    latest_snapshot.portfolio_value_dollars AS bankroll_amount,
    latest_snapshot.snapshot_hour_utc AS bankroll_observed_at,
    TO_CHAR(latest_snapshot.snapshot_hour_utc, 'YYYY-MM-DD"T"HH24:MI:SS')::VARCHAR AS bankroll_snapshot_id
FROM sport_exposure se
LEFT JOIN latest_snapshot
    ON TRUE
LEFT JOIN peak_snapshot
    ON TRUE
LEFT JOIN portfolio_exposure
    ON TRUE
LEFT JOIN same_event_exposure see
    ON see.sport = se.sport
LEFT JOIN same_side_exposure sse
    ON sse.sport = se.sport
LEFT JOIN sport_validation_state_v1 validation
    ON validation.sport = se.sport;
