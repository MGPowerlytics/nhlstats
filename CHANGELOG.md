# Changelog

## 2026-01-19 - Portfolio-Level Betting Optimization

### Added
- **Portfolio optimization system** using Kelly Criterion for optimal bet sizing
  - `plugins/portfolio_optimizer.py`: Core optimization engine
  - `plugins/portfolio_betting.py`: Kalshi integration
  - `PORTFOLIO_BETTING.md`: Comprehensive documentation
  - **`tests/test_portfolio_optimizer.py`: 19 unit tests (100% passing)**
- **Kelly Criterion bet sizing** with configurable fractional Kelly (default: 0.25)
- **Portfolio-level risk management**:
  - Daily spending limits (default: **25% of bankroll**)
  - Per-bet maximum (default: 5% of bankroll)
  - Prioritization by expected value
- **Multi-sport allocation**: Optimizes across NHL, NBA, MLB, NFL, NCAAB, Tennis simultaneously
- **Comprehensive reporting**:
  - Human-readable reports in `data/portfolio/betting_report_*.txt`
  - Machine-readable results in `data/portfolio/betting_results_*.json`
- **Expected value tracking** for each bet opportunity
- **Dry-run mode** for safe testing
- **Tennis and NCAAB support** in portfolio optimizer
- **DAG integration**: New `portfolio_optimized_betting` task in workflow

### Testing
- **19 unit tests** covering:
  - Kelly Criterion mathematical correctness
  - Expected value calculations
  - Portfolio allocation logic
  - Risk management constraints (daily limits, bet sizes)
  - Multi-sport data loading (NBA, Tennis formats)
  - Edge cases (small bankrolls, negative edges)
- **Manual testing** completed with real data (23 opportunities, 5 bets placed)
- **Integration testing** pending production DAG run

### Changed
- Bet sizing now based on mathematical optimization rather than fixed amounts
- Replaced simple `edge/4` formula with Kelly Criterion
- Bets now sorted and prioritized by expected value
- Portfolio stops allocating when daily risk limit reached
- **Default daily risk increased to 25%** (from 10%) for small bankrolls
- Old `place_bets_on_recommendations` deprecated in favor of unified portfolio betting

### Improved
- Much better risk management across all sports
- Higher expected ROI through optimal sizing
- Prevents over-betting by capping daily exposure
- Clear visibility into expected profits and risk
- Handles different bet file formats (tennis players vs team sports)

### Technical Details
- Kelly formula: `f* = (p×b - q) / b` where p=elo_prob, b=net odds
- Uses fractional Kelly for safety (reduces variance)
- Filters by minimum edge (5%) and confidence (68%)
- Respects hard limits ($2-$50 per bet, configurable)
- Portfolio task runs after all sports complete bet identification

## 2026-01-19 - Earlier Updates

All notable changes to this project are documented in this file.

## 2026-01-19
- Added Markov Momentum overlay (`plugins/markov_momentum.py`) to provide a lightweight Markov-chain-based recent-form adjustment on top of Elo.
- Extended lift/gain analysis to support arbitrary probability columns and to compute `elo_markov_prob` (`plugins/lift_gain_analysis.py`).
- Added a current-season-only comparison runner for NBA/NHL Elo vs Elo+Markov (`plugins/compare_elo_markov_current_season.py`).
- Added a leakage-safe Elo calibration runner (Platt scaling) for NBA/NHL (`plugins/compare_elo_calibrated_current_season.py`).
- Enhanced the calibration runner with recent-window training controls (`--train-window-days`, `--train-max-games`) and leakage-safe tuned-threshold accuracy reporting.
