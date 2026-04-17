# Airflow Setup Guide

This document covers all manual setup steps required before certain DAGs can
run.  Pools must be created once per Airflow installation (they are not
version-controlled in the database).

---

## Table of Contents

1. [Airflow Pools — historical_stats_daily](#1-airflow-pools--historical_stats_daily)
2. [Legacy DuckDB Writer Pool](#2-legacy-duckdb-writer-pool-deprecated)
3. [Verification Checklist](#3-verification-checklist)
4. [Troubleshooting](#4-troubleshooting)

---

## 1. Airflow Pools — `historical_stats_daily`

The `historical_stats_daily` DAG assigns each sport task to a dedicated pool
that enforces the source-appropriate rate limit.  These pools **must** be
created before the DAG can be enabled.

| Pool name | Slots | Source | Effective rate |
|---|---|---|---|
| `stats_nba_pool` | 3 | NBA Stats API | ~1 req / s |
| `stats_nhl_pool` | 1 | NHL API | ~0.5 req / s |
| `stats_mlb_pool` | 2 | MLB Stats API | ~1 req / s |
| `stats_nfl_pool` | 2 | nfl_data_py parquet | Bulk download |
| `stats_fbref_pool` | 1 | FBRef / Sports-Reference | 1 req / 4 s |
| `stats_cbb_pool` | 2 | Sports-Reference CBB | 1 req / 4 s |
| `stats_tennis_pool` | 1 | Tennis Abstract GitHub CSV | Bulk download |

### Option A — Airflow UI (recommended for one-time setup)

1. Open the Airflow UI at `http://localhost:8080`.
2. Navigate to **Admin → Pools**.
3. Click **+** and create each pool from the table above.

### Option B — Airflow CLI (scriptable)

```bash
# Run from within any Airflow container, e.g. the scheduler:
docker compose exec airflow-scheduler bash -c "
  airflow pools set stats_nba_pool    3 'NBA Stats API — ~1 req/s'
  airflow pools set stats_nhl_pool    1 'NHL API — ~0.5 req/s'
  airflow pools set stats_mlb_pool    2 'MLB Stats API — ~1 req/s'
  airflow pools set stats_nfl_pool    2 'nfl_data_py parquet download'
  airflow pools set stats_fbref_pool  1 'FBRef / Sports-Reference — 1 req/4s'
  airflow pools set stats_cbb_pool    2 'Sports-Reference CBB — 1 req/4s'
  airflow pools set stats_tennis_pool 1 'Tennis Abstract GitHub CSV'
"
```

### Option C — Docker Compose one-liner

```bash
docker compose exec airflow-apiserver airflow pools import /dev/stdin <<'EOF'
[
  {"name": "stats_nba_pool",    "slots": 3, "description": "NBA Stats API — ~1 req/s"},
  {"name": "stats_nhl_pool",    "slots": 1, "description": "NHL API — ~0.5 req/s"},
  {"name": "stats_mlb_pool",    "slots": 2, "description": "MLB Stats API — ~1 req/s"},
  {"name": "stats_nfl_pool",    "slots": 2, "description": "nfl_data_py parquet download"},
  {"name": "stats_fbref_pool",  "slots": 1, "description": "FBRef / Sports-Reference — 1 req/4s"},
  {"name": "stats_cbb_pool",    "slots": 2, "description": "Sports-Reference CBB — 1 req/4s"},
  {"name": "stats_tennis_pool", "slots": 1, "description": "Tennis Abstract GitHub CSV"}
]
EOF
```

### Verify pools were created

```bash
docker compose exec airflow-scheduler airflow pools list
```

Expected output (columns: Pool | Slots | Running | Queued | Scheduled | Open | Description):

```
stats_nba_pool     | 3 | ...
stats_nhl_pool     | 1 | ...
stats_mlb_pool     | 2 | ...
stats_nfl_pool     | 2 | ...
stats_fbref_pool   | 1 | ...
stats_cbb_pool     | 2 | ...
stats_tennis_pool  | 1 | ...
```

---

## 2. Legacy DuckDB Writer Pool (deprecated)

> ⚠️ The project has migrated to PostgreSQL.  The `duckdb_writer` pool is no
> longer used by any active DAG.  This section is kept for historical reference
> only.  Do **not** create it in new installations.

The original `AIRFLOW_POOL_SETUP.md` (now superseded by this file) described a
single-slot `duckdb_writer` pool used by `dags/nhl_daily_download.py` to
serialize DuckDB writes.  That DAG is archived.

---

## 3. Verification Checklist

Run the following after completing setup to confirm everything is ready:

```bash
# 1. All 7 stats pools exist
docker compose exec airflow-scheduler airflow pools list | grep stats_

# 2. DAG parses without error
docker compose exec airflow-scheduler python /opt/airflow/dags/historical_stats_daily.py

# 3. DAG is visible and not paused
docker compose exec airflow-scheduler airflow dags list | grep historical_stats_daily
```

---

## 4. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Task stuck in `queued` indefinitely | Pool not created or has 0 slots | Create the pool (§1) |
| `KeyError: 'stats_nba_pool'` in logs | Pool missing | Create the pool |
| DAG not visible in UI | Parse error or not yet scanned | Run `python dags/historical_stats_daily.py` locally to check |
| `NotImplementedError` in task logs | Expected — stubs not yet implemented | Track in plan.yaml Wave 2 |

---

*Last updated: 2026-04-17*
