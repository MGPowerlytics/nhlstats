# Portfolio Betting Runtime Runbook

## Purpose

This runbook documents the live governed portfolio-betting behavior implemented in Waves 1-6. It is the operator-facing source of truth for approval gating, exposure accounting, drawdown handling, and runtime rejection semantics.

Use this document for runtime review only. It does **not** authorize any bankroll, Kelly, threshold, or eligibility relaxation.

## Live runtime controls

The live portfolio path loads recommendations from PostgreSQL and enforces governed controls before any approval-sized allocation is produced.

Current runtime sizing parameters:

| Control | Live value | Source |
| --- | --- | --- |
| Daily risk cap | `25%` of current portfolio value | `plugins/constants.py`, `plugins/portfolio_optimizer.py`, `governed_portfolio_risk_state_v1.daily_risk_cap_dollars` |
| Kelly scaling | `0.20` fractional Kelly | `plugins/constants.py`, `plugins/portfolio_optimizer.py` |
| Minimum bet size | `$2.00` | `plugins/portfolio_optimizer.py` |
| Maximum bet size | `$10.00` | `plugins/constants.py`, `plugins/portfolio_optimizer.py` |
| Maximum single-bet exposure | `3%` of bankroll | `plugins/constants.py`, `plugins/portfolio_optimizer.py` |
| Minimum edge filter | `3%` | `plugins/constants.py`, `plugins/portfolio_optimizer.py` |

These are runtime values, not change approvals. Any proposal to raise Kelly, risk caps, bet size limits, or eligibility thresholds remains blocked unless approval-grade CLV, calibration, and walk-forward evidence are all simultaneously reviewable.

## Evidence gate before sizing

The live database-backed optimizer fails closed before sizing:

1. If governed recommendations are unavailable, live approvals stop with `approval_blocked_reason=governed_recommendations_unavailable`.
2. If governed portfolio-risk context is unavailable, live approvals stop with `approval_blocked_reason=governed_risk_context_unavailable`.
3. If a recommendation is marked `abstain`, `sizing_eligible=false`, contaminated, or missing approval-grade evidence, it is excluded before sizing.
4. Approval-sized allocation is allowed only when recommendation evidence is not contaminated **and** CLV, calibration, and walk-forward evidence are approval-grade (or `approval_grade_evidence=true`).

Descriptive metrics are not approval evidence. Positive edge, positive EV, a Kelly output, or a non-null CLV row do **not** authorize sizing changes on their own.

## Probability and confidence semantics

Use the governed recommendation surface for probability review:

- Read model: `governed_evidence_record_v1`
- Key fields:
  - `probability_source`
  - `calibrated_probability`
  - `market_probability`
  - `edge`
  - `expected_value`
  - `kelly_fraction`
  - `confidence_label`

Important:

- `confidence_label` is a descriptive edge band (`HIGH`/`MEDIUM`/`LOW`), not an approval gate.
- Legacy numeric confidence settings are not the live approval control.
- Sport approval readiness is determined by governed evidence state and approval-grade evidence, not by dashboard confidence labels.

## Pricing and CLV semantics

Use governed surfaces instead of legacy page-local inference:

### Recommendation-time pricing

- Read model: `governed_evidence_record_v1`
- Key fields:
  - `quote_price_role`
  - `quote_source_system`
  - `quote_bookmaker`
  - `quote_observed_at`
  - `quote_loaded_at`
  - `quote_payload_ref`
  - `quote_lineage_status`
  - `quote_freshness_result`
  - `quote_fallback_status`

`quote_price_role` is the recommendation-time executable quote context. It is not the same as close-line evidence.

### CLV review

- Read model: `governed_clv_evidence_envelope_v1`
- Key fields:
  - `clv_source_type`
  - `clv_delta`
  - `clv_direction`
  - `closing_quote_source`
  - `closing_quote_at`
  - `close_price_role`
  - `close_freshness_result`
  - `selected_close_rule`
  - `selected_close_provenance`
  - `clv_evidence_tier`
  - `clv_contaminated_flag`

Interpretation:

- `clv_source_type=market_close` is the only governed market-close lineage.
- `binary_result_placeholder`, `missing_close`, and `unlinked_close` are not approval-grade close evidence.
- `clv_evidence_tier` and `clv_contaminated_flag` are descriptive quality fields; they do not by themselves unlock sizing changes.

## Exposure truth and drawdown handling

Use `governed_portfolio_risk_state_v1` for operator review and the Portfolio page's **Governed Risk State** table.

Key fields:

- `open_exposure_amount`
- `resting_order_exposure_amount`
- `executed_unsettled_exposure_amount`
- `remaining_daily_risk_budget_dollars`
- `drawdown_amount_dollars`
- `drawdown_ratio`
- `drawdown_state`
- `risk_of_ruin_state`
- `portfolio_guardrail_state`
- `portfolio_guardrail_reason_code`
- `portfolio_guardrail_reason_detail`
- `exposure_state`
- `rejection_reason_code`
- `rejection_reason_detail`

Runtime meaning:

- Governed open exposure includes `pending`, `open`, `placed`, and `filled` positions.
- Executed-but-unsettled exposure is included in live risk truth.
- Remaining daily risk budget is `25%` of current portfolio value minus governed open exposure.
- Drawdown state is derived from `portfolio_value_snapshots`.
- The portfolio guardrail blocks new approvals when bankroll state is unavailable,
  exhausted, governed open exposure already exhausts current portfolio value, or
  the latest governed snapshot explicitly enables a drawdown guardrail via
  `drawdown_gate_active=true`.
- `concentration_state=descriptive_only_no_governed_limit` means concentration is being reported, but no separate governed sport concentration cap is currently approved in the live path.

## Same-match conflict handling

The runtime blocks new approvals when the portfolio already carries resting or executed-but-unsettled exposure on the same governed match.

Operator cues:

- `same_match_conflict`
- `existing_position_state`
- `rejection_reason_code=existing_position_conflict`

This applies to same-side and same-event conflicts and uses canonical match linkage from governed execution context, not page-local ticker matching alone.

## Sport validation baseline

Use `sport_validation_state_v1` for readiness review.

Current governed baseline:

- `MLB`, `TENNIS`, `EPL`, `LIGUE1`: `shadow_only`
- `NBA`, `NHL`, `NFL`, `NCAAB`, `WNCAAB`: `blocked`

There is no current approval-grade sport state in the governed validation surface. Recommendations may still appear as descriptive rows, but approval-grade sizing changes remain blocked.

## Rejection semantics to use in operations

When reviewing blocked approvals, use the governed reason fields instead of legacy dashboard wording.

| Field | Meaning |
| --- | --- |
| `portfolio_guardrail_reason_code` | Portfolio-level block such as `risk_of_ruin_gate_blocked` or `drawdown_gate_blocked` |
| `portfolio_guardrail_reason_detail` | Human-readable explanation for the portfolio-level block |
| `rejection_reason_code` | Recommendation/sport-level rejection such as `missing_evidence`, `contaminated_evidence`, `existing_position_conflict`, or `risk_of_ruin_gate_blocked` |
| `rejection_reason_detail` | Human-readable reason aligned to the governed runtime decision |

If any governed surface shows `descriptive_only_flag=true`, `excluded_from_approval_flag=true`, contamination, or a non-null rejection code, do not loosen Kelly, edge, exposure, or approval thresholds.

## Operator review order

1. Check `sport_validation_state_v1` for the sport readiness state.
2. Check `governed_evidence_record_v1` for recommendation probability and quote lineage.
3. Check `governed_clv_evidence_envelope_v1` for close-line lineage and contamination.
4. Check `governed_recommendation_execution_link_v1` for recommendation-to-execution linkage.
5. Check `governed_portfolio_risk_state_v1` for open exposure truth, drawdown state, and rejection codes.
6. If evidence is descriptive-only, contaminated, or blocked anywhere in that chain, keep sizing and threshold changes blocked.

## What operators must not infer

- Do not treat dashboard confidence labels as approval readiness.
- Do not treat descriptive CLV rows as approval-grade evidence.
- Do not treat legacy open-risk semantics as current exposure truth.
- Do not infer that current runtime parameters are approved to increase.
- Do not recommend Kelly, bankroll, threshold, or eligibility relaxation without approval-grade CLV, calibration, and walk-forward evidence reviewed together.
