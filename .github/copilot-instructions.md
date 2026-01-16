# Copilot Instructions for Multi-Sport Data Pipeline

This repository is a data engineering project orchestrating sports data collection (NHL & Hong Kong Racing) using Apache Airflow and Python.

## 🏗 Architecture & Core Patterns

- **Orchestration**: Apache Airflow drives all data collection. DAGs are located in `dags/`.
- **Component Structure**:
    - **DAGs**: `dags/*.py` define the schedule and dependencies.
    - **Core Logic**: Root-level scripts (`nhl_game_events.py`, `hk_racing_scraper.py`) contain the actual business logic for API calls and scraping.
    - **Plugins**: `plugins/` folder contains potential extensions for other sports.
- **Data Storage**:
    - Raw data is stored locally in `data/`.
    - Directory structure is strict: `data/{sport}/{category}/`.
    - **Future**: Migration to DuckDB (`data/nhlstats.duckdb`).
- **Imports**: Airflow DAGs import root-level modules. Note the convention of using `sys.path.insert(0, str(Path(__file__).parent.parent))` in DAG files to resolve these imports.

## 🛠 Tech Stack & Libraries

- **Language**: Python 3.x
- **Core Libraries**:
    - `apache-airflow`: Scheduling and orchestration.
    - `requests`: REST API interaction (NHL).
    - `beautifulsoup4` (`bs4`) & `lxml`: HTML parsing (HK Racing).
    - `pandas`: Data manipulation.
    - `pathlib`: ALL file path operations.

## 🚀 Key Workflows & Commands

### 1. Airflow Setup
The project runs on a local Airflow instance.
```bash
export AIRFLOW_HOME=~/airflow
airflow db init
airflow webserver -p 8080
airflow scheduler
```

### 2. Running & Testing
- **Standalone Scripts**: Core modules like `hk_racing_scraper.py` often have `if __name__ == "__main__":` blocks for direct testing without Airflow.
- **Backfilling**: Prefer standard Airflow backfill commands over custom loops.

## 📏 Code Standards & Conventions

- **Path Handling**: **ALWAYS** use `pathlib.Path` for file system operations. Avoid `os.path`.
- **Data Validation**:
    - For APIs: Check HTTP status codes before parsing JSON.
    - For Scraping: Validate HTML structure (e.g., table existence) before extraction.
- **Scraper Etiquette**: Include `User-Agent` headers in all requests (`hk_racing_scraper.py` exemplifies this).
- **Date Handling**: Use standard `datetime` objects. Be mindful of Season logic (e.g., NHL season spans two years).

## ⚠️ Gotchas

- **Import Path**: If creating a new DAG, ensure the `sys.path` modification is present at the top to allow importing root modules.
- **NHL Season Logic**: The NHL API often requires specific season IDs (e.g., "20232024"). Check `nhl_game_events.py` for helper methods.
