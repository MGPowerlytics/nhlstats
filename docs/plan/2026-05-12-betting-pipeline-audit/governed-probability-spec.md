# Governed Probability Source, Calibration, and Eligibility Specification

## Purpose and scope
This document is the Wave 2 governed probability contract for NBA, NHL, MLB, NFL, EPL, LIGUE1, NCAAB, WNCAAB, and TENNIS. It is implementation-ready for a later execution wave but non-executable in this round: it defines approved probability-source, calibration, fallback, and eligibility rules without changing runtime behavior, models, thresholds, or hardening controls.

## Evidence-qualified state model
- Blocked: evidence is insufficient for governed eligibility or sizing use; sport may appear only in descriptive audits.
- Shadow-only: evidence is material enough for monitoring/comparison, but not for live sizing or eligibility expansion.
- Candidate: reserved for a future state where governed artifact lineage, sport-specific calibration, walk-forward evidence, and market-based CLV exist but approval is still pending. No sport currently qualifies.
- Approval-grade: reserved for a future state where governed artifact lineage, cohort-clean calibration evidence, leakage-safe walk-forward validation, and market-based CLV all pass together.

## Sport-by-sport probability source contract
| Sport | Current state | Approved probability source contract | Calibration contract | Fallback contract | Eligibility rule |
| --- | --- | --- | --- | --- | --- |
| MLB | Shadow-only | `mlb_model_predictions` governed rows are the only approved future probability source for eligible MLB use. Raw Elo is not an approved substitute when governed mode is expected. | Persisted prediction rows must retain model version, calibration method, ECE-at-train, feature hash, run date, abstain flag, and abstention reason. | If governed artifact or validated feature row is unavailable, fail closed to explicit abstention; do not fall back to ensemble or plain Elo for eligible/sizing paths. | Remains shadow-only until market-based CLV, walk-forward evidence, and runtime/reporting parity are all approval-grade. |
| TENNIS | Shadow-only | The canonical source is the tennis Elo payload with `calibrated_prob_a`; an optional feature-model artifact may be used only as a governed overlay with explicit enablement and provenance. | Tour-specific calibration must remain explicit (`ATP`/`WTA`) and carry artifact identity, holdout metadata, and validation window provenance. | Feature-model failure may fall back to calibrated Elo only for descriptive/shadow use; future eligible/sizing paths must fail closed until the fallback itself is approval-grade. | Remains shadow-only until CLV contamination is removed, synthetic-ticker lineage is excluded from approval use, and walk-forward evidence is reviewable. |
| EPL | Shadow-only | A future governed EPL source must be the same artifact/runtime path claimed by the evidence package; plain DAG Elo and dashboard-side ensemble evidence are not interchangeable. | Any EPL calibration must be sport-specific, artifact-bound, and tied to the live consumer path rather than descriptive dashboard-only usage. | No future eligible path may silently degrade from governed ensemble/calibrated output to plain Elo. | Remains shadow-only until governed runtime parity, persisted holdout evidence, and market-based CLV support are present together. |
| LIGUE1 | Shadow-only | The live-wired ensemble family is the strongest current source and is the only acceptable starting point for a later governed LIGUE1 contract. | Later governed artifacts must add model version, sample window, calibration summary, and provenance fields not currently present in the reviewed artifact. | If ensemble artifact provenance or availability fails, future eligible/sizing paths must abstain rather than substitute plain Elo. | Remains shadow-only until provenance, calibration evidence, walk-forward evidence, and CLV quality are approval-grade. |
| NBA | Blocked | Current plain Elo is descriptive only and is not an approved governed source for future eligibility or sizing. | Offline/global calibration views are not admissible because they are not sport-specific approval evidence and rely on selected cohorts. | No automatic fallback is approved; future eligible use must fail closed until a governed calibrated artifact exists. | Blocked until sport-specific calibration, walk-forward validation, and market-based CLV evidence exist with runtime parity. |
| NHL | Blocked | Current plain Elo is descriptive only. | Offline NHL coefficients without live governed consumption are not sufficient. | No automatic fallback is approved; fail closed for future eligible use. | Blocked until governed calibrated runtime consumption and approval-grade validation evidence exist. |
| NFL | Blocked | Current plain Elo is descriptive only. | No approved sport-specific governed calibration artifact was audited. | No automatic fallback is approved; fail closed for future eligible use. | Blocked until governed artifact lineage, calibration evidence, walk-forward evidence, and CLV evidence exist. |
| NCAAB | Blocked | Current plain Elo is descriptive only. | Checked-in offline Platt metadata is descriptive only and not runtime-governed. | No automatic fallback is approved; fail closed for future eligible use. | Blocked until runtime consumer parity and approval-grade validation evidence exist. |
| WNCAAB | Blocked | Current plain Elo is descriptive only. | Checked-in offline Platt metadata is descriptive only and not runtime-governed. | No automatic fallback is approved; fail closed for future eligible use. | Blocked until runtime consumer parity and approval-grade validation evidence exist. |

## Calibration artifact contract
Any future approved calibration artifact must be sport-specific and market-comparable, and must expose at minimum: `sport`, `market_type`, `artifact_id`, `artifact_version`, `runtime_consumer`, `training_window`, `holdout_window`, `walk_forward_window`, `cohort_type`, `placed_bet_only` lineage, calibration method, summary quality metric(s), and review timestamp. Approval use is excluded when calibration is derived from mixed executed/recommendation-only cohorts, non-sport-specific dashboard aggregates, or artifacts not consumed by the audited runtime path.

## Eligibility states and fail-closed rules
1. Current baseline by sport: MLB/TENNIS/EPL/LIGUE1 are shadow-only; NBA/NHL/NFL/NCAAB/WNCAAB are blocked.
2. No sport may be treated as candidate or approval-grade in this round.
3. Future sizing recommendations must fail closed unless the same sport has all three of: approval-grade market-based CLV evidence, approval-grade calibration evidence, and approval-grade leakage-safe walk-forward evidence.
4. Contaminated evidence is non-qualifying even when attached to otherwise stronger sports. This includes binary-result CLV updates, mixed recommendation/execution cohorts, and synthetic ticker lineage for approval purposes.
5. Runtime/reporting divergence is disqualifying for eligibility promotion. The approved evidence package must validate the same artifact and consumer path intended for future governed use.
6. Shadow-only evidence may support monitoring, comparison, and planning, but never sizing recommendations.
7. Blocked sports may be described in audits but must not receive governed eligibility or sizing treatment.

## Deferred implementation dependencies
The following are prerequisites for later execution waves and are not commitments for this round: sport-specific read-model visibility for sport/cohort/provenance fields; artifact lineage persistence; clean separation of executed versus recommendation-only cohorts; removal of contaminated CLV from approval evidence; and parity between dashboard/reporting consumers and the governed runtime consumer.

## Acceptance criteria verification
- All supported sports are named with evidence-qualified states.
- Approved probability-source, calibration, fallback, and eligibility requirements are defined by sport.
- Future gating is fail-closed and explicitly requires CLV, calibration, and walk-forward evidence before sizing recommendations.
- The specification is implementation-ready but non-executable in this round.
- The specification stays inside PRD scope and makes no runtime hardening commitments.
