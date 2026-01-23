# Dead Code Deletion Plan - Phase 1.1
# Generated: 2026-01-23
# Based on Vulture analysis and system dependency check

## 1. CONFIRMED DEAD CODE (Safe to Delete)

### Archive Directory Files (Historical/Backup)
These files appear to be historical backups and are not imported anywhere in the current system:

1. **archive/nhl_trueskill_ratings.py** - Unused import 'Rating' (Vulture flagged)
2. **archive/kalshi_markets_old.py** - Old version, unused import 'cryptography'
3. **archive/build_training_dataset.py** and variants - Old training code
4. **archive/nba_db_loader.py** - Old database loader
5. **archive/nhl_db_loader.py** - Old database loader
6. **archive/other_techniques/train_traditional_stats.py** - Unused import

### Test File Cleanup (Unused variables/imports)
These are minor cleanup items in test files that don't affect functionality:

1. **tests/test_analyze_positions.py** - Unused mock_mkdir variable
2. **tests/test_bet_metrics_pipeline.py** - Various unused setup variables
3. **tests/test_coverage_boost4.py** - Unused mock_nfl_data variables
4. **tests/test_dag_task_functions.py** - Unused kalshi_sandbox_client variables
5. **tests/test_elo_actual.py** - Unused imports for rating systems
6. **tests/test_kalshi_markets.py** - Unused mock_config variables

## 2. POTENTIAL DEAD CODE (Needs Verification)

### Scripts Directory
These scripts might be utility scripts but need verification:
- scripts/backtest_betting.py
- scripts/backtest_nhl_betting.py
- scripts/check_kalshi_markets.py
- scripts/find_ncaab.py
- scripts/generate_bets_basketball.py

## 3. RECOMMENDED ACTION PLAN

### Immediate Deletion (Safe):
1. Delete specific archive files flagged by Vulture
2. Clean up unused variables in test files
3. Remove obviously duplicate/backup files

### Verification Needed:
1. Check if any scripts are referenced in DAGs or documentation
2. Verify no production code depends on archive files
3. Run tests after cleanup to ensure no regressions

## 4. DELETION COMMANDS

```bash
# Backup first (optional)
cp -r archive/ archive_backup_$(date +%Y%m%d)/

# Delete specific Vulture-flagged archive files
rm archive/nhl_trueskill_ratings.py
rm archive/kalshi_markets_old.py
rm archive/build_training_dataset.py
rm archive/build_training_dataset_old.py
rm archive/build_training_dataset_v3.py
rm archive/nba_db_loader.py
rm archive/nhl_db_loader.py
rm archive/other_techniques/train_traditional_stats.py

# Clean test files (remove unused variables/imports)
# This requires editing files rather than deletion
```

## 5. RISK ASSESSMENT
- **Low Risk**: Archive directory files are clearly historical
- **Medium Risk**: Test file cleanup could affect test functionality if done incorrectly
- **High Risk**: Script deletion without verification could remove useful utilities

## 6. NEXT STEPS AFTER DELETION
1. Run test suite to verify no regressions
2. Run Vulture again to confirm issues resolved
3. Update PROJECT_PLAN.md with completion status
