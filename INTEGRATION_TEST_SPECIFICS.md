# Specific Integration Test Recommendations

Based on the system architecture analysis, here are specific tests needed for each integration point:

## 1. Data Ingestion → Database Integration Tests

### Test File: test_data_pipeline_integration.py

**Test Cases:**
1. **test_nba_game_ingestion()**
   - Download sample NBA games
   - Parse and validate game data
   - Insert into unified_games table
   - Verify all required columns populated
   - Test duplicate game prevention

2. **test_nhl_game_ingestion_with_events()**
   - Test NHL game events ingestion
   - Verify shift/play-by-play data
   - Test relationship to game records
   - Validate data completeness

3. **test_tennis_player_normalization()**
   - Test ATP/WTA player name normalization
   - Verify naming_resolver integration
   - Test handling of player aliases
   - Validate canonical name mapping

4. **test_soccer_3way_outcome_ingestion()**
   - Test EPL/Ligue1 game ingestion
   - Verify home/draw/away outcome storage
   - Test Gaussian draw probability calculation
   - Validate 3-way market integration

5. **test_data_validation_integration()**
   - Run data_validation.py after ingestion
   - Verify validation reports match ingested data
   - Test error detection for missing data
   - Validate team coverage checks

## 2. Elo Engine → Market Data Integration Tests

### Test File: test_elo_market_integration.py

**Test Cases:**
1. **test_elo_probability_calibration()**
   - Generate Elo predictions for historical games
   - Compare to actual outcomes
   - Calculate Brier score and calibration
   - Verify sport-specific thresholds

2. **test_market_probability_parsing()**
   - Parse Kalshi market tickers for all sports
   - Convert prices to probabilities
   - Verify probability calculations (100/price for YES markets)
   - Test edge cases (prices near 0 or 100)

3. **test_naming_resolver_integration()**
   - Test team/player name resolution across all sports
   - Verify canonical_mappings table usage
   - Test cache performance
   - Validate fallback behavior

4. **test_edge_calculation_validation()**
   - Calculate edge = elo_prob - market_prob
   - Verify edge > min_edge (0.05) for recommended bets
   - Test negative edge handling
   - Validate edge distribution by sport

5. **test_sport_specific_parameters()**
   - Verify K-factor per sport (all 20 except variations)
   - Test home_advantage values
   - Validate initial_rating consistency
   - Test neutral site adjustments

## 3. Portfolio Optimization → Betting Execution Tests

### Test File: test_betting_pipeline_integration.py

**Test Cases:**
1. **test_portfolio_optimizer_integration()**
   - Mock Elo predictions and market data
   - Run portfolio optimization
   - Verify Kelly criterion calculations
   - Test bankroll allocation logic

2. **test_bet_size_validation()**
   - Verify min_bet_size ($2.00) enforcement
   - Test max_bet_size ($50.00) limits
   - Validate max_single_bet_pct (5%) constraint
   - Test max_daily_risk_pct (10-25%) limits

3. **test_kalshi_betting_integration()**
   - Mock Kalshi API responses
   - Test bet placement with dry-run
   - Verify order validation and error handling
   - Test balance synchronization

4. **test_market_status_validation()**
   - Test handling of closed markets
   - Verify active vs initialized market status
   - Test close_time validation
   - Validate error messages for inactive markets

5. **test_bet_tracking_integration()**
   - Verify placed_bets table updates
   - Test bet status transitions (open → filled → settled)
   - Validate P&L calculation
   - Test reconciliation with Kalshi fills

## 4. Database → Dashboard Integration Tests

### Test File: test_dashboard_data_integration.py

**Test Cases:**
1. **test_portfolio_value_calculation()**
   - Calculate expected portfolio value from database
   - Compare to dashboard display
   - Test real-time updates
   - Validate cash + open_positions formula

2. **test_performance_metrics_integration()**
   - Verify ROI calculation
   - Test Sharpe ratio computation
   - Validate win rate statistics
   - Test sport-by-sport performance breakdown

3. **test_bet_history_integration()**
   - Verify bet history display
   - Test filtering by sport, date, outcome
   - Validate P&L aggregation
   - Test export functionality

4. **test_real_time_updates()**
   - Simulate new bet placement
   - Verify dashboard updates
   - Test WebSocket/streaming integration
   - Validate cache invalidation

5. **test_error_handling_integration()**
   - Test dashboard with database errors
   - Verify graceful degradation
   - Test user notification system
   - Validate recovery procedures

## 5. Airflow DAG Integration Tests

### Test File: test_airflow_integration.py

**Test Cases:**
1. **test_dag_task_dependencies()**
   - Verify task execution order
   - Test sport-specific task generation
   - Validate dependency graph
   - Test parallel execution limits

2. **test_xcom_data_passing()**
   - Verify data passing between tasks
   - Test large data payload handling
   - Validate data type preservation
   - Test error propagation

3. **test_schedule_compliance()**
   - Verify daily schedule (10 AM)
   - Test catchup=False behavior
   - Validate timezone handling
   - Test manual trigger functionality

4. **test_error_handling_and_retries()**
   - Test task failure scenarios
   - Verify retry logic (1 retry, 5 min delay)
   - Test alerting and notifications
   - Validate log aggregation

## 6. Multi-Sport Consistency Tests

### Test File: test_multi_sport_integration.py

**Test Cases:**
1. **test_unified_elo_interface_compliance()**
   - Verify all 9 sports implement BaseEloRating
   - Test polymorphic usage
   - Validate method signatures
   - Test backward compatibility

2. **test_sport_config_consistency()**
   - Verify SPORTS_CONFIG completeness
   - Test elo_threshold values per sport
   - Validate series_ticker patterns
   - Test games_module and kalshi_function mappings

3. **test_cross_sport_data_validation()**
   - Verify consistent date formats
   - Test team name normalization across sports
   - Validate score storage consistency
   - Test outcome representation (win/loss vs 3-way)

4. **test_performance_benchmarking()**
   - Compare prediction accuracy across sports
   - Test calibration consistency
   - Validate edge distribution by sport
   - Test risk-adjusted returns comparison

## Test Infrastructure Requirements

### Mock Services Needed:
1. **MockKalshiAPI**: Simulate Kalshi API responses
2. **MockDatabase**: In-memory test database
3. **MockGameData**: Sample game data for all sports
4. **MockMarketData**: Simulated market prices and probabilities

### Test Data Requirements:
1. **Historical game data** for validation
2. **Market data samples** for all sport formats
3. **Edge case scenarios** for error testing
4. **Performance benchmarks** for regression testing

### CI/CD Integration:
1. **Docker test environment** with all dependencies
2. **Database migration testing** for schema changes
3. **Performance regression testing**
4. **Security vulnerability scanning**

## Implementation Timeline

### Phase 1 (Week 1-2): Critical Path Tests
- Data ingestion → database integration tests
- Elo → market data integration tests
- Portfolio → betting execution tests

### Phase 2 (Week 3-4): Core Integration Tests
- Database → dashboard integration tests
- Multi-sport consistency tests
- Basic Airflow integration tests

### Phase 3 (Week 5-6): Comprehensive Testing
- Advanced error handling tests
- Performance and load testing
- Security and compliance testing
- Regression test suite completion

## Success Metrics

1. **Test Coverage**: >90% for integration points
2. **Test Execution Time**: <10 minutes for full suite
3. **False Positive Rate**: <5% for integration tests
4. **Defect Detection**: >80% of integration issues caught
5. **Regression Prevention**: 100% of critical bugs prevented
