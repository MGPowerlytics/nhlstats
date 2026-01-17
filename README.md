# Multi-Sport Data Pipeline

This repository contains Airflow DAGs that automatically download sports data daily for analysis.

## Sports Covered

### 🏒 NHL Hockey
- Game events (shots, goals, hits, penalties)
- Shift data (time on ice)
- Player and team statistics
- **TrueSkill player ratings** ⭐ NEW!
- **Schedule:** Daily at 7:00 AM

### 🏇 Hong Kong Horse Racing
- Race results from Happy Valley and Sha Tin
- Horse performances and placings
- Jockey and trainer statistics
- Dividend/payout data
- **Schedule:** Daily at 7:00 AM

## Project Structure

```
nhlstats/
├── dags/
│   ├── nhl_daily_download.py          # NHL data collection
│   └── hk_racing_daily_download.py    # HK racing data collection
├── nhl_game_events.py                 # NHL API client
├── nhl_shifts.py                      # NHL shifts data
├── nhl_trueskill.py                   # TrueSkill rating system ⭐
├── calculate_trueskill_ratings.py     # Calculate player ratings ⭐
├── query_trueskill_ratings.py         # Query player ratings ⭐
├── hk_racing_scraper.py               # HKJC web scraper
├── data/
│   ├── games/                         # NHL game data
│   ├── shifts/                        # NHL shift data
│   ├── hk_racing/                     # HK racing results
│   └── nhlstats.duckdb                # DuckDB database (future)
├── NORMALIZATION_PLAN.md              # NHL schema design
├── HK_RACING_SCHEMA.md                # Racing schema design
├── README_TRUESKILL.md                # TrueSkill rating system guide ⭐
└── README_AIRFLOW.md                  # Airflow setup guide
```

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. TrueSkill Player Ratings (NEW!)

Calculate skill ratings for all NHL players:

```bash
# Calculate ratings for 2023-24 season
python calculate_trueskill_ratings.py --season 2023

# Or process all available seasons
python calculate_trueskill_ratings.py --all-seasons

# Query top players
python query_trueskill_ratings.py --top 50

# Search for specific player
python query_trueskill_ratings.py --player "McDavid"

# View ratings by position
python query_trueskill_ratings.py --by-position
```

**See [README_TRUESKILL.md](README_TRUESKILL.md) for detailed documentation.**

### 3. Initialize Airflow
```bash
export AIRFLOW_HOME=~/airflow
airflow db init
airflow users create --username admin --password admin --firstname Admin --lastname User --role Admin --email admin@example.com
```

### 4. Configure DAGs
Copy DAGs to Airflow folder or configure `dags_folder` in `airflow.cfg`:
```bash
cp dags/*.py ~/airflow/dags/
```

### 5. Start Airflow
```bash
# Terminal 1: Web server
airflow webserver --port 8080

# Terminal 2: Scheduler
airflow scheduler
```

### 6. Enable DAGs
Go to http://localhost:8080 and toggle on:
- `nhl_daily_download`
- `hk_racing_daily_download`

## Data Collection Details

### NHL Data
- **Source:** Official NHL API (api-web.nhle.com)
- **Frequency:** Daily at 7am
- **Coverage:** All games from previous day
- **Outputs:**
  - `{game_id}_playbyplay.json` - All game events
  - `{game_id}_boxscore.json` - Player statistics
  - `{game_id}_shifts.json/csv` - Shift data

### HK Racing Data
- **Source:** Hong Kong Jockey Club website (racing.hkjc.com)
- **Frequency:** Daily at 7am
- **Coverage:** All races from previous day (Happy Valley & Sha Tin)
- **Outputs:**
  - `{YYYYMMDD}_{VENUE}.json` - Full race card with results

## Future Development

### Phase 1: Data Normalization ✅
- [x] NHL schema design (see NORMALIZATION_PLAN.md)
- [x] HK Racing schema design (see HK_RACING_SCHEMA.md)

### Phase 2: DuckDB Integration (Planned)
- [ ] Implement ETL pipelines
- [ ] Load normalized data to DuckDB
- [ ] Create unified multi-sport database
- [ ] Add data validation and quality checks

### Phase 3: Analysis & Visualization (Planned)
- [ ] Sample analysis queries
- [ ] Performance dashboards
- [ ] Statistical models
- [ ] Predictive analytics

## Manual Testing

### Test NHL Scraper
```bash
python nhl_game_events.py
python nhl_shifts.py
```

### Test HK Racing Scraper
```bash
python hk_racing_scraper.py
```

### Trigger DAG Manually
```bash
# Trigger specific date
airflow dags trigger nhl_daily_download
airflow dags trigger hk_racing_daily_download

# Test specific task
airflow tasks test nhl_daily_download get_games_for_date 2024-11-15
airflow tasks test hk_racing_daily_download scrape_previous_day_races 2026-01-14
```

## Database Schema

Both sports will be normalized into DuckDB for efficient querying:

### NHL Tables
- `games`, `teams`, `players`
- `game_events`, `shots`, `shifts`
- `player_game_stats`, `goalie_game_stats`
- `player_trueskill_ratings`, `player_trueskill_history` ⭐ NEW!

### Racing Tables
- `race_meetings`, `races`
- `horses`, `jockeys`, `trainers`
- `race_results`, `sectional_times`, `dividends`

See detailed schemas in:
- [NORMALIZATION_PLAN.md](NORMALIZATION_PLAN.md) - NHL schema
- [README_TRUESKILL.md](README_TRUESKILL.md) - TrueSkill rating system ⭐
- [HK_RACING_SCHEMA.md](HK_RACING_SCHEMA.md) - Racing schema

## Configuration

### Change Schedule
Edit `schedule_interval` in the DAG files:
```python
schedule_interval='0 7 * * *',  # Daily at 7am
```

### Change Data Directories
```python
# NHL
fetcher = NHLGameEvents(output_dir="data/games")

# Racing
scraper = HKJCRacingScraper(output_dir="data/hk_racing")
```

## Contributing

To add a new sport:
1. Create a data fetcher/scraper (e.g., `{sport}_scraper.py`)
2. Create an Airflow DAG in `dags/`
3. Design normalized schema (create `{SPORT}_SCHEMA.md`)
4. Update this README

## Notes

- DAGs download data from the **previous day**
- `catchup=False` prevents backfilling
- Racing scraper checks both HK venues (some days have no races)
- NHL API is public and rate-limit friendly
- HKJC website scraping should respect robots.txt

## License

This project is for educational and personal use. Respect API terms of service and scraping policies.
