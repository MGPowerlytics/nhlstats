#!/bin/bash
# Test File Cleanup Script
# Removes unused variables and imports flagged by Vulture

echo "Cleaning test files..."

# test_analyze_positions.py - remove unused mock_mkdir variable
sed -i "289s/mock_mkdir =.*/# Removed unused variable/" tests/test_analyze_positions.py

# test_bet_metrics_pipeline.py - remove unused variables
sed -i '/setup_recommendations =/d' tests/test_bet_metrics_pipeline.py
sed -i '/mock_db_manager_to_test_engine =/d' tests/test_bet_metrics_pipeline.py

# test_coverage_boost4.py - remove unused mock_nfl_data variables
sed -i '/mock_nfl_data =/d' tests/test_coverage_boost4.py

# test_dag_task_functions.py - remove unused variables
sed -i '/kalshi_sandbox_client =/d' tests/test_dag_task_functions.py

# test_elo_actual.py - remove unused imports
sed -i "167s/import nhl_elo_rating/# import nhl_elo_rating/" tests/test_elo_actual.py
sed -i "171s/import tennis_elo_rating/# import tennis_elo_rating/" tests/test_elo_actual.py
sed -i "172s/import epl_elo_rating/# import epl_elo_rating/" tests/test_elo_actual.py
sed -i "173s/import ligue1_elo_rating/# import ligue1_elo_rating/" tests/test_elo_actual.py
sed -i "174s/import glicko2_rating/# import glicko2_rating/" tests/test_elo_actual.py

# test_kalshi_markets.py - remove unused mock_config variables
sed -i '/mock_config =/d' tests/test_kalshi_markets.py

echo "Cleanup complete. Run tests to verify no regressions."
