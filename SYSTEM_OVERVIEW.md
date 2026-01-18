# Multi-Sport Betting Analytics Platform

A unified platform for collecting sports data, calculating Elo ratings, simulating betting strategies, and visualizing performance across multiple leagues (NHL, MLB, NFL, NBA, EPL, Tennis).

## 📂 Project Structure

### Core Components
- **`dags/`**: Airflow DAGs for orchestrating daily workflows.
  - `multi_sport_betting_workflow.py`: Main daily DAG for all sports.
- **`plugins/`**: Python modules for data fetching, processing, and Elo calculations.
  - **Data Fetchers:** `*_games.py` (e.g., `nhl_games.py`, `tennis_games.py`)
  - **Elo Logic:** `*_elo_rating.py` (e.g., `mlb_elo_rating.py`)
  - **Market Data:** `kalshi_markets.py` (Integration with Kalshi prediction markets)
  - **Database:** `db_loader.py` (Unified loading into DuckDB)
- **`data/`**: Local storage for downloaded raw data and DuckDB database.
  - `nhlstats.duckdb`: Central data warehouse.
- **`dashboard_app.py`**: Streamlit interactive dashboard for analysis.

### Supported Sports
| Sport | League | Data Source | Elo System |
|-------|--------|-------------|------------|
| Hockey | NHL | NHL API | Team-based |
| Baseball | MLB | MLB API | Team-based |
| Football | NFL | ESPN/NFL | Team-based |
| Basketball| NBA | NBA API | Team-based |
| Soccer | EPL | football-data.co.uk | 3-Way (Win/Draw/Loss) |
| Tennis | ATP/WTA | tennis-data.co.uk | Player-based |

## 🚀 Usage

### 1. Dashboard
Run the interactive analytics dashboard:
```bash
streamlit run dashboard_app.py
```

### 2. Airflow
The DAG `multi_sport_betting_workflow` runs daily at 10:00 AM. It performs:
1. **Download:** Fetches latest game results.
2. **Elo Update:** Recalculates team/player ratings.
3. **Market Scan:** Fetches active markets from Kalshi.
4. **Bet Identification:** Finds +EV bets where Model Prob > Market Prob.

### 3. Utilities
- **Backfill Scripts:**
  - `analyze_season_timing.py`: Compare model accuracy across season stages.
  - `plugins/db_loader.py`: Manually load generic data files.

## 🛠 Setup

**Dependencies:**
```bash
pip install -r requirements.txt
pip install -r requirements_dashboard.txt
```

**Database:**
The system uses DuckDB (`data/nhlstats.duckdb`). No server setup required.

## 📈 Methodology
- **Elo Ratings:** We use customized K-factors and Home Advantage settings per sport.
- **Calibration:** Verified via Brier Score and lift charts in the dashboard.
- **ROI Calculation:** Assumes standard -110 odds unless specific market data is available.

## 📝 Developer Notes
- **Adding a new sport:**
  1. Create `plugins/{sport}_games.py` (Fetcher).
  2. Create `plugins/{sport}_elo_rating.py` (Logic).
  3. Update `plugins/db_loader.py` (Schema).
  4. Register in `dags/multi_sport_betting_workflow.py`.
  5. Add to `dashboard_app.py`.
