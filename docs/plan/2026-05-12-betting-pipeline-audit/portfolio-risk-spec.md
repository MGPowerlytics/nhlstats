# Portfolio Risk and Evidence-Qualified Sizing Specification

## 1. Purpose and scope

This document is the implementation-ready planning specification for future portfolio-risk hardening in the 2026-05-12 betting pipeline audit program. It converts the current-state findings in `pipeline-evidence-map.md`, `bankroll-risk-audit.md`, `validation-evidence-audit.md`, `runtime-config-drift-audit.md`, `docs/prd.yaml`, and `plan.yaml` into a future contract for risk controls, exposure truth, and evidence-qualified sizing governance.

This artifact is planning-only. It does **not** change live bankroll, Kelly, threshold, allocation, or execution behavior, and it does **not** modify `plan.yaml`.

The scope covers the nine PRD sports: NBA, NHL, MLB, NFL, EPL, LIGUE1, NCAAB, WNCAAB, and TENNIS. The contract applies to both:

- **portfolio-level behavior**: cross-sport allocation, concentration, drawdown handling, exposure reconciliation, and operator-visible risk state
- **single-bet behavior**: per-bet eligibility, same-match conflict handling, evidence-qualified sizing inputs, and rejection semantics

## 2. Current audited baseline to preserve during planning

The following current behaviors are treated as read-only baseline facts for this planning round:

| Area | Current audited baseline | Evidence status |
| --- | --- | --- |
| Live bankroll input | Sizing uses live Kalshi balance before optimization and refreshes after placement. | Evidence-backed |
| Daily portfolio cap | Live sizing enforces `25%` max daily allocation. | Evidence-backed control with heuristic value |
| Single-bet caps | Live sizing enforces `$10` max bet and `3%` max single-bet exposure. | Evidence-backed control with heuristic values |
| Kelly scaling | Live DAG/config uses `0.20` fractional Kelly; optimizer defaults/docs drift elsewhere. | Runtime-enforced, drifted documentation |
| Eligibility filter | Live optimizer filters on excluded segments, minimum edge, and positive Kelly; configured numeric confidence threshold is not applied there. | Mixed control and drift |
| Cross-sport allocation | Current allocator gives each sport one initial seat, then ranks remaining bets by EV. | Evidence-backed heuristic |
| Match conflict protection | Existing position/resting order check occurs at execution time, not during optimizer sizing. | Evidence-backed but split-surface |
| Correlation and concentration | No explicit cross-sport correlation model, sport cap, shared-slate cap, or covariance penalty is implemented. | Gap |
| Drawdown handling | No drawdown-triggered sizing reduction, bankroll floor, stop-loss, or risk-of-ruin gate is implemented. | Gap |
| Exposure reporting | Dashboard open-risk semantics exclude `filled` exposure even though live bankroll may already be committed. | Material operator-semantics gap |

This specification freezes that baseline for planning. No current parameter value is approved for increase, relaxation, or wider rollout through this document.

## 3. Portfolio risk-control domains

### 3.1 Domain contract summary

| Domain | Current finding | Future contract requirement |
| --- | --- | --- |
| Cross-sport allocation | Current diversification is a one-seat-per-sport ordering heuristic, not a governed concentration model. | Future runtime must separate diversification intent from hard concentration controls and expose both at portfolio level. |
| Concentration control | No per-sport, per-slate, per-market, or correlated-position cap is currently governed. | Future runtime must evaluate concentration before bet approval and persist the decision basis. |
| Drawdown control | No live drawdown or risk-of-ruin gate exists. | Future runtime must support drawdown-state-aware sizing eligibility and operator-visible drawdown state. |
| Exposure reconciliation | Live bankroll, `placed_bets`, and dashboard views do not currently express one exposure truth. | Future runtime and reporting must share a canonical exposure taxonomy and auditable reconciliation fields. |
| Single-bet risk gating | Per-bet caps exist, but same-match conflict logic is applied late and open exposure is not subtracted from sizing budget. | Future runtime must make single-bet approval contingent on portfolio-aware remaining budget and conflict checks. |
| Evidence-qualified sizing | Current risk values are hard-coded and not evidence-gated by CLV, calibration, and walk-forward quality. | Future sizing changes must fail closed unless approval-grade evidence exists for the affected sport and cohort. |
| Operator semantics | Dashboard labels and recommendation details can overstate what is governed or currently exposed. | Future read models must expose explicit provenance, cohort, contamination, and exposure-state fields. |

### 3.2 Required domains for future implementation

Future implementation under this specification must treat the following as first-class risk domains, not optional enhancements:

1. **Cross-sport allocation**
   The system must evaluate how much of the daily risk budget is allocated across sports, not only whether any one bet fits a per-bet cap.

2. **Concentration**
   The system must measure concentration at minimum by sport, event/match, market/ticker family, and same-slate or same-driver grouping where multiple positions can fail together.

3. **Drawdown and bankroll state**
   The system must support drawdown-aware eligibility and operator-visible portfolio state, even if exact thresholds are defined only in a later implementation phase.

4. **Exposure truth**
   The system must reconcile resting orders, executed-but-unsettled exposure, settled P&L, and snapshot balance/value into a single governed portfolio-risk interpretation.

5. **Single-bet logic inside portfolio logic**
   A bet may satisfy edge and per-bet caps yet still be rejected because it breaches concentration, drawdown, evidence-tier, or remaining-budget constraints.

## 4. Evidence-qualified sizing contract

### 4.1 Governing rule

No future change to bankroll sizing, Kelly fraction, max daily risk, single-bet limits, confidence/edge thresholds, sport eligibility expansion, or concentration/drawdown parameters may be recommended or implemented unless the affected decision is supported by **all three** of the following for the relevant sport and market cohort:

1. **CLV evidence** using market-based closing evidence, not binary-result or otherwise contaminated close substitutes
2. **Calibration evidence** with sport-specific provenance, artifact identity, and cohort hygiene
3. **Walk-forward evidence** with chronological boundaries, repeatable holdout governance, and runtime-parity support

Shadow-only evidence may inform monitoring and planning, but it does not qualify a sizing change. Blocked, contaminated, synthetic, recommendation-backfilled, or runtime-divergent evidence must fail closed for sizing-governance purposes.

### 4.2 Evidence-qualified sizing inputs

Every future sizing decision must be traceable to the following conceptual inputs or direct equivalents:

| Input class | Required meaning | Current planning implication |
| --- | --- | --- |
| `sport` / `market_type` / `cohort_type` | Identifies the exact sport and comparable cohort for the decision. | Must remain sport-aware; cross-sport aggregation cannot substitute for sport-specific approval. |
| `live_bankroll_dollars` | Live bankroll used for sizing at decision time. | Must remain distinguishable from hourly snapshot balance/value. |
| `current_open_exposure_dollars` | Unsettled committed risk already consuming capital. | Must include executed exposure, not only pending/open/placed rows. |
| `remaining_daily_risk_budget_dollars` | Residual portfolio budget after subtracting already-committed eligible exposure. | Cannot be inferred from recommendation-only rows. |
| `evidence_tier` | Approval-grade vs shadow-only vs blocked vs contaminated/missing. | Only approval-grade can support sizing changes. |
| `walk_forward_artifact_id` / window metadata | Repeatable chronology and holdout lineage. | Required before any threshold or sizing recommendation advances. |
| `calibration_artifact_id` / provenance | Sport-specific calibration lineage and cohort cleanliness. | Required before any threshold or sizing recommendation advances. |
| `clv_source_type` / provenance | Market-based closing evidence lineage. | Binary-result CLV is explicitly non-qualifying. |
| `contamination_flags` | Synthetic ticker, recommendation backfill, mixed executed/non-executed cohorts, runtime divergence, or other exclusion markers. | Any active contamination flag blocks evidence-qualified sizing use. |
| `existing_position_state` | Open position/resting order/same-match conflict state. | Must be evaluated before approval, not only at final placement. |
| `portfolio_concentration_state` | Current exposure concentration across defined buckets. | Required for portfolio-level approval logic. |
| `drawdown_state` | Current drawdown/risk-of-ruin regime used by the approved policy. | Required for any future drawdown-aware gate. |

### 4.3 Rejection conditions

A future sizing or allocation decision must be rejected when any of the following is true:

1. The sport or cohort lacks approval-grade CLV, calibration, **or** walk-forward evidence.
2. The evidence set is contaminated by binary-result CLV, synthetic ticker substitution, recommendation backfill, mixed executed/non-executed cohorts, or runtime-parity failure.
3. The runtime consumer cannot prove it is using the same governed evidence artifact claimed by the approval package.
4. The exposure view excludes executed-but-unsettled capital or otherwise cannot reconcile live bankroll to open commitments.
5. The bet would exceed the approved remaining daily risk budget after already-open exposure is accounted for.
6. The bet breaches a governed concentration bucket, same-match conflict rule, or drawdown regime.
7. Operator-facing reporting cannot show the rejection basis and evidence provenance for the decision.

### 4.4 Parameter-change policy

This specification does not approve any new numeric setting. Instead, it sets the future change policy:

- Current hard-coded live values remain descriptive baseline only.
- Any proposal to increase, decrease, relax, or reinterpret a sizing parameter must cite approval-grade CLV, calibration, and walk-forward evidence.
- Evidence from one sport cannot justify a sizing increase for another sport without sport-specific approval evidence.
- A stronger single-sport result cannot bypass portfolio-level concentration, exposure-truth, or drawdown requirements.

## 5. Exposure-truth and operator-semantics contract

### 5.1 Canonical exposure semantics

Future runtime and reporting must converge on one governed exposure interpretation with at least these distinct states:

| Exposure state | Required meaning |
| --- | --- |
| `resting_order_exposure` | Capital reserved by orders not yet executed. |
| `executed_unsettled_exposure` | Capital already committed by executed/filled positions that are still live. |
| `settled_exposure` | Positions resolved to won/lost/void/cancelled/settlement-pending outcome accounting states. |
| `realized_pnl_dollars` | Realized result from settled positions only. |
| `snapshot_balance_dollars` | Periodic balance/value snapshot for historical reporting, separate from live decision-time bankroll. |
| `live_bankroll_dollars` | Exchange-sourced bankroll used for the current decision. |
| `remaining_daily_risk_budget_dollars` | Decision-time budget after subtracting governed open exposure from the approved daily cap. |

`filled` or equivalent executed states must not disappear from operator-visible open-risk semantics simply because the order is no longer resting.

### 5.2 Recommendation-to-execution semantics

The audited pipeline shows that recommendation `bet_id` and execution `bet_id` are not a reliable canonical join. Future implementation under this specification must therefore:

- treat recommendation identity and execution identity as separate concepts
- use a governed market/exchange linkage contract for recommendation-to-execution traceability
- expose when a recommendation has no valid execution linkage
- prevent operator pages from implying a direct recommendation-to-execution trace when the evidence model cannot prove it

### 5.3 Operator-facing audit fields

Future read models or equivalent operator surfaces must expose enough state to audit both approved and rejected decisions. At minimum, the portfolio-risk contract requires fields equivalent to:

| Field | Purpose |
| --- | --- |
| `decision_timestamp_utc` | Time of sizing/risk decision |
| `decision_scope` (`single_bet` / `portfolio`) | Distinguishes per-bet vs portfolio-level decision |
| `sport` / `market_type` / `ticker` | Sports and market identity |
| `recommendation_id` / `execution_id` / linkage status | Makes recommendation-execution relationship explicit |
| `live_bankroll_dollars` | Decision-time bankroll |
| `daily_risk_cap_dollars` | Decision-time cap derived from approved policy |
| `resting_order_exposure_dollars` | Unexecuted committed risk |
| `executed_unsettled_exposure_dollars` | Live filled exposure |
| `remaining_daily_risk_budget_dollars` | Residual allocable budget |
| `requested_bet_size_dollars` / `approved_bet_size_dollars` | Approval delta |
| `single_bet_cap_state` | Shows whether per-bet cap constrained the bet |
| `concentration_bucket` / `concentration_state` | Shows concentration evaluation basis |
| `drawdown_state` | Shows current drawdown/risk regime |
| `existing_position_state` / `same_match_conflict` | Shows conflict gating basis |
| `evidence_tier` | Approval-grade, shadow-only, blocked, contaminated, missing |
| `walk_forward_artifact_id` / window metadata | Chronological validation provenance |
| `calibration_artifact_id` / provenance | Calibration provenance |
| `clv_source_type` / `clv_artifact_id` | CLV provenance and admissibility |
| `contamination_flags` | Explicit exclusion reasons |
| `rejection_reason_code` / `rejection_reason_detail` | Operator-readable fail-closed basis |
| `operator_semantics_version` | Allows dashboards/runtime to prove they use the same contract meaning |

## 6. Drift-to-backlog mapping

The runtime drift findings must map into deferred implementation work as follows:

| Drift finding from audit package | Required backlog destination | Why this mapping is required |
| --- | --- | --- |
| Dashboard open-risk semantics understate live filled exposure. | `evidence-readmodel-spec`, `risk-control-hardening`, `portfolio-drawdown-gate` | Exposure truth must be corrected in both reporting and runtime budget logic. |
| Configured confidence thresholds are described as gates but are not live optimizer gates. | `risk-control-hardening`, probability/calibration governance follow-on, `runtime-docs-and-final-gate` | Future risk controls must distinguish descriptive labels from governed eligibility rules. |
| Static excluded segments act as live gates without evidence linkage. | `risk-control-hardening`, `approval-readiness-review` | Legacy heuristics must either become evidence-qualified controls or remain explicitly non-governed. |
| Calibration page sport semantics are cosmetic. | `evidence-readmodel-spec`, `sport-validation-framework` | Sport-specific approval evidence must be visible and queryable. |
| Bet detail implies recommendation-to-execution traceability that the data model does not prove. | `evidence-readmodel-spec`, `pricing-clv-governance-spec`, `runtime-docs-and-final-gate` | Risk, pricing, and operator surfaces require a governed linkage contract. |
| Runtime parameter values have drifted from durable docs. | `runtime-docs-and-final-gate` | Durable documentation must reflect implemented behavior only after governance and hardening land. |
| Sport-scope semantics drift across PRD, defaults, constants, and dashboard selectors. | `sport-validation-framework`, `evidence-readmodel-spec`, `runtime-docs-and-final-gate` | Supported-sport scope must be consistent across runtime, evidence, and operator surfaces. |

## 7. Deferred implementation dependencies

This specification is intentionally upstream of runtime changes. Future execution depends on the following later work:

1. **Pricing and CLV governance contract**
   Portfolio-risk hardening cannot approve sizing changes until market-based CLV provenance, contamination exclusions, and pricing semantics are governed.

2. **Sport-aware evidence/read-model contract**
   Exposure truth, sport-specific evidence tiers, operator audit fields, and recommendation/execution linkage need a governed reporting contract.

3. **Approval-readiness review**
   Parameter changes must be blocked until the review can verify approval-grade evidence and runtime parity.

4. **Sport validation framework**
   Shadow-only, blocked, contaminated, and approval-grade states must become testable per sport and cohort.

5. **Risk-control hardening**
   This is the downstream implementation phase that will apply the contract to live concentration, exposure, and sizing logic.

6. **Portfolio drawdown gate**
   Drawdown and risk-of-ruin behavior remain deferred until evidence and exposure contracts are operationalized.

7. **Runtime docs finalization**
   Durable operator documentation must wait until implementation is complete and verified so docs reflect runtime truth rather than planned intent.

## 8. Acceptance criteria verification

| Criterion | Verification |
| --- | --- |
| Covers cross-sport allocation, concentration, drawdown, and exposure reconciliation | Sections 3 and 5 define those domains as required future contract surfaces. |
| States that future sizing changes require CLV, calibration, and walk-forward evidence | Section 4.1 and Section 4.4 make this an explicit fail-closed governing rule. |
| Defines evidence-qualified sizing inputs, rejection conditions, and operator-facing audit fields | Sections 4.2, 4.3, and 5.3 enumerate the required contract inputs, rejections, and audit fields. |
| Addresses portfolio-level behavior plus single-bet logic | Sections 3.2 and 4.3 require portfolio-aware gating in addition to per-bet controls. |
| Remains planning-only with no live parameter changes | Sections 1 and 2 explicitly freeze the current audited baseline and approve no new numeric setting. |

## 9. Planning decision summary

The audited system currently has evidence-backed per-bet and daily caps, but portfolio-level concentration, drawdown, and exposure-truth governance remain incomplete. Future work must therefore implement risk controls only after pricing/CLV provenance, calibration evidence, walk-forward evidence, and sport-aware reporting contracts can prove that sizing decisions are evidence-qualified, portfolio-aware, and operator-auditable.
