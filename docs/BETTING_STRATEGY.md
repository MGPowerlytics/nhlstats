# Governed Betting Strategy

## Strategy summary

The live system is a governed value-betting pipeline. It compares internal win probabilities with market-implied probabilities, records executable quote lineage, and only allows approval-sized allocation when governed evidence passes fail-closed review.

This document describes implemented runtime behavior only. It does not approve any bankroll, Kelly, threshold, or eligibility increase.

## Supported governed sports

The governed implementation cycle covers:

- `NBA`
- `NHL`
- `MLB`
- `NFL`
- `EPL`
- `LIGUE1`
- `NCAAB`
- `WNCAAB`
- `TENNIS`

Current sport validation is published in `sport_validation_state_v1`. The shipped baseline is `shadow_only` for `MLB`, `TENNIS`, `EPL`, and `LIGUE1`, and `blocked` for `NBA`, `NHL`, `NFL`, `NCAAB`, and `WNCAAB`. No sport should be described as approval-grade in durable docs.

Additional constants or dashboard selectors outside this list are not governed approval scope for this cycle.

## Probability semantics

Recommendation evidence is published through `governed_evidence_record_v1`.

The implemented probability fields are:

- `probability_source`
- `calibrated_probability`
- `market_probability`
- `edge`
- `expected_value`
- `kelly_fraction`
- `confidence_label`

Runtime notes:

- `edge = calibrated_probability - market_probability`
- `confidence_label` is descriptive and edge-derived
- the live minimum edge gate is `3%`
- numeric confidence settings are not the current approval gate

Recommendation metrics can describe opportunity quality, but they are not approval-grade evidence by themselves.

## Pricing semantics

Recommendation-time pricing and execution-time pricing are separated.

### Recommendation-time quote role

`governed_evidence_record_v1` carries:

- `quote_price_role`
- `quote_source_system`
- `quote_bookmaker`
- `quote_observed_at`
- `quote_loaded_at`
- `quote_payload_ref`
- `quote_lineage_status`
- `quote_freshness_result`
- `quote_fallback_status`

These fields describe the executable quote context used for recommendation review.

### Execution and linkage

`governed_recommendation_execution_link_v1` is the recommendation-to-execution lineage surface. Operators should use it to review:

- recommendation linkage status
- execution status
- entry quote source and freshness
- canonical game, ticker, and selection linkage

## CLV semantics

`governed_clv_evidence_envelope_v1` is the canonical CLV review surface.

Implemented distinctions:

- `entry_price_role=executable`
- `close_price_role=close` only when a governed market close is available
- `selected_close_rule=latest_admissible_pregame_quote` for governed market-close selection
- `clv_source_type` distinguishes `market_close` from `binary_result_placeholder`, `missing_close`, and `unlinked_close`

Approval guidance:

- `market_close` is required for governed close-line review
- placeholder, missing, stale, or unlinked close evidence is not approval-grade
- CLV rows remain descriptive unless they are clean and reviewed together with calibration and walk-forward evidence

## Exposure and drawdown semantics

Portfolio risk review is published through `governed_portfolio_risk_state_v1`.

Implemented behavior:

- open exposure includes resting orders and executed-but-unsettled filled positions
- daily risk budget is governed off current portfolio value
- `drawdown_state`, `drawdown_ratio`, and `drawdown_amount_dollars` come from governed portfolio snapshots
- an explicit drawdown block is activated only when the latest governed portfolio
  snapshot sets `drawdown_gate_active=true`, with the matching governed reason
  code/detail persisted alongside the snapshot
- `risk_of_ruin_state` and `portfolio_guardrail_state` can block new approvals even when a single recommendation looks attractive
- same-match conflicts are governed from canonical execution linkage and open-position state

The live portfolio path therefore uses portfolio-level exposure truth, not legacy “open orders only” semantics.

## Current runtime sizing policy

The implemented runtime parameters are:

- `25%` daily risk cap
- `20%` Kelly scaling
- `$2` minimum bet size
- `$10` maximum bet size
- `3%` maximum single-bet exposure
- `3%` minimum edge

These are current runtime settings only. They are not a recommendation to increase size, edge thresholds, or risk appetite.

## Approval-grade evidence policy

Sizing or threshold changes remain blocked unless all three evidence streams are approval-grade and reviewable together:

1. CLV evidence
2. Calibration evidence
3. Walk-forward evidence

If any stream is missing, descriptive-only, contaminated, placeholder-based, stale, or excluded from approval, recommendations stay blocked for approval-grade sizing changes.

Explicitly:

- descriptive metrics are not enough
- positive EV is not enough
- positive CLV alone is not enough
- a shadow-only or blocked sport state is not enough
- dashboard labels alone are not enough
- calibration bucket summaries are descriptive unless they are tied back to governed approval evidence

## Operator-facing decision rules

When reviewing live behavior:

1. Start with `sport_validation_state_v1`.
2. Review recommendation probability and quote lineage in `governed_evidence_record_v1`.
3. Review execution linkage in `governed_recommendation_execution_link_v1`.
4. Review close-line lineage and contamination in `governed_clv_evidence_envelope_v1`.
5. Review portfolio rejection fields in `governed_portfolio_risk_state_v1`.

Blocked recommendations must be described with governed fields such as:

- `evidence_state`
- `governance_status`
- `descriptive_only_flag`
- `contamination_flag`
- `excluded_from_approval_flag`
- `portfolio_guardrail_reason_code`
- `rejection_reason_code`

## What this strategy does not claim

- It does not claim that any sport is currently approval-grade.
- It does not claim that Kelly or bankroll should be increased.
- It does not claim that threshold relaxation is approved.
- It does not claim that descriptive dashboard summaries substitute for governed evidence review.
