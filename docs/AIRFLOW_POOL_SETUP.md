# Airflow Pool Configuration for DuckDB

## Purpose
The `duckdb_writer` pool ensures only ONE Airflow task writes to DuckDB at a time, preventing lock conflicts.

## Setup Instructions

### Option 1: Airflow UI (Recommended)
1. Open Airflow UI: http://localhost:8080
2. Go to **Admin** → **Pools**
3. Click **+** to add a new pool
4. Configure:
   - **Pool Name**: `duckdb_writer`
   - **Slots**: `1` (CRITICAL - only 1 writer allowed!)
   - **Description**: "Serialize DuckDB write operations"
5. Click **Save**

### Option 2: Airflow CLI
```bash
# From your Airflow environment
airflow pools set duckdb_writer 1 "Serialize DuckDB write operations"

# Verify it was created
airflow pools list
```

### Option 3: Docker Compose
```bash
# If using Docker Compose
docker compose exec airflow-scheduler airflow pools set duckdb_writer 1 "Serialize DuckDB write operations"
```

## Verification

Check the pool exists and has `slots=1`:
```bash
airflow pools list | grep duckdb_writer
```

Expected output:
```
duckdb_writer    | 1/1   | Serialize DuckDB write operations
```

## How It Works

In `dags/nhl_daily_download.py`:
```python
load_db = PythonOperator(
    task_id='load_into_duckdb',
    python_callable=load_into_duckdb,
    pool='duckdb_writer',  # ← This references the pool
)
```

- With `max_active_runs=2` in the DAG, multiple dates can be processing simultaneously
- But only 1 task can use the `duckdb_writer` pool at a time
- This prevents concurrent writes to DuckDB
- Other tasks (download, etc.) run in parallel normally

## Troubleshooting

If you still see lock errors:
1. **Verify pool slots**: `airflow pools list` → should show `1` slot
2. **Check running tasks**: Multiple tasks shouldn't show "running" with `pool='duckdb_writer'`
3. **Restart scheduler**: `docker compose restart airflow-scheduler`
4. **Clear stale locks**: Remove `/opt/airflow/data/nhlstats.duckdb.wal` if it exists

## Related Files
- DAG configuration: `dags/nhl_daily_download.py`
- Database loader: `nhl_db_loader.py`
- Connection guide: `DUCKDB_MULTI_SESSION_GUIDE.md`
