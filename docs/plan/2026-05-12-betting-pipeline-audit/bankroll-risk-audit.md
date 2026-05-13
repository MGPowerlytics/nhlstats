# Bankroll Risk Audit — 2026-05-12 Betting Pipeline Audit

## Scope

- Task: `bankroll-risk-audit`
- PRD in-scope sports: NBA, NHL, MLB, NFL, EPL, LIGUE1, NCAAB, WNCAAB, TENNIS
- Relevant runtime files reviewed:
  - `dags/multi_sport_betting_workflow.py`
  - `plugins/portfolio_optimizer.py`
  - `plugins/portfolio_betting.py`
  - `plugins/kalshi_betting.py`
  - `plugins/bet_tracker.py`
  - `plugins/constants.py`
  - `plugins/portfolio_snapshots.py`
  - `dashboard/data_layer.py`
  - `dashboard/pages/portfolio.py`
  - `migrations/stats_schema/V008__create_dashboard_read_model_views.sql`
  - selected tests and strategy docs

## Evidence labels used in this audit

- **Evidence-backed control**: present in live code and/or directly validated by tests or governed read-model SQL
- **Heuristic**: hard-coded parameter, ranking rule, or exclusion rule with no live evidence gate
- **Gap / blind spot**: materially relevant risk area with no direct control or with mismatched control surfaces

## Supported sport and control-path coverage

| Surface | Current coverage |
| --- | --- |
| PRD scope | NBA, NHL, MLB, NFL, EPL, LIGUE1, NCAAB, WNCAAB, TENNIS (`docs/prd.yaml:18-23`) |
| Live portfolio betting entrypoint | Same 9 sports passed explicitly into `process_daily_bets()` (`dags/multi_sport_betting_workflow.py:1607-1620`) |
| Optimizer default sport list when no explicit list is supplied | `nhl`, `nba`, `mlb`, `nfl`, `ncaab`, `tennis` only (`plugins/portfolio_optimizer.py:642-643`, `701-702`, `964-965`) |
| Global constants list | Adds `cba` and `unrivaled` beyond PRD scope (`plugins/constants.py:5-18`) |

## Control inventory

| Control surface | Current behavior | Classification | Repo evidence |
| --- | --- | --- | --- |
| Bankroll source for sizing | Live sizing uses Kalshi cash balance from `get_balance()` when building `PortfolioConfig` (`dags/multi_sport_betting_workflow.py:1525-1538`) | Evidence-backed control | Runtime code |
| Kelly scaling | Live DAG uses `KELLY_FRACTION = 0.20`; optimizer default remains `0.25` (`dags/multi_sport_betting_workflow.py:67-70`, `plugins/constants.py:63-71`, `plugins/portfolio_optimizer.py:29-33`, `221-230`) | Heuristic | Hard-coded constants |
| Daily bankroll cap | Live DAG caps same-day planned allocation at `25%` of bankroll via `MAX_DAILY_RISK_PCT` and `max_daily_allocation = bankroll * pct` (`dags/multi_sport_betting_workflow.py:67`, `plugins/portfolio_optimizer.py:843-846`) | Evidence-backed control; heuristic threshold | Runtime code |
| Single-bet cap | Live DAG caps any bet at `3%` of bankroll (`dags/multi_sport_betting_workflow.py:70`, `plugins/portfolio_optimizer.py:898-900`) | Evidence-backed control; heuristic threshold | Runtime code |
| Dollar cap per bet | Live DAG also caps each bet at `$10` (`dags/multi_sport_betting_workflow.py:69`, `plugins/portfolio_optimizer.py:898-900`) | Evidence-backed control; heuristic threshold | Runtime code |
| Minimum edge | Opportunities below `3%` edge are filtered out (`dags/multi_sport_betting_workflow.py:65`, `plugins/portfolio_optimizer.py:798-801`) | Evidence-backed control; heuristic threshold | Runtime code |
| Minimum confidence parameter | `PortfolioConfig.min_confidence` is populated from the DAG, but `filter_opportunities()` does not apply it; the only active confidence filter is segment exclusion (`plugins/portfolio_optimizer.py:230`, `535`, `783-811`) | Gap / blind spot | Live code drift |
| Confidence labels | HIGH/MEDIUM/LOW are derived from edge only: `>=15%`, `>=8%`, else LOW (`plugins/constants.py:46-49`, `plugins/odds_comparator.py:136-144`) | Heuristic | Hard-coded thresholds |
| Segment exclusions | `_get_excluded_segments()` hard-codes LOW across sports plus selected NHL/TENNIS/WNCAAB/NCAAB segments from prior ROI commentary (`dags/multi_sport_betting_workflow.py:1473-1508`) | Heuristic | Static list with comments, not live evidence query |
| Allocation ordering | `_prioritize_sport_diversity()` gives each sport one initial “seat,” then ranks remaining bets by EV (`plugins/portfolio_optimizer.py:887`, `926-955`); test coverage asserts multi-sport exposure is preserved (`tests/test_portfolio_optimizer.py:273-331`) | Evidence-backed control; heuristic allocator | Runtime code + test |
| Existing position blocking | Placement refuses a new order when Kalshi reports an open position or resting order on the same match prefix (`plugins/kalshi_betting.py:762-780`) | Evidence-backed control | Runtime code |
| Same-match / opposite-side protection | Implemented only at execution time via `get_open_positions()` / `get_open_orders()`; not considered during optimizer sizing (`plugins/kalshi_betting.py:762-780`, `plugins/portfolio_optimizer.py:836-924`) | Gap / blind spot | Split optimizer vs execution control surfaces |
| Open-order persistence | After live placement, order-aware sync writes orders to `placed_bets` immediately so dashboard/reconciliation can see them without waiting for fills (`plugins/portfolio_betting.py:176-196`, `plugins/bet_tracker.py:788-940`) | Evidence-backed control | Runtime code + tests |
| Correlation handling | No explicit correlation model, same-slate concentration model, team/league cap, or covariance penalty appears in portfolio sizing code; allocation stops only on daily and per-bet caps (`plugins/portfolio_optimizer.py:836-924`) | Gap / blind spot | Absent in runtime logic |
| Drawdown handling | No drawdown-triggered sizing reduction, bankroll floor, stop-loss, or risk-of-ruin gate appears in live bankroll sizing code reviewed here | Gap / blind spot | Absent in runtime logic |

## Live vs dashboard exposure paths

### Live runtime path

1. Live bankroll for sizing is fetched from Kalshi before optimization (`dags/multi_sport_betting_workflow.py:1525-1528`).
2. The optimizer sizes bets against that live bankroll and same-day cap (`plugins/portfolio_optimizer.py:843-924`).
3. After placement, bankroll is refreshed from Kalshi again (`plugins/portfolio_betting.py:176-181`).
4. Newly placed orders are then synced into `placed_bets` for downstream visibility (`plugins/portfolio_betting.py:183-196`).

### Dashboard path

1. Portfolio value and balance come from hourly `portfolio_value_snapshots` rows (`plugins/portfolio_snapshots.py:63-136`, `dags/portfolio_hourly_snapshot.py:20-41`).
2. Open risk and position counts come from `dashboard_portfolio_v1`, which aggregates `placed_bets` by status (`migrations/stats_schema/V008__create_dashboard_read_model_views.sql:106-140`).
3. The Streamlit portfolio page renders balance/value from snapshots and open risk from the read model (`dashboard/data_layer.py:559-583`, `dashboard/pages/portfolio.py:78-123`).

### Exposure mismatches observed

| Mismatch | Description | Repo evidence |
| --- | --- | --- |
| Different source systems | Live sizing uses Kalshi API balance; dashboard combines snapshot balance/value with `placed_bets`-derived open risk | `dags/multi_sport_betting_workflow.py:1525-1538`, `dashboard/data_layer.py:559-583` |
| Different freshness windows | Snapshot balance/value is hourly; order visibility is near-real-time only if order sync succeeds | `dags/portfolio_hourly_snapshot.py:52-67`, `plugins/portfolio_betting.py:183-196` |
| Status taxonomy mismatch | `dashboard_portfolio_v1` counts open exposure only for `pending/open/placed`, but order sync maps executed orders to `filled` (`migrations/stats_schema/V008__create_dashboard_read_model_views.sql:112-120`, `plugins/bet_tracker.py:794-815`) |
| Execution-vs-portfolio timing gap | Order sync failure is non-blocking, so live placement can succeed while dashboard exposure lags | `plugins/portfolio_betting.py:183-196` |

## Hard-coded heuristics present in current control path

- `20%` live Kelly fraction (`dags/multi_sport_betting_workflow.py:68`, `plugins/constants.py:64`)
- `25%` max daily risk (`dags/multi_sport_betting_workflow.py:67`, `plugins/constants.py:63`)
- `$10` max bet size and `3%` max single-bet percentage (`dags/multi_sport_betting_workflow.py:69-70`, `plugins/constants.py:65-70`)
- `3%` minimum edge (`dags/multi_sport_betting_workflow.py:65`, `plugins/constants.py:42-44`, `71`)
- Confidence bands at `15%` / `8%` edge (`plugins/constants.py:46-49`)
- Static sport-confidence exclusions for LOW, NHL MEDIUM, TENNIS HIGH/MEDIUM, WNCAAB HIGH/MEDIUM, NCAAB HIGH/MEDIUM (`dags/multi_sport_betting_workflow.py:1479-1508`)
- One-seat-per-sport allocation ordering (`plugins/portfolio_optimizer.py:929-955`)

## Correlation and concentration blind spots

- No explicit cross-sport correlation penalty or shared-slate covariance model in live allocation (`plugins/portfolio_optimizer.py:836-924`)
- No per-sport notional cap beyond the one-seat ordering heuristic
- No drawdown-aware downshift once bankroll declines
- Same-match conflict prevention exists only when orders are about to be placed, not during portfolio construction (`plugins/kalshi_betting.py:762-780`)
- Optimizer sizing does not subtract already-open positions or resting orders from remaining daily risk budget before sizing new bets (`plugins/portfolio_optimizer.py:843-924`, `plugins/kalshi_betting.py:762-780`)

## Evidence-backed controls present today

- Live bankroll is taken from Kalshi before sizing and refreshed after placement (`dags/multi_sport_betting_workflow.py:1525-1538`, `plugins/portfolio_betting.py:176-181`)
- Daily and single-bet caps are enforced directly in the allocation loop (`plugins/portfolio_optimizer.py:843-924`)
- Match-level duplicate prevention checks both open positions and resting orders (`plugins/kalshi_betting.py:762-780`)
- Newly placed orders are synced into `placed_bets` without waiting for fills (`plugins/portfolio_betting.py:183-196`, `tests/test_order_sync.py:103-149`)
- Dashboard portfolio KPIs are sourced through governed read-model helpers and SQL views rather than ad hoc page queries (`dashboard/data_layer.py:559-583`, `migrations/stats_schema/V008__create_dashboard_read_model_views.sql:106-140`, `tests/test_dashboard_portfolio_page.py:220-232`)

## Heuristics and gaps that remain descriptive concerns

- Current risk parameter values are hard-coded, not evidence-gated by CLV, calibration, or walk-forward status
- Docs and code drift on key risk settings: portfolio docs still describe `25%`/`5%` or `10%`/`5%` examples while live code uses `25%`/`3%` and `20%` Kelly (`docs/PORTFOLIO_BETTING.md:25-27`, `96-105`; `docs/BETTING_STRATEGY.md:24-34`; `dags/multi_sport_betting_workflow.py:65-71`)
- Supported-sport definitions drift between PRD scope, live DAG list, optimizer defaults, and global constants
- Dashboard open-risk semantics can understate exposure when executed orders remain `filled`
