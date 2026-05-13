# Pricing / CLV Audit — 2026-05-12 Betting Pipeline Audit

## Scope

- Task: `pricing-clv-audit`
- Reviewed runtime and reporting surfaces:
  - `dags/multi_sport_betting_workflow.py`
  - `dags/bet_sync_hourly.py`
  - `plugins/kalshi_markets.py`
  - `plugins/the_odds_api.py`
  - `plugins/odds_comparator.py`
  - `plugins/bet_loader.py`
  - `plugins/opportunity_loader.py`
  - `plugins/portfolio_optimizer.py`
  - `plugins/portfolio_betting.py`
  - `plugins/bet_tracker.py`
  - `plugins/clv_tracker.py`
  - `plugins/update_clv_data.py`
  - `plugins/mlb_modeling/evidence.py`
  - `dashboard/data_layer.py`
  - `dashboard/pages/bet_detail.py`
  - `migrations/stats_schema/V003__govern_legacy_runtime_tables.sql`
  - `migrations/stats_schema/V008__create_dashboard_read_model_views.sql`
  - `migrations/stats_schema/V009__create_dashboard_tennis_predictions_view.sql`
  - `migrations/stats_schema/V012__create_mlb_odds_snapshots.sql`
  - selected pricing / CLV tests

## Evidence labels used in this audit

- **Audit-evidence capable**: code path persists source, timestamp, and enough price-shape metadata to support later governed review.
- **Partially evidenced**: path has some timestamps or provenance but not enough persisted context to stand alone as approval-grade price evidence.
- **Descriptive-only**: current path is useful for reporting or operational convenience, but not as governed pricing / CLV evidence.

## Cross-cutting findings

1. There is no explicit cross-sport `fair_odds` or no-vig computation in the live pipeline. Current “fair price” behavior is implicit: model probability (`elo_prob` / governed model probability) is compared directly against Kalshi-implied market probability (`1 / market_odds`) to derive `edge`, `expected_value`, and `kelly_fraction` (`plugins/odds_comparator.py:301-337`, `423-462`).
2. Best-price logic is split and not canonical. The live recommendation path uses Kalshi only, while `OddsComparator.get_best_odds()` queries the highest decimal `price` across `game_odds`, and `TheOddsAPI._parse_game()` separately labels “best” books by maximizing implied probability rather than payout (`plugins/odds_comparator.py:505-531`; `plugins/the_odds_api.py:414-431`).
3. CLV is also split. Fill/order sync writes entry probability immediately, but two different closing-line paths exist: a binary settlement-result placeholder in `bet_tracker.py` / `update_clv_data.py`, and a later real-price backfill from `game_odds` in `clv_tracker.py` (`plugins/bet_tracker.py:234-260`, `570-594`; `plugins/update_clv_data.py:33-66`; `plugins/clv_tracker.py:58-100`, `240-387`).
4. The strongest current audit-evidence path is MLB snapshot history in `mlb_odds_snapshots`, where snapshot role (`open` / `close` / `intraday`), source timestamp, bookmaker, and raw payload are persisted and then audited in `plugins/mlb_modeling/evidence.py` (`migrations/stats_schema/V012__create_mlb_odds_snapshots.sql:4-50`; `plugins/mlb_modeling/evidence.py:365-495`, `529-571`).

## Current computation-path inventory

| Path | Current computation | Freshness / provenance assumptions | Closing-line assumption | Downstream consumers | Evidence quality |
| --- | --- | --- | --- | --- | --- |
| Live recommendation market price / implicit fair-odds path | Kalshi markets are written into `game_odds` as decimal odds derived from `yes_ask` (`100 / yes_ask`), then `OddsComparator` computes `market_prob = 1 / market_odds`, `edge = elo_prob - market_prob`, `expected_value = edge / market_prob`, and Kelly from the same implied probability (`plugins/kalshi_markets.py:1210-1231`, `1263-1273`, `1357-1374`; `plugins/odds_comparator.py:431-462`) | Requires a Kalshi row in `game_odds`; `OddsComparator` has no explicit max-age filter. Kalshi rows use `external_id=ticker`; `last_update` is set on upsert update, but insert relies on table defaults and can leave freshness inferred from `loaded_at` instead of a source timestamp (`plugins/odds_comparator.py:574-581`; `migrations/stats_schema/V003__govern_legacy_runtime_tables.sql:135-147`) | None at recommendation time | `data/<sport>/bets_*.json`, `bet_recommendations`, portfolio loading/sizing, recommendation-backed dashboard views (`dags/multi_sport_betting_workflow.py:1427-1439`, `1086-1096`; `plugins/bet_loader.py:521-547`; `dashboard/data_layer.py:707-810`, `1042-1150`) | Partially evidenced |
| `OddsComparator.get_best_odds()` best-price helper | Queries `game_odds` per side, sorts by `price DESC`, returns top bookmaker / decimal odds / `last_update` (`plugins/odds_comparator.py:505-531`) | Uses whatever is in `game_odds`; no source-role filter, no freshness threshold, no pregame filter | None | Tests / ad hoc helper only; no live DAG caller found (`tests/test_odds_comparator.py:59`, `249`) | Descriptive-only |
| `TheOddsAPI._parse_game()` “best_*” fields | Computes `best_home_*` and `best_away_*` from `max(bookmakers, key=home_prob/away_prob)`, where `home_prob = 1 / home_odds` and `away_prob = 1 / away_odds` (`plugins/the_odds_api.py:414-431`, `510-520`) | Provenance is The Odds API bookmaker payload plus bookmaker `last_update`; these “best” fields are in-memory parse output, not the canonical DB contract | None | File output / console output from The Odds API helper; not consumed by the live recommendation path (`plugins/the_odds_api.py:532-552`) | Descriptive-only |
| Recommendation persistence path | `BetLoader` persists `market_prob`, `edge`, `expected_value`, `kelly_fraction`, optional `yes_ask` / `no_ask`, and ticker into `bet_recommendations`; if EV/Kelly are absent they are recomputed from stored `edge` and `market_prob` (`plugins/bet_loader.py:46-64`, `100-139`, `427-547`) | Assumes the JSON recommendation payload is the authoritative source for market probability; no persisted source-bookmaker or timestamp columns exist in `bet_recommendations` (`migrations/stats_schema/V008__create_dashboard_read_model_views.sql:24-43`) | None | Portfolio loaders, dashboard bet detail, dashboard calibration, tennis predictions, bet backfill into `placed_bets` (`plugins/opportunity_loader.py:74-128`; `plugins/bet_tracker.py:430-457`; `migrations/stats_schema/V008__create_dashboard_read_model_views.sql:142-264`, `376-430`; `V009__create_dashboard_tennis_predictions_view.sql:17-54`) | Descriptive-only |
| Portfolio sizing / execution price path | Portfolio loaders trust stored `market_prob`; if asks are missing they estimate `yes_ask` / `no_ask` from `market_prob`. At placement time `PortfolioBettingManager` prefers the live Kalshi ask from `get_market_details()`, falls back to stored ask, and records `bet_line_prob = price / 100` (`plugins/portfolio_optimizer.py:119-127`, `281-341`, `427-503`; `plugins/portfolio_betting.py:282-299`, `392-431`) | Live execution price quality is strongest when `get_market_details()` returns a current Kalshi ask. If it falls back to stored asks, the stored asks may be persisted recommendation values or synthetic estimates from `market_prob` | None | Actual order placement, `results["placed_bets"]`, later `placed_bets.bet_line_prob` via order/fill sync (`plugins/portfolio_betting.py:61-93`, `183-196`, `282-299`) | Live ask: partially evidenced; fallback ask: descriptive-only |
| Immediate CLV placeholder path (fill sync) | `bet_tracker` sets `bet_line_prob` from fill price, derives `closing_line_prob` from final market result (`yes`→1.0 / `no`→0.0), and stores `clv = bet_line_prob - closing_line_prob` (`plugins/bet_tracker.py:234-260`, `548-594`, `624-719`) | Provenance is Kalshi fill/order payload plus market settlement result; no closing-price snapshot or bookmaker provenance is stored on the bet row | Treats realized outcome as a temporary closing-line proxy | `placed_bets`, any query that reads CLV before backfill, and the daily workflow before the hourly backfill overwrites qualifying rows (`dags/multi_sport_betting_workflow.py:1828-1832`, `1996-2003`) | Descriptive-only |
| Immediate CLV placeholder path (post-betting DAG task) | `update_clv_data.py` fetches closed Kalshi markets, maps market result to `{"yes":1.0,"no":0.0}`, and updates `closing_line_prob` / `clv` for unsettled rows (`plugins/update_clv_data.py:33-66`, `73-132`) | Same provenance as above: Kalshi market result, no external closing-price evidence | Realized outcome stands in for close | Multi-sport daily DAG `update_clv_data` task (`dags/multi_sport_betting_workflow.py:1828-1832`, `1996-2003`) | Descriptive-only |
| Real closing-price CLV backfill path | `clv_tracker.compute_real_closing_price()` resolves the game, selects the latest acceptable pre-close `game_odds` snapshot ordered by `last_update DESC` and bookmaker priority, converts decimal odds to implied probability, and overwrites `placed_bets.closing_line_prob` / `clv` (`plugins/clv_tracker.py:58-100`, `141-218`, `240-387`) | Provenance comes from `game_odds` plus bookmaker priority list `["Kalshi","SBR","fanduel","betrivers","bovada"]`; stale if more than 4 hours before market close, but stale status is counted only in-memory and not persisted on the bet row (`plugins/constants.py:54-57`, `129-130`; `plugins/clv_tracker.py:221-237`, `329-357`) | Uses explicit market close if available; otherwise the latest snapshot becomes the proxy close | Hourly DAG CLV task, `CLVTracker.fetch_closing_lines_*()`, `placed_bets`, EV-vs-CLV reporting, P&L diagnostics (`dags/bet_sync_hourly.py:71-93`, `131-139`; `plugins/ev_accuracy_report.py:437-525`; `plugins/pnl_diagnostic.py:660-707`) | Partially evidenced |
| MLB governed odds-snapshot evidence path | `TheOddsAPI` and free historical builders persist `mlb_odds_snapshots` with `snapshot_type`, `source_snapshot_at`, `bookmaker_key`, `implied_probability`, and raw payload; `mlb_modeling.evidence` selects open/close snapshots, computes `market_prob`, `entry_implied_probability`, `close_implied_probability`, CLV hit, and CLV delta (`plugins/the_odds_api.py:250-333`; `plugins/mlb_modeling/free_odds_sources.py:167-222`; `plugins/mlb_modeling/evidence.py:365-495`, `529-571`, `665-717`) | Explicit source metadata and snapshot timestamps are persisted; evidence code enforces pregame-only snapshots and prefers explicit `open` / `close` markers when available | Explicit `close` snapshot preferred; otherwise last pregame snapshot is used as a proxy and the audit code exposes proxy-close rates | Offline / governed MLB evidence scripts and tests, not the live multi-sport recommendation or portfolio path (`scripts/evaluate_mlb_betting_evidence.py:252-273`; `tests/test_mlb_modeling_evidence.py:265`) | Audit-evidence capable |

## Split implementations and downstream effects

| Split area | Current implementations | Consumer effect |
| --- | --- | --- |
| Market probability source | Live `OddsComparator` uses Kalshi decimal odds from `game_odds`; portfolio loaders trust persisted `bet_recommendations.market_prob`; JSON/file loaders may derive `market_prob` from asks or synthesize asks from `market_prob` (`plugins/odds_comparator.py:427-439`; `plugins/portfolio_optimizer.py:329-341`, `427-503`; `plugins/portfolio_parsers.py:31-55`, `146-155`, `235-260`) | Edge / EV can reflect recommendation-time Kalshi pricing even when execution uses a fresher or synthetic ask |
| Best-price semantics | `get_best_odds()` sorts by highest decimal `price`; The Odds API “best_*” fields maximize implied probability; live recommendation path ignores both and uses Kalshi only (`plugins/odds_comparator.py:505-531`; `plugins/the_odds_api.py:414-431`) | “Best price” is not one governed concept today; different code paths mean different things |
| Entry price vs execution price | Recommendation persistence stores `market_prob` plus optional asks; execution prefers live Kalshi ask and falls back to stored / synthetic ask (`plugins/bet_loader.py:121-139`; `plugins/portfolio_betting.py:406-431`) | `bet_recommendations.market_prob` is not guaranteed to match realized `placed_bets.bet_line_prob` |
| CLV close definition | Binary outcome placeholder in `bet_tracker.py` / `update_clv_data.py`; real closing-price overwrite in `clv_tracker.py`; separate MLB snapshot-based CLV in `mlb_modeling.evidence.py` (`plugins/bet_tracker.py:570-594`; `plugins/update_clv_data.py:33-66`; `plugins/clv_tracker.py:58-100`; `plugins/mlb_modeling/evidence.py:448-490`) | Downstream reporting can read materially different CLV meanings depending on timing and table/source |
| Reporting surface semantics | Dashboard recommendation views expose recommendation-time `market_prob`, `edge`, `expected_value`, and ask fields from `bet_recommendations`, while CLV reporting lives in offline diagnostic/report modules over `placed_bets` (`migrations/stats_schema/V008__create_dashboard_read_model_views.sql:142-264`, `376-430`; `plugins/ev_accuracy_report.py:437-525`; `plugins/pnl_diagnostic.py:678-707`) | Current dashboard surfaces are recommendation-descriptive, not closing-line evidence surfaces |

## Freshness, provenance, and closing-line controls observed

| Surface | Current control / assumption | Evidence |
| --- | --- | --- |
| `game_odds` freshness in dashboard data quality | Freshness is `MAX(COALESCE(last_update, loaded_at))`; dashboard warns if lag exceeds 240 minutes | `migrations/stats_schema/V008__create_dashboard_read_model_views.sql:299-306`, `344-370` |
| Kalshi recommendation eligibility | Live comparator requires a Kalshi row but does not reject stale rows by age | `plugins/odds_comparator.py:574-581`, `427-439` |
| External bookmaker provenance | The Odds API writes bookmaker name and source-provided `last_update` into `game_odds` | `plugins/the_odds_api.py:137-181`, `503-520` |
| CLV bookmaker precedence | Real-price CLV backfill prefers acceptable bookmakers in fixed priority order after sorting by latest `last_update` | `plugins/constants.py:54-57`; `plugins/clv_tracker.py:160-218` |
| Stale closing-price detection | Snapshot older than 4 hours before close is counted as stale during backfill, but that flag is not written back to `placed_bets` | `plugins/constants.py:129-130`; `plugins/clv_tracker.py:221-237`, `329-357` |
| MLB evidence provenance | Snapshot source, role, bookmaker, source timestamp, and raw payload are persisted per snapshot | `migrations/stats_schema/V012__create_mlb_odds_snapshots.sql:4-31`; `plugins/mlb_modeling/free_odds_sources.py:167-222` |

## Current evidence-quality split

### Strong enough for audit evidence today

- **MLB odds-snapshot evidence only**: `mlb_odds_snapshots` persists explicit source timestamps, snapshot roles, bookmaker identity, and raw payload; `mlb_modeling.evidence.py` exposes whether a recommendation used explicit open/close snapshots versus proxies (`migrations/stats_schema/V012__create_mlb_odds_snapshots.sql:4-50`; `plugins/mlb_modeling/evidence.py:529-571`).

### Stronger than descriptive reporting but still incomplete

- **Real-price CLV backfill in `placed_bets`**: closing prices are sourced from `game_odds` rather than market outcomes, but the chosen bookmaker, selected timestamp, and stale/not-stale result are not persisted per bet (`plugins/clv_tracker.py:141-218`, `329-372`).
- **Live execution price capture**: `placed_bets.bet_line_prob` can reflect the actual live Kalshi ask used at order time, but recommendation-time `market_prob` remains a separate field and may not share the same timestamp or source-role label (`plugins/portfolio_betting.py:282-299`, `406-431`; `plugins/bet_tracker.py:624-719`).

### Descriptive-only today

- Cross-sport recommendation-time `market_prob`, `edge`, `expected_value`, and dashboard recommendation views.
- `OddsComparator.get_best_odds()` and The Odds API “best_*” helpers.
- Binary CLV written from market results before real-price backfill runs.
- Dashboard data-quality freshness warnings, which report relation freshness but do not certify the specific price used for a recommendation or a CLV overwrite.

## Reporting-surface summary

- `dashboard_live_markets_v1` joins latest recommendation `edge` / `expected_value` onto current `game_odds` rows by ticker; it is a recommendation-context surface, not a recomputed pricing-evidence surface (`migrations/stats_schema/V008__create_dashboard_read_model_views.sql:142-191`).
- `dashboard_bet_detail_v1` shows recommendation-time `market_prob`, `edge`, `expected_value`, `yes_ask`, and `no_ask` from `bet_recommendations`, plus placement status / P&L from `placed_bets`; it does not expose CLV or closing-price provenance (`migrations/stats_schema/V008__create_dashboard_read_model_views.sql:376-430`; `dashboard/pages/bet_detail.py:125-175`).
- `dashboard_calibration_v1` aggregates recommendation-time `market_prob`, `edge`, and `expected_value`; it does not consume closing-line data (`migrations/stats_schema/V008__create_dashboard_read_model_views.sql:215-264`).
- `dashboard_tennis_predictions_v1` is likewise recommendation-time only (`migrations/stats_schema/V009__create_dashboard_tennis_predictions_view.sql:17-54`).
- CLV-facing reporting currently sits in offline modules over `placed_bets` (`plugins/ev_accuracy_report.py:437-525`; `plugins/pnl_diagnostic.py:678-707`).

## Acceptance-criteria check

- **Every current fair-odds, best-price, and CLV computation path identified:** covered above, including live Kalshi-implied edge, best-price helpers, recommendation persistence, execution entry-price capture, binary CLV, real-price CLV backfill, and MLB snapshot-based CLV evidence.
- **Freshness, provenance, and closing-line assumptions recorded for each path:** captured in the computation-path inventory and controls sections.
- **Split implementations and downstream consumers documented:** captured in the split-implementations matrix and reporting-surface summary.
- **Price-quality strength separated from descriptive-only reporting:** captured in the evidence-quality split.
- **No runtime bug fixes or production hardening included:** this document is descriptive only.
