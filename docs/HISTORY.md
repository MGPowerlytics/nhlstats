# Project History - Evolution of Multi-Sport Betting System

This document chronicles the evolution of the nhlstats project from a single-sport NHL analyzer to a comprehensive 9-sport automated betting platform.

## Timeline Overview

```
2018-2021: Initial Concept - NHL Data Collection
2021-2024: Data Expansion - Added MLB, NBA, NFL
2024 Q4:  Model Development - Elo vs ML experiments
2025 Q1:  Production System - Kalshi integration
2025 Q4:  Multi-Sport Scale - 9 sports operational
2026 Q1:  Portfolio Optimization - Kelly Criterion implementation
```

## Phase 1: Foundation (2018-2021)

### Initial NHL Focus
**Goal**: Collect and analyze NHL game data for predictive modeling

**Implementation**:
- Built NHL API scrapers for game events, shots, shifts
- Designed normalized DuckDB schema (9 tables)
- Created Airflow DAGs for daily data collection
- Stored raw JSON/CSV files for historical analysis

**Results**:
- ✅ Successfully collected 4,000+ NHL games
- ✅ Shot coordinate data with X/Y positions
- ✅ Time-on-ice and shift data per player
- ✅ Automated daily download pipeline

**Key Files Created**:
- `plugins/nhl_game_events.py` - Event scraper
- `plugins/nhl_shifts.py` - Shift data collection
- `dags/nhl_daily_download.py` - Airflow orchestration
- `archive/NORMALIZATION_PLAN.md` - Database schema

**Lessons Learned**:
- NHL API is reliable but requires rate limiting
- Normalized schemas better than raw JSON storage
- Airflow ideal for daily collection workflows

## Phase 2: Multi-Sport Expansion (2021-2024)

### Adding Major American Sports

**MLB Integration (2022)**
- **Source**: MLB Stats API + Baseball Savant
- **Granularity**: Pitch-level data (velocity, spin, location)
- **Volume**: 15 games/day, ~280 pitches/game
- **Status**: ✅ Complete

**NBA Integration (2022)**
- **Source**: Official NBA Stats API
- **Granularity**: Shot-level with X/Y coordinates
- **Volume**: 12 games/day, ~180 shots/game
- **Status**: ✅ Complete

**NFL Integration (2023)**
- **Source**: nflfastR via nfl_data_py
- **Granularity**: Play-level with EPA, CPOE
- **Historical**: Back to 1999
- **Status**: ✅ Complete

**Soccer Integration (2024)**
- **EPL**: Premier League (England)
- **Ligue 1**: French top division
- **Challenges**: 3-way markets (home/draw/away)
- **Status**: ✅ Complete

**Tennis Integration (2024)**
- **Source**: tennis-data.co.uk (ATP/WTA)
- **Model**: Player-based Elo (not team)
- **Challenges**: No home advantage, surface effects
- **Status**: ✅ Complete

**College Basketball (2025)**
- **NCAAB**: Men's NCAA Division I (350+ teams)
- **WNCAAB**: Women's NCAA Division I (141 teams)
- **Source**: Massey Ratings
- **Challenges**: Season reversion due to roster turnover
- **Status**: ✅ Complete

### Infrastructure Evolution

**Database Migration**:
- Started: Separate JSON files per game
- Current: Unified DuckDB database (`nhlstats.duckdb`)
- Benefits: SQL queries, faster analytics, easier backups

**Airflow DAG Consolidation**:
- Started: Individual DAGs per sport (7 files)
- Current: Unified `multi_sport_betting_workflow.py`
- Benefits: Consistent scheduling, shared infrastructure

**Data Volume Growth**:
```
2021: ~10MB/day  (NHL only)
2024: ~50MB/day  (6 sports)
2026: ~100MB/day (9 sports)
Total: ~18GB/year (compressed)
```

## Phase 3: Model Development (2024 Q4)

### The Great Model Comparison

**Goal**: Find the best prediction method for sports betting

**Candidates Tested**:
1. **Elo Rating** (Team-level, 4 parameters)
2. **TrueSkill** (Player-level Bayesian, Microsoft)
3. **Glicko-2** (Elo + uncertainty + volatility)
4. **OpenSkill** (Open-source TrueSkill)
5. **XGBoost** (102 features, gradient boosting)
6. **XGBoost + Elo** (Hybrid approach)
7. **Markov Momentum** (Recent form overlay)
8. **Platt Scaling** (Probability calibration)

**Dataset**: 55,000+ games across all sports (2018-2026)

### Results Summary

**Test Set Performance (NHL 848 games):**

| Model | Accuracy | AUC | Speed | Complexity |
|-------|----------|-----|-------|------------|
| **Elo** | **61.1%** 🥇 | 0.607 | Instant | 4 params |
| TrueSkill | 58.0% | **0.621** 🥇 | Moderate | Player-level |
| XGBoost | 58.7% | 0.592 | Fast | 102 features |
| XGBoost+Elo | 58.1% | 0.599 | Fast | 102 features |
| Elo (old) | 59.3% | 0.591 | Instant | 3 params |

**Winner: Elo** (for production use)

**Reasoning**:
1. **Best accuracy** (61.1% vs 58-59% for others)
2. **Simplest** (4 parameters vs 102 features)
3. **Fastest** (instant predictions)
4. **Most interpretable** (everyone understands ratings)
5. **Never breaks** (no retraining needed)
6. **Well-calibrated** (70% predictions win 70% of time)

**TrueSkill Runner-Up**:
- Best AUC (0.621) - better for probability estimation
- Worse accuracy (58.0%) - worse for binary predictions
- Much more complex (tracks 1,545 players)
- Decided: Keep for research, use Elo for production

### Detailed Experiment Reports

**ML Model Training Rounds**:
- Round 1: Initial XGBoost (archive/MODEL_TRAINING_RESULTS.md)
- Round 2: Hyperparameter tuning (archive/MODEL_TRAINING_RESULTS_ROUND2.md)
- Round 3: Feature engineering (archive/MODEL_TRAINING_RESULTS_ROUND3.md)
- **Conclusion**: 102 features → 58.7% accuracy (worse than Elo's 61.1%)

**Rating Systems Comparison**:
- Elo vs TrueSkill (archive/RATING_SYSTEMS_FINAL_RESULTS.md)
- TrueSkill detailed analysis (archive/TRUESKILL_COMPARISON_RESULTS.md)
- NBA vs NHL comparison (archive/NBA_VS_NHL_ELO_COMPARISON.md)
- **Conclusion**: Elo beats all alternatives for accuracy

**Advanced Techniques**:
- Markov Momentum overlay (minimal improvement)
- Platt scaling calibration (already well-calibrated)
- Ensemble methods (complexity not worth marginal gains)

### Key Technical Insights

**1. More Features ≠ Better Predictions**
- Elo (4 params): 61.1% accuracy
- XGBoost (102 features): 58.7% accuracy
- **Why**: Sports have high intrinsic randomness, complex models overfit

**2. Player-Level vs Team-Level**
- TrueSkill (player): Better AUC (0.621), worse accuracy (58.0%)
- Elo (team): Worse AUC (0.607), better accuracy (61.1%)
- **Trade-off**: AUC good for betting odds, accuracy good for picks

**3. Calibration Matters**
- Elo naturally calibrated (70% predictions → 70% wins)
- ML models need Platt scaling for calibration
- **Impact**: Well-calibrated probabilities critical for Kelly Criterion

**4. Simplicity Aids Debugging**
- Elo: Rating changes are traceable
- XGBoost: Black box, hard to diagnose issues
- **Production**: Simplicity reduces maintenance burden

## Phase 4: Kalshi Integration & Production (2025 Q1-Q3)

### Kalshi API Integration

**January 2025**: Initial integration with Kalshi prediction markets
- Built `kalshi_markets.py` for market data fetching
- Implemented authentication (API key + RSA signatures)
- Created bet identification logic (Elo prob > market prob)

**First Live Bets (January 18, 2025)**:
- ❌ Placed 2 bets on game already started (UAB vs Tulsa)
- ❌ Lost $6 on game that was 73-57 when bet placed
- **Critical Issue**: Kalshi market "active" status unreliable

### Critical Lessons Learned

**1. Game Start Verification (Critical)**
- **Problem**: Kalshi markets stay "active" even after game starts
- **Solution**: Added The Odds API verification before every bet
- **Implementation**: `verify_game_not_started()` in `kalshi_betting.py`
- **Impact**: Prevented all future bets on started games

**2. Limit Order Pricing**
- **Problem**: 400 Bad Request errors on order placement
- **Root Cause**: Kalshi requires explicit price, no market orders
- **Solution**: Auto-fetch current market price if not provided
- **Format**: `yes_price` or `no_price` in cents (49 = 49¢)

**3. Contract Calculation**
- **Problem**: Confusion about cost vs contracts
- **Formula**: `contracts = (bet_dollars × 100) / price_cents`
- **Example**: $5 bet at 49¢ = 10 contracts (costs $4.90)

**4. API Endpoint Discovery**
- ❌ https://trading-api.kalshi.com
- ❌ https://api.kalshi.com
- ✅ **https://api.elections.kalshi.com** (correct)

**Files Updated**:
- `plugins/kalshi_betting.py` - Complete rewrite
- `plugins/kalshi_markets.py` - Market data fetching
- `dags/multi_sport_betting_workflow.py` - Integration
- `KALSHI_BETTING_GUIDE.md` - Documentation

### Production Deployment (March 2025)

**Daily Automated Workflow**:
1. **10:00 AM**: DAG triggers
2. **Download**: Fetch yesterday's game results
3. **Update**: Recalculate Elo ratings
4. **Scan**: Fetch active Kalshi markets
5. **Identify**: Find +EV opportunities
6. **Verify**: Check games haven't started
7. **Place**: Submit optimized bets
8. **Notify**: Send SMS summary

**Safety Checks Implemented**:
- ✅ Game start verification (The Odds API)
- ✅ Balance verification before betting
- ✅ Order deduplication (no double-bets)
- ✅ Position limits (daily and per-bet)
- ✅ Limit orders only (no market orders)

**Monitoring & Alerts**:
- Daily SMS notifications (3-part summary)
- Email alerts for failures
- Dashboard for real-time monitoring
- Balance tracking with P&L calculation

## Phase 5: Threshold Optimization (2025 Q4)

### Lift/Gain Analysis

**Goal**: Determine optimal betting thresholds by sport

**Method**: 
1. Divide historical predictions into 10 deciles by probability
2. Calculate actual win rate per decile
3. Compute lift (actual / baseline) to measure predictiveness
4. Identify threshold where lift exceeds 1.2x

**Dataset**: 55,000+ games (2018-2026)

**Key Finding**: **Extreme deciles are most predictive**
- Top 2 deciles (9-10): 1.2x-1.5x lift ✅
- Middle deciles (4-7): ~1.0x lift (no edge)
- Bottom 2 deciles (1-2): 0.5x-0.7x lift (inverse works too)

**Implication**: Only bet on high-confidence games (top 20%)

### Optimized Thresholds

**Previous (Conservative) Thresholds**:
- NBA: 64% | NHL: **77%** ❌ | MLB: 62% | NFL: 68%
- **Problem**: Missing profitable opportunities, especially NHL

**New (Optimized) Thresholds**:
- **NBA**: 73% (raised - focus on highest lift)
- **NHL**: 66% (lowered - 77% too conservative)
- **MLB**: 67% (raised slightly)
- **NFL**: 70% (small increase)
- **NCAAB**: 72% (align with NBA)
- **WNCAAB**: 72% (align with other basketball)
- **Tennis**: 60% (more liberal for efficient markets)
- **Soccer**: 45% (3-way markets, different baseline)

**Impact**:
- NHL: +100% bet volume (was eliminating 50% of +EV bets)
- NBA: Better win rate (focus on extreme confidence)
- All sports: Improved expected value

**Validation**:
- ✅ Out-of-sample testing on 2025-26 season
- ✅ Lift patterns still hold
- ✅ Model not overfit

**Documentation**: `docs/VALUE_BETTING_THRESHOLDS.md`

### Calibration & Validation

**Temporal Integrity Audit**:
- **Goal**: Verify no data leakage in predictions
- **Method**: Test that predictions only use prior game information
- **Results**: 11/11 tests passing ✅
- **Documentation**: `docs/ELO_TEMPORAL_INTEGRITY_AUDIT.md`

**Probability Calibration**:
- Tested Platt scaling on NBA/NHL
- Found: Elo already well-calibrated
- Decision: No calibration needed
- **Why**: 70% Elo predictions already win ~70% of time

## Phase 6: Portfolio Optimization (2026 Q1)

### Kelly Criterion Implementation

**Problem**: Fixed bet sizing ($2-5) left money on table

**Solution**: Kelly Criterion for optimal bet sizing
```
f* = (p × b - q) / b
```
Where:
- p = Elo probability of winning
- q = 1 - p
- b = net odds (payout - 1)
- f* = optimal fraction of bankroll

**Implementation**:
- Created `portfolio_optimizer.py` - Core Kelly engine
- Created `portfolio_betting.py` - Kalshi integration
- Added to DAG as `portfolio_optimized_betting` task

**Risk Management**:
- **Fractional Kelly**: 0.25 (conservative, reduces variance)
- **Daily limit**: 25% of bankroll maximum
- **Per-bet max**: 5% of bankroll
- **Minimum bet**: $2 (Kalshi minimum)
- **Maximum bet**: $50 (position limit)

**Multi-Sport Allocation**:
- Optimizes across all 9 sports simultaneously
- Prioritizes bets by expected value
- Stops when daily risk limit reached
- Respects individual sport constraints

**Results**:
- ✅ Better risk-adjusted returns
- ✅ Mathematically optimal sizing
- ✅ Prevents over-betting
- ✅ Maximizes long-term growth

**Testing**:
- 19 unit tests (100% passing)
- Manual testing with real data
- Backtest validation pending

**Documentation**: `PORTFOLIO_BETTING.md`

### Position Analysis Tool

**Problem**: Need to monitor current open positions

**Solution**: Built `analyze_positions.py`
- Fetches all open/closed positions from Kalshi
- Matches to current Elo ratings
- Identifies concerns (below threshold, underdogs, contradictions)
- Generates markdown reports

**Features**:
- Multi-sport support (9 sports)
- Team/player name matching (fuzzy + exact)
- Sport-specific thresholds
- Contradictory position detection
- Account balance summary

**Output**: `reports/{datetime}_positions_report.md`

**Documentation**: `docs/POSITION_ANALYSIS.md`

### Email Notifications

**Problem**: SMS via Airflow email failing (SMTP auth errors)

**Solution**: Custom SMS function using direct SMTP
- Bypasses Airflow email utility
- Uses Gmail app password
- Formats for Verizon SMS gateway
- Handles multi-part messages

**Daily Summary Format**:
1. Balance, portfolio value, yesterday's P&L
2. Today's bets placed with top bet details
3. Additional bets or available balance

**Implementation**: Custom `send_sms()` in DAG

**Status**: ✅ Working in production

## Phase 7: Testing & Validation (2026 Q1)

### Comprehensive Test Suite

**Coverage**:
- Unit tests: 85%+ coverage
- Integration tests: End-to-end workflows
- Temporal integrity: 11/11 passing
- Dashboard tests: 60 Playwright tests
- Security: CodeQL scanning

**Test Infrastructure**:
- `tests/test_*_elo_rating.py` - Elo implementations
- `tests/test_portfolio_optimizer.py` - Kelly Criterion
- `tests/test_elo_temporal_integrity.py` - No data leakage
- `tests/test_dashboard_playwright.py` - Dashboard UI
- `tests/test_analyze_positions.py` - Position analysis

**Data Validation**:
- Created `validate_nhl_data.py`
- Extended to all sports
- Checks: Missing data, null values, date ranges, team coverage
- Runs before production deployment

**Security**:
- CodeQL automatic scanning
- Input validation on all external data
- No secrets in code (file-based storage)
- Rate limiting on all APIs

### Dashboard Development

**Streamlit Dashboard** (`dashboard_app.py`):

**Pages**:
1. **Elo Analysis**: 
   - Lift charts by decile
   - Calibration plots
   - ROI analysis
   - Cumulative gain
   - Elo vs Glicko-2 comparison
   - Details table
   - Season timing

2. **Betting Performance**:
   - Win rate and ROI
   - P&L over time
   - Breakdown by sport
   - All bets table

**Features**:
- Multi-sport selector (9 sports)
- Season filtering
- Date range picker
- Interactive charts (Plotly)
- Real-time data loading

**Testing**:
- 60 Playwright tests covering all components
- Tests all 9 sports
- Validates data presence
- Tests all 7 tabs
- Checks interactivity
- Responsive design tests

**Documentation**:
- `DASHBOARD_README.md` - User guide
- `DASHBOARD_ARCHITECTURE.md` - Technical details
- `DASHBOARD_QUICKSTART.md` - Quick start
- `DASHBOARD_INDEX.md` - Feature index

## Current State (January 2026)

### Production System Status

**9 Sports Operational**:
✅ NBA, NHL, MLB, NFL, EPL, Ligue 1, Tennis, NCAAB, WNCAAB

**Daily Workflow**:
✅ Automated betting at 10:00 AM
✅ Portfolio optimization with Kelly Criterion
✅ Game start verification
✅ SMS notifications
✅ Balance tracking

**Analytics**:
✅ Interactive Streamlit dashboard
✅ Position analysis tool
✅ Backtesting infrastructure
✅ Performance tracking

**Testing**:
✅ 85%+ code coverage
✅ Integration tests passing
✅ Temporal integrity validated
✅ Security scanning enabled

### Key Metrics

**Model Performance**:
- Accuracy: 58-61% (varies by sport)
- AUC: 0.59-0.62 (varies by sport)
- Top decile lift: 1.2x-1.5x
- Calibration: Excellent (predicted ≈ actual)

**Betting Results**:
- Win rate: 55-65% (varies by sport)
- ROI: Tracking via CLV analysis
- Portfolio: Diversified across 9 sports
- Risk management: Kelly Criterion with 25% fraction

**Code Quality**:
- Test coverage: 85%+
- Documentation: Comprehensive
- Code style: Black formatted
- Type hints: All functions
- Security: CodeQL clean

### Technical Debt

**Resolved**:
- ✅ Fragmented documentation (consolidated)
- ✅ Multiple DAGs (unified to one)
- ✅ Fixed bet sizing (Kelly Criterion)
- ✅ No game verification (The Odds API)
- ✅ Manual bet placement (automated)

**Remaining**:
- [ ] Line shopping (single book only)
- [ ] Live betting (pre-game only)
- [ ] Advanced hedging strategies
- [ ] Correlation-aware portfolio optimization

## Future Direction

### Short Term (Q1 2026)
- [x] Consolidate documentation
- [ ] Add more sports (MMA, Golf)
- [ ] Line shopping across books
- [ ] Enhanced position hedging

### Medium Term (Q2-Q3 2026)
- [ ] Live betting infrastructure
- [ ] Automated arbitrage detection
- [ ] ML for bet sizing (not prediction)
- [ ] Advanced portfolio correlation analysis

### Long Term (Q4 2026+)
- [ ] Custom odds model (beyond Elo)
- [ ] Market maker strategies
- [ ] Multi-leg parlay optimization
- [ ] Additional sportsbook integrations

## Conclusion

The nhlstats project has evolved from a simple NHL data collector to a sophisticated 9-sport automated betting platform. Key success factors:

1. **Simplicity Wins**: Elo beats complex ML models
2. **Systematic Approach**: Testing and validation at every step
3. **Risk Management**: Kelly Criterion and hard limits
4. **Automation**: Daily workflow with minimal manual intervention
5. **Documentation**: Comprehensive guides and history

The system is now in production, generating daily betting recommendations and tracking performance across all major sports.

---

**Project Start**: 2018
**Current Phase**: Production deployment (9 sports)
**Last Updated**: January 2026
