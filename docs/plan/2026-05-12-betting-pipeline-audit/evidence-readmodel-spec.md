# Evidence / Read-Model Specification — 2026-05-12 Betting Pipeline Audit

## Purpose and scope

This specification defines the implementation-ready, planning-only evidence contract that later PostgreSQL schema, view, and read-model work must satisfy for the betting pipeline audit package. It is derived from the canonical audit artifacts for pipeline lineage, probability/calibration, pricing/CLV, bankroll/risk, validation evidence, the PRD, and `plan.yaml`.

This round does **not** create migrations, tables, views, or runtime changes. The purpose is to define the field-level contract required to trace end-to-end behavior across:

- game and schedule identity
- market and quote lineage
- recommendation generation
- sizing and portfolio allocation
- execution and order/fill capture
- settlement and realized outcomes
- calibration, validation, and evidence-state governance
- pricing, closing-line, and CLV evidence

The contract must remain sport-aware for NBA, NHL, MLB, NFL, EPL, LIGUE1, NCAAB, WNCAAB, and TENNIS, while also supporting the current audit baseline that no sport is candidate-grade today.

## Source-of-truth alignment

This specification keeps parity with the audited findings:

- PostgreSQL remains the system of record for audit evidence and pipeline truth.
- `unified_games`, `game_odds`, `bet_recommendations`, `placed_bets`, `portfolio_value_snapshots`, and governed dashboard views are the current reporting/evidence backbone.
- Current evidence is fragmented by broken or weak joins, especially recommendation-to-execution linkage, CLV game resolution, sport-less calibration reporting, and dashboard bet detail sport loss.
- Current evidence states are descriptive and must distinguish **blocked** versus **shadow-only** sports; **candidate** remains reserved but unused in the current baseline.
- Portfolio-risk and settlement evidence are first-class audit requirements, not downstream add-ons.

## Core entity lineage and field groups

The future read-model layer should expose one coherent evidence contract across the following logical entities. The field groups below are required contract groups, not implementation instructions.

### 1. Game and market identity lineage

Required to prevent name/date-only joins and to keep sport-specific evidence comparable.

| Field group | Required fields | Why required |
| --- | --- | --- |
| Sport and competition context | `sport`, `league`, `market_type`, `competition_scope` | Validation and pricing evidence must remain sport-aware and like-for-like. |
| Canonical game identity | `canonical_game_id`, `source_game_id`, `source_game_table`, `event_date`, `scheduled_start_at` | Current pipeline uses both `unified_games` and sport-specific schedule tables. |
| Participant identity | `home_entity`, `away_entity`, `participant_a`, `participant_b`, `selection_side` | Tennis and some market types do not fit strict home/away semantics. |
| Canonical market identity | `market_ticker`, `market_external_id`, `market_source_system`, `selection_key` | Recommendation, execution, and CLV evidence cannot rely on `bet_id` alone. |
| Identity quality flags | `synthetic_ticker_flag`, `market_link_status`, `game_link_status`, `identity_notes` | Required because MLB and TENNIS can use synthetic or incomplete linkage today. |

### 2. Quote and pricing lineage

Required to support future pricing, freshness, and CLV consumers.

| Field group | Required fields | Why required |
| --- | --- | --- |
| Quote provenance | `quote_source_system`, `quote_bookmaker`, `quote_role`, `quote_observed_at`, `quote_loaded_at`, `quote_payload_ref` | Current pricing evidence is split across Kalshi, `game_odds`, and MLB snapshot history. |
| Quote values | `yes_ask`, `no_ask`, `decimal_price`, `implied_probability`, `market_probability` | Current recommendation and execution paths use different price shapes. |
| Freshness metadata | `quote_age_seconds`, `freshness_status`, `freshness_policy_name` | Current recommendation logic requires Kalshi presence but does not persist approval-grade freshness context. |
| Closing-line metadata | `closing_quote_role`, `proxy_close_flag`, `close_selection_rule`, `close_bookmaker_priority` | Current CLV paths split real close, proxy close, and binary placeholder behavior. |

### 3. Recommendation evidence

Required to trace model output into downstream sizing and dashboard consumers.

| Field group | Required fields | Why required |
| --- | --- | --- |
| Recommendation identity | `recommendation_id`, `recommendation_created_at`, `recommendation_run_id`, `recommendation_source_surface` | Current DB rows and JSON/file paths can diverge before reporting catches up. |
| Probability inputs | `raw_model_probability`, `calibrated_probability`, `market_probability`, `probability_source`, `calibration_method` | Probability and market evidence must remain separately visible. |
| Value metrics | `edge`, `expected_value`, `kelly_fraction`, `confidence_label`, `confidence_basis` | Current dashboard and sizing consumers rely on these values descriptively. |
| Join keys | `canonical_game_id`, `market_ticker`, `selection_key` | Later read models must support direct linkage from recommendation to market and outcome evidence. |
| Recommendation quality flags | `descriptive_only_flag`, `runtime_parity_flag`, `recommendation_backfill_flag` | Needed because current recommendation evidence can be descriptive-only or backfilled. |

### 4. Execution and placed-bet evidence

Required because current recommendation-to-execution linkage is broken when using `bet_id` as the shared join key.

| Field group | Required fields | Why required |
| --- | --- | --- |
| Execution identity | `placed_bet_id`, `order_id`, `trade_id`, `execution_source_surface`, `execution_status` | Current `placed_bets` identity can differ from recommendation identity. |
| Shared lineage keys | `recommendation_id`, `market_ticker`, `selection_key`, `canonical_game_id` | Later implementation must not depend on `bet_id` parity across tables. |
| Entry-price evidence | `entry_probability`, `entry_price_source`, `entry_price_at`, `entry_quote_role` | Execution may use fresher live asks than recommendation-time prices. |
| Order/fill timing | `submitted_at`, `accepted_at`, `filled_at`, `synced_at` | Required to distinguish recommendation timing from execution timing. |
| Notional and exposure | `stake_amount`, `contracts`, `max_loss`, `notional_exposure`, `bankroll_at_execution` | Needed for risk and exposure consumers, not only bet-detail reporting. |

### 5. Settlement and outcome evidence

Required because settlement is currently carried on `placed_bets` rather than a separate ledger.

| Field group | Required fields | Why required |
| --- | --- | --- |
| Settlement identity | `settlement_status`, `settlement_source`, `settled_at`, `result_recorded_at` | Current settlement evidence is merged into execution records. |
| Outcome values | `market_result`, `selection_result`, `win_flag`, `loss_flag`, `push_flag`, `realized_pnl` | Later audit consumers need direct realized-outcome fields. |
| Outcome lineage | `settlement_game_id`, `settlement_market_ticker`, `settlement_notes` | Preserves traceability when market identity or game identity was synthetic upstream. |
| Settlement quality flags | `outcome_placeholder_flag`, `manual_reconciliation_flag` | Needed to separate settled truth from operational placeholders or reconciled rows. |

### 6. CLV and closing-line evidence

Required because current CLV semantics are split between binary-result placeholders, real market closes, and MLB snapshot-based evidence.

| Field group | Required fields | Why required |
| --- | --- | --- |
| CLV computation identity | `clv_source_type`, `clv_computed_at`, `clv_definition_version` | Consumers must know which CLV meaning they are reading. |
| Entry/close comparison | `entry_probability`, `closing_probability`, `clv_delta`, `clv_direction` | Core pricing audit fields. |
| Closing provenance | `closing_quote_source`, `closing_quote_bookmaker`, `closing_quote_at`, `closing_quote_role` | Current backfill does not persist enough provenance on the bet row. |
| Quality and contamination | `binary_result_placeholder_flag`, `stale_close_flag`, `proxy_close_flag`, `clv_contaminated_flag` | Required to distinguish approval-grade evidence from descriptive-only evidence. |
| Join keys | `market_ticker`, `canonical_game_id`, `selection_key` | Needed because current CLV lookup can depend on team/date matching. |

### 7. Calibration, validation, and governance evidence

Required because current calibration dashboards lose sport identity and current validation evidence must distinguish blocked/shadow/candidate states.

| Field group | Required fields | Why required |
| --- | --- | --- |
| Sport-aware evidence state | `evidence_state`, `evidence_state_scope`, `evidence_state_reason`, `evidence_state_as_of`, `evidence_state_source_artifact` | Current audits require blocked, shadow-only, and candidate-aware labeling. |
| Probability artifact provenance | `artifact_id`, `artifact_version`, `artifact_family`, `runtime_consumer`, `artifact_available_flag` | Needed to evaluate research-to-production parity. |
| Validation lineage | `cohort_type`, `placed_bet_only_flag`, `synthetic_identity_flag`, `backfill_flag` | Required to separate executed, recommendation-only, and synthetic cohorts. |
| Temporal validation metadata | `training_window`, `holdout_window`, `walk_forward_window`, `review_timestamp` | Required for chronological validation review. |
| Governance flags | `governance_status`, `descriptive_only_flag`, `excluded_from_approval_flag`, `contamination_reason` | Current validation audit explicitly distinguishes admissible vs contaminated evidence. |

### 8. Portfolio-risk and exposure evidence

Required because the PRD and audits cover cross-sport allocation, exposure reconciliation, concentration, and drawdown behavior.

| Field group | Required fields | Why required |
| --- | --- | --- |
| Bankroll state | `bankroll_source`, `bankroll_amount`, `bankroll_observed_at`, `bankroll_snapshot_id` | Live sizing and dashboard history currently come from different sources/timings. |
| Sizing policy context | `kelly_fraction_applied`, `daily_risk_cap_pct`, `single_bet_cap_pct`, `single_bet_cap_amount`, `minimum_edge_threshold` | Risk consumers need the control context attached to decisions. |
| Exposure state | `open_exposure_flag`, `open_exposure_amount`, `position_status`, `exposure_inclusion_state` | Required because dashboard open-risk semantics currently exclude some `filled` rows. |
| Concentration context | `sport_exposure_amount`, `same_event_exposure_amount`, `same_side_exposure_amount`, `existing_position_flag` | Needed for later concentration and duplicate-risk review. |
| Portfolio timeline | `allocation_created_at`, `placement_completed_at`, `portfolio_snapshot_at`, `drawdown_state` | Cross-sport portfolio behavior cannot be reconstructed from recommendation rows alone. |

## Producer / consumer mapping

This contract should be produced and consumed at the following logical boundaries.

| Evidence area | Current producer surfaces named in audits | Required contract focus | Expected consumers |
| --- | --- | --- | --- |
| Game identity | `unified_games` plus legacy sport tables | Expose sport-aware canonical game identity and source-table lineage | Future audit joins, dashboard schedule/read models |
| Market quotes | `game_odds`; MLB snapshot history where available | Preserve quote source, role, freshness, and closing-line provenance | Pricing audit views, CLV consumers, live-market reporting |
| Recommendations | `bet_recommendations`; parallel JSON/file outputs still exist | Preserve recommendation-time probability, value metrics, and canonical join keys | Dashboard bet detail, calibration reporting, portfolio loaders, audits |
| Execution / settlement | `placed_bets` | Separate execution identity from recommendation identity while preserving shared join keys | Portfolio reporting, settlement review, CLV reporting, audit consumers |
| Portfolio history | `portfolio_value_snapshots` | Join bankroll/exposure state to recommendation and execution timing | Portfolio dashboards, risk audits, follow-on risk governance |
| Calibration / validation | Current dashboard calibration surface and offline/live artifact metadata described in audits | Add sport, market-type, evidence-state, cohort, and provenance fields | Future dashboard calibration pages, audit packages, governance review |

## Sport-aware evidence-state fields

Every future evidence-facing read model should carry a sport-aware state block. This is a contract requirement even where the underlying relation is aggregated.

### Required state fields

- `sport`
- `market_type`
- `evidence_state` (`blocked`, `shadow_only`, `candidate`)
- `evidence_dimension` (`probability`, `pricing_clv`, `validation`, `portfolio_risk`, `read_model`)
- `evidence_state_reason`
- `evidence_state_as_of`
- `evidence_state_source_artifact`
- `descriptive_only_flag`
- `contamination_flag`
- `contamination_reason`

### Current audited baseline

| Sport | Current baseline state | Notes required for parity |
| --- | --- | --- |
| MLB | `shadow_only` | Strongest current descriptive stack, but CLV and parity limitations remain. |
| TENNIS | `shadow_only` | Strong chronological/calibrated descriptive evidence, but not approval-grade. |
| EPL | `shadow_only` | Descriptive ensemble/calibration evidence exists, but live DAG parity is incomplete. |
| LIGUE1 | `shadow_only` | Live ensemble path exists, but provenance/parity remain incomplete. |
| NBA | `blocked` | No repeatable approval-grade validation path found. |
| NHL | `blocked` | Offline coefficients exist, but not governed live evidence. |
| NFL | `blocked` | Descriptive-only evidence. |
| NCAAB | `blocked` | Offline calibration metadata exists without runtime consumer parity. |
| WNCAAB | `blocked` | Offline calibration metadata exists without runtime consumer parity. |

`candidate` must remain a supported value in the contract even though no current sport qualifies.

## Provenance and freshness requirements

The future read-model layer must expose provenance strongly enough that audit consumers can tell **what** evidence they are reading, **where** it came from, **when** it was observed, and **whether** it is clean enough for descriptive versus governed use.

### Required provenance rules

1. **Every quote-derived field must expose source and time.**
   - Recommendation-time market probability, entry price, and closing price must each carry their own source/timestamp fields.
2. **Every model/calibration field must expose artifact lineage.**
   - Probability or calibration evidence without artifact identity, runtime consumer, and review timestamp is descriptive at best.
3. **Every synthetic or backfilled identity must be explicitly flagged.**
   - This is required for MLB/TENNIS synthetic ticker cases and recommendation backfills.
4. **Every settlement and CLV field must disclose placeholder vs market-based origin.**
   - Binary-result placeholders must never be indistinguishable from market-based closing evidence.
5. **Every portfolio-risk field must disclose timing basis.**
   - Consumers must be able to distinguish live bankroll/exposure timing from snapshot/reporting timing.

### Required freshness fields

At minimum, quote-bearing and exposure-bearing read models should support:

- `observed_at`
- `loaded_at`
- `last_updated_at`
- `freshness_status`
- `freshness_threshold_seconds`
- `stale_flag`

These are required contract concepts, not a mandated physical schema.

## Deferred implementation dependencies

The following dependencies are required inputs to later implementation, but none are executed in this round:

1. **Canonical join-key design**
   - Later schema/view work must expose a stable linkage across recommendation, market, execution, settlement, and CLV evidence without relying on `bet_id` parity.
2. **Sport-aware calibration/read-model surfacing**
   - Later dashboard and audit consumers must receive `sport` and `market_type` on calibration and validation evidence.
3. **Closing-line provenance persistence**
   - Later implementation must preserve chosen closing source, timestamp, stale/proxy status, and contamination flags.
4. **Portfolio exposure reconciliation**
   - Later work must align live exposure states with reporting semantics so open-risk consumers can distinguish filled-but-still-exposed rows from closed rows.
5. **Settlement and portfolio lineage bridging**
   - Later work must support traceability from recommendation through execution, settlement, and bankroll snapshots for the same decision chain.

This section defines dependencies only. It does not authorize migrations, runtime hardening, or view creation in the current round.

## Acceptance criteria verification

| Requirement | Verification |
| --- | --- |
| The spec defines the evidence fields needed to trace end-to-end pipeline behavior in PostgreSQL. | Satisfied through the concrete field groups for game identity, quotes, recommendations, execution, settlement, CLV, calibration/validation, and portfolio-risk evidence. |
| The spec supports future dashboard and audit consumers without requiring implementation this round. | Satisfied through producer/consumer mapping, sport-aware evidence-state fields, provenance/freshness requirements, and explicit planning-only framing. |
| The deliverable remains planning-only and does not create migrations or live views. | Satisfied; this document defines a contract and deferred dependencies only. |

## Implementation-readiness summary

This specification is implementation-ready because it defines the minimum field groups, join expectations, state semantics, and provenance/freshness requirements that later PostgreSQL schema, view, and read-model work must satisfy. It remains non-executable in this round and preserves parity with the audited findings that current evidence is fragmented, sport-sensitive, and not yet candidate-grade for any supported sport.
