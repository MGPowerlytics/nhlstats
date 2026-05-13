# Pipeline Evidence Map — 2026-05-12 Betting Pipeline Audit

## Scope

- Task: `pipeline-evidence-map`
- PRD in-scope sports: NBA, NHL, MLB, NFL, EPL, LIGUE1, NCAAB, WNCAAB, TENNIS
- Runtime files reviewed:
  - `dags/multi_sport_betting_workflow.py`
  - `dags/historical_stats_daily.py`
  - `dags/bet_sync_hourly.py`
  - `plugins/db_loader.py`
  - `plugins/csv_processors.py`
  - `plugins/elo/elo_update_helpers.py`
  - `plugins/odds_comparator.py`
  - `plugins/kalshi_markets.py`
  - `plugins/the_odds_api.py`
  - `plugins/bet_loader.py`
  - `plugins/opportunity_loader.py`
  - `plugins/portfolio_optimizer.py`
  - `plugins/portfolio_betting.py`
  - `plugins/bet_tracker.py`
  - `plugins/clv_tracker.py`
  - `plugins/update_clv_data.py`
  - `plugins/portfolio_snapshots.py`
  - `dashboard/data_layer.py`
  - `migrations/stats_schema/V002__create_stats_schema.sql`
  - `migrations/stats_schema/V003__govern_legacy_runtime_tables.sql`
  - `migrations/stats_schema/V006__create_elo_ratings.sql`
  - `migrations/stats_schema/V007__canonicalize_elo_ratings.sql`
  - `migrations/stats_schema/V008__create_dashboard_read_model_views.sql`
  - `migrations/stats_schema/V009__create_dashboard_tennis_predictions_view.sql`
  - `migrations/stats_schema/V010__add_mlb_predictive_modeling_tables.sql`
  - `migrations/stats_schema/V011__create_dashboard_mlb_model_health_view.sql`
  - `migrations/stats_schema/V012__create_mlb_odds_snapshots.sql`
  - `migrations/stats_schema/V013__add_tennis_model_evaluation_dashboard_view.sql`
- Read-only PostgreSQL checks were run against the local `airflow` database on 2026-05-12 to confirm currently populated tables, view rows, join coverage, and status distributions.

## Stage-by-stage PostgreSQL evidence surfaces

| Pipeline stage | Current primary PostgreSQL surface(s) | Persisted non-PostgreSQL evidence still in active use | Notes |
| --- | --- | --- | --- |
| Ingestion / schedule identity | `unified_games`; legacy `games`, `mlb_games`, `nfl_games`, `epl_games`, `ligue1_games`, `tennis_games`, `ncaab_games`, `wncaab_games` | `data/{sport}/...` download files | `unified_games` is the common downstream schedule surface, but several sports still maintain parallel sport-specific tables. |
| Box-score / stats enrichment | `team_game_stats`, sport extension tables, `tennis_player_match_stats` | none identified as canonical runtime outputs | `historical_stats_daily` consumes `unified_games` for all in-scope sports except MLB, which reads `mlb_games`. |
| Elo / rating persistence | `elo_ratings` | `data/{sport}_current_elo_ratings.csv`, `data/atp_current_elo_ratings.csv`, `data/wta_current_elo_ratings.csv`, `data/{sport}_current_glicko2_ratings.csv` | Dashboard rankings use `elo_ratings`; Glicko remains file-only. |
| Model generation | `mlb_model_predictions`, `mlb_matchup_features`, `mlb_odds_snapshots`, `tennis_model_evaluations` | `data/models/tennis_probability_model_v1.joblib`, `data/models/tennis_probability_model_v1_metrics.json` | MLB has live DB-backed model rows; tennis model evidence exists structurally but no current `tennis_model_evaluations` rows were found. |
| Market normalization | `game_odds` plus `unified_games` join key | `data/{sport}/markets_{date}.json`, `data/{sport}/odds_api_markets_{date}.json` | Kalshi and The Odds API both write normalized market state. |
| Recommendation persistence | `bet_recommendations` | `data/{sport}/bets_{date}.json` | Runtime still writes files first, then loads DB rows. |
| Sizing / allocation | no dedicated table; reads `bet_recommendations` | `data/portfolio/betting_report_{date}.txt`, `data/portfolio/betting_results_{date}.json` | Allocation state is computed in memory and persisted only as reports/results files. |
| Execution / order capture | `placed_bets` | none | `placed_bets` is written by fill sync, order sync, and reconciliation discovery. |
| Settlement | `placed_bets` | none | There is no separate settlement ledger table. |
| CLV refresh | `placed_bets` updated from `game_odds`; legacy binary close updates also write `placed_bets` | none | Real close path and legacy binary close path both remain present. |
| Portfolio history | `portfolio_value_snapshots` | none | Dashboard portfolio history reads this table. |
| Dashboard surfacing | `dashboard_portfolio_v1`, `dashboard_live_markets_v1`, `dashboard_rankings_v1`, `dashboard_calibration_v1`, `dashboard_bet_detail_v1`, `dashboard_tennis_predictions_v1`, `dashboard_mlb_model_health_v1`, `dashboard_tennis_model_health_v1` | none | `dashboard/data_layer.py` treats versioned views as the governed reporting boundary. |

## Current PostgreSQL snapshot observed during audit

- `unified_games` rows currently exist for `NBA`, `NHL`, `MLB`, `EPL`, `LIGUE1`, `TENNIS`, and `CBA`; no current `NFL`, `NCAAB`, or `WNCAAB` rows were returned by the audit query.
- `bet_recommendations` currently contains `MLB`, `EPL`, `LIGUE1`, `TENNIS`, and `CBA` rows only.
- `placed_bets` currently contains `NBA`, `NHL`, `MLB`, `EPL`, `LIGUE1`, `NCAAB`, `WNCAAB`, and `TENNIS` rows, plus `NULL`-sport rows.
- Active `elo_ratings` rows currently exist for `NBA`, `NHL`, `MLB`, `EPL`, `LIGUE1`, `NCAAB`, `WNCAAB`, `TENNIS`, `CBA`, plus a separate `Ligue1` casing variant and a `TEST` residue row.
- `mlb_model_predictions` has live rows; `mlb_market_signals` and `tennis_model_evaluations` were empty in the audited database snapshot.
- `dashboard_tennis_predictions_v1` and `dashboard_mlb_model_health_v1` return rows; `dashboard_tennis_model_health_v1` is currently empty.

## Sport-by-sport lineage map

| Sport | Ingestion / game source | Elo / model generation | Market normalization | Recommendation persistence | Sizing / execution / settlement | CLV / dashboard surfacing | Divergence observed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NBA | `download_games()` + `load_data_to_db()` populate `unified_games`; historical stats remap native API IDs back onto `unified_games` | `update_elo_ratings()` persists `elo_ratings`; Glicko CSV also written | Kalshi writes `game_odds` | JSON file then `bet_recommendations`, but no current DB recommendation rows were found | Portfolio path explicitly includes NBA; `placed_bets` rows exist | `placed_bets` feeds CLV and dashboard portfolio; rankings surface via `dashboard_rankings_v1` | Live execution evidence exists without current recommendation evidence in `bet_recommendations`; recommendation→execution join is not direct |
| NHL | `download_games()` + loader path populate `unified_games`; historical stats remap native IDs | `elo_ratings` + Glicko CSV | Kalshi writes `game_odds` | JSON file then `bet_recommendations`, but no current DB recommendation rows were found | Portfolio path explicitly includes NHL; `placed_bets` rows exist | Rankings via `dashboard_rankings_v1`; portfolio via `placed_bets`/`portfolio_value_snapshots` | Same recommendation/execution split as NBA |
| MLB | `mlb_games` plus `unified_games`; Kalshi ID reconciliation moves synthetic rows onto native `mlb_games.game_id` identity | `elo_ratings`; governed moneyline path persists `mlb_model_predictions`; odds history persists `mlb_odds_snapshots` | Kalshi and The Odds API both write `game_odds`; The Odds API also writes `mlb_odds_snapshots` | JSON file then `bet_recommendations`; BetLoader synthesizes tickers when missing | Portfolio path includes MLB; `placed_bets` rows exist | CLV refresh uses `game_odds`; model health via `dashboard_mlb_model_health_v1` | Deepest parallel pipeline: native `mlb_games`, normalized `unified_games`, governed model rows, and bookmaker snapshot history coexist |
| NFL | `nfl_games` loader exists; historical stats downstream expects `unified_games` rows for stats ingestion | `elo_ratings` + Glicko CSV path defined | Kalshi writer exists in config | Recommendation generation path exists in DAG, but no current `bet_recommendations` rows were found | Portfolio call includes NFL, but no current `placed_bets` rows were found | No current dashboard-facing live evidence beyond generic rankings support if `elo_ratings` existed | Runtime support is wired, but current audited DB snapshot showed no active normalized schedule, recommendation, or execution evidence for NFL |
| EPL | CSV ingestion writes `epl_games`, `unified_games`, `team_game_stats`, `soccer_team_game_stats_ext` | `elo_ratings` persisted from EPL table input | Kalshi writes `game_odds` | JSON file then `bet_recommendations`; EPL gets stable recommendation IDs | Portfolio call includes EPL; `placed_bets` rows exist | Portfolio/dashboard views consume recommendations and placed bets; rankings surface exists | Most complete soccer lineage; still affected by generic recommendation↔execution join mismatch |
| LIGUE1 | CSV ingestion writes `ligue1_games` only; normalized upcoming schedule instead depends on Kalshi/unified path | `elo_ratings` persisted from Ligue1 table input; optional ensemble wrapper present | Kalshi writes `game_odds` and `unified_games` upcoming identity | JSON file then `bet_recommendations` | Portfolio call includes LIGUE1; `placed_bets` rows exist | Rankings and portfolio views surface rows | Historical table path and normalized upcoming path diverge; DB currently contains both `Ligue1` and `LIGUE1` Elo sport casing |
| NCAAB | CSV processor writes `ncaab_games` only | `update_elo_ratings()` uses sport-specific loader/class rather than normalized DB table | Kalshi market fetch exists in config | Recommendation path exists in DAG, but no current `bet_recommendations` rows were found | Portfolio call includes NCAAB; `placed_bets` rows exist | Rankings view surfaces `elo_ratings`; placed bets feed portfolio | Historical stats DAG expects `unified_games` rows, but the reviewed CSV processor does not populate them |
| WNCAAB | CSV processor writes `wncaab_games` only | `update_elo_ratings()` uses sport-specific loader/class rather than normalized DB table | Kalshi market fetch exists in config | Recommendation path exists in DAG, but no current `bet_recommendations` rows were found | Portfolio call includes WNCAAB; `placed_bets` rows exist | Rankings view surfaces `elo_ratings`; placed bets feed portfolio | Same normalized-schedule gap as NCAAB |
| TENNIS | CSV ingestion writes `tennis_games` and `unified_games`; historical stats remap slug-based matchup IDs; `tennis_player_match_stats` persists player rows | `elo_ratings` combines ATP/WTA ratings; optional model training persists file artifact and can publish `tennis_model_evaluations` | Kalshi writes `game_odds`; tennis outcome names are player names rather than `home`/`away` | JSON file then `bet_recommendations`; BetLoader can synthesize tennis tickers | Portfolio call includes TENNIS; `placed_bets` rows exist | Dedicated `dashboard_tennis_predictions_v1`; generic portfolio/bet-detail views also read recommendation/placed-bet state | Tennis has the most bespoke naming/identity handling and a dashboard surface keyed by run date rather than settlement date |

## Current PostgreSQL source-of-truth assessment

| Concern | Current source of truth | Evidence |
| --- | --- | --- |
| Normalized upcoming game + market identity | `unified_games` + `game_odds` | Shared across Kalshi market ingestion, live-markets view, CLV lookup, and stats ingestion for most sports |
| Historical sport-specific schedules | Sport tables remain active (`mlb_games`, `epl_games`, `ligue1_games`, `tennis_games`, `ncaab_games`, `wncaab_games`, `nfl_games`, `games`) | Multiple DAGs and loaders still read these directly |
| User-facing rankings | `elo_ratings` | `dashboard_rankings_v1` reads active rows only |
| Recommendation record | `bet_recommendations` intended, but JSON files remain active parallel evidence | `PortfolioOptimizer` still falls back to `data/{sport}/bets_{date}.json` |
| Execution / settlement / realized CLV | `placed_bets` | Orders, fills, reconciliation, settlement fields, and CLV fields all converge here |
| Portfolio history | `portfolio_value_snapshots` | `dashboard_portfolio_v1` reads it directly |
| Dashboard read boundary | `dashboard_*_v1` views | `dashboard.data_layer.py` uses versioned views for page reads |

## Missing links and broken evidence joins

1. **Recommendation-to-execution join is structurally broken on `bet_id`.**
   - `bet_recommendations.bet_id` is recommendation-generated.
   - `placed_bets.bet_id` is either `order_id` or `{ticker}_{trade_id}`.
   - Read-only DB check: `joined_on_bet_id = 0` across every sport returned by the audit query.
   - The codebase already uses `ticker` rather than `bet_id` when backfilling execution metrics from recommendations.

2. **MLB recommendation-to-market linkage is incomplete in current persisted evidence.**
   - Read-only DB check: `69` MLB recommendation rows currently have no ticker.
   - Read-only DB check: `447` MLB recommendation rows with a ticker did not find a `game_odds.external_id` match.
   - BetLoader’s synthetic MLB ticker path exists specifically to keep downstream linkage alive when the producer omits a real Kalshi ticker.

3. **Historical stats ingestion expects normalized schedule rows that some loaders do not populate.**
   - `historical_stats_daily` queries `unified_games` for NFL, EPL, LIGUE1, NCAAB, WNCAAB, and TENNIS.
   - Reviewed CSV processors populate `unified_games` for EPL and TENNIS, but not for NCAAB, WNCAAB, or LIGUE1.

4. **CLV lookup still depends on team/date matching rather than a direct market identity bridge.**
   - `clv_tracker._find_game_id()` resolves `placed_bets` into `unified_games` by sport, date, and team names/IDs.
   - That means CLV refresh depends on name alignment rather than a persisted `placed_bets -> unified_games.game_id` key.

5. **Calibration reporting loses sport identity.**
   - `dashboard_calibration_v1` aggregates all recommendations into shared probability buckets without a sport column.
   - `dashboard/pages/calibration.py` presents a sport filter, but `get_calibration_data(sport)` does not apply one.

6. **Dashboard bet detail also loses sport identity in the data layer.**
   - `dashboard_bet_detail_v1` does not project sport.
   - `dashboard.data_layer.get_bet_detail()` and `get_placed_bets()` synthesize blank/derived sport values in the mapped page shape.

## Duplicate paths and cross-surface divergence

### Live-vs-reporting divergence

| Divergence | Live/runtime path | Reporting path | Current evidence |
| --- | --- | --- | --- |
| Open exposure semantics | Order sync marks executed orders as `filled` in `placed_bets` | `dashboard_portfolio_v1` only counts `pending`, `open`, `placed` as open risk | Read-only DB check: `393` `filled` rows totaling about `$1,826.12` are excluded from dashboard open risk, while current `dashboard_portfolio_v1` shows only `$17.88` open risk |
| Portfolio time alignment | Live bankroll is fetched from Kalshi immediately before/after placement | Portfolio view cross-joins current `placed_bets` summary onto every historical snapshot row | Every `dashboard_portfolio_v1` row reuses the same current bet summary against historical snapshot timestamps |
| Recommendation visibility | Runtime writes JSON recommendations first, then DB load | Dashboard reads only `bet_recommendations` / views | If JSON exists before DB load, sizing can still proceed while reporting waits for DB state |
| CLV calculation | Hourly sync can replace binary close placeholders with real market closes from `game_odds` | Legacy `update_clv_data.py` still writes binary result-based close probabilities into `placed_bets` | Two CLV writers remain present |

### Duplicate persistence paths

- `unified_games` / `game_odds` receive writes from both Kalshi market ingestion and The Odds API normalization.
- Recommendations persist to both JSON files and `bet_recommendations`.
- `placed_bets` is written by fill sync, order sync, and reconciliation discovery.
- Ratings persist to both `elo_ratings` and CSV mirrors.
- MLB and TENNIS each carry separate model-artifact/file surfaces in addition to PostgreSQL evidence.

## Acceptance-criteria check

| Requirement | Audit result |
| --- | --- |
| Covers NBA, NHL, MLB, NFL, EPL, LIGUE1, NCAAB, WNCAAB, TENNIS | Satisfied via the sport-by-sport lineage matrix above |
| Ties each stage to named PostgreSQL tables, views, or persisted evidence objects | Satisfied via the stage map and source-of-truth sections |
| Identifies live-vs-reporting divergence and missing evidence joins | Satisfied via the divergence tables and broken-link register |
| Remains descriptive only with no implementation commitments | Satisfied; this artifact records current-state evidence only |
