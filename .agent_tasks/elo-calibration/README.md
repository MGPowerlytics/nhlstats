# Elo Calibration with Real Data — Backfill Phase

**Status**: DONE
**Task**: Backfill missing `elo_prob` values in `placed_bets` and re-run calibration.

## Phase C1 — Recon Results

| Sport | Missing elo_prob | Date Range |
|-------|-----------------|------------|
| NBA | 319 | 2026-02-17 → 2026-04-16 |
| NCAAB | 56 | 2026-02-15 → 2026-03-01 |
| NHL | 68 | 2026-03-03 → 2026-04-14 |
| TENNIS | 15 | 2026-02-15 → 2026-02-18 |
| WNCAAB | 14 | 2026-02-15 → 2026-02-23 |

All these bets have `home_team` = NULL and `away_team` = NULL in the DB. Team names are embedded in the `market_title` column (e.g., "Philadelphia at Boston Winner?") and/or the `ticker` column (e.g., `KXNBAGAME-26MAR01PHIBOS-BOS`).

## Strategy

**Option C** was used: Load latest Elo backup CSVs (snapshot from 2026-02-05) into fresh Elo instances, then compute `predict()` using current ratings. This is an approximation since ratings have changed since the bets were placed, but is the best available approach since we don't have historical replay data.

### Team Name Mapping

Different sports use different naming conventions in the Elo system vs market titles:
- **NBA**: market_title uses city names ("Boston"), Elo uses 3-letter codes ("BOS") — mapping in script
- **NHL**: market_title uses city names ("Anaheim"), Elo uses 3-letter codes ("ANA") — mapping in script
- **NCAAB**: Both use full names but with different formatting — mapping normalizes "St." → "_St", spaces → underscores
- **WNCAAB**: Same as NCAAB
- **TENNIS**: Backup CSV was empty (0 ratings), so no tennis bets could be backfilled

### Elo Backup Sources

Backup CSVs found in `data/elo_backups/` with suffix `_20260205_162426.csv`:
- NBA: 30 teams
- NHL: 33 teams
- NCAAB: 367 teams
- WNCAAB: 138 teams
- TENNIS: 0 players (file exists but is empty — no player ratings persisted)

## Phase C3 — Backfill Execution

Script: `scripts/backfill_elo_prob.py`

| Sport | Found | Updated | Skipped | Notes |
|-------|-------|---------|---------|-------|
| NBA | 319 | **177** | 142 | 142 skipped due to missing market_title |
| NHL | 68 | **34** | 34 | 34 skipped due to missing market_title |
| NCAAB | 56 | **25** | 31 | 31 skipped (missing title or unmapped team) |
| WNCAAB | 14 | **9** | 5 | 5 skipped |
| TENNIS | 15 | **0** | 15 | No backup ratings available |
| **Total** | 472 | **245** | 227 | |

## Phase C4 — Calibration Re-run

After backfill, ran `scripts/calibrate_elo_real_data.py`. Results:

| Sport | Settled+elo | Qualifies? |
|-------|-------------|-----------|
| MLB | 83 | ✅ (was already) |
| **NBA** | **174** | ✅ **NEW** |
| **NHL** | **34** | ✅ **NEW** |
| EPL | 25 | ❌ (needs 5 more) |
| NCAAB | 25 | ❌ (needs 5 more) |
| LIGUE1 | 4 | ❌ |
| WNCAAB | 9 | ❌ |
| TENNIS | 0 | ❌ |

### NBA Calibration
- **n_train**: 174
- **Coef**: 1.554
- **Intercept**: -1.064
- **Avg raw bias**: +0.126 (Elo overestimates)
- **Avg cal bias**: -0.000015 (near-zero after calibration)

### NHL Calibration
- **n_train**: 34
- **Coef**: 2.893
- **Intercept**: -0.633
- **Avg raw bias**: -0.111 (Elo underestimates)
- **Avg cal bias**: -0.000038 (near-zero after calibration)

## Exit Criteria Met
- ✅ Script runs successfully and increases elo_prob coverage for **4 sports** (NBA, NHL, NCAAB, WNCAAB — exceeded requirement of 3+)
- ✅ After re-running calibration, **2 additional sports** (NBA, NHL) now qualify beyond MLB (exceeded requirement of 1+)
- ✅ NBA has 174 settled bets with elo_prob (far above 30 threshold)
- ✅ NHL has 34 settled bets with elo_prob (above 30 threshold)

## Artifacts
- `scripts/backfill_elo_prob.py` — Backfill script (idempotent, re-runnable)
- `scripts/calibrate_elo_real_data.py` — Updated with correct sys.path
- `data/calibration/platt_coefficients.json` — Now has MLB + NBA + NHL coefficients
