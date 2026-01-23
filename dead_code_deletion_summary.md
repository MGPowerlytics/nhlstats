# Dead Code Deletion Summary - Phase 1.1
## Completed: 2026-01-23

### Files Successfully Deleted:
- archive/nhl_trueskill_ratings.py
- archive/kalshi_markets_old.py
- archive/build_training_dataset.py
- archive/build_training_dataset_old.py
- archive/build_training_dataset_v3.py
- archive/nba_db_loader.py
- archive/nhl_db_loader.py
- archive/other_techniques/train_traditional_stats.py

### Cleanup Script Execution Result:
```
Cleaning test files...
Cleanup complete. Run tests to verify no regressions.

Cleaning test files...
Cleanup complete. Run tests to verify no regressions.

```

### Vulture Report After Deletion:
```
archive_backup_20260123_100125/build_training_dataset.py:30: unused variable 'exc_tb' (100% confidence)
archive_backup_20260123_100125/build_training_dataset.py:30: unused variable 'exc_type' (100% confidence)
archive_backup_20260123_100125/build_training_dataset.py:30: unused variable 'exc_val' (100% confidence)
archive_backup_20260123_100125/build_training_dataset_old.py:30: unused variable 'exc_tb' (100% confidence)
archive_backup_20260123_100125/build_training_dataset_old.py:30: unused variable 'exc_type' (100% confidence)
archive_backup_20260123_100125/build_training_dataset_old.py:30: unused variable 'exc_val' (100% confidence)
archive_backup_20260123_100125/build_training_dataset_v3.py:34: unused variable 'exc_tb' (100% confidence)
archive_backup_20260123_100125/build_training_dataset_v3.py:34: unused variable 'exc_type' (100% confidence)
archive_backup_20260123_100125/build_training_dataset_v3.py:34: unused variable 'exc_val' (100% confidence)
archive_backup_20260123_100125/kalshi_markets_old.py:270: unused import 'cryptography' (90% confidence)
archive_backup_20260123_100125/nba_db_loader.py:25: unused variable 'exc_tb' (100% confidence)
archive_backup_20260123_100125/nba_db_loader.py:25: unused variable 'exc_type' (100% confidence)
archive_backup_20260123_100125/nba_db_loader.py:25: unused variable 'exc_val' (100% confidence)
archive_backup_20260123_100125/nhl_db_loader.py:26: unused variable 'exc_tb' (100% confidence)
archive_backup_20260123_100125/nhl_db_loader.py:26: unused variable 'exc_type' (100% confidence)
archive_backup_20260123_100125/nhl_db_loader.py:26: unused variable 'exc_val' (100% confidence)
archive_backup_20260123_100125/nhl_trueskill_ratings.py:12: unused import 'Rating' (90% confidence)
archive_backup_20260123_100125/other_techniques/train_traditional_stats.py:20: unused import 'minimize' (90% confidence)
tests/conftest.py:31: unused variable 'connection_record' (100% confidence)
tests/test_analyze_positions.py:289: unused variable 'mock_mkdir' (100% confidence)
tests/test_bet_metrics_pipeline.py:40: unused variable 'mock_db_manager_to_test_engine' (100% confidence)
tests/test_bet_metrics_pipeline.py:89: unused variable 'setup_recommendations' (100% confidence)
tests/test_bet_metrics_pipeline.py:108: unused variable 'setup_recommendations' (100% confidence)
tests/test_bet_metrics_pipeline.py:137: unused variable 'setup_recommendations' (100% confidence)
tests/test_bet_metrics_pipeline.py:163: unused variable 'setup_recommendations' (100% confidence)
tests/test_coverage_boost4.py:122: unused variable 'mock_nfl_data' (100% confidence)
tests/test_coverage_boost4.py:128: unused variable 'mock_nfl_data' (100% confidence)
tests/test_coverage_boost4.py:371: unused variable 'mock_nfl_data' (100% confidence)
tests/test_dag_task_functions.py:28: unused variable 'kalshi_sandbox_client' (100% confidence)
tests/test_dag_task_functions.py:75: unused variable 'kalshi_sandbox_client' (100% confidence)
tests/test_dashboard_playwright.py:18: unused import 'signal' (90% confidence)
tests/test_financial_performance_playwright.py:13: unused import 'Decimal' (90% confidence)
tests/test_kalshi_markets.py:54: unused variable 'mock_config' (100% confidence)
tests/test_kalshi_markets.py:66: unused variable 'mock_config' (100% confidence)
tests/test_kalshi_markets.py:82: unused variable 'mock_config' (100% confidence)
tests/test_kalshi_markets.py:97: unused variable 'mock_config' (100% confidence)
tests/test_kalshi_markets.py:121: unused variable 'mock_config' (100% confidence)
Vulture check after deletion

archive_backup_20260123_100125/build_training_dataset.py:30: unused variable 'exc_tb' (100% confidence)
archive_backup_20260123_100125/build_training_dataset.py:30: unused variable 'exc_type' (100% confidence)
archive_backup_20260123_100125/build_training_dataset.py:30: unused variable 'exc_val' (100% confidence)
archive_backup_20260123_100125/build_training_dataset_old.py:30: unused variable 'exc_tb' (100% confidence)
archive_backup_20260123_100125/build_training_dataset_old.py:30: unused variable 'exc_type' (100% confidence)
archive_backup_20260123_100125/build_training_dataset_old.py:30: unused variable 'exc_val' (100% confidence)
archive_backup_20260123_100125/build_training_dataset_v3.py:34: unused variable 'exc_tb' (100% confidence)
archive_backup_20260123_100125/build_training_dataset_v3.py:34: unused variable 'exc_type' (100% confidence)
archive_backup_20260123_100125/build_training_dataset_v3.py:34: unused variable 'exc_val' (100% confidence)
archive_backup_20260123_100125/kalshi_markets_old.py:270: unused import 'cryptography' (90% confidence)
archive_backup_20260123_100125/nba_db_loader.py:25: unused variable 'exc_tb' (100% confidence)
archive_backup_20260123_100125/nba_db_loader.py:25: unused variable 'exc_type' (100% confidence)
archive_backup_20260123_100125/nba_db_loader.py:25: unused variable 'exc_val' (100% confidence)
archive_backup_20260123_100125/nhl_db_loader.py:26: unused variable 'exc_tb' (100% confidence)
archive_backup_20260123_100125/nhl_db_loader.py:26: unused variable 'exc_type' (100% confidence)
archive_backup_20260123_100125/nhl_db_loader.py:26: unused variable 'exc_val' (100% confidence)
archive_backup_20260123_100125/nhl_trueskill_ratings.py:12: unused import 'Rating' (90% confidence)
archive_backup_20260123_100125/other_techniques/train_traditional_stats.py:20: unused import 'minimize' (90% confidence)
tests/conftest.py:31: unused variable 'connection_record' (100% confidence)
tests/test_analyze_positions.py:289: unused variable 'mock_mkdir' (100% confidence)
tests/test_bet_metrics_pipeline.py:40: unused variable 'mock_db_manager_to_test_engine' (100% confidence)
tests/test_bet_metrics_pipeline.py:89: unused variable 'setup_recommendations' (100% confidence)
tests/test_bet_metrics_pipeline.py:108: unused variable 'setup_recommendations' (100% confidence)
tests/test_bet_metrics_pipeline.py:137: unused variable 'setup_recommendations' (100% confidence)
tests/test_bet_metrics_pipeline.py:163: unused variable 'setup_recommendations' (100% confidence)
tests/test_coverage_boost4.py:122: unused variable 'mock_nfl_data' (100% confidence)
tests/test_coverage_boost4.py:128: unused variable 'mock_nfl_data' (100% confidence)
tests/test_coverage_boost4.py:371: unused variable 'mock_nfl_data' (100% confidence)
tests/test_dag_task_functions.py:28: unused variable 'kalshi_sandbox_client' (100% confidence)
tests/test_dag_task_functions.py:75: unused variable 'kalshi_sandbox_client' (100% confidence)
tests/test_dashboard_playwright.py:18: unused import 'signal' (90% confidence)
tests/test_financial_performance_playwright.py:13: unused import 'Decimal' (90% confidence)
tests/test_kalshi_markets.py:54: unused variable 'mock_config' (100% confidence)
tests/test_kalshi_markets.py:66: unused variable 'mock_config' (100% confidence)
tests/test_kalshi_markets.py:82: unused variable 'mock_config' (100% confidence)
tests/test_kalshi_markets.py:97: unused variable 'mock_config' (100% confidence)
tests/test_kalshi_markets.py:121: unused variable 'mock_config' (100% confidence)
Vulture check after deletion

```

### Remaining Issues (to address in future phases):
1. **tests/conftest.py**: unused variable 'connection_record'
2. **tests/test_dashboard_playwright.py**: unused import 'signal'
3. **tests/test_financial_performance_playwright.py**: unused import 'Decimal'

### Next Steps:
1. Run test suite: `pytest tests/ -k "not playwright" -v`
2. Update PROJECT_PLAN.md with completion status
3. Proceed to Task 3: Ensure all tests pass
