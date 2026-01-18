# NHL Stats Airflow DAG

This repository contains an Airflow DAG that automatically downloads NHL game data daily at 7am.

## Structure

```
nhlstats/
├── dags/
│   └── nhl_daily_download.py    # Airflow DAG definition
├── nhl_game_events.py            # Game events downloader
├── nhl_shifts.py                 # Shift data downloader
├── data/
│   ├── games/                    # Play-by-play and boxscore data
│   └── shifts/                   # Shift data
└── requirements.txt
```

## DAG Overview

**DAG ID:** `nhl_daily_download`

**Schedule:** Daily at 7:00 AM UTC (`0 7 * * *`)

**Tasks:**
1. `get_games_for_date` - Retrieves list of games from the previous day
2. `download_game_events` - Downloads play-by-play and boxscore data
3. `download_game_shifts` - Downloads shift data (JSON and CSV formats)

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Initialize Airflow

```bash
# Set Airflow home (optional)
export AIRFLOW_HOME=~/airflow

# Initialize the database
airflow db init

# Create an admin user
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com
```

### 3. Configure DAG Directory

Option A: Copy DAG to Airflow's default location:
```bash
cp dags/nhl_daily_download.py ~/airflow/dags/
```

Option B: Configure Airflow to use this directory:
Edit `~/airflow/airflow.cfg`:
```ini
dags_folder = /root/nhlstats/dags
```

### 4. Start Airflow

```bash
# Start the web server (default port 8080)
airflow webserver --port 8080

# In another terminal, start the scheduler
airflow scheduler
```

## Usage

### Access Web UI
Navigate to `http://localhost:8080` and log in with your admin credentials.

### Enable the DAG
1. Find `nhl_daily_download` in the DAG list
2. Toggle the switch to enable it
3. The DAG will run daily at 7am

### Manual Trigger
To run immediately:
```bash
airflow dags trigger nhl_daily_download
```

Or use the "Play" button in the web UI.

### Test Individual Tasks
```bash
# Test getting games for a specific date
airflow tasks test nhl_daily_download get_games_for_date 2024-11-15

# Test downloading game events
airflow tasks test nhl_daily_download download_game_events 2024-11-15
```

## Configuration

### Change Schedule
Edit `schedule_interval` in `dags/nhl_daily_download.py`:
```python
schedule_interval='0 7 * * *',  # Cron expression
```

Common schedules:
- `0 7 * * *` - Daily at 7am
- `0 */6 * * *` - Every 6 hours
- `0 0 * * 0` - Weekly on Sunday at midnight

### Change Data Directory
Modify the output directories in `nhl_game_events.py` and `nhl_shifts.py`:
```python
fetcher = NHLGameEvents(output_dir="/path/to/games")
fetcher = NHLShifts(output_dir="/path/to/shifts")
```

### Notification Settings
Update `default_args` in the DAG:
```python
default_args = {
    'email': ['your-email@example.com'],
    'email_on_failure': True,
    'email_on_retry': True,
}
```

## Data Output

### Game Events
- Location: `data/games/`
- Files per game:
  - `{game_id}_playbyplay.json` - All events with coordinates
  - `{game_id}_boxscore.json` - Player stats and summary

### Shifts
- Location: `data/shifts/`
- Files per game:
  - `{game_id}_shifts.json` - Complete shift data
  - `{game_id}_shifts.csv` - Shift data in CSV format

## Monitoring

### View Logs
```bash
# View logs for a specific task run
airflow tasks logs nhl_daily_download get_games_for_date 2024-11-15
```

Or view in the web UI: DAG → Task → Logs

### Check DAG Status
```bash
airflow dags list
airflow dags state nhl_daily_download 2024-11-15
```

## Troubleshooting

### DAG Not Appearing
- Check `dags_folder` in `airflow.cfg`
- Verify no Python syntax errors: `python dags/nhl_daily_download.py`
- Check Airflow logs: `~/airflow/logs/scheduler/`

### Task Failures
- Retry logic is configured (2 retries with 5 min delay)
- Check if NHL API is accessible
- Verify data directories have write permissions

### Import Errors
- Ensure `nhl_game_events.py` and `nhl_shifts.py` are in parent directory
- Check Python path configuration in DAG file

## Notes

- The DAG downloads games from the **previous day** (execution_date - 1 day)
- `catchup=False` prevents backfilling historical runs
- Shift data downloads continue even if individual games fail
- Game event failures will halt the task and trigger retry logic
