# Multi-Sport Betting System

A production-grade, automated sports betting system powered by Airflow, PostgreSQL, and Kelly Criterion portfolio management.

## 📂 Project Structure

- **`dags/`**: Airflow DAGs for automated workflows.
- **`plugins/`**: Core logic (Elo ratings, Market fetching, Betting engines).
- **`scripts/`**: Utility scripts for backfilling, analysis, and ad-hoc tasks.
- **`docs/`**: Detailed system documentation and guides.
- **`reports/`**: Historical analysis, backtest results, and fix logs.
- **`data/`**: Local data storage (JSON/CSV archives).
- **`dashboard_app.py`**: Streamlit dashboard for monitoring performance.

## 🚀 Quick Start

### 1. Betting Strategy
See [docs/BETTING_STRATEGY.md](docs/BETTING_STRATEGY.md) for the core methodology, including:
- Sharp Odds Confirmation (Tennis, NHL, Ligue 1)
- Elo Value Betting (NBA, NFL, MLB)
- Portfolio Management (Quarter Kelly)

### 2. Dashboard
```bash
./run_dashboard.sh
```
See [docs/DASHBOARD_QUICKSTART.md](docs/DASHBOARD_QUICKSTART.md) for more details.

### 3. Airflow Automation
The system runs daily at 5:00 AM ET via the `multi_sport_betting_workflow` DAG.
See [docs/SYSTEM_OVERVIEW.md](docs/SYSTEM_OVERVIEW.md) for architectural details.

## 🛠️ Key Components

- **Unified Database**: PostgreSQL (`unified_games`, `game_odds`, `placed_bets`).
- **Naming Resolver**: `plugins/naming_resolver.py` handles entity resolution across data sources.
- **Odds Comparator**: `plugins/odds_comparator.py` identifies value bets against sharp bookmakers.
- **Kalshi Betting**: `plugins/kalshi_betting.py` handles execution with match-level locking.
