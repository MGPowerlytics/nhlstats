# Multi-Sport Betting System

A production-grade, automated sports betting system powered by Airflow, PostgreSQL, and Kelly Criterion portfolio management.

## 🚀 Getting Started

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/your-org/nhlstats.git
cd nhlstats

# Install dependencies
pip install -r requirements.txt
```

### 2. Run the Dashboard
Visualize model performance and lift/gain analysis.
```bash
./run_dashboard.sh
```
See [**Dashboard Guide**](docs/DASHBOARD_GUIDE.md) for details.

### 3. Run the Automation
The system uses Airflow for daily data ingestion and betting.
```bash
docker compose up -d
```
See [**System Overview**](docs/SYSTEM_OVERVIEW.md) for architecture.

---

## 📚 Documentation

### Core Guides
- [**Betting Strategy**](docs/BETTING_STRATEGY.md): The math behind the money (Elo, Kelly, Sharp Confirmation).
- [**Dashboard Guide**](docs/DASHBOARD_GUIDE.md): How to use the Streamlit interface.
- [**System Overview**](docs/SYSTEM_OVERVIEW.md): Architecture, DAGs, and Data Flow.
- [**Troubleshooting**](docs/TROUBLESHOOTING.md): Fix common issues.

### Integration Guides
- [**Kalshi Betting**](docs/KALSHI_BETTING_GUIDE.md)
- [**BetMGM Integration**](docs/BETMGM_INTEGRATION_GUIDE.md)
- [**Portfolio Management**](docs/PORTFOLIO_BETTING.md)

### Developer Skills & SOPs
*Located in `.github/skills/`*
- [**Adding a New Sport**](.github/skills/adding-new-sport/SKILL.md)
- [**Airflow DAG Patterns**](.github/skills/airflow-dag-patterns/SKILL.md)
- [**Database Operations**](.github/skills/database-operations/SKILL.md)

### Data Flow & Integration (NEW)
- [**DAG Task Data Flow**](docs/DAG_TASK_DATA_FLOW.md): Complete task documentation with data sources/destinations
- [**Data Flow Quick Reference**](docs/DAG_DATA_FLOW_QUICK_REFERENCE.md): Quick guide for monitoring and troubleshooting
- [**Integration Fixes 2026-01-29**](docs/INTEGRATION_FIXES_2026_01_29.md): Summary of critical data consistency fixes
- [**Database Schema**](docs/database_schema.md): Updated with current data flow information
- [**Testing Patterns**](.github/skills/testing-patterns/SKILL.md)

---

## 🏗️ Repository Structure

```plaintext
├── dags/                  # Airflow workflows (DAGs)
├── plugins/               # Core logic (Elo, Betting, API)
├── scripts/               # Utility scripts (Backfills, Analysis)
├── tests/                 # Unit and Integration tests
├── docs/                  # Detailed documentation
├── reports/               # Historical analysis and logs
├── data/                  # Local data storage
└── dashboard_app.py       # Streamlit entry point
```

## 🧪 Testing

Run the full test suite (including documentation integrity):
```bash
pytest
```
See [**Testing Patterns**](.github/skills/testing-patterns/SKILL.md) for more.
```
