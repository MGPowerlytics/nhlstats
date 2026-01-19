# Changelog

## 2026-01-19 - Daily Summary Email Notifications & Fixed SMS

### Added
- **Daily Summary SMS**: New `send_daily_summary` task at end of DAG sends 3-part SMS:
  - Message 1: Balance, portfolio value, yesterday's P/L
  - Message 2: Today's bets placed with top bet details  
  - Message 3: Additional bets or available balance
- **Custom SMS Function**: Added `send_sms()` using direct SMTP instead of Airflow's email utility
  - Bypasses Airflow email authentication issues with Gmail
  - Properly formats for Verizon SMS gateway (7244959219@vtext.com)
  - Handles multi-part messages with 2-second delays between sends
- **Balance Tracking**: Daily balance snapshots saved to `data/portfolio/balance_YYYY-MM-DD.json`
  - Enables day-over-day P/L calculation
  - Tracks both cash balance and total portfolio value

### Fixed
- **Email Notifications**: Replaced Airflow `send_email()` with custom `send_sms()`
  - Resolves SMTP authentication errors (530: Authentication Required)
  - Uses `smtplib` directly with Gmail app password from environment
  - Applied to both bet placement notifications and daily summaries
  - Task failure notifications still use Airflow default (DAG default_args)

### Technical Details
- SMS messages split into 3 parts to stay under 160 char SMS limit
- 2-second delays between messages ensure proper delivery order
- Graceful fallback if yesterday's balance data not available
- Task runs after `portfolio_optimized_betting` task
- Imports: Added `time` module for message delays

---

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
- Added Kalshi historical candlestick backfill utility for research/backtesting (`plugins/kalshi_historical_data.py`).
- Extended Kalshi historical backfill to support market metadata and trade tape ingestion (`plugins/kalshi_historical_data.py`, `--mode markets|trades`).
- Added a first-pass NHL backtest harness against historical Kalshi prices using last trade before decision time (`plugins/backtest_kalshi_nhl.py`).
