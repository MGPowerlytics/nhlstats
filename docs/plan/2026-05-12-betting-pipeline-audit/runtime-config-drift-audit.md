# Runtime Config Drift Audit — 2026-05-12 Betting Pipeline Audit

## Scope

- Task: `runtime-config-drift-audit`
- Reviewed runtime and operator-facing surfaces:
  - `dags/multi_sport_betting_workflow.py`
  - `plugins/portfolio_optimizer.py`
  - `plugins/constants.py`
  - `plugins/odds_comparator.py`
  - `plugins/portfolio_betting.py`
  - `plugins/bet_tracker.py`
  - `dashboard/data_layer.py`
  - `dashboard/pages/portfolio.py`
  - `dashboard/pages/live_markets.py`
  - `dashboard/pages/bet_detail.py`
  - `dashboard/pages/calibration.py`
  - `dashboard/contracts/bet_recommendation_v1.json`
  - `dashboard/contracts/portfolio_summary_v1.json`
  - `migrations/stats_schema/V008__create_dashboard_read_model_views.sql`
  - `docs/PORTFOLIO_BETTING.md`
  - `docs/BETTING_STRATEGY.md`
  - previously completed artifacts in this plan directory, especially `pipeline-evidence-map.md`, `bankroll-risk-audit.md`, `pricing-clv-audit.md`, and `probability-calibration-audit.md`

## Evidence labels used in this audit

- **Runtime-enforced control**: actively applied in live code.
- **Documented-but-not-enforced**: present in docs/config shape but not applied by the current live filter path.
- **Operator-semantics gap**: dashboard or operator-facing surfaces describe a different meaning, freshness, or scope than live behavior.
- **Undocumented heuristic**: hard-coded rule with no governed evidence contract or operator-facing explanation.

## Current runtime control baseline

| Control area | Current runtime behavior | Operator-facing semantics today | Classification | Repo evidence |
| --- | --- | --- | --- | --- |
| Minimum edge | Live filter excludes `opp.edge < 0.03`; confidence labels are also derived from edge bands (`0.15` / `0.08`) | Live Markets and Bet Detail show `edge`, `expected_value`, and `confidence`, but not the freshness/provenance split behind those values | Runtime-enforced control + operator-semantics gap | `dags/multi_sport_betting_workflow.py:65-71`, `plugins/constants.py:42-49`, `plugins/portfolio_optimizer.py:798-801`, `plugins/odds_comparator.py:131-144`, `migrations/stats_schema/V008__create_dashboard_read_model_views.sql:142-191,376-430` |
| Confidence threshold | DAG passes `min_confidence=0.65`; constants also define `MIN_CONFIDENCE_FOR_BET = 0.68`, but `PortfolioOptimizer.filter_opportunities()` never applies either numeric threshold | Dashboard presents `confidence` as a primary recommendation field; docs still describe “minimum confidence” / Elo probability thresholds as if enforced | Documented-but-not-enforced + operator-semantics gap | `dags/multi_sport_betting_workflow.py:71,1528-1537`, `plugins/constants.py:71-79`, `plugins/portfolio_optimizer.py:222-230,533-536,783-811`, `docs/PORTFOLIO_BETTING.md:33-35,97-105`, `docs/BETTING_STRATEGY.md:15,42-45,58-61` |
| Segment exclusions | `_get_excluded_segments()` hard-codes all LOW segments plus NHL MEDIUM, TENNIS HIGH/MEDIUM, WNCAAB HIGH/MEDIUM, NCAAB HIGH/MEDIUM from prior ROI commentary | No reviewed dashboard surface exposes which segments are suppressed or why; operators only see surviving recommendations | Undocumented heuristic + operator-semantics gap | `dags/multi_sport_betting_workflow.py:1473-1508`, `plugins/portfolio_optimizer.py:792-799` |
| Kelly fraction | Live DAG and constants use `0.20` fractional Kelly | Operator-facing docs still describe quarter Kelly (`0.25`) as the default | Runtime-enforced control + operator-facing drift | `dags/multi_sport_betting_workflow.py:67-70,1530-1534`, `plugins/constants.py:63-70`, `docs/PORTFOLIO_BETTING.md:21,98-99`, `docs/BETTING_STRATEGY.md:23-30` |
| Daily and single-bet caps | Live path uses `25%` max daily risk, `$10` max bet, `3%` max single-bet exposure | Portfolio page shows aggregate exposure but not the cap values or whether current exposure is measured against live bankroll or dashboard snapshot balance; docs still cite `$50` and `5%` | Runtime-enforced control + operator-semantics gap | `dags/multi_sport_betting_workflow.py:67-70,1528-1535`, `plugins/constants.py:63-71`, `plugins/portfolio_optimizer.py:843-924`, `dashboard/contracts/portfolio_summary_v1.json:3-16`, `dashboard/pages/portfolio.py:81-123`, `docs/PORTFOLIO_BETTING.md:25-27,98-103`, `docs/BETTING_STRATEGY.md:27-30` |
| Sport coverage defaults | Live DAG passes all nine PRD sports into `process_daily_bets()`, but optimizer defaults still fall back to six sports if no explicit list is supplied; constants add `cba` and `unrivaled` | Calibration page selector offers `CBA` and `Unrivaled`; operator pages can imply broader governed coverage than the PRD/live betting scope | Undocumented heuristic + operator-semantics gap | `docs/prd.yaml:18-25`, `dags/multi_sport_betting_workflow.py:1607-1620`, `plugins/portfolio_optimizer.py:642-643,701-702,964-965`, `plugins/constants.py:5-24`, `dashboard/pages/calibration.py:70-85` |
| Open exposure semantics | Live placement refreshes bankroll and syncs orders immediately; order sync maps executed orders to local status `filled` | Portfolio read model counts open exposure only for `pending/open/placed`; Portfolio page labels this as “Open Risk” / “Open Positions” | Operator-semantics gap | `plugins/portfolio_betting.py:176-196`, `plugins/bet_tracker.py:794-815`, `migrations/stats_schema/V008__create_dashboard_read_model_views.sql:106-140`, `dashboard/data_layer.py:559-583`, `dashboard/pages/portfolio.py:95-123` |
| Calibration evidence semantics | Runtime betting path is sport-specific, but the calibration view aggregates all recommendations into shared buckets with no sport column | Calibration page exposes a sport selector and returns a `by_sport` block labeled with the selected sport even though the underlying query is not sport-filtered | Operator-semantics gap | `migrations/stats_schema/V008__create_dashboard_read_model_views.sql:215-264`, `dashboard/data_layer.py:1062-1150`, `dashboard/pages/calibration.py:70-149` |
| Bet detail semantics | Runtime execution records order/fill state in `placed_bets`, but recommendation and execution use different `bet_id` conventions | Bet Detail presents recommendation probability, edge, EV, Kelly, and placement status in one view, joined on `bet_id`, which does not represent the actual runtime recommendation→execution linkage contract | Operator-semantics gap | `migrations/stats_schema/V008__create_dashboard_read_model_views.sql:376-430`, `dashboard/data_layer.py:1042-1058`, `dashboard/pages/bet_detail.py:125-205`, `docs/plan/2026-05-12-betting-pipeline-audit/pipeline-evidence-map.md:90-109` |

## Prioritized drift register

| Rank | Drift item | Downstream risk | Planning significance | Current state evidence |
| --- | --- | --- | --- | --- |
| 1 | **Dashboard open-risk semantics understate live filled exposure.** Executed orders become `filled`, but dashboard open risk excludes `filled` and labels the remainder as current exposure. | High: operator can read materially understated active risk while live bankroll has already been committed. | High: affects portfolio-risk spec, evidence read-model spec, and roadmap prioritization for risk observability. | `plugins/bet_tracker.py:802-815`, `migrations/stats_schema/V008__create_dashboard_read_model_views.sql:109-120`, `dashboard/pages/portfolio.py:95-123`, `docs/plan/2026-05-12-betting-pipeline-audit/bankroll-risk-audit.md:70-110`, `docs/plan/2026-05-12-betting-pipeline-audit/pipeline-evidence-map.md:123-128` |
| 2 | **Configured confidence thresholds are not runtime gates.** `min_confidence`/`MIN_CONFIDENCE_FOR_BET` exist, docs describe Elo confidence floors, but live filtering uses edge and segment exclusions instead. | High: operators and future planners can misclassify a descriptive label as a governed control. | High: directly impacts portfolio-risk spec and any future eligibility/risk governance contract. | `dags/multi_sport_betting_workflow.py:71,1535-1537`, `plugins/constants.py:71-79`, `plugins/portfolio_optimizer.py:783-811`, `docs/PORTFOLIO_BETTING.md:33-35,103-105`, `docs/BETTING_STRATEGY.md:15,42-45` |
| 3 | **Static excluded segments act as live gates without dashboard visibility or evidence linkage.** | High: selection behavior is materially shaped by undocumented ROI heuristics that are invisible in operator-facing read models. | High: roadmap needs a governed distinction between evidence-qualified blocks and legacy heuristics. | `dags/multi_sport_betting_workflow.py:1473-1508`, `plugins/portfolio_optimizer.py:792-799`, `dashboard/pages/live_markets.py:72-86` |
| 4 | **Calibration page sport semantics are cosmetic.** The selector changes labels, not the underlying evidence cohort. | Medium-High: can mislead sport-level approval judgments and contaminate planning around calibration readiness. | High: directly affects evidence-readmodel and governed-probability follow-on work. | `migrations/stats_schema/V008__create_dashboard_read_model_views.sql:215-264`, `dashboard/data_layer.py:1062-1150`, `dashboard/pages/calibration.py:70-149`, `docs/plan/2026-05-12-betting-pipeline-audit/probability-calibration-audit.md:28-33,64-69` |
| 5 | **Recommendation detail surfaces present recommendation-time pricing/confidence as if they are traceable execution evidence.** | Medium-High: operator interpretation of edge/EV/confidence can blur recommendation context with placed-bet reality. | High: blocks clean consumer contracts for pricing/CLV and evidence read models. | `migrations/stats_schema/V008__create_dashboard_read_model_views.sql:142-191,376-430`, `dashboard/pages/live_markets.py:72-86`, `dashboard/pages/bet_detail.py:125-205`, `docs/plan/2026-05-12-betting-pipeline-audit/pricing-clv-audit.md:55-63,94-100` |
| 6 | **Runtime parameter values have drifted from operator-facing docs.** Live uses `0.20` Kelly, `3%` min edge, `$10` max bet, `3%` max single-bet exposure; docs still describe `0.25`, `5%`, `$50`, `5%`, and explicit Elo-confidence floors. | Medium: does not change runtime, but it distorts planning baselines and control classification. | Medium-High: follow-on roadmap needs a clean current-state baseline before specifying governed controls. | `dags/multi_sport_betting_workflow.py:65-71`, `plugins/constants.py:42-49,63-72`, `docs/PORTFOLIO_BETTING.md:21-35,96-105`, `docs/BETTING_STRATEGY.md:15,23-30` |
| 7 | **Sport-scope semantics drift across PRD, runtime defaults, constants, and dashboard selectors.** | Medium: can hide unsupported/default-fallback behavior and misstate audit scope to operators. | Medium: matters for roadmap packaging and supported-sport governance boundaries. | `docs/prd.yaml:18-25`, `dags/multi_sport_betting_workflow.py:1607-1620`, `plugins/portfolio_optimizer.py:642-643,701-702,964-965`, `plugins/constants.py:5-24`, `dashboard/pages/calibration.py:70-85` |

## Runtime vs operator-facing semantics matrix

| Surface | Runtime meaning | Operator-facing meaning today | Divergence observed |
| --- | --- | --- | --- |
| `confidence` | Edge-band label (`HIGH` `>=15%`, `MEDIUM` `>=8%`, else `LOW`); not a numeric Elo-probability gate in the active optimizer filter | Displayed as a recommendation attribute in Live Markets and Bet Detail; docs also describe confidence as Elo-probability thresholds | One term carries two meanings: edge-derived label in code, probability-floor language in docs/operator framing |
| `Open Risk` / `Open Positions` | Live bankroll can already be consumed by executed orders synced as `filled` | Portfolio page surfaces only `pending/open/placed` rows as open exposure | Dashboard label is narrower than live committed risk |
| Calibration sport filter | Runtime modeling and betting are sport-specific | UI exposes a sport selector and a by-sport summary row | The selector does not constrain the underlying view, so sport labels can overstate specificity |
| Bet detail status and P&L context | Execution state lives in `placed_bets`, with order rows keyed differently from recommendation rows | Bet Detail combines recommendation metrics and placement fields in one record keyed from recommendation `bet_id` | The page shape implies a direct recommendation→execution trace that the runtime evidence model does not actually provide |
| “Governed” live-market evidence | Current market rows come from `game_odds`; recommendation context is latest persisted recommendation by ticker | Page title and schema present a governed live-market table with edge/EV/confidence columns | Recommendation-time metrics are displayed beside live market rows without freshness/provenance labels, so governed market state and descriptive recommendation state are blended |

## Governed controls vs undocumented heuristics in current behavior

### Runtime-enforced controls with stable code anchors

- `3%` minimum edge filter in portfolio selection (`plugins/portfolio_optimizer.py:798-801`)
- `25%` max daily allocation cap (`plugins/portfolio_optimizer.py:843-846`)
- `$10` max bet size and `3%` max single-bet cap (`plugins/portfolio_optimizer.py:898-900`)
- `20%` Kelly scaling at live DAG/config level (`dags/multi_sport_betting_workflow.py:1530-1534`, `plugins/constants.py:63-70`)

### Controls presented or implied but not currently governed as live filters

- Numeric confidence threshold fields (`min_confidence`, `MIN_CONFIDENCE_FOR_BET`, docs’ `68%` / sport-specific Elo thresholds)
- Dashboard “sport-specific” calibration interpretation
- Bet Detail’s apparent recommendation-to-execution traceability via `bet_id`

### Active heuristics without reviewed governed evidence contracts

- Static excluded segments derived from prior ROI commentary (`dags/multi_sport_betting_workflow.py:1479-1508`)
- Edge-band confidence labels standing in for risk-quality semantics (`plugins/constants.py:46-49`, `plugins/odds_comparator.py:131-144`)
- Optimizer default sport list omitting part of the PRD/live DAG scope while constants and dashboard selectors add extra sports (`plugins/portfolio_optimizer.py:642-643,701-702,964-965`, `plugins/constants.py:5-24`, `dashboard/pages/calibration.py:70-85`)

## Acceptance-criteria check

| Requirement | Audit result |
| --- | --- |
| Covers thresholds, caps, exclusions, and evidence presentation gaps | Satisfied via the runtime baseline, prioritized drift register, and runtime-vs-operator matrix |
| Ranks drift items by downstream risk and planning significance | Satisfied via the prioritized drift register |
| Explicitly compares runtime behavior with dashboard/operator-facing semantics | Satisfied via the baseline table and runtime-vs-operator matrix |
| Remains descriptive only with no doc or runtime modifications beyond the audit artifact | Satisfied by audit content; this artifact records current-state behavior only |
