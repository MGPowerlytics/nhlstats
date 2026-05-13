# Probability Calibration Audit — 2026-05-12 Betting Pipeline Audit

## Scope

- Task: `probability-calibration-audit`
- PRD in-scope sports: NBA, NHL, MLB, NFL, EPL, LIGUE1, NCAAB, WNCAAB, TENNIS (`docs/prd.yaml:18-25`)
- Primary files reviewed:
  - `dags/multi_sport_betting_workflow.py`
  - `plugins/odds_comparator.py`
  - `plugins/probability_calibration.py`
  - `plugins/elo/tennis_elo_rating.py`
  - `plugins/elo/tennis_probability_model.py`
  - `plugins/elo/epl_ensemble_adapter.py`
  - `plugins/elo/ligue1_ensemble.py`
  - `plugins/mlb_modeling/models.py`
  - `plugins/mlb_modeling/airflow_tasks.py`
  - `dashboard/pages/calibration.py`
  - `dashboard/data_layer.py`
  - `migrations/stats_schema/V008__create_dashboard_read_model_views.sql`
  - checked-in calibration/model artifacts under `data/calibration/` and `data/models/`

## Evidence labels used in this audit

- **Live-wired**: the repo shows the artifact or logic is directly consumed by the live betting or scoring path.
- **Descriptive-only**: the repo shows dashboard/reporting or offline research usage, but not live bet-selection wiring.
- **Blocked / shadow-only / candidate**: descriptive current-state evidence labels for later governance review; these are not implementation commitments.

## Cross-cutting findings

1. All nine in-scope sports fetch Kalshi markets in the DAG, and `OddsComparator` only evaluates games when a `Kalshi` quote is present in `odds_by_bm`; market probability is derived from those Kalshi prices (`dags/multi_sport_betting_workflow.py:172-180`, `214-221`, `264-265`, `306-307`, `316-317`, `342-343`, `352-353`, `362-363`, `409-410`; `plugins/odds_comparator.py:580-581`).
2. The dashboard calibration surface is descriptive, not a production inference input: the page accepts a sport selector, but `get_calibration_data(sport)` reads the same `dashboard_calibration_v1` view without a sport filter, and that SQL view has no sport column (`dashboard/pages/calibration.py:70-90`; `dashboard/data_layer.py:1062-1149`; `migrations/stats_schema/V008__create_dashboard_read_model_views.sql:215-264`).
3. The generic Platt calibrator fits from `placed_bets` plus matched `bet_recommendations`/`unified_games`, so its sample is a selected historical recommendation/bet cohort rather than an all-predictions cohort (`plugins/probability_calibration.py:195-296`).
4. Repo-local live wiring is narrow: Tennis Platt calibration is directly applied in the betting path; Ligue 1 loads a live ensemble artifact; MLB routes through governed prediction rows; EPL ensemble calibration exists but is not wired into the live betting DAG; NBA, NHL, NFL, NCAAB, and WNCAAB remain plain Elo in the live betting path (`dags/multi_sport_betting_workflow.py:1099-1147`; `plugins/odds_comparator.py:301-336`; `plugins/elo/tennis_elo_rating.py:526-631`; `plugins/elo/epl_ensemble_adapter.py:74-88`).

## Per-sport audit matrix

| Sport | Live probability source in current behavior | Calibration/model artifact wiring status | Sample quality / cohort provenance | Leakage / selection-bias risk | Production-to-research parity | Current evidence label |
| --- | --- | --- | --- | --- | --- | --- |
| NBA | Plain Elo via `_load_elo_system('nba')` and `elo_system.predict(...)` (`dags/multi_sport_betting_workflow.py:1099-1147`; `plugins/odds_comparator.py:332-336`) | No live calibration artifact found. `platt_coefficients.json` is written by an offline script and is not the runtime loader target (`scripts/calibrate_elo_real_data.py:5-7`, `51`; `plugins/probability_calibration.py:95-99`) | Only descriptive calibration evidence found is the global dashboard bucket view over recommendations / linked placed bets (`dashboard/data_layer.py:1062-1149`; `migrations/stats_schema/V008__create_dashboard_read_model_views.sql:215-264`) | High selection-bias risk: recommendation-selected and placed-bet-linked cohort, not all live predictions | Research artifact/output names diverge from runtime loader path | Blocked |
| NHL | Plain Elo via `_load_elo_system('nhl')` and `elo_system.predict(...)` (`dags/multi_sport_betting_workflow.py:1099-1147`; `plugins/odds_comparator.py:332-336`) | `recalculated_platt.json` contains NHL coefficients, but no live NHL consumer was found in the betting path (`data/calibration/recalculated_platt.json:6-9`; `plugins/probability_calibration.py:95-118`) | Same descriptive dashboard cohort as above | High selection-bias risk from recommendation / placed-bet cohort | Offline coefficients exist without live betting-path use | Blocked |
| MLB | Governed prediction rows: `MLB_USE_GOVERNED_MODEL = True`, the DAG scores `mlb_model_predictions`, and the comparator refuses Elo fallback when governed mode is enabled (`plugins/elo/elo_update_config.py:39-45`; `dags/multi_sport_betting_workflow.py:1138-1157`, `1905-1917`; `plugins/odds_comparator.py:305-309`, `650-751`) | Live code expects `data/models/mlb_moneyline_model_v1.joblib`, but this checkout only contains `data/models/mlb/logistic_ensemble.pkl`; when the governed artifact is unavailable the scorer writes abstentions (`plugins/mlb_modeling/models.py:19`; `plugins/mlb_modeling/airflow_tasks.py:314-343`; `plugins/mlb_modeling/airflow_tasks.py:250-285`) | Strongest runtime evidence contract in scope: persisted rows include `calibration_method`, `ece_at_train`, `feature_hash`, `abstain`, and `abstention_reason` (`plugins/mlb_modeling/airflow_tasks.py:250-285`) | Lower leakage risk than most sports in repo terms because the artifact contract and runtime feature validation are explicit, but repo-local proof of active artifact availability is missing | Dashboard upcoming-games path still uses an MLB ensemble adapter instead of governed prediction rows (`dashboard/data_layer.py:831-859`) | Shadow-only |
| NFL | Plain Elo via `_load_elo_system('nfl')` and `elo_system.predict(...)` (`dags/multi_sport_betting_workflow.py:1099-1147`; `plugins/odds_comparator.py:332-336`) | No live calibration artifact found | Same descriptive dashboard cohort as above | High selection-bias risk from recommendation / placed-bet cohort | No repo evidence of calibrated runtime path | Blocked |
| EPL | Live betting path uses `EPLEloRating` 3-way probabilities because the DAG does not wrap EPL with the ensemble adapter (`dags/multi_sport_betting_workflow.py:1099-1147`; `plugins/odds_comparator.py:324-331`) | `EPLEnsembleAdapter` applies `ProbabilityCalibrator.calibrate('epl', ...)`, and `data/models/epl/model.pkl` exists, but that adapter is not wired into the live betting DAG (`plugins/elo/epl_ensemble_adapter.py:74-88`; `plugins/probability_calibration.py:81-118`; `dashboard/data_layer.py:853-859`) | Calibrator training uses `placed_bets` plus matched `bet_recommendations` and settled games (`plugins/probability_calibration.py:195-296`) | High selection-bias risk from selected recommendation / placed-bet cohort | Clear parity gap: dashboard/upcoming-games uses ensemble; betting DAG stays on plain Elo, so the evidence supports descriptive shadow use only | Shadow-only |
| LIGUE1 | Live betting path wraps Elo with `Ligue1EnsembleAdapter` when `LIGUE1_USE_ENSEMBLE = True` (`plugins/elo/elo_update_config.py:43-45`; `dags/multi_sport_betting_workflow.py:1160-1192`) | `data/models/ligue1/models.pkl` is live-wired through `Ligue1EnsembleModel.load()`; no separate probability-calibration artifact is applied in the live path (`plugins/elo/ligue1_ensemble.py:117-139`) | Runtime artifact stores models, scaler, features, and `is_trained`, but not model version, sample window, or calibration summary (`plugins/elo/ligue1_ensemble.py:117-139`) | Team-stat feature loading is date-bounded to prior matches, which reduces obvious leakage, but runtime artifact provenance is thin (`plugins/elo/ligue1_ensemble_adapter.py:103-123`) | Dashboard and betting DAG use the same adapter family | Shadow-only |
| NCAAB | Plain Elo via `_load_elo_system('ncaab')` and `elo_system.predict(...)` (`dags/multi_sport_betting_workflow.py:1115-1118`, `1237-1287`; `plugins/odds_comparator.py:332-336`) | `data/calibration/ncaab_platt_home.json` exists, but no runtime consumer was found (`data/calibration/ncaab_platt_home.json:1-9`) | Artifact metadata records `n_train: 17205` and `train_seasons: 3`, but only as offline file metadata (`data/calibration/ncaab_platt_home.json:1-9`) | High selection-bias risk remains because the only visible dashboard calibration surface is the global recommendation / placed-bet view | Explicit offline artifact with no live wiring | Blocked |
| WNCAAB | Plain Elo via `_load_elo_system('wncaab')` and `elo_system.predict(...)` (`dags/multi_sport_betting_workflow.py:1116-1118`; `plugins/odds_comparator.py:332-336`) | `data/calibration/wncaab_platt_home.json` exists, but no runtime consumer was found (`data/calibration/wncaab_platt_home.json:1-9`) | Artifact metadata records `n_train: 4735` and `train_seasons: 3`, but only as offline file metadata (`data/calibration/wncaab_platt_home.json:1-9`) | High selection-bias risk remains because the only visible dashboard calibration surface is the global recommendation / placed-bet view | Explicit offline artifact with no live wiring | Blocked |
| TENNIS | Betting path calls `predict_with_payload()` and uses `calibrated_prob_a`, then optionally overlays the feature-model artifact (`plugins/odds_comparator.py:310-323`, `373-401`; `plugins/elo/tennis_elo_rating.py:526-631`) | `data/calibration/tennis_platt_by_tour.json` is live-wired; `data/models/tennis_probability_model_v1.joblib` is wired but current metrics mark it `enabled: false`, so the live fallback is calibrated Elo (`data/calibration/tennis_platt_by_tour.json:1-15`; `data/models/tennis_probability_model_v1_metrics.json:14-29`) | Strongest checked-in temporal-validation story: chronological training frame, `TimeSeriesSplit`, and production-health publication blocked when `betmgm_holdout_rows == 0` (`plugins/elo/tennis_probability_model.py:150-262`, `1007-1023`) | Lower leakage risk than most sports in repo terms because the training/eval path is chronological, but current repo metrics still show no production-grade BetMGM holdout rows (`data/models/tennis_probability_model_v1_metrics.json:8-16`) | Feature-model artifact exists but is disabled; live behavior stays on calibrated Elo while the health page tracks descriptive evidence | Shadow-only |

## Calibration and model artifact inventory

| Artifact | Observed status in repo | Current behavior evidence |
| --- | --- | --- |
| `data/calibration/recalculated_platt.json` | Descriptive/offline for most sports; loader exists | Generic loader preloads it, but repo-local live betting-path use was only confirmed through EPL ensemble code, which is not DAG-wired (`plugins/probability_calibration.py:81-118`; `plugins/elo/epl_ensemble_adapter.py:74-88`) |
| `data/calibration/tennis_platt_by_tour.json` | Live-wired | Tennis Elo prediction payload applies it directly (`plugins/elo/tennis_elo_rating.py:526-631`) |
| `data/models/tennis_probability_model_v1.joblib` | Wired but disabled in checked-in metrics | Comparator will try it, then fall back to calibrated Elo on unavailability/error; metrics file marks `enabled: false` (`plugins/odds_comparator.py:373-401`; `data/models/tennis_probability_model_v1_metrics.json:14-29`) |
| `data/models/epl/model.pkl` | Descriptive / dashboard-side | Used by EPL ensemble path, but betting DAG does not wire that adapter (`dashboard/data_layer.py:853-859`; `dags/multi_sport_betting_workflow.py:1099-1147`) |
| `data/models/ligue1/models.pkl` | Live-wired | Loaded by Ligue 1 ensemble in the betting path (`plugins/elo/ligue1_ensemble.py:117-139`; `dags/multi_sport_betting_workflow.py:1160-1192`) |
| `data/models/mlb_moneyline_model_v1.joblib` | Expected live artifact path but absent in this checkout | Governed MLB scorer loads this path and otherwise writes abstentions (`plugins/mlb_modeling/models.py:19`; `plugins/mlb_modeling/airflow_tasks.py:314-343`) |
| `data/models/mlb/logistic_ensemble.pkl` | Present fallback/offline artifact relative to current DAG | Checkout contains this file, but live MLB betting is configured for governed predictions instead of the ensemble path (`plugins/elo/elo_update_config.py:37-45`) |
| `data/calibration/ncaab_platt_home.json` | Descriptive-only | No runtime consumer found (`data/calibration/ncaab_platt_home.json:1-9`) |
| `data/calibration/wncaab_platt_home.json` | Descriptive-only | No runtime consumer found (`data/calibration/wncaab_platt_home.json:1-9`) |
| `data/calibration/platt_coefficients.json` | Descriptive-only | Offline calibration script output; runtime loader reads `recalculated_platt.json` instead (`scripts/calibrate_elo_real_data.py:5-7`, `51`; `plugins/probability_calibration.py:95-99`) |

## Evidence-quality and parity notes that affect all sports

- The current dashboard calibration page is not sport-specific evidence even though it exposes a sport selector; the data helper returns one aggregate payload and labels it with the requested sport value (`dashboard/pages/calibration.py:70-90`; `dashboard/data_layer.py:1129-1149`).
- `dashboard_calibration_v1` computes observed win rate from linked `placed_bets` with `won/lost` status only, while bucket counts still include unsettled recommendations; this makes it descriptive reporting rather than clean approval-grade evidence (`migrations/stats_schema/V008__create_dashboard_read_model_views.sql:223-264`).
- The generic probability calibrator augments placed bets with historical recommendations joined to settled games, which mixes executed and non-executed cohorts and embeds selection risk in any sport using that calibrator (`plugins/probability_calibration.py:195-296`).
- No reviewed file provided repo-local evidence strong enough to classify any sport as a current **candidate** for future gating decisions. The strongest repo-local stacks were MLB, LIGUE1, TENNIS, and EPL, but each still had a material evidence or parity limitation in the checked-in state.

## Descriptive eligibility baseline

| Label | Sports | Basis in current repo state |
| --- | --- | --- |
| Blocked | NBA, NHL, NFL, NCAAB, WNCAAB | Live path is plain Elo or an unconsumed offline calibration artifact without enough audited descriptive support to justify a higher baseline |
| Shadow-only | MLB, EPL, LIGUE1, TENNIS | Repo-local model/calibration evidence is material enough for descriptive shadow treatment, but artifact availability, provenance, runtime parity, or production-grade validation evidence is still incomplete |
| Candidate | None observed | No repo-local sport combined live wiring, clean sample provenance, sport-specific evidence surface, and production/research parity strongly enough to support a higher label |
