# EPL xG Ensemble Integration

**Date**: 2025-07-17
**Author**: Engineer (Henchman)
**Status**: Complete

## Objective

Add Understat xG/xGA rolling features (last 5 games) to the EPL ensemble model feature set and retrain.

## Changes Made

### `plugins/elo/epl_ensemble.py`

1. **Features list (17 total)**: Added 4 new features: `home_avg_xg`, `away_avg_xg`, `home_avg_xga`, `away_avg_xga`
2. **`_DEFAULT_FEATURE_VALUES`**: Added defaults for these features (1.5/1.3/1.3/1.5)
3. **New `_build_xg_lookup()` method**: Queries `soccer_team_game_stats_ext` JOIN `team_game_stats` to build a lookup dict keyed by `(game_date, team_name)` → `{xg, xga}`. Gracefully returns empty dict if DB unavailable.
4. **`build_training_frame()`**:
   - Added `team_xg` and `team_xga` deques (maxlen=5)
   - Builds xg lookup at start via `_build_xg_lookup()`
   - Adds xg features to each training row using current deque state
   - Pushes xg/xga after processing each game (same pattern as goals)
5. **Imports**: Added `DBManager` import

### `plugins/elo/epl_ensemble_adapter.py`

1. **Imports**: Added `deque`, `defaultdict` from `collections`; imported `_DEFAULT_FEATURE_VALUES` and `_mean_or_default` from ensemble module
2. **New fields**: `team_xg` and `team_xga` deques on the adapter
3. **`_load_team_stats()`**: Now queries xg/xga alongside goals, maintains rolling 5-game deques, stores them on the adapter
4. **`predict_probs()`**: Adds `home_avg_xg`, `away_avg_xg`, `home_avg_xga`, `away_avg_xga` to the features dict with fallback defaults

### Retrained Model

- Old model deleted, new model at `data/models/epl/model.pkl`
- 17 features instead of 13
- Trained from all available CSVs (2005-06 to 2025-26)

## Verification

All 3 Done When conditions pass:

1. **Feature count**: `Fitted: True Features: 17 Coefs: (3, 17)` ✅
2. **ruff check**: Both files pass ✅
3. **Adapter init**: `Ratings: 0` (no errors) ✅

## Artifacts

- `.agent_tasks/epl-xg-ensemble/check_schema.py` — DB schema verification
- `.agent_tasks/epl-xg-ensemble/check_teams.py` — Team name mapping check
- `.agent_tasks/epl-xg-ensemble/check_match.py` — CSV-to-DB match verification
- `.agent_tasks/epl-xg-ensemble/check_match2.py` — Detailed season-by-season match check
- `.agent_tasks/epl-xg-ensemble/train_model.py` — Training script
- `.agent_tasks/epl-xg-ensemble/test_db_override.py` — DB connection test
