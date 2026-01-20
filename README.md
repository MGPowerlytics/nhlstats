# Multi-Sport Betting Analytics Platform

A production-grade, AI-powered sports betting system that uses Elo ratings to identify value betting opportunities across 9 sports on Kalshi prediction markets.

## 🎯 What This System Does

This system automatically:
1. **Downloads game data** for 9 sports (NBA, NHL, MLB, NFL, EPL, Ligue 1, Tennis, NCAAB, WNCAAB)
2. **Calculates Elo ratings** for all teams/players
3. **Scans Kalshi markets** for betting opportunities
4. **Identifies +EV bets** where our model probability > market probability
5. **Places optimal bets** using Kelly Criterion portfolio optimization
6. **Tracks performance** with comprehensive analytics dashboard

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.10+
- Kalshi API credentials (`kalshkey` file)
- The Odds API key (`odds_api_key` file)

### Running the System

**1. Start Airflow (Daily Automated Betting)**
```bash
docker-compose up -d
# Access Airflow UI at http://localhost:8080
# DAG runs daily at 10:00 AM
```

**2. Run Dashboard (Analytics & Monitoring)**
```bash
pip install -r requirements_dashboard.txt
streamlit run dashboard_app.py
# Access at http://localhost:8501
```

**3. Manual Operations**
```bash
# Backfill historical data
python backfill_nhl_current_season.py

# Analyze betting performance
python analyze_bets.py

# Check portfolio positions
python analyze_positions.py

# Validate data quality
python validate_nhl_data.py
```

## 📊 Current Performance

**Best Sports by Win Rate:**
- **NFL**: 70% threshold, strong discrimination
- **NBA**: 73% threshold, high-confidence predictions
- **NHL**: 66% threshold, balanced approach
- **Baseball/Basketball**: 67-72% thresholds

**Validation Results (55,000+ historical games):**
- Top decile predictions: **1.2x-1.5x lift** over baseline
- Model calibration: Predicted probabilities match actual outcomes
- Out-of-sample validation: Positive performance on 2025-26 season

See [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md) for detailed experiment results.

## 🏗️ Architecture

```
nhlstats/
├── dags/                          # Airflow orchestration
│   └── multi_sport_betting_workflow.py  # Main daily DAG
├── plugins/                       # Core Python modules
│   ├── *_elo_rating.py           # Elo implementations (9 sports)
│   ├── *_games.py                # Data downloaders
│   ├── kalshi_markets.py         # Kalshi API integration
│   ├── portfolio_optimizer.py    # Kelly Criterion bet sizing
│   └── portfolio_betting.py      # Automated bet placement
├── data/                          # Local data storage
│   ├── nhlstats.duckdb           # DuckDB analytics database
│   ├── *_current_elo_ratings.csv # Current ratings by sport
│   └── */bets_*.json             # Daily bet recommendations
├── dashboard_app.py               # Streamlit analytics dashboard
├── tests/                         # Comprehensive test suite
└── docs/                          # Documentation
```

### Supported Sports

| Sport | Data Source | Elo System | Markets | Status |
|-------|-------------|------------|---------|--------|
| NBA | NBA API | Team Elo | Kalshi KXNBAGAME | ✅ Production |
| NHL | NHL API | Team Elo | Kalshi KXNHLGAME | ✅ Production |
| MLB | MLB API | Team Elo | Kalshi KXMLBGAME | ✅ Production |
| NFL | ESPN API | Team Elo | Kalshi KXNFLGAME | ✅ Production |
| NCAAB | Massey Ratings | Team Elo | Kalshi KXNCAAMBGAME | ✅ Production |
| WNCAAB | Massey Ratings | Team Elo | Kalshi KXNCAAWBGAME | ✅ Production |
| Tennis | tennis-data.co.uk | Player Elo | Kalshi Tennis | ✅ Production |
| EPL | football-data.co.uk | Team Elo (3-way) | Kalshi Soccer | ✅ Production |
| Ligue 1 | football-data.co.uk | Team Elo (3-way) | Kalshi Soccer | ✅ Production |

## 🧠 How It Works

### 1. Elo Rating System

Each sport uses customized Elo parameters:
- **K-factor**: Controls rating volatility (typically 20)
- **Home Advantage**: Points added to home team (50-100)
- **Reversion**: Season-based mean reversion for college sports

**Probability Formula:**
```
P(home win) = 1 / (1 + 10^((away_elo - home_elo - home_adv) / 400))
```

### 2. Value Identification

A bet is recommended when:
1. **High Confidence**: `elo_prob > sport_threshold` (60-73% depending on sport)
2. **Positive Edge**: `elo_prob - market_prob > 0.05` (minimum 5% edge)

### 3. Portfolio Optimization

Uses **Kelly Criterion** for optimal bet sizing:
```
f* = (p × b - q) / b
```
Where:
- `p` = Elo probability of winning
- `q` = 1 - p
- `b` = net odds (payout - 1)
- `f*` = fraction of bankroll to bet

**Risk Management:**
- Daily limit: 25% of bankroll
- Per-bet max: 5% of bankroll
- Fractional Kelly: 0.25 (conservative sizing)
- Bets prioritized by expected value

### 4. Validation & Safety

**Pre-Bet Checks:**
- ✅ Game hasn't started (verified via The Odds API)
- ✅ Sufficient balance available
- ✅ No duplicate positions on same market
- ✅ Bet size within limits

**Post-Bet Tracking:**
- Balance snapshots saved daily
- Closing Line Value (CLV) tracked
- Performance analytics by sport/date
- Position reports generated

## 📈 Key Features

### Automated Betting Workflow (Airflow DAG)
- Runs daily at 10:00 AM
- Downloads yesterday's game results
- Updates Elo ratings
- Scans Kalshi for opportunities
- Places optimized bets
- Sends SMS notifications with results

### Interactive Dashboard (Streamlit)
- **Elo Analysis**: Lift charts, calibration plots, ROI by decile
- **Betting Performance**: Win rate, ROI, P&L by sport
- **Position Monitoring**: Current open positions with Elo analysis
- **Season Comparison**: Early vs late season performance
- **Glicko-2 Comparison**: Alternative rating system benchmarks

### Portfolio Management
- **Kelly Criterion** optimal bet sizing
- **Risk limits** (daily and per-bet)
- **Multi-sport allocation** across 9 sports simultaneously
- **Expected value** tracking and prioritization
- **Position analysis** tool to review current bets

### Data Quality & Testing
- **Data validation**: Automated checks for missing/incorrect data
- **Unit tests**: 85%+ code coverage
- **Integration tests**: End-to-end workflow validation
- **Temporal integrity**: Tests ensure no data leakage
- **CodeQL security**: Automated vulnerability scanning

## 📚 Documentation

### User Guides
- **[Quick Start Guide](DASHBOARD_QUICKSTART.md)** - Get started in 5 minutes
- **[Dashboard Guide](DASHBOARD_README.md)** - Using the analytics dashboard
- **[Kalshi Betting Guide](KALSHI_BETTING_GUIDE.md)** - API integration and betting
- **[Portfolio Betting](PORTFOLIO_BETTING.md)** - Kelly Criterion implementation
- **[Position Analysis](docs/POSITION_ANALYSIS.md)** - Reviewing open positions

### Technical Documentation
- **[Project History](docs/HISTORY.md)** - Evolution from single sport to 9 sports
- **[Experiment Results](docs/EXPERIMENTS.md)** - What worked and what didn't
- **[Backtesting Reports](docs/BACKTESTING.md)** - Historical performance analysis
- **[System Architecture](DASHBOARD_ARCHITECTURE.md)** - Technical deep dive
- **[Value Betting Strategy](docs/VALUE_BETTING_THRESHOLDS.md)** - Threshold optimization

### Development
- **[CHANGELOG.md](CHANGELOG.md)** - Detailed change history
- **[Testing Guide](FINAL_TEST_REPORT.md)** - Running the test suite
- **[Contributing](#)** - Code conventions and workflow

## 🔬 Why Elo? (Spoiler: It Beats Everything)

After extensive experimentation with various prediction methods, **simple Elo ratings emerged as the clear winner**:

### Methods Tested
- ✅ **Elo**: 61% accuracy, 0.607 AUC
- ❌ TrueSkill (player-level): 58% accuracy, 0.621 AUC (better AUC, worse accuracy)
- ❌ XGBoost (102 features): 58.7% accuracy, 0.592 AUC
- ❌ XGBoost + Elo features: 58.1% accuracy, 0.599 AUC
- ❌ Glicko-2: Implementation incomplete
- ❌ Markov Momentum: Marginal improvement, added complexity

### Key Findings
1. **Simplicity wins**: Elo's 4 parameters beat XGBoost's 102 features
2. **Speed matters**: Elo is instant, ML models are slower
3. **Interpretability**: Everyone understands "rating of 1700"
4. **Maintenance**: Elo never breaks, ML models need retraining
5. **Calibration**: Elo probabilities match actual outcomes

**Verdict**: Use Elo for production. Keep TrueSkill for player-level insights.

See [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md) for full comparison.

## 🎓 Lessons Learned

### What Worked ✅
1. **Elo over ML**: Simple beats complex for sports prediction
2. **Sport-specific thresholds**: Hockey ≠ basketball in predictability
3. **Kelly Criterion**: Mathematical bet sizing beats fixed amounts
4. **Portfolio approach**: Optimize across all sports, not individually
5. **Extreme deciles**: Only bet high-confidence games (top 20%)
6. **Temporal validation**: Always test on future data, not past

### What Didn't Work ❌
1. **ML models**: 102 features underperformed 4 parameters
2. **TrueSkill for accuracy**: Better AUC but worse win rate
3. **Fixed bet sizing**: Left money on the table
4. **Conservative thresholds**: 77% NHL threshold was too high
5. **Single-sport optimization**: Missed portfolio diversification benefits
6. **Trusting market status**: Games can be "active" but already started

### Critical Safety Fixes 🚨
- **Game start verification**: Always check The Odds API, not just Kalshi status
- **Order deduplication**: Prevent double-betting same ticker
- **Limit orders**: Never use market orders on Kalshi
- **Balance checks**: Verify funds before placing bets
- **Position limits**: Daily and per-bet caps prevent over-exposure

See [KALSHI_LESSONS_LEARNED.md](KALSHI_LESSONS_LEARNED.md) for details.

## 📊 Data & Analytics

### DuckDB Database
Central analytics warehouse (`data/nhlstats.duckdb`):
- Historical game results (2018-2026)
- Elo rating time series
- Bet tracking (placed_bets table)
- Kalshi market history
- Trade price data

### Analytics Tools
- `analyze_bets.py` - Betting performance breakdown
- `analyze_positions.py` - Current portfolio review
- `analyze_season_timing.py` - Early vs late season comparison
- `backtest_*.py` - Historical performance validation
- `optimize_betting_thresholds.py` - Threshold tuning

## 🛠️ Development

### Setup Development Environment
```bash
# Clone repository
git clone https://github.com/MGPowerlytics/nhlstats.git
cd nhlstats

# Install dependencies
pip install -r requirements.txt
pip install -r requirements_dashboard.txt

# Run tests
pytest tests/ -v --cov=plugins --cov=dags

# Start local Airflow
docker-compose up -d

# Run linting
black plugins/ dags/ tests/
```

### Code Conventions
1. **Black** for code formatting
2. **Type hints** for all functions
3. **Google-style docstrings**
4. **85%+ test coverage**
5. **No manual DAG runs** - let Airflow schedule
6. **Tests before commits**
7. **Update CHANGELOG.md**

### Testing
```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_nhl_elo_rating.py -v

# Run with coverage
pytest tests/ --cov=plugins --cov-report=html

# Run integration tests
pytest tests/test_multi_sport_workflow.py -v
```

## 🔐 Security

- **API keys**: Stored in files (`kalshkey`, `odds_api_key`), never committed
- **CodeQL scanning**: Automated vulnerability detection
- **Input validation**: All external data validated before use
- **Rate limiting**: Respects API terms of service
- **Error handling**: Graceful failure, never exposes sensitive data

## 📞 Monitoring & Alerts

### Daily SMS Notifications
3-part SMS sent at end of DAG:
1. Balance, portfolio value, yesterday's P&L
2. Today's bets placed with details
3. Additional bets or available balance

### Email Alerts
- Task failures (Airflow default)
- Critical errors (game verification failures)
- Daily summary reports

### Dashboard Monitoring
- Real-time balance and portfolio value
- Open positions with Elo analysis
- Win rate and ROI by sport
- Recent bet history

## 🎯 Roadmap

### Short Term
- [ ] Add more sports (MMA, Golf)
- [ ] Line shopping across multiple books
- [ ] Live betting with real-time updates
- [ ] Improved tennis Elo with surface effects

### Medium Term
- [ ] Machine learning for bet sizing (not prediction)
- [ ] Automated arbitrage detection
- [ ] Position hedging strategies
- [ ] Advanced portfolio optimization (correlation-aware)

### Long Term
- [ ] Custom odds model (improve on Elo)
- [ ] Market maker strategies
- [ ] Multi-leg parlay optimization
- [ ] Integration with additional sportsbooks

## 🤝 Contributing

This is a personal project, but suggestions welcome! Please:
1. Open an issue to discuss major changes
2. Follow existing code conventions
3. Add tests for new features
4. Update documentation
5. Run `black` before committing

## 📄 License

Private project - All rights reserved.

## 🙏 Acknowledgments

Built on the shoulders of giants:
- **Bill Benter**: Horse racing modeling pioneer
- **Nate Silver**: FiveThirtyEight Elo implementations
- **Haim Bodek**: Market structure insights
- **Ed Thorp**: Kelly Criterion application to gambling
- **Kalshi**: Prediction market platform

## 📧 Contact

**MGPowerlytics**
- GitHub: [@MGPowerlytics](https://github.com/MGPowerlytics)
- Repository: [nhlstats](https://github.com/MGPowerlytics/nhlstats)

---

**Status**: 🟢 Production (9 sports, daily automated betting)

**Last Updated**: January 2026
