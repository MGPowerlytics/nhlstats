# Pricing / CLV Governance Spec

## Purpose and scope

This document defines the canonical pricing, freshness, closing-line, and CLV governance contract for later implementation. It is spec-only: it does not change runtime behavior, plan state, or production code in this round.

This spec covers all downstream consumers that currently read or depend on pricing or CLV concepts, including recommendation generation, recommendation persistence, portfolio sizing, execution capture, placed-bet evidence, offline diagnostics, and dashboard read models.

## Current-state baseline

- Live pricing is **not** governed by a single fair-odds contract today. Current live behavior compares model probability to Kalshi-implied probability and does not implement one explicit no-vig fair-odds path.
- Best-price behavior is split today:
  - live recommendations use Kalshi only;
  - `OddsComparator.get_best_odds()` returns the highest stored decimal price;
  - The Odds API `best_*` fields currently maximize implied probability rather than payout.
- CLV is split across three meanings today:
  - binary settlement placeholder CLV;
  - later `game_odds` backfill CLV;
  - separate MLB snapshot-based CLV evidence logic.
- Audit evidence is strongest in `mlb_odds_snapshots`. Cross-sport `placed_bets` CLV is only partially evidenced, and dashboard recommendation surfaces are descriptive-only.
- Approval-grade evidence must be treated separately from descriptive metrics. **No sport is approval-grade today.**

## Canonical pricing terminology

| Term | Canonical meaning | Notes on current state |
| --- | --- | --- |
| **Reference price** | The governed market-derived probability or odds baseline used for comparison, validation, or reporting. | Today this is inconsistent across consumers. |
| **Fair-odds / fair price** | The governed non-executable estimate of true outcome probability after the chosen normalization method. | No single live fair-odds contract exists today. |
| **Executable price** | The actual venue-specific price available for order entry at decision time. | Live path is Kalshi-first; persisted evidence is inconsistent. |
| **Best price** | The highest-payout executable price among eligible contemporaneous quotes after freshness and provenance rules are applied. | Current helpers disagree on what “best” means. |
| **Close price** | The governed final pre-resolution reference quote selected under closing-line precedence rules. | Must never mean realized outcome. |
| **Descriptive CLV** | A reporting metric that may use incomplete or non-governed evidence and is not admissible for approval decisions. | Includes current dashboard-adjacent and placeholder paths. |
| **Approval-grade CLV evidence** | CLV supported by persisted provenance, freshness outcome, close-selection lineage, and cohort cleanliness sufficient for governance review. | No sport meets this today. |

## Fair-odds and price-role contract

Future implementation must separate price roles instead of allowing one field to serve multiple meanings.

1. **Fair-odds/reference contract**
   - A consumer must declare whether it uses:
     - a **fair-odds/reference price** for edge and validation, or
     - an **executable price** for order-entry realism.
   - Fair-odds must be distinct from executable venue quotes.
   - If no governed fair-odds path exists for a consumer, that consumer must be labeled as using an executable-market comparison only.

2. **Executable-price contract**
   - Executable price must identify the actual venue/source and quote timestamp used for the decision or bet.
   - Recommendation-time executable price and realized execution price are separate concepts and must remain separately attributable.

3. **Best-price contract**
   - “Best price” means **best payout among eligible executable quotes**, not highest implied probability.
   - A best-price result is valid only if all candidate quotes pass the same freshness, source-eligibility, and market-role rules.
   - If a consumer uses one venue only, it must not be labeled “best price”; it is a single-venue executable price.

## Freshness and provenance rules

Every governed pricing or CLV evidence row must persist enough context to reconstruct why a price was chosen.

### Required provenance fields

For any persisted reference, executable, best, or close price used by a downstream consumer, the consuming evidence row must carry or be able to join to:

- source timestamp from the originating feed;
- persistence/load timestamp;
- bookmaker or source identity;
- price role (`reference`, `executable`, `best`, `close`, or equivalent);
- quote side / outcome identity;
- stale/not-stale outcome under the governing freshness policy;
- selected-close provenance when the row is used for CLV;
- raw-source linkage or payload identity sufficient for audit replay.

### Freshness requirements

- Freshness must be evaluated against the **source timestamp**, not only database write time.
- A stale decision must be explicit and reviewable, not inferred later.
- If a consumer falls back from a preferred quote to an older or proxy quote, the fallback status must be evident on the consuming row.
- A quote that lacks source timestamp or source identity is descriptive-only by definition.

## Closing-line precedence contract

The canonical close-price meaning is the final eligible **pre-resolution** quote selected under explicit precedence.

### Precedence

1. Prefer an explicit close-designated snapshot if one exists and is admissible.
2. Otherwise select the latest admissible pregame/pre-resolution quote.
3. Apply the governed source-priority list only after admissibility and recency are evaluated.
4. Persist the selected source, timestamp, role, and stale/not-stale result on the consuming evidence row.
5. Realized outcome, settlement result, or binary market resolution must never be labeled close price.

### Consumer rule

- Reporting that uses placeholder or outcome-derived values may exist only as **descriptive CLV**.
- Approval-facing consumers must use the governed close-price contract or remain non-qualifying.

## CLV evidence contract and quality tiers

CLV must always specify both the entry-side evidence and the close-side evidence.

### Canonical CLV definition

`CLV = entry implied probability - governed close implied probability`

Where:
- entry implied probability comes from the governed executable-entry evidence for the bet or recommendation cohort being analyzed; and
- governed close implied probability comes from the closing-line precedence contract above.

### Quality tiers

| Tier | Meaning | Current baseline |
| --- | --- | --- |
| **Tier 0 — Descriptive-only** | Useful for reporting or monitoring, but not admissible for approval or sizing governance. Includes missing provenance, missing stale outcome, missing selected-close lineage, or outcome-derived close placeholders. | Dashboard recommendation surfaces; binary placeholder CLV; helper-only best-price paths. |
| **Tier 1 — Partially evidenced** | Uses real market quotes but does not persist all selected provenance, freshness outcome, or cohort-clean metadata on the consuming evidence row. | Current cross-sport `placed_bets` real-price backfill from `game_odds`. |
| **Tier 2 — Approval-grade evidence** | Persists source timestamp, source identity, role, selected-close provenance, freshness result, and cohort-clean linkage sufficient for audit review and downstream approval use. | No sport qualifies today. |

### Current evidence assessment

- **Strongest current evidence pattern:** MLB snapshot history, because it persists source timestamp, role, bookmaker, implied probability, and raw payload.
- **Cross-sport gap:** selected bookmaker, selected timestamp, and stale status are not consistently persisted per bet when CLV is backfilled from `game_odds`.
- **Governance conclusion:** MLB provides the best current model for approval-grade provenance, but no sport is approval-grade because approval-facing CLV remains globally contaminated or incomplete.

## Descriptive vs approval-grade consumer mapping

| Consumer type | Governed interpretation |
| --- | --- |
| Recommendation dashboards and recommendation read models | Descriptive pricing surfaces unless they persist governed provenance and role semantics. |
| `placed_bets` CLV populated from outcome-derived placeholder logic | Descriptive-only. |
| `placed_bets` CLV populated from later `game_odds` backfill without persisted selected-close provenance | Partially evidenced only. |
| MLB snapshot-based offline evidence | Strongest current provenance pattern, but still not approval-grade as a repo-wide operating state. |
| Approval, eligibility, or sizing decisions | Must require approval-grade CLV evidence and may not rely on descriptive metrics. |

## Deferred implementation dependencies

The following are deferred requirements for later execution and are not performed in this round:

1. A single governed fair-odds/reference-price contract for edge consumers.
2. A canonical best-price selector that optimizes payout under shared admissibility rules.
3. Persisted provenance/freshness fields on consuming evidence rows, especially for cross-sport `placed_bets` CLV.
4. Explicit close-selection lineage and stale outcome persistence.
5. Consumer labeling that distinguishes descriptive metrics from approval-grade evidence in read models and reporting.
6. Cohort-clean evidence separation so recommendation-only, synthetic, backfilled, and executed-bet records cannot be conflated in approval workflows.

## Acceptance criteria verification

- **Canonical pricing and CLV terms, provenance requirements, and quality tiers:** satisfied by the terminology, freshness/provenance, close-precedence, and CLV tier sections above.
- **Actionable for later implementation without embedding runtime fixes:** satisfied; this artifact defines contracts, roles, and deferred dependencies only.
- **Inside PRD scope with no production code work:** satisfied; this is a non-executable governance spec and does not alter runtime behavior or `plan.yaml`.
