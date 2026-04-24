# Project TODOs

## Team Factors Implementation - Next Steps

### Phase 1: Integration with Probability Calculation
- [ ] Modify `plugins/portfolio_optimizer.py` to fetch team factors for each game
- [ ] Apply team factor adjustments to base Elo probabilities
- [ ] Ensure adjustments are capped at +/- 5% as designed
- [ ] Test integration with existing betting workflow

### Phase 2: Backtesting and Model Improvement
- [ ] Re-run MLB backtest (2021-2024) with team factors integrated
- [ ] Extend team factor back testing to NBA, NHL, NFL (2021-2024)
- [ ] Run model improvement back testing (ensemble methods, hyperparameter tuning) across all sports
- [ ] Compare ROI, log loss, and Brier score vs. Pure Elo baseline
- [ ] Analyze which team factors contribute most to improvement
- [ ] Document backtest results in `backtest_summary.md`

### Phase 3: Data Enhancement
- [ ] Add multi-year historical data (2021-2023) to team factors CSVs for all sports (MLB, NBA, NHL, NFL)
- [ ] Collect raw team statistics (points, goals, assists, etc.) back to 2021 for all sports to enable comprehensive backtesting
- [ ] Add park factors (hitter/pitcher friendly parks)
- [ ] Add bullpen strength metrics (late-inning ERA, leverage index)
- [ ] Add recent form tracking (last 10 games rolling average)
- [ ] Add starting pitcher matchup adjustments

### Phase 4: Expand to All Sports
- [ ] Create `data/nba_team_factors.csv` with team stats
- [ ] Create `data/nhl_team_factors.csv` with team stats
- [ ] Create `data/nfl_team_factors.csv` with team stats
- [ ] Create `data/tennis_team_factors.csv` with player stats
- [ ] Create `data/ncaab_team_factors.csv` with team stats
- [ ] Create `data/wncaab_team_factors.csv` with team stats
- [ ] Adapt `fetch_team_stats()` function for NBA API
- [ ] Adapt `fetch_team_stats()` function for NHL API
- [ ] Adapt `fetch_team_stats()` function for NFL API
- [ ] Adapt `fetch_team_stats()` function for tennis APIs
- [ ] Adapt `fetch_team_stats()` function for college basketball APIs
- [ ] Update DAG to run team factors fetch for all supported sports

### Phase 5: Production Monitoring
- [ ] Add data quality checks (validate stats are within expected ranges)
- [ ] Add alerting for failed data fetches
- [ ] Monitor team factors impact on daily betting ROI
- [ ] Set up weekly review of factor performance by sport

### Phase 6: Comprehensive Backtesting Across All Sports
- [ ] Design and implement backtesting framework for all sports (MLB, NBA, NHL, NFL, tennis, NCAAB, WNCAAB)
- [ ] Run backtests for each sport (2021-2024) with team factors integrated
- [ ] Compare performance metrics (ROI, log loss, Brier score) across sports
- [ ] Identify optimal model configurations per sport
- [ ] Generate cross-sport backtest summary reports

## Code Review & Technical Debt
- [ ] Review team_factors.py and adapt for NBA, NHL, NFL, tennis, NCAAB, WNCAAB, EPL, Ligue1, CBA, Unrivaled
- [ ] Create sport-specific fetch_team_stats() functions for each sport
- [ ] Update DAG task `fetch_team_factors` to support multiple sports
- [ ] Ensure database schema `team_factors` supports sport-specific metrics
- [ ] Review portfolio_optimizer.py integration with team factors
- [ ] Check backtesting scripts (backtest_mlb_demo.py, backtest_from_csv.py) and extend to other sports
- [ ] Add data validation for team stats collection (2021-2024)
- [ ] Implement error handling and logging for team stats API calls
- [ ] Create unit tests for team factors pipeline

## Other Pending Tasks

### Glicko-2 Implementation
- [ ] Extend Glicko-2 support to MLB (currently only NBA, NHL, NFL)
- [ ] Test Glicko-2 vs. Elo for early-season predictions
- [ ] Calibrate Glicko-2 rating volatility parameter

### Sharp Bookmaker Blending
- [ ] Integrate actual BetMGM historical odds
- [ ] Test optimal blend weights per sport (currently simulated)
- [ ] Implement walk-forward validation for blend calibration

### Recency Weighting
- [ ] Implement exponential decay based on days since last game
- [ ] Calibrate decay rate via cross-validation
- [ ] Test sport-specific decay rates

### Situation Adjustments
- [ ] Add back-to-back game adjustments (NBA, NHL)
- [ ] Add rest day performance adjustments
- [ ] Add travel distance fatigue factor
- [ ] Add divisional rivalry adjustments
- [ ] Add playoff vs. regular season adjustments

## Reference Documents
- [Team Factors Implementation Guide](TEAM_FACTORS_IMPLEMENTATION.md)
- [MLB Backtest Summary](backtest_summary.md)
- [Betting Strategy](docs/BETTING_STRATEGY.md)

## Last Updated
2026-04-11
