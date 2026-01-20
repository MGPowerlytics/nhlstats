# Documentation Index - User & Developer Guides

This index organizes all documentation for easy navigation. Start here to find what you need.

## 🚀 Getting Started

**New to the project?** Start here:

1. **[README.md](../README.md)** - Project overview, quick start, architecture
2. **[DASHBOARD_QUICKSTART.md](dashboard/DASHBOARD_QUICKSTART.md)** - Get the dashboard running in 5 minutes
3. **[SYSTEM_OVERVIEW.md](../SYSTEM_OVERVIEW.md)** - High-level system description

## 📖 Core Documentation

### Project Understanding
- **[Project History](HISTORY.md)** - Evolution from single sport to 9-sport platform
- **[Experiment Results](EXPERIMENTS.md)** - What we tested and why Elo won
- **[Backtesting Results](BACKTESTING.md)** - Historical performance validation
- **[CHANGELOG.md](../CHANGELOG.md)** - Detailed change history (very long!)

### System Architecture
- **[DASHBOARD_ARCHITECTURE.md](dashboard/DASHBOARD_ARCHITECTURE.md)** - Technical deep dive on dashboard
- **[SYSTEM_OVERVIEW.md](../SYSTEM_OVERVIEW.md)** - Platform components and structure

## 🎯 User Guides

### Operating the System

**Daily Operations:**
- **[Kalshi Betting Guide](../KALSHI_BETTING_GUIDE.md)** - Using Kalshi API for betting
- **[Kalshi Lessons Learned](../KALSHI_LESSONS_LEARNED.md)** - Critical safety lessons
- **[Portfolio Betting Guide](../PORTFOLIO_BETTING.md)** - Kelly Criterion implementation

**Monitoring & Analysis:**
- **[Dashboard User Guide](dashboard/DASHBOARD_README.md)** - Using the Streamlit dashboard
- **[Position Analysis Guide](POSITION_ANALYSIS.md)** - Reviewing open positions
- **[Bet Tracking Guide](BET_TRACKING.md)** - Understanding bet tracking database

### Analytics & Optimization

**Performance Analysis:**
- **[Value Betting Thresholds](VALUE_BETTING_THRESHOLDS.md)** - Threshold optimization explained
- **[Value Betting Complete Guide](VALUE_BETTING_COMPLETE.md)** - Full value betting strategy
- **[AUC vs Accuracy Explained](AUC_VS_ACCURACY_EXPLAINED.md)** - Understanding metrics
- **[CLV Tracking Guide](CLV_TRACKING_GUIDE.md)** - Closing line value analysis

**System Validation:**
- **[Temporal Integrity Audit](ELO_TEMPORAL_INTEGRITY_AUDIT.md)** - Data leakage prevention
- **[Data Leakage Prevention](DATA_LEAKAGE_PREVENTION.md)** - Best practices

## 🛠️ Developer Guides

### Development Setup

**Getting Started:**
- **[README.md](../README.md)** - Installation and setup
- **Testing Guide** - See [Test Reports](#test-reports) below

**Code Structure:**
- **[Multi-Sport Plugins](multi_sport_plugins.md)** - Plugin architecture
- **[NHL Prediction Features](nhl_prediction_features.md)** - Feature engineering

### Testing & Validation

**Test Reports:**
- **[Testing Documentation](testing/README.md)** - All testing documentation
- **[Final Test Report](testing/FINAL_TEST_REPORT.md)** - Comprehensive test results
- **[Completed Test Fixes](../archive/completed_implementations/)** - Historical test fixes

**Data Quality:**
- **[NHL Data Validation Report](testing/NHL_DATA_VALIDATION_REPORT.md)** - Data quality checks
- **[Completed Data Fixes](../archive/completed_implementations/)** - Historical bug fixes

### Implementation Summaries

**Recent Features:**
- **[Completed Implementations](../archive/completed_implementations/)** - All implementation summaries
  - Tennis betting system
  - WNCAAB (Women's basketball)
  - Ligue 1 (French soccer)
  - Email/SMS notifications
  - And more...

## 🔬 Research & Experiments

### Model Comparisons

**Rating Systems:**
- **[Experiments Overview](EXPERIMENTS.md)** - Complete experiment summary
- **[Archived Comparisons](../archive/backtest_reports/)** - Historical comparison reports
  - NHL System Comparison
  - NHL ELO Tuning Results
  - And more...

**Archived Experiments:**
See [Archive Documentation](#archive-documentation) below.

### Performance Analysis

**Backtesting:**
- **[Backtesting Results](BACKTESTING.md)** - Consolidated backtest reports
- **[Historical Backtests](../archive/backtest_reports/)** - Individual sport reports
  - Betting Backtest Summary
  - Multi-League Backtest
  - NCAAB Backtest Summary
  - NHL System Comparison
- **[Basketball Kalshi Backtest Status](BASKETBALL_KALSHI_BACKTEST_STATUS.md)** - Ongoing work

**Threshold Optimization:**
- **[Value Betting Thresholds](VALUE_BETTING_THRESHOLDS.md)** - Lift/gain analysis
- **[Threshold Optimization Report](THRESHOLD_OPTIMIZATION_20260119_195406.md)** - Detailed results

## 📊 Operational Reports

### System Status

**Current State:**
- **[README.md](../README.md)** - Complete system status
- **[Dashboard Documentation](dashboard/README.md)** - Dashboard features and guides
- **[Completed Work](../archive/completed_implementations/)** - Historical milestones
  - Email Setup Complete
  - Job Complete summaries
  - Fixes Applied reports

## 🗃️ Archive Documentation

Legacy documentation (historical reference only):

### Early Project Documents
- **[archive/README.md](../archive/README.md)** - Original project README
- **[archive/README_AIRFLOW.md](../archive/README_AIRFLOW.md)** - Airflow setup (old)
- **[archive/README_NHL.md](../archive/README_NHL.md)** - NHL-specific docs (old)
- **[archive/PROJECT_SUMMARY.md](../archive/PROJECT_SUMMARY.md)** - Early project state

### ML Model Training
- **[archive/MODEL_TRAINING_RESULTS.md](../archive/MODEL_TRAINING_RESULTS.md)** - Round 1
- **[archive/MODEL_TRAINING_RESULTS_ROUND2.md](../archive/MODEL_TRAINING_RESULTS_ROUND2.md)** - Round 2
- **[archive/MODEL_TRAINING_RESULTS_ROUND3.md](../archive/MODEL_TRAINING_RESULTS_ROUND3.md)** - Round 3
- **[archive/XGBOOST_WITH_ELO_RESULTS.md](../archive/XGBOOST_WITH_ELO_RESULTS.md)** - Hybrid model

### Rating System Comparisons
- **[archive/ALL_MODELS_COMPARISON.md](../archive/ALL_MODELS_COMPARISON.md)** - Complete comparison
- **[archive/RATING_SYSTEMS_FINAL_RESULTS.md](../archive/RATING_SYSTEMS_FINAL_RESULTS.md)** - Final verdict
- **[archive/TRUESKILL_COMPARISON_RESULTS.md](../archive/TRUESKILL_COMPARISON_RESULTS.md)** - TrueSkill analysis
- **[archive/NBA_VS_NHL_ELO_COMPARISON.md](../archive/NBA_VS_NHL_ELO_COMPARISON.md)** - Cross-sport

### Analysis Reports
- **[archive/LIFT_GAIN_ANALYSIS.md](../archive/LIFT_GAIN_ANALYSIS.md)** - Original lift/gain
- **[archive/NBA_NHL_LIFT_GAIN_ANALYSIS.md](../archive/NBA_NHL_LIFT_GAIN_ANALYSIS.md)** - Cross-sport lift

### Infrastructure
- **[archive/NORMALIZATION_PLAN.md](../archive/NORMALIZATION_PLAN.md)** - Database schema
- **[archive/HK_RACING_SCHEMA.md](../archive/HK_RACING_SCHEMA.md)** - Horse racing (abandoned)
- **[archive/BETTING_WORKFLOW_DAGS.md](../archive/BETTING_WORKFLOW_DAGS.md)** - Old DAG structure
- **[archive/DUCKDB_MULTI_SESSION_GUIDE.md](../archive/DUCKDB_MULTI_SESSION_GUIDE.md)** - Database guide

### External Data (Abandoned)
- **[archive/EXTERNAL_DATA_INTEGRATION_PLAN.md](../archive/EXTERNAL_DATA_INTEGRATION_PLAN.md)**
- **[archive/EXTERNAL_DATA_STATUS.md](../archive/EXTERNAL_DATA_STATUS.md)**
- **[archive/ML_TRAINING_DATASET.md](../archive/ML_TRAINING_DATASET.md)**

### Old Task Lists
- **[archive/NHL_FEATURES_TASKLIST.md](../archive/NHL_FEATURES_TASKLIST.md)**
- **[archive/SCHEDULE_FEATURES_IMPLEMENTATION.md](../archive/SCHEDULE_FEATURES_IMPLEMENTATION.md)**

## 🔍 Finding What You Need

### By Topic

**Betting Operations:**
- Setup: [Kalshi Betting Guide](../KALSHI_BETTING_GUIDE.md)
- Safety: [Kalshi Lessons Learned](../KALSHI_LESSONS_LEARNED.md)
- Strategy: [Portfolio Betting Guide](../PORTFOLIO_BETTING.md)
- Thresholds: [Value Betting Thresholds](VALUE_BETTING_THRESHOLDS.md)

**Analytics:**
- Dashboard: [Dashboard User Guide](dashboard/DASHBOARD_README.md)
- Positions: [Position Analysis Guide](POSITION_ANALYSIS.md)
- Performance: [Backtesting Results](BACKTESTING.md)
- Metrics: [AUC vs Accuracy](AUC_VS_ACCURACY_EXPLAINED.md)

**Development:**
- Setup: [README.md](../README.md)
- Architecture: [Dashboard Architecture](dashboard/DASHBOARD_ARCHITECTURE.md)
- Testing: [Testing Documentation](testing/README.md)
- History: [Project History](HISTORY.md)

**Research:**
- Experiments: [Experiment Results](EXPERIMENTS.md)
- Comparisons: [NHL System Comparison](../NHL_SYSTEM_COMPARISON_SUMMARY.md)
- Validation: [Temporal Integrity Audit](ELO_TEMPORAL_INTEGRITY_AUDIT.md)

### By Sport

**All Sports:**
- [Experiments Overview](EXPERIMENTS.md) - Cross-sport model comparisons
- [Backtesting Results](BACKTESTING.md) - Performance by sport
- [Project History](HISTORY.md) - Sport-by-sport implementation timeline

**Sport-Specific Archives:**
- [NHL Reports](../archive/backtest_reports/) - System comparison, tuning, validation
- [Basketball Reports](../archive/backtest_reports/) - NBA, NCAAB backtests
- [Implementation Summaries](../archive/completed_implementations/) - Tennis, WNCAAB, Ligue 1

## 📝 External Resources

### Betting Theory
- **[Bill Benter Model](bill_benter_model.md)** - Horse racing modeling pioneer
- **[Real World Betting Examples](real_world_betting_examples.md)** - Case studies
- **[Ethereum Smart Contract Betting](ethereum_smart_contract_betting.md)** - Blockchain betting

### Data Sources
- **[Historical Odds Sources](historical_odds_sources.md)** - Where to get data
- **[Data Collection Strategy](data_collection_strategy.md)** - Collection approach
- **[Betting APIs Legal Options](betting_apis_legal_options.md)** - API landscape
- **[Betting Odds Integration](BETTING_ODDS_INTEGRATION.md)** - Integration guide

### Advanced Topics
- **[Arbitrage Guide](ARBITRAGE_GUIDE.md)** - Finding arbitrage opportunities
- **[Airflow Pool Setup](AIRFLOW_POOL_SETUP.md)** - Concurrency management

## 🆕 Recent Additions

**January 2026:**
- ✅ [README.md](../README.md) - Comprehensive project overview
- ✅ [Project History](HISTORY.md) - Complete timeline
- ✅ [Experiment Results](EXPERIMENTS.md) - All experiments consolidated
- ✅ [Backtesting Results](BACKTESTING.md) - All backtests consolidated
- ✅ [Documentation Index](GUIDES.md) - This file!

**December 2025:**
- [Portfolio Betting Guide](../PORTFOLIO_BETTING.md)
- [Position Analysis Guide](POSITION_ANALYSIS.md)
- [WNCAAB Implementation](../WNCAAB_IMPLEMENTATION_SUMMARY.md)

## 🔄 Document Status

### Active Documents (Current System)
✅ Used in production or current operations

**Root Directory:**
- README.md - Main documentation
- CHANGELOG.md - Change history
- KALSHI_BETTING_GUIDE.md - Betting guide
- KALSHI_LESSONS_LEARNED.md - Critical lessons
- PORTFOLIO_BETTING.md - Portfolio optimization
- POSITION_ANALYSIS_README.md - Position analysis
- SYSTEM_OVERVIEW.md - System overview

**docs/ Directory:**
- HISTORY.md - Project timeline
- EXPERIMENTS.md - Model comparisons
- BACKTESTING.md - Performance validation
- GUIDES.md - This file
- All other docs/*.md files

**docs/dashboard/ Directory:**
- All dashboard documentation (6 files)

**docs/testing/ Directory:**
- All testing documentation (3 files)

### Archive Directories (Historical)
📦 Historical reference only, not current state

**archive/ Directory:**
- Original archived experiments and docs (23 files)

**archive/completed_implementations/ Directory:**
- Completed feature implementations (15 files)
- Test fixes and bug reports
- Email/notification setup docs

**archive/backtest_reports/ Directory:**
- Individual sport backtest reports (6 files)
- System comparison summaries
- Betting system reviews

### Consolidated Documents
✅ Information from these historical docs is now in consolidated docs:

**Consolidated into README.md:**
- Project overview information
- Quick start guides
- Architecture summaries

**Consolidated into HISTORY.md:**
- Implementation summaries
- Feature additions timeline
- System evolution

**Consolidated into EXPERIMENTS.md:**
- Model training results (rounds 1-3)
- Rating system comparisons
- XGBoost experiments
- TrueSkill analysis

**Consolidated into BACKTESTING.md:**
- Sport-specific backtest reports
- Multi-league summaries
- NHL/NBA/NCAAB results
- System comparison summaries

## 🤝 Contributing to Documentation

When adding new documentation:

1. **Update this index** - Add your document to appropriate section
2. **Follow naming convention** - Use UPPERCASE for major docs, lowercase for guides
3. **Link from README** - Major docs should be linked from main README
4. **Update CHANGELOG** - Note documentation additions
5. **Consider consolidation** - Can this be added to existing doc instead of new file?

---

**Last Updated**: January 2026  
**Total Documents**: 75+ files (35+ active, 20+ archived, 20+ external)  
**Status**: 🟢 Consolidated and organized
