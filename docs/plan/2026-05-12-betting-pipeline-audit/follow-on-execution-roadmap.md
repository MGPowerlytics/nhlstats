# Follow-on Execution Roadmap

## Purpose and scope
This roadmap packages the approved follow-on execution sequence for the betting-pipeline audit deliverables. It is planning-only, directly consumable by a later implementation cycle, and keeps all runtime, migration, model, threshold, bankroll, and documentation changes outside the current approval round.

Primary inputs: `governed-probability-spec.md`, `pricing-clv-governance-spec.md`, `portfolio-risk-spec.md`, `evidence-readmodel-spec.md`, `pipeline-evidence-map.md`, `probability-calibration-audit.md`, `pricing-clv-audit.md`, `bankroll-risk-audit.md`, `validation-evidence-audit.md`, `runtime-config-drift-audit.md`, `docs/prd.yaml`, and `plan.yaml`.

## Recommended later waves
| Wave | Later implementation area | Explicit dependencies | Verification gates and evidence prerequisites |
| --- | --- | --- | --- |
| 0 | Approval gate close (`approval-readiness-review`) | This roadmap; full audit/spec package | Confirms the package remains audit/spec/planning only, closes hidden dependency issues, and keeps all runtime work deferred. |
| 1 | Evidence visibility foundation (`evidence-readmodel-spec` + `sport-validation-framework`) | Approval gate close; governed probability, pricing/CLV, and evidence/read-model specs; validation baseline | Supported sports must emit visible `blocked` / `shadow-only` / `candidate` evidence states, carry provenance/cohort fields, and expose contamination/runtime-parity flags before runtime hardening starts. |
| 2 | Probability pipeline hardening (`probability-pipeline-hardening`) | Wave 0; Wave 1; governed-probability spec | Sport-specific governed artifacts or explicit fail-closed blocked/shadow behavior must be wired consistently across runtime and reporting. No sport may advance without calibration, walk-forward, and market-based CLV prerequisites. |
| 2 | Pricing and CLV hardening (`pricing-execution-hardening`) | Wave 0; Wave 1; pricing/CLV governance spec | Reference price, executable price, best price, and close-price roles must be contract-aligned; binary-result CLV must remain non-qualifying; provenance, freshness, and selected-close lineage must be reviewable. |
| 3 | Portfolio risk hardening (`risk-control-hardening`) | Wave 2 pricing hardening; Wave 1 evidence visibility; portfolio-risk spec | Exposure truth, concentration state, and operator-visible rejection reasons must exist; no Kelly, bankroll, threshold, or allocation change may advance without approval-grade CLV, calibration, and walk-forward evidence. |
| 4 | Portfolio drawdown gate (`portfolio-drawdown-gate`) | Wave 3 risk hardening; Wave 1 validation outputs; portfolio-risk spec | Drawdown, concentration, and risk-of-ruin states must align across runtime and reporting; strong single-sport metrics cannot bypass portfolio-level safety gates. |
| 5 | Runtime docs and final gate (`runtime-docs-and-final-gate`) | Waves 2-4 complete and verified | Durable docs must reflect implemented behavior only after runtime parity is proven and final approval evidence states are reviewable. |

## Deferred backlog and out of scope in this round
**Non-executable in this round:** `probability-pipeline-hardening`, `pricing-execution-hardening`, `risk-control-hardening`, `sport-validation-framework`, `portfolio-drawdown-gate`, and `runtime-docs-and-final-gate`.

**Also out of scope in this round:** production code changes, migrations, model retuning, live betting parameter updates, bankroll/Kelly/threshold changes, dashboard redesign, and any approval of candidate or approval-grade sports before evidence gates pass.

## Risks and sequencing notes
- Start with evidence visibility and sport-state outputs; current audits show broken joins, sport-loss in read models, contaminated CLV, and runtime/reporting drift.
- Do not parallelize pricing and risk hardening before evidence/read-model visibility exists; otherwise approval evidence and operator semantics can diverge again.
- Treat MLB, TENNIS, EPL, and LIGUE1 as shadow-only baselines and NBA, NHL, NFL, NCAAB, and WNCAAB as blocked until later gates prove otherwise.
- Keep legacy heuristics, binary-result CLV, synthetic ticker lineage, recommendation backfills, and dashboard-only calibration outputs non-qualifying for approval use.

## Acceptance criteria verification
- **Purpose and scope present:** yes; this artifact defines the follow-on package and preserves the no-runtime-change boundary for the current round.
- **Later waves with dependencies present:** yes; Waves 0-5 provide ordered implementation areas and explicit prerequisites.
- **Verification gates present:** yes; each wave lists evidence prerequisites and review gates.
- **Deferred backlog and out-of-scope items marked non-executable:** yes.
- **Directly consumable by later implementation:** yes; backlog items, ordering, and gates are stated in execution-ready form.
