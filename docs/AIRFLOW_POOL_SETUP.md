# Airflow Pool Configuration for DuckDB

## Purpose
The `duckdb_writer` pool ensures only ONE Airflow task writes to DuckDB at a time, preventing lock conflicts.

## Setup Instructions

### Supported repo bootstrap flow
```bash
# Re-apply the checked-in pool contract from config/airflow_pools.json
docker compose run --rm airflow-bootstrap-admin
```

For this repository, `config/airflow_pools.json` plus
`docker compose run --rm airflow-bootstrap-admin` is the supported pool bootstrap
path. Manual scheduler-side pool creation commands are not part of the
remediation-state runbook.

## Verification

Open the Airflow UI at `http://localhost:8080`, go to **Admin** → **Pools**, and
confirm `duckdb_writer` exists with `slots=1`. The expected definition comes from
`config/airflow_pools.json`.

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
1. **Re-apply the checked-in pool contract**: `docker compose run --rm airflow-bootstrap-admin`, then confirm `duckdb_writer` shows `slots=1` in **Admin** → **Pools**
2. **Check running tasks**: Multiple tasks shouldn't show "running" with `pool='duckdb_writer'`
3. **Restart scheduler**: `docker compose restart airflow-scheduler`
4. **Clear stale locks**: Remove `/opt/airflow/data/nhlstats.duckdb.wal` if it exists

## Related Files
- DAG configuration: `dags/nhl_daily_download.py`
- Database loader: `nhl_db_loader.py`
- Connection guide: `DUCKDB_MULTI_SESSION_GUIDE.md`
