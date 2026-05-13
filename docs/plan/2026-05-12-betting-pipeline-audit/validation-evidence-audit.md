# Validation Evidence Audit

## Scope

This audit reviews walk-forward, backtest, replay, and evidence-quality governance across the nine PRD sports: MLB, TENNIS, EPL, LIGUE1, NBA, NHL, NFL, NCAAB, and WNCAAB. It is descriptive only and records the current validation-evidence baseline for planning and approval-readiness review.

## Baseline normalization note

Wave 1 artifacts should treat EPL as **Shadow-only**. The completed audits show more than a fully blocked/descriptive-only posture because repo-local ensemble and calibration artifacts exist for EPL and are consumed on descriptive/dashboard-side paths, but the evidence stops short of a higher tier because the audited live DAG path still runs plain Elo and no persisted holdout or governed runtime artifact was found on that production path.

## Approval-Grade Validation Checklist

No sport is approval-grade today. A sport only meets the approval-grade checklist when all of the following are simultaneously true:

| Checklist item | Approval-grade expectation | Current repo-wide baseline |
| --- | --- | --- |
| Chronological validation | Leakage-safe walk-forward or equivalent time-ordered validation is repeatable and sport-specific. | Partial only; strongest checked-in chronology is TENNIS, with weaker or missing parity elsewhere. |
| Holdout governance | Holdout window, cohort boundaries, and artifact identity are persisted and reviewable. | Incomplete across all sports. |
| CLV evidence quality | CLV uses real market quotes and clear opening/closing precedence, not outcome-derived fields. | Fails globally because the binary-result updater contaminates approval use. |
| Cohort separation | Placed-bet evidence is separated from recommendation-only, backfilled, and synthetic records. | Incomplete; several paths mix these cohorts. |
| Runtime parity | The audited runtime path consumes the same governed artifact that the evidence claims to validate, fail-closed. | Incomplete; multiple sports have research/runtime divergence. |
| Read-model visibility | Validation tier, contamination flags, and artifact provenance are visible to downstream audit consumers. | Not consistently surfaced in reviewed read models. |

Descriptive evidence shows that a sport has some research, replay, calibration, or reporting support. Approval-grade status requires passing every checklist item above, not just showing partial research evidence.

## Cross-Cutting Findings

1. Live CLV is globally contaminated for approval use because the DAG calls `update_clv_for_closed_markets`, which writes `closing_line_prob` as `1.0` or `0.0` from final result, while real-price CLV exists separately.
2. Calibration training can mix placed bets with recommendation-only rows.
3. Placed-bet evidence lineage is weakened by backfill from recommendations.
4. Synthetic ticker generation exists for MLB and TENNIS recommendation persistence and should not be treated as exchange-grade approval evidence.
5. Dashboard calibration is descriptive, not approval-grade governance.

## Evidence Qualification Rubric

| Evidence qualification | Meaning in this audit package | What it can support in Wave 2 contracts | What keeps it out of a higher tier |
| --- | --- | --- | --- |
| Approval-grade | Leakage-safe, cohort-clean, runtime-parity evidence with governed artifact lineage and market-based CLV support. | Approval-ready validation, pricing, and sizing gates. | No sport currently satisfies this tier. |
| Shadow-only | Descriptive evidence is material enough to inform monitoring, planning, and downstream spec baselines, but not enough to approve live sizing or eligibility expansion. | Baseline matrices, gap registers, and descriptive comparators. | Missing governed holdout, contaminated CLV, weak cohort hygiene, or runtime parity gaps. |
| Blocked | Evidence is too weak, too indirect, or too disconnected from runtime behavior to support even a shadow-grade validation claim beyond descriptive mention. | Gap identification only. | No repeatable sport-specific validation path or governed artifact lineage. |
| Contaminated / excluded | Evidence exists, but the cohort or metric is not admissible for approval use. | Explicit exclusion rules in pricing, probability, and risk specs. | Binary-result CLV updater, recommendation backfills, synthetic tickers, or mixed executed/non-executed cohorts. |
| Missing | No audited evidence was found for the required validation dimension. | Dependency note for later planning only. | Absent artifact, absent read-model field, or absent repeatable workflow. |

## Sport-by-Sport Evidence Matrix

| Sport | State | Current evidence baseline | Approval-grade blocker |
| --- | --- | --- | --- |
| MLB | Shadow-only | Strongest descriptive evidence in repo. | Live CLV still uses the binary updater, so approval-grade CLV evidence is contaminated. |
| TENNIS | Shadow-only | Strong chronological and calibrated descriptive evidence. | Global CLV contamination remains, and synthetic ticker fallback creates approval-risk for evidence governance. |
| EPL | Shadow-only | Partial offline ensemble and calibration evidence. | No persisted holdout or governed runtime artifact on the production path. |
| LIGUE1 | Shadow-only | Partial runtime ensemble path and replay evidence. | Research-to-production parity remains weak. |
| NBA | Blocked | Descriptive-only evidence. | No repeatable approval-grade validation path found. |
| NHL | Blocked | Descriptive-only evidence. | No repeatable approval-grade validation path found. |
| NFL | Blocked | Descriptive-only evidence. | No repeatable approval-grade validation path found. |
| NCAAB | Blocked | Descriptive-only evidence. | No repeatable approval-grade validation path found. |
| WNCAAB | Blocked | Descriptive-only evidence. | No repeatable approval-grade validation path found. |

Across the nine sports, MLB and TENNIS have the strongest descriptive validation evidence, EPL and LIGUE1 have partial offline evidence, and NBA, NHL, NFL, NCAAB, and WNCAAB lack repeatable approval-grade validation governance.

## Sizing-Gate Evidence Policy

This audit supports the following descriptive policy baseline for downstream portfolio-risk work:

1. A future sizing gate is only evidence-qualified when the same sport has approval-grade support for walk-forward validation, calibration provenance, and market-based CLV evidence.
2. Shadow-only evidence can support monitoring, comparison, and planning discussions, but it does not satisfy a sizing gate on its own.
3. Contaminated evidence cannot be upgraded by aggregation. Binary-result CLV, recommendation-backfilled cohorts, and synthetic ticker-derived records remain non-qualifying even when attached to otherwise stronger sports.
4. Missing or runtime-divergent evidence leaves the sport blocked for sizing-gate purposes until a later wave defines a governed parity contract.

## Validation-Related Schema / Read-Model Notes

For the downstream evidence-read-model specification, this audit implies that validation consumers need a clear way to distinguish sport, cohort, provenance, and contamination state. At minimum, the reviewed artifacts point to the need for the following conceptual fields or equivalents:

| Note area | Why downstream consumers need it |
| --- | --- |
| `sport` and `market_type` context | Validation evidence must remain sport-specific and comparable only within like-for-like markets. |
| `validation_status` / `evidence_tier` | Dashboards and audits need to surface blocked vs shadow-only vs higher tiers explicitly. |
| `cohort_type` and `placed_bet_only` lineage | Approval review depends on separating executed bets from recommendation-only, backfill, and synthetic cohorts. |
| `artifact_id` / `artifact_version` / `runtime_consumer` linkage | Research-to-production parity cannot be judged without artifact provenance and the consuming runtime path. |
| `holdout_window` / `walk_forward_window` metadata | Chronological validation claims need reviewable window boundaries. |
| `clv_source_type` and contamination flags | Approval-grade CLV must be distinguishable from binary-result or otherwise contaminated updates. |
| `governance_status` and `review_timestamp` | Later approval packages need to show whether evidence was governed, descriptive-only, or explicitly excluded. |

## Eligibility Baseline Matrix by Sport

| Sport | Baseline state | Why this is the current baseline | Why it is not higher |
| --- | --- | --- | --- |
| MLB | Shadow-only | Governed prediction/evidence contract is the strongest in repo, with explicit persisted prediction metadata. | Approval-grade CLV remains contaminated and checked-in artifact availability/parity is still incomplete. |
| TENNIS | Shadow-only | Chronological calibration evidence and live calibrated Elo usage provide the clearest descriptive validation path. | Production-grade holdout/governance evidence is still incomplete, and synthetic ticker fallback weakens approval use. |
| EPL | Shadow-only | Partial ensemble/calibration evidence exists and is strong enough to justify descriptive shadow treatment across Wave 1 artifacts. | The audited live DAG path does not consume that governed evidence, and no persisted holdout/runtime artifact was found. |
| LIGUE1 | Shadow-only | Live ensemble wiring and replay evidence support a descriptive shadow baseline. | Provenance and research-to-production parity remain too weak for a higher tier. |
| NBA | Blocked | Only descriptive/global evidence was found. | No repeatable approval-grade validation path or governed calibrated runtime artifact was found. |
| NHL | Blocked | Offline coefficients exist, but approval-grade runtime validation evidence does not. | The audited betting path does not show governed calibrated consumption. |
| NFL | Blocked | Descriptive-only evidence was found. | No repeatable approval-grade validation path or governed calibrated runtime artifact was found. |
| NCAAB | Blocked | Offline calibration metadata exists descriptively. | No runtime consumer or approval-grade validation governance was found. |
| WNCAAB | Blocked | Offline calibration metadata exists descriptively. | No runtime consumer or approval-grade validation governance was found. |

No sport is currently classified as candidate or approval-grade in this Wave 1 baseline.

## Acceptance Criteria Verification

1. Walk-forward, backtest, replay, and evidence-quality governance were evaluated across all supported sports.
2. Approval-grade evidence requirements for CLV, calibration, walk-forward validation, and runtime parity are defined in the checklist and rubric above.
3. Shadow-only sports are explicitly identified: MLB, TENNIS, EPL, and LIGUE1.
4. Blocked sports are explicitly identified: NBA, NHL, NFL, NCAAB, and WNCAAB.
5. The artifact now supplies the downstream contract detail promised in `plan.yaml`: validation checklist, evidence qualification rubric, sizing-gate evidence policy, schema/read-model notes, and eligibility baseline matrix.
6. The audit remains descriptive only and makes no implementation commitments.
